"""Incident layers: where deaths happened (and, where published, where the person lived).

Sources (each layer declares which map causes it can show, via "show": {cause: category index})
Medical examiners / coroners
- Cook County (IL): incident coordinates + residence ZIP. Daily.
- Santa Clara County (CA): coordinates + residence ZIP. Daily.
- Orange County (FL, District 9 incl. Osceola): coordinates of the place of death. ~Weekly.
- San Diego County (CA): ZIP where the death happened (often a hospital) + residence ZIP, 1997–. Monthly.
- Sacramento County (CA) coroner: drug, homicide and road deaths by incident ZIP, 2021–. Daily.
- Allegheny County (PA): accidental overdoses by incident ZIP + residence ZIP, 2007–. Monthly. CC0.
- Connecticut accidental drug-related deaths: injury town + residence town. Annual.
Police / city records (where the death happened only)
- People killed by police, nationwide: Fatal Encounters 2000–2021, Washington Post Fatal Force 2022–2024.
- Homicides: Chicago (1991–), Philadelphia fatal shootings (2015–), NYPD murders (2006–), Detroit (2010–).

Privacy rules applied here (the source tables are more detailed than what we publish):
- Incident points are snapped to a ~1 km grid (0.01 degree) and only counts per cell, year and
  category are kept. No ages, names, case numbers, addresses, causes or exact times.
- Residence is aggregated to ZIP Code (ZCTA centroid) or town; never a street.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime

from build_data import get, log  # shared helpers

GRID = 0.01  # degrees, ~1.1 km north-south


def snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 4)


def socrata_all(domain: str, dataset: str, select: str, where: str, page: int = 50000):
    import urllib.parse
    off = 0
    while True:
        q = urllib.parse.urlencode({"$select": select, "$where": where, "$limit": page, "$offset": off, "$order": ":id"})
        rows = json.loads(get(f"https://{domain}/resource/{dataset}.json?{q}"))
        yield from rows
        if len(rows) < page:
            return
        off += page


_zcta = None


def zcta_centroids():
    """ZIP Code Tabulation Area centroids from the Census Gazetteer."""
    global _zcta
    if _zcta is None:
        raw = get("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip")
        z = zipfile.ZipFile(io.BytesIO(raw))
        txt = z.read(z.namelist()[0]).decode("utf-8")
        rows = csv.reader(io.StringIO(txt), delimiter="\t")
        head = [h.strip() for h in next(rows)]
        gi, la, lo = head.index("GEOID"), head.index("INTPTLAT"), head.index("INTPTLONG")
        _zcta = {r[gi].strip(): (round(float(r[lo]), 4), round(float(r[la]), 4)) for r in rows}
    return _zcta


def _pack(cells: dict, years: list[int], labels: dict | None = None):
    """cells[(lon,lat,year)] -> [counts] → compact rows [lon,lat,yearIdx,c0..cN(,label)]."""
    yi = {y: i for i, y in enumerate(years)}
    out = []
    for (lon, lat, y), c in cells.items():
        if y not in yi:
            continue
        row = [lon, lat, yi[y], *c]
        if labels is not None:
            row.append(labels.get((lon, lat), ""))
        out.append(row)
    return out


CATS = ["all", "overdose", "suicide", "homicide", "firearm", "traffic", "heart"]
NC = len(CATS)
DRUG_TERMS = ("drug", "fentanyl", "heroin", "cocaine", "methamphetamine", "amphetamine", "opioid", "opiate",
              "oxycodone", "hydrocodone", "morphine", "methadone", "benzodiazepine", "alprazolam", "xylazine",
              "tramadol", "overdose", "buprenorphine", "carfentanil")
GUN_TERMS = ("gunshot", "firearm", "shotgun", "rifle", "handgun")
TRAFFIC_TERMS = ("motor vehicle", "mva", "pedestrian", "traffic", "motorcycle", "vehicular", "automobile", "bicycl")
HEART_TERMS = ("cardiovascular", "coronary", "heart", "cardiac", "cardiomyopathy", "ascvd", "myocardial")
SHOW_ME = {"all": 0, "overdose": 1, "suicide": 2, "homicide": 3, "firearm": 4, "heart": 6}


def categories(manner: str, cause: str, gun_flag=None, opioid_flag=None, extra: str = "") -> list[int]:
    m, c = (manner or "").lower(), f"{cause or ''} {extra or ''}".lower()
    out = [0]
    if not m.startswith("natural") and (any(t in c for t in DRUG_TERMS) or str(opioid_flag).lower() == "true"):
        out.append(1)
    if m.startswith("suicide"):
        out.append(2)
    if m.startswith("homicide"):
        out.append(3)
    if str(gun_flag).lower() in ("true", "yes") or any(t in c for t in GUN_TERMS):
        out.append(4)
    if m.startswith("accident") and any(t in c for t in TRAFFIC_TERMS):
        out.append(5)
    if m.startswith("natural") and any(t in c for t in HEART_TERMS):
        out.append(6)
    return out


class Acc:
    """Counts per (lon, lat, year) cell for the place of death and the place of residence."""

    def __init__(self):
        self.died, self.lived, self.labels = defaultdict(lambda: [0] * NC), defaultdict(lambda: [0] * NC), {}
        self.monthly = defaultdict(lambda: [0] * NC)  # (lon, lat, year, month) for the place of death
        self.years, self.n, self.latest = set(), 0, ""

    def add(self, y, cats, died=None, lived=None, dlabel=None, llabel=None, date="", w=1):
        if not y or y > datetime.now().year or w <= 0:
            return
        self.n += w
        self.years.add(y)
        self.latest = max(self.latest, str(date)[:10])
        mo = str(date)[5:7]
        if died and mo.isdigit() and 1 <= int(mo) <= 12 and str(date)[:4] == str(y):
            c = self.monthly[(*died, y, int(mo))]
            for k in cats:
                c[k] += w
        for pt, bucket, lab in ((died, self.died, dlabel), (lived, self.lived, llabel)):
            if pt:
                c = bucket[(*pt, y)]
                for k in cats:
                    c[k] += w
                if lab:
                    self.labels[pt] = lab


def layer(key, label, area, acc, *, kind, what, show, source, url, died_note, lived_note=None, color=1):
    years = sorted(acc.years)
    if not years:
        raise RuntimeError("no rows")
    log(f"  {acc.n:,} deaths {years[0]}–{years[-1]}; {len(acc.died):,} death cells, {len(acc.lived):,} residence cells")
    return {
        "key": key, "label": label, "kind": kind, "what": what, "area": area, "years": years, "cats": CATS,
        "show": show, "hasLived": bool(acc.lived), "latest": acc.latest or str(years[-1]), "cases": acc.n, "color": color,
        "died": _pack(acc.died, years, acc.labels), "lived": _pack(acc.lived, years, acc.labels),
        "monthly": [[lon, lat, years.index(y), m, *c] for (lon, lat, y, m), c in acc.monthly.items() if y in years],
        "diedNote": died_note, "livedNote": lived_note or "", "source": source, "sourceUrl": url,
    }


def zip_pt(z, code):
    code = str(code or "").strip()[:5]
    return (z[code], f"ZIP {code}") if code in z else (None, None)


def _arcgis_json(url, tries=3):
    """One ArcGIS query as JSON. ArcGIS servers sometimes answer a good query with {"error": "Unable to complete operation"} (code 400)
    and accept it a moment later (seen on Charlotte's service during the 2026-10-10 verification build), so retry before giving up."""
    import time
    for i in range(tries):
        try:
            j = json.loads(get(url))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))
            continue
        if "error" in j and i < tries - 1:
            time.sleep(5 * (i + 1))
            continue
        return j


def arcgis_all(url, where="1=1", fields="*", geometry=True, page=2000, order=None):
    import urllib.parse
    off = 0
    while True:
        q = urllib.parse.urlencode({"where": where, "outFields": fields, "returnGeometry": str(geometry).lower(), "outSR": 4326,
                                    "resultOffset": off, "resultRecordCount": page, "orderByFields": order or ("OBJECTID" if fields == "*" else ""), "f": "json"})
        j = _arcgis_json(f"{url}/query?{q}")
        if "error" in j:
            raise RuntimeError(j["error"])
        feats = j.get("features", [])
        yield from feats
        if len(feats) < page and not j.get("exceededTransferLimit"):
            return
        off += len(feats)


def medical_examiner(name, domain, dataset, cols, since_year, area, url, color=1):
    """Generic Socrata ME source → died (~1 km grid) + lived (ZIP) counts per year and category."""
    log(f"• {name} medical examiner …")
    z = zcta_centroids()
    acc = Acc()
    where = f"{cols['date']} >= '{since_year}-01-01'"
    fields = [cols[k] for k in ("date", "manner", "lat", "lon", "rzip", "cause", "gun", "opioid") if cols.get(k)]
    for r in socrata_all(domain, dataset, ",".join(fields), where):
        try:
            y = int(str(r.get(cols["date"]))[:4])
        except ValueError:
            continue
        cats = categories(r.get(cols["manner"]), r.get(cols.get("cause", ""), ""), r.get(cols.get("gun", "")), r.get(cols.get("opioid", "")))
        died = None
        try:
            lat, lon = float(r[cols["lat"]]), float(r[cols["lon"]])
            if lat and lon:
                died = (snap(lon), snap(lat))
        except (KeyError, TypeError, ValueError):
            pass
        lived, llab = zip_pt(z, r.get(cols["rzip"]))
        acc.add(y, cats, died, lived, None, llab, r.get(cols["date"]))
    return layer(name.lower().replace(" ", "_"), f"{name} Medical Examiner", area, acc, kind="me", what="medical examiner",
                 show=SHOW_ME, source=f"{name} Medical Examiner open data", url=url, color=color,
                 died_note="where the injury or death happened (~1 km squares)", lived_note="where the person lived (ZIP Codes)")


def orange_fl():
    log("• Orange County FL medical examiner …")
    acc = Acc()
    base = "https://services1.arcgis.com/0U8EQ1FrumPeIqDb/arcgis/rest/services/Cases_DeathAddress/FeatureServer/0"
    for f in arcgis_all(base, fields="Death_Date,Death_Year,Manner_Of_Death,Cat_Death,Cat_Death_2,Accident_Cat"):
        a, g = f["attributes"], f.get("geometry") or {}
        y = a.get("Death_Year")
        cats = categories(a.get("Manner_Of_Death"), a.get("Cat_Death"), extra=f"{a.get('Cat_Death_2') or ''} {a.get('Accident_Cat') or ''}")
        died = None
        x, yy = g.get("x"), g.get("y")
        if x and yy and -82.2 < x < -80.6 and 27.6 < yy < 29.0:  # District 9 only; drops stray geocodes
            died = (snap(x), snap(yy))
        d = datetime.utcfromtimestamp(a["Death_Date"] / 1000).strftime("%Y-%m-%d") if a.get("Death_Date") else ""
        acc.add(y, cats, died, None, date=d)
    return layer("orange_fl", "Orange County FL Medical Examiner", "Orange & Osceola counties, FL (Orlando)", acc, kind="me",
                 what="medical examiner", show=SHOW_ME, color=3,
                 source="District Nine (Orange/Osceola) Medical Examiner via Orange County GIS",
                 url="https://services1.arcgis.com/0U8EQ1FrumPeIqDb/arcgis/rest/services/Cases_DeathAddress/FeatureServer/0",
                 died_note="where the death happened (~1 km squares)")


def san_diego():
    log("• San Diego County medical examiner …")
    z = zcta_centroids()
    acc = Acc()
    sel = "death_date,manner,manner_type_standardized_,opioid_related,cod_string,death_zip,res_zip"
    for r in socrata_all("data.sandiegocounty.gov", "jkvb-n4p7", sel, "death_date IS NOT NULL"):
        y = int(r["death_date"][:4])
        if y < 1997:  # the series starts in 1997; a few rows carry old injury dates
            continue
        mt = r.get("manner_type_standardized_") or ""
        op = (r.get("opioid_related") or "").startswith("Opioid")
        cats = categories(r.get("manner"), r.get("cod_string"), gun_flag=(mt == "Firearm"), opioid_flag=op,
                          extra=("motor vehicle" if mt in ("Motor Vehicle", "Bicycle") else "") + (" drug" if mt.startswith("Drug") else "") + (" cardiovascular" if mt == "Cardiovascular" else ""))
        died, dlab = zip_pt(z, r.get("death_zip"))
        lived, llab = zip_pt(z, r.get("res_zip"))
        acc.add(y, cats, died, lived, dlab, llab, r["death_date"])
    return layer("san_diego", "San Diego County Medical Examiner", "San Diego County, CA", acc, kind="zip", what="medical examiner",
                 show=SHOW_ME, color=2, source="San Diego County Medical Examiner via data.sandiegocounty.gov",
                 url="https://data.sandiegocounty.gov/d/jkvb-n4p7",
                 died_note="ZIP Code where the person died (often a hospital)", lived_note="where the person lived (ZIP Codes)")


def sacramento():
    log("• Sacramento County coroner …")
    z = zcta_centroids()
    acc = Acc()
    base = "https://services1.arcgis.com/5NARefyPVtAeuJPU/arcgis/rest/services/{}/FeatureServer/0"
    for lay, fixed in (("Drug_Deaths", [1]), ("Homicides", [3]), ("Motor_Vehicle_Accident_Deaths", [5])):
        for f in arcgis_all(base.format(lay), geometry=False):
            a = f["attributes"]
            cats = list(fixed)
            if lay == "Homicides" and "gunshot" in f"{a.get('Manner_GROUPED')} {a.get('Cause')}".lower():
                cats.append(4)
            d = datetime.utcfromtimestamp(a["DeathDate"] / 1000).strftime("%Y-%m-%d") if a.get("DeathDate") else ""
            died, dlab = zip_pt(z, a.get("Incident_Zip"))
            acc.add(a.get("DeathYear"), cats, died, None, dlab, None, d)
    return layer("sacramento", "Sacramento County Coroner", "Sacramento County, CA", acc, kind="zip", what="coroner",
                 show={"overdose": 1, "homicide": 3, "firearm": 4, "traffic": 5}, color=1,
                 source="Sacramento County Coroner via Sacramento County GIS",
                 url="https://data.saccounty.gov/", died_note="ZIP Code where the death or injury happened")


def allegheny():
    log("• Allegheny County overdoses …")
    z = zcta_centroids()
    acc = Acc()
    off = 0
    while True:
        j = json.loads(get(f"https://data.wprdc.org/api/3/action/datastore_search?resource_id=1c59b26a-1684-4bfb-92f7-205b947530cf&limit=10000&offset={off}"))
        recs = j["result"]["records"]
        for r in recs:
            d = r.get("death_date_and_time") or ""
            try:
                y = int(r.get("case_year") or d[:4])
            except ValueError:
                continue
            died, dlab = zip_pt(z, r.get("incident_zip"))
            lived, llab = zip_pt(z, r.get("decedent_zip"))
            acc.add(y, [0, 1], died, lived, dlab, llab, d)
        if len(recs) < 10000:
            break
        off += 10000
    return layer("allegheny", "Allegheny County Medical Examiner", "Allegheny County, PA (Pittsburgh)", acc, kind="zip",
                 what="medical examiner", show={"overdose": 1}, color=3,
                 source="Allegheny County Office of the Medical Examiner via WPRDC (CC0)",
                 url="https://data.wprdc.org/dataset/allegheny-county-fatal-accidental-overdoses",
                 died_note="ZIP Code where the overdose was found", lived_note="where the person lived (ZIP Codes)")


def police_killings():
    """Fatal Encounters 2000–2012, Mapping Police Violence 2013– (trimmed copy in data_manual/mpv).
    Without the MPV file, falls back to Fatal Encounters to 2021 + Washington Post Fatal Force 2022–24."""
    from pathlib import Path
    mpv = Path(__file__).resolve().parents[1] / "data_manual" / "mpv" / "mpv_killings_trimmed.csv"
    use_mpv = mpv.exists()
    fe_last = 2012 if use_mpv else 2021
    log(f"• People killed by police (Fatal Encounters{', Mapping Police Violence' if use_mpv else ', Washington Post'}) …")
    acc = Acc()
    fe = get("https://docs.google.com/spreadsheets/d/1dKmaV_JiWcG8XBoRgP8b4e9Eopkpgt7FL7nyspvzAsE/export?format=csv").decode("utf-8", "replace")
    rows = csv.reader(io.StringIO(fe))
    head = [h.strip() for h in next(rows)]
    di = next(i for i, h in enumerate(head) if h.lower().startswith("date of injury"))
    la, lo, fo = head.index("Latitude"), head.index("Longitude"), head.index("Highest level of force")
    for r in rows:
        if len(r) <= max(di, la, lo, fo):
            continue
        force = r[fo].strip().lower()
        if "suicide" in force or not force:
            continue  # FE also logs suicides during police encounters; not killings
        try:
            mo, dd, yy = r[di].split("/")
            y = int(yy)
            pt = (snap(float(r[lo])), snap(float(r[la])))
        except ValueError:
            continue
        if y > fe_last:
            continue
        cats = [0] + ([4] if "gunshot" in force else []) + ([5] if "vehicle" in force else [])
        acc.add(y, cats, pt, None, date=f"{yy}-{int(mo):02d}-{int(dd):02d}")
    if use_mpv:
        for r in csv.DictReader(mpv.open()):
            force = r["use_of_force"].lower()
            cats = [0] + ([4] if "gunshot" in force else []) + ([5] if "vehicle" in force else [])
            acc.add(int(r["date"][:4]), cats, (snap(float(r["lon"])), snap(float(r["lat"]))), None, date=r["date"])
        src = "Fatal Encounters (2000–2012) and Mapping Police Violence / Campaign Zero (2013–)"
        url = "https://mappingpoliceviolence.org/methodology"
    else:
        wp = get("https://raw.githubusercontent.com/washingtonpost/data-police-shootings/master/v2/fatal-police-shootings-data.csv").decode("utf-8")
        for r in csv.DictReader(io.StringIO(wp)):
            y = int(r["date"][:4])
            if y <= 2021:
                continue
            try:
                pt = (snap(float(r["longitude"])), snap(float(r["latitude"])))
            except ValueError:
                continue
            acc.add(y, [0, 4], pt, None, date=r["date"])
        src, url = "Fatal Encounters (2000–2021) and The Washington Post Fatal Force (2022–2024, CC BY-NC-SA)", "https://fatalencounters.org/"
    return layer("police", "Killed by police", "United States", acc, kind="me", what="killed by police,",
                 show={"all": 0, "firearm": 4, "traffic": 5}, color=4, source=src, url=url,
                 died_note="where the person was killed (~1 km squares); shootings, vehicle pursuits and other force")


def other_accidents():
    """Rail accidents (FRA, 1975–) and mine accidents (MSHA, 2000–): deaths with a location, shown on All deaths."""
    import urllib.parse
    log("• Rail and mine accidents (FRA, MSHA) …")
    acc = Acc()
    seen = set()
    for r in socrata_all("data.transportation.gov", "85tf-25kj", "incidentkey,date,latitude,longitude,totalpersonskilled", "totalpersonskilled != '0'"):
        key = r.get("incidentkey") or r.get("date")
        if key in seen:  # one accident can be reported by several railroads
            continue
        seen.add(key)
        try:
            k = int(float(r.get("totalpersonskilled") or 0))
            pt = (snap(float(r["longitude"])), snap(float(r["latitude"])))
        except (KeyError, TypeError, ValueError):
            continue
        if not (-180 < pt[0] < -60 and 15 < pt[1] < 72):
            continue
        acc.add(int(r["date"][:4]), [0], pt, None, date=r["date"], w=k)
    mines = {}
    z = zipfile.ZipFile(io.BytesIO(get("https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip")))
    rows = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")), delimiter="|")
    head = next(rows)
    mi, la, lo = head.index("MINE_ID"), head.index("LATITUDE"), head.index("LONGITUDE")
    for r in rows:
        try:
            lat, lon = float(r[la]), float(r[lo])
        except (IndexError, ValueError):
            continue
        if lon > 0:
            lon = -lon  # a few rows store west longitude as positive
        if 15 < lat < 72 and -180 < lon < -60:
            mines[r[mi]] = (snap(lon), snap(lat))
    z = zipfile.ZipFile(io.BytesIO(get("https://arlweb.msha.gov/OpenGovernmentData/DataSets/Accidents.zip")))
    rows = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")), delimiter="|")
    head = next(rows)
    mi, dt, dg = head.index("MINE_ID"), head.index("ACCIDENT_DT"), head.index("DEGREE_INJURY")
    for r in rows:
        if len(r) <= max(mi, dt, dg) or "FATAL" not in r[dg].upper() or r[mi] not in mines:
            continue
        try:
            mo, dd, yy = r[dt].split("/")
        except ValueError:
            continue
        acc.add(int(yy), [0], mines[r[mi]], None, date=f"{yy}-{mo}-{dd}")
    return layer("other_accidents", "Rail and mine deaths", "United States", acc, kind="me", what="federal accident records",
                 show={"all": 0}, color=4, source="FRA rail equipment accidents (1975–) and MSHA mine accidents (2000–)",
                 url="https://data.transportation.gov/d/85tf-25kj",
                 died_note="rail and mine accidents where someone died (~1 km squares)")


_places = None


def place_point(location):
    """'Twin Falls, Idaho' → (lon, lat) from the Census places gazetteer (city centroid)."""
    global _places
    if _places is None:
        _places = {}
        try:
            raw = get("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip")
            z = zipfile.ZipFile(io.BytesIO(raw))
            rows = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")), delimiter="\t")
            head = [h.strip() for h in next(rows)]
            ui, ni, la, lo = head.index("USPS"), head.index("NAME"), head.index("INTPTLAT"), head.index("INTPTLONG")
            for r in rows:
                name = re.sub(r" (city|town|village|CDP|borough|municipality)$", "", r[ni].strip()).lower()
                _places[(name, r[ui])] = (snap(float(r[lo])), snap(float(r[la])))
        except Exception as e:  # noqa: BLE001
            log(f"  ! places gazetteer: {e}")
    try:
        city, state = [x.strip() for x in location.rsplit(",", 1)]
    except ValueError:
        return None
    return _places.get((city.lower(), STATE_ABBR.get(state.lower(), state.upper()[:2])))


STATE_ABBR = {n.lower(): a for a, n in [("AL","Alabama"),("AK","Alaska"),("AZ","Arizona"),("AR","Arkansas"),("CA","California"),("CO","Colorado"),("CT","Connecticut"),("DE","Delaware"),("DC","District of Columbia"),("FL","Florida"),("GA","Georgia"),("HI","Hawaii"),("ID","Idaho"),("IL","Illinois"),("IN","Indiana"),("IA","Iowa"),("KS","Kansas"),("KY","Kentucky"),("LA","Louisiana"),("ME","Maine"),("MD","Maryland"),("MA","Massachusetts"),("MI","Michigan"),("MN","Minnesota"),("MS","Mississippi"),("MO","Missouri"),("MT","Montana"),("NE","Nebraska"),("NV","Nevada"),("NH","New Hampshire"),("NJ","New Jersey"),("NM","New Mexico"),("NY","New York"),("NC","North Carolina"),("ND","North Dakota"),("OH","Ohio"),("OK","Oklahoma"),("OR","Oregon"),("PA","Pennsylvania"),("RI","Rhode Island"),("SC","South Carolina"),("SD","South Dakota"),("TN","Tennessee"),("TX","Texas"),("UT","Utah"),("VT","Vermont"),("VA","Virginia"),("WA","Washington"),("WV","West Virginia"),("WI","Wisconsin"),("WY","Wyoming")]}


def mass_shootings():
    log("• Mass shootings (Mother Jones) …")
    acc = Acc()
    txt = get("https://docs.google.com/spreadsheets/d/1b9o6uDO18sLxBqPwl_Gh9bnhW-ev_dABH83M5Vb5L8o/export?format=csv").decode("utf-8", "replace")
    rows = csv.reader(io.StringIO(txt))
    head = next(rows)
    loc_i = head.index("location")  # the sheet has two "location" columns; the first is "City, State"
    for vals in rows:
        r = dict(zip(head, vals))
        r["location"] = vals[loc_i] if len(vals) > loc_i else ""
        try:
            mo, dd, yy = r["date"].split("/")
            yy = int(yy)
            if yy < 100:  # the sheet mixes 2- and 4-digit years
                yy += 2000 if yy <= datetime.now().year % 100 else 1900
            k = int(float(r.get("fatalities") or 0))
        except (KeyError, ValueError):
            continue
        try:
            pt = (snap(float(r["longitude"])), snap(float(r["latitude"])))
        except (KeyError, ValueError):
            pt = place_point(r["location"])  # newest rows lack coordinates
            if not pt:
                continue
        acc.add(yy, [0, 3, 4], pt, None, date=f"{yy}-{int(mo):02d}-{int(dd):02d}", w=k)
    return layer("mass_shootings", "Mass shootings", "United States", acc, kind="me", what="news database",
                 show={"all": 0, "homicide": 3, "firearm": 4}, color=4,
                 source="Mother Jones US mass shootings database (1982–)",
                 url="https://www.motherjones.com/politics/2012/12/mass-shootings-mother-jones-full-data/",
                 died_note="public mass shootings, sized by people killed")


def city_homicides(key, city, fetch, url, source, cats_fn, color=2, show=None, before=None, note="", report_missing=False):
    log(f"• {city} homicides …")
    acc = Acc()
    total = missing = 0
    for y, lon, lat, extra, d in fetch():
        if before and y and y >= before:
            continue
        total += 1
        try:
            pt = (snap(float(lon)), snap(float(lat)))
        except (TypeError, ValueError):
            missing += 1
            continue
        if not (-180 < pt[0] < -60 and 15 < pt[1] < 72):
            missing += 1
            continue
        acc.add(y, cats_fn(extra), pt, None, date=d)
    if report_missing:
        log(f"  {missing:,} of {total:,} records have no usable location")
        if missing:
            share = f"{missing / max(total, 1):.0%}" if missing / max(total, 1) >= 0.01 else "under 1%"
            note += f" — {missing:,} of {total:,} records ({share}) have no usable location in the source and are not on the map"
    return layer(key, f"{city} homicides", city, acc, kind="me", what="police-recorded", show=show or {"homicide": 3, "firearm": 4},
                 color=color, source=source, url=url, died_note="where the homicide happened (~1 km squares)" + note)


def _chicago():
    for r in socrata_all("data.cityofchicago.org", "gumc-mgzr", "date,latitude,longitude,gunshot_injury_i", "victimization_primary='HOMICIDE'"):
        yield int(r["date"][:4]), r.get("longitude"), r.get("latitude"), r.get("gunshot_injury_i"), r["date"]


def _nypd():
    for r in socrata_all("data.cityofnewyork.us", "833y-fsy8", "occur_date,latitude,longitude", "statistical_murder_flag=true"):
        yield int(r["occur_date"][:4]), r.get("longitude"), r.get("latitude"), "YES", r["occur_date"]


def _philly():
    import urllib.parse
    q = "select date_, point_x, point_y from shootings where fatal = '1' and coalesce(officer_involved,'N') <> 'Y'"
    for r in json.loads(get("https://phl.carto.com/api/v2/sql?q=" + urllib.parse.quote(q)))["rows"]:
        if r.get("date_"):
            yield int(r["date_"][:4]), r.get("point_x"), r.get("point_y"), "YES", r["date_"]


# LAPD weapon codes that are firearms (Crm Cd 101-107, 109, 110, 115, 116, 122); starter pistols (111) and air/BB guns (114) are not.
_LAPD_FIREARM = {"101", "102", "103", "104", "105", "106", "107", "109", "110", "115", "116", "122"}


def _lapd():
    """Los Angeles Police Department criminal homicide (Crm Cd 110) from the two frozen public sets, 2010-2019 and 2020-2024.
    The NIBRS sets (from March 2024) need a login and are not used. Exact duplicate rows (66 in 2016) are dropped by DR number.
    Only date, coordinates and weapon code are requested: no victim age, sex or descent, no MO codes."""
    seen = set()
    for ds in ("63jg-8b9z", "2nrs-mtv8"):
        for r in socrata_all("data.lacity.org", ds, "dr_no,date_occ,lat,lon,weapon_used_cd", "crm_cd='110'"):
            if r["dr_no"] in seen or not r.get("date_occ"):
                continue
            seen.add(r["dr_no"])
            yield int(r["date_occ"][:4]), r.get("lon"), r.get("lat"), "YES" if str(r.get("weapon_used_cd") or "") in _LAPD_FIREARM else "", r["date_occ"]


_CIN_MURDER = ("MURDER", "AGGRAVATED MURDER", "AGGRAVATED MURDER - FELONY", "AGGRAVATED MURDER - PREMEDITATED", "VOLUNTARY MANSLAUGHTER")


def _cincinnati():
    """Cincinnati Police murders from two datasets: the old RMS file to 2024-06-02 (k59e-2pvf) and the new STARS-category file from
    2024-06-03 (7aqy-xrv9). Murder, aggravated murder and voluntary manslaughter only; involuntary manslaughter, reckless and negligent
    homicide are left out. The old file repeats each incident once per spatial-join match (same instanceid, coordinates jittered by
    a few metres), so rows are counted once per instanceid. 2010 is a part-year in the old file and is left out. Only date and
    coordinates are requested: no victim age or sex, no weapon (the new file has none, so there is no firearm split)."""
    seen = {}
    names = ",".join("'%s'" % o for o in _CIN_MURDER)
    for r in socrata_all("data.cincinnati-oh.gov", "k59e-2pvf", "instanceid,date_from,longitude_x,latitude_x",
                         f"offense in ({names}) AND date_from >= '2011-01-01' AND date_from < '2024-06-03'"):
        k = r["instanceid"]
        if k not in seen or (not seen[k][1] and r.get("longitude_x")):
            seen[k] = (r["date_from"], r.get("longitude_x"), r.get("latitude_x"))
    for d, lon, lat in seen.values():
        yield int(d[:4]), lon, lat, "", d
    for r in socrata_all("data.cincinnati-oh.gov", "7aqy-xrv9", "incident_no,datefrom,longitude_x,latitude_x",
                         "stars_category='Homicide' AND datefrom >= '2024-06-03'"):
        yield int(r["datefrom"][:4]), r.get("longitude_x"), r.get("latitude_x"), "", r["datefrom"]


_CLT_GUN = re.compile(r"handgun|firearm|rifle|shotgun", re.I)


def _charlotte():
    """Charlotte-Mecklenburg Police homicide victims (UCR murder and non-negligent manslaughter), 2015-. The layer does not
    support paging (it returns all ~1,000 rows in one reply, under its 2,000 limit), so it is read in one request.
    Only year, date reported, weapon and the public coordinates are requested: no age, sex, race, circumstances or clearance."""
    import urllib.parse
    base = "https://gis.charlottenc.gov/arcgis/rest/services/ODP/CMPD_Homicide/MapServer/0"
    q = urllib.parse.urlencode({"where": "1=1", "outFields": "ID,CALENDAR_YEAR,DATE_REPORTED,WEAPON,LATITUDE_PUBLIC,LONGITUDE_PUBLIC",
                                "returnGeometry": "false", "f": "json"})
    j = _arcgis_json(f"{base}/query?{q}")
    if "error" in j:
        raise RuntimeError(j["error"])
    if j.get("exceededTransferLimit"):
        raise RuntimeError("Charlotte homicide layer now exceeds one page; add per-year requests")
    for f in j["features"]:
        a = f["attributes"]
        d = datetime.utcfromtimestamp(a["DATE_REPORTED"] / 1000).strftime("%Y-%m-%d") if a.get("DATE_REPORTED") else ""
        try:
            y = int(a.get("CALENDAR_YEAR") or d[:4])
        except ValueError:
            continue
        yield y, a.get("LONGITUDE_PUBLIC"), a.get("LATITUDE_PUBLIC"), "YES" if _CLT_GUN.search(a.get("WEAPON") or "") else "", d


def _atlanta():
    """Atlanta Police Department homicides from three open-data files that follow each other: 1997-2008 (UCR code 110, murder; negligent
    manslaughter 120 is left out), 2009-2020 (APD's own 'HOMICIDE' crime type, whose local offense codes the portal does not define,
    so a few non-murder records may be included) and 2021- (NIBRS 09A murder and non-negligent manslaughter, one count per victim).
    Only the year, date and coordinates are requested: no victim, weapon or address fields."""
    base = "https://services3.arcgis.com/Et5Qfajgiyosiw4d/arcgis/rest/services"
    iso = lambda ms: datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else ""  # noqa: E731
    for f in arcgis_all(f"{base}/Crime_Data_1997_2008/FeatureServer/0", where="UCR__=110 AND UPPER(UC2literal)='HOMICIDE' AND CrmYear<=2008",
                        fields="CrmYear,Date_From1,Longitude,Latitude", geometry=False, order="ObjectId"):
        a = f["attributes"]
        if a.get("CrmYear"):
            yield int(a["CrmYear"]), a.get("Longitude"), a.get("Latitude"), "", iso(a.get("Date_From1"))
    for f in arcgis_all(f"{base}/2009_2020CrimeData/FeatureServer/0", where="Crime_Type='HOMICIDE'",
                        fields="Report_Date,Occur_Date,Longitude,Latitude", geometry=False, order="ObjectId"):
        a = f["attributes"]
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", a.get("Occur_Date") or "")
        d = f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}" if m else iso(a.get("Report_Date"))
        if d and 2009 <= int(d[:4]) <= 2020:
            yield int(d[:4]), a.get("Longitude"), a.get("Latitude"), "", d
    for f in arcgis_all(f"{base}/OpenDataWebsite_Crime_view/FeatureServer/0", where="NIBRS_Bucket='Homicide'",
                        fields="OccurredFromDate,ReportDate,Vic_Count,Longitude,Latitude", geometry=False, order="OBJECTID"):
        a = f["attributes"]
        d = iso(a.get("OccurredFromDate") or a.get("ReportDate"))
        for _ in range(max(1, int(a.get("Vic_Count") or 1))):
            yield int(d[:4]), a.get("Longitude"), a.get("Latitude"), "", d


def _denver():
    """Denver Police murders from the NIBRS offenses file (previous five calendar years plus the current year, so 2021-): offense category
    'murder', types homicide-family (0902) and homicide-other (0912), one count per victim (VICTIM_COUNT). Negligent homicide (0910)
    and police killings by gun (0907, covered by the police-killings layer) are left out. Only date and coordinates are requested."""
    base = "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_CRIME_OFFENSES_P/FeatureServer/324"
    seen = set()
    for f in arcgis_all(base, where="OFFENSE_CATEGORY_ID='murder' AND OFFENSE_TYPE_ID IN ('homicide-family','homicide-other')",
                        fields="OFFENSE_ID,FIRST_OCCURRENCE_DATE,VICTIM_COUNT,GEO_LON,GEO_LAT", geometry=False, order="OBJECTID"):
        a = f["attributes"]
        if a["OFFENSE_ID"] in seen or not a.get("FIRST_OCCURRENCE_DATE"):
            continue
        seen.add(a["OFFENSE_ID"])
        d = datetime.utcfromtimestamp(a["FIRST_OCCURRENCE_DATE"] / 1000).strftime("%Y-%m-%d")
        for _ in range(max(1, int(round(a.get("VICTIM_COUNT") or 1)))):
            yield int(d[:4]), a.get("GEO_LON"), a.get("GEO_LAT"), "", d


def _detroit():
    base = "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/RMS_Crime_Incidents/FeatureServer/0"
    for f in arcgis_all(base, where="offense_category='HOMICIDE'", fields="incident_year,longitude,latitude,incident_occurred_at", geometry=False):
        a = f["attributes"]
        d = datetime.utcfromtimestamp(a["incident_occurred_at"] / 1000).strftime("%Y-%m-%d") if a.get("incident_occurred_at") else ""
        yield a.get("incident_year"), a.get("longitude"), a.get("latitude"), "", d


def ct_drug_deaths():
    log("• Connecticut accidental drug-related deaths …")
    died, lived, labels = defaultdict(lambda: [0] * NC), defaultdict(lambda: [0] * NC), {}
    years = set()
    n = 0
    for r in socrata_all("data.ct.gov", "rybz-nyjw", "date,injurycity,injurycitygeo,residencecity,residencecitygeo,deathcitygeo,deathcity", "date IS NOT NULL"):
        y = int(r["date"][:4])
        years.add(y)
        n += 1
        for geo, city, bucket in [(r.get("injurycitygeo") or r.get("deathcitygeo"), r.get("injurycity") or r.get("deathcity"), died),
                                  (r.get("residencecitygeo"), r.get("residencecity"), lived)]:
            if geo and geo.get("latitude"):
                k = (round(float(geo["longitude"]), 4), round(float(geo["latitude"]), 4))
                c = bucket[(*k, y)]
                c[0] += 1  # all
                c[1] += 1  # every record is a drug death
                labels[k] = (city or "").title()
    years = sorted(years)
    log(f"  {n:,} deaths {years[0]}–{years[-1]}")
    return {
        "key": "ct_drug", "label": "Connecticut drug deaths", "kind": "town", "area": "Connecticut", "what": "medical examiner",
        "show": {"overdose": 1}, "color": 3, "years": years, "cats": CATS, "hasLived": True, "latest": f"{years[-1]}", "cases": n,
        "died": _pack(died, years, labels), "lived": _pack(lived, years, labels),
        "diedNote": "town where the drug use happened",
        "livedNote": "town where the person lived",
        "source": "CT Office of the Chief Medical Examiner via data.ct.gov", "sourceUrl": "https://data.ct.gov/d/rybz-nyjw",
    }


IPOP = "https://github.com/UK-IPOP/open-data-pipeline/releases/{}/{}"


def _ipop_rows(tag, name):
    """Medical examiner tables republished by the UK-IPOP open data pipeline (GitHub releases)."""
    csv.field_size_limit(10**9)
    url = IPOP.format("latest/download" if tag == "latest" else f"download/{tag}", name)
    return csv.DictReader(io.StringIO(get(url, timeout=600).decode("utf-8", "replace")))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def milwaukee():
    """Milwaukee County ME, every case 2002–Nov 2025, geocoded death address. Frozen: the county moved to a dashboard."""
    log("• Milwaukee County medical examiner (UK-IPOP snapshot) …")
    acc = Acc()
    for r in _ipop_rows("2025-12-01", "milwaukee_county_wide_form.csv"):
        y = int(_num(r.get("death_year")) or 0)
        if y < 2002:
            continue
        cats = categories(r.get("mode"), f"{r.get('causea')} {r.get('causeb')} {r.get('causeother')}",
                          gun_flag=(r.get("deathtype") == "Gunshot Injury"),
                          extra=("drug" if r.get("deathtype") == "Drug Related" else "") + (" cardiovascular" if r.get("deathtype") == "Cardiovascular" else ""))
        lat, lon = _num(r.get("geocoded_latitude")), _num(r.get("geocoded_longitude"))
        died = (snap(lon), snap(lat)) if lat and lon and 42.6 < lat < 43.4 and -88.4 < lon < -87.6 else None
        acc.add(y, cats, died, None, date=(r.get("deathdate") or "")[:10])
    return layer("milwaukee", "Milwaukee County Medical Examiner", "Milwaukee County, WI", acc, kind="me", what="medical examiner",
                 show=SHOW_ME, color=4, source="Milwaukee County Medical Examiner, via the UK-IPOP open data pipeline (snapshot, Dec 2025)",
                 url="https://github.com/UK-IPOP/open-data-pipeline/releases/tag/2025-12-01",
                 died_note="where the death happened (~1 km squares); snapshot ends Nov 2025")


def pima():
    """Pima County (Tucson) OME drug-related deaths, 2017–, geocoded death location + residence ZIP. Monthly."""
    log("• Pima County drug deaths (UK-IPOP) …")
    z = zcta_centroids()
    acc = Acc()
    for r in _ipop_rows("latest", "pima_county_wide_form.csv"):
        y = int(_num(r.get("death_year")) or 0)
        m = r.get("dc_worksheet_-_manner_of_death") or ""
        cats = [0] + ([1] if not m.startswith("Natural") else []) + ([2] if m.startswith("Suicide") else [])
        lat, lon = _num(r.get("composite_latitude")) or _num(r.get("geocoded_latitude")), _num(r.get("composite_longitude")) or _num(r.get("geocoded_longitude"))
        died = (snap(lon), snap(lat)) if lat and lon and 31.2 < lat < 32.8 and -113.4 < lon < -110.4 else None
        lived, llab = zip_pt(z, str(r.get("identification_-_zip") or "").split(".")[0])
        acc.add(y, cats, died, lived, None, llab, (r.get("identification_-_date_of_death") or "")[:10])
    return layer("pima", "Pima County drug deaths", "Pima County, AZ (Tucson)", acc, kind="me", what="medical examiner",
                 show={"overdose": 1}, color=2, source="Pima County Office of the Medical Examiner, via the UK-IPOP open data pipeline",
                 url="https://github.com/UK-IPOP/open-data-pipeline", died_note="where the death happened (~1 km squares)",
                 lived_note="where the person lived (ZIP Codes)")


def cuyahoga():
    """Cuyahoga County (Cleveland) ME drug-related deaths, 2014–, residence ZIP only (no geocodes). Monthly."""
    log("• Cuyahoga County drug deaths (UK-IPOP) …")
    z = zcta_centroids()
    acc = Acc()
    for r in _ipop_rows("latest", "cuyahoga_county_wide_form.csv"):
        y = int(_num(r.get("death_date_year")) or 0)
        m = r.get("rc_app_manner") or ""
        if m.startswith("Natural"):
            continue
        cats = [0, 1] + ([2] if m.startswith("Suicide") else [])
        mo = int(_num(r.get("death_date_month")) or 0)
        lived, llab = zip_pt(z, str(r.get("zip") or "").split(".")[0])
        acc.add(y, cats, None, lived, None, llab, f"{y}-{mo:02d}" if mo else "")
    return layer("cuyahoga", "Cuyahoga County drug deaths", "Cuyahoga County, OH (Cleveland)", acc, kind="zip", what="medical examiner",
                 show={"overdose": 1}, color=3, source="Cuyahoga County Medical Examiner, via the UK-IPOP open data pipeline",
                 url="https://github.com/UK-IPOP/open-data-pipeline", died_note="", lived_note="where the person lived (ZIP Codes)")


def _live_layers():
    """Layer keys whose pipeline/sources.yml entry has status `live`."""
    import yaml
    from pathlib import Path
    reg = yaml.safe_load((Path(__file__).parent / "sources.yml").read_text())["sources"]
    return {r["layer"] for r in reg if r.get("layer") and r.get("status") == "live"}


def new_city_jobs():
    """Homicide layers added 2026-10-10 (owner choice: Cincinnati, Charlotte, Atlanta, Denver). Homicide victims only, ~1 km squares."""
    only_homicide = lambda v: [3]  # noqa: E731
    yes = lambda v: [3] + ([4] if str(v).upper() in ("YES", "Y", "TRUE") else [])  # noqa: E731
    return [
        ("cincinnati_homicides", lambda: city_homicides("cincinnati_homicides", "Cincinnati", _cincinnati,
            "https://data.cincinnati-oh.gov/d/k59e-2pvf", "Cincinnati Police Department via City of Cincinnati Open Data (public domain)",
            only_homicide, color=2, show={"homicide": 3}, before=None, report_missing=True,
            note=" — murder, aggravated murder and voluntary manslaughter, 2011 on, one count per incident ID; no firearm split (the new records have no weapon field)")),
        ("charlotte_homicides", lambda: city_homicides("charlotte_homicides", "Charlotte (CMPD)", _charlotte,
            "https://gis.charlottenc.gov/arcgis/rest/services/ODP/CMPD_Homicide/MapServer/0",
            "Charlotte-Mecklenburg Police Department via City of Charlotte Open Data", yes, color=2, report_missing=True,
            note=" — Charlotte-Mecklenburg Police jurisdiction, 2015 on, by year reported; firearm = a weapon field that names a handgun, rifle, shotgun or firearm")),
        ("atlanta_homicides", lambda: city_homicides("atlanta_homicides", "Atlanta (APD)", _atlanta,
            "https://opendata.atlantapd.org/", "Atlanta Police Department via APD Open Data", only_homicide, color=2, show={"homicide": 3},
            report_missing=True,
            note=" — City of Atlanta, 1997 on, by year occurred; no firearm split (the 2009-2020 file has no weapon field); 2009-2020 uses APD's own homicide type, so a few non-murder records may be included")),
        ("denver_homicides", lambda: city_homicides("denver_homicides", "Denver (DPD)", _denver,
            "https://www.denvergov.org/opendata/dataset/city-and-county-of-denver-crime", "Denver Police Department via Denver Open Data Catalog",
            only_homicide, color=2, show={"homicide": 3}, report_missing=True,
            note=" — City and County of Denver, 2021 on (the source keeps five years), murder offenses counted per victim; negligent homicide and police shootings left out; no firearm split")),
    ]


# Layers that are no longer fetched: the previous file is kept as it is (marked stale) and the reason is logged.
FROZEN = {
    "allegheny": "WPRDC's robots.txt disallows /api/ (seen 2026-10-15) and its datastore API returned only 1,000 rows that day; "
                 "kept at its last full pull (7,780 deaths, 2026-10-12) until a permitted download route is chosen",
}
SHRINK_LIMIT = 0.5  # a refresh that returns under half of last time's deaths is treated as a failed fetch


def build_incidents(out_dir, status: dict):
    """Build every incident layer. A failing source keeps its previous file and is reported.
    A source whose refresh returns under SHRINK_LIMIT of its previous deaths also keeps its previous file (a capped or broken API)."""
    (out_dir / "points").mkdir(exist_ok=True)
    layers = []
    yes = lambda v: [3] + ([4] if str(v).upper() in ("YES", "Y", "TRUE") else [])  # noqa: E731
    jobs = [
        ("cook_county", lambda: medical_examiner(
            "Cook County", "datacatalog.cookcountyil.gov", "cjeq-bs86",
            {"date": "death_date", "manner": "manner", "lat": "latitude", "lon": "longitude", "rzip": "residence_zip",
             "cause": "primarycause", "gun": "gunrelated", "opioid": "opioids"},
            2014, "Cook County, IL (Chicago)", "https://datacatalog.cookcountyil.gov/d/cjeq-bs86", color=1)),
        ("santa_clara_county", lambda: medical_examiner(
            "Santa Clara County", "data.sccgov.org", "s3fb-yrjp",
            {"date": "death_date", "manner": "manner_of_death", "lat": "latitude", "lon": "longitude", "rzip": "resident_zip",
             "cause": "cause_of_death"},
            2018, "Santa Clara County, CA (San Jose)", "https://data.sccgov.org/d/s3fb-yrjp", color=2)),
        ("orange_fl", orange_fl),
        ("san_diego", san_diego),
        ("sacramento", sacramento),
        ("allegheny", allegheny),
        ("milwaukee", milwaukee),
        ("pima", pima),
        ("cuyahoga", cuyahoga),
        ("ct_drug", ct_drug_deaths),
        ("police", police_killings),
        ("other_accidents", other_accidents),
        ("mass_shootings", mass_shootings),
        ("chicago_homicides", lambda: city_homicides("chicago_homicides", "Chicago", _chicago,
            "https://data.cityofchicago.org/d/gumc-mgzr", "Chicago Police Department via City of Chicago Data Portal", yes, color=2,
            before=2014, note=" — before 2014; the Cook County ME layer covers later years")),
        ("nyc_homicides", lambda: city_homicides("nyc_homicides", "New York City", _nypd,
            "https://data.cityofnewyork.us/d/833y-fsy8", "NYPD shooting incidents (murders) via NYC Open Data", yes, color=2)),
        ("philly_homicides", lambda: city_homicides("philly_homicides", "Philadelphia", _philly,
            "https://opendataphilly.org/datasets/shooting-victims/", "Philadelphia Police fatal shootings via OpenDataPhilly", yes, color=2)),
        ("lapd_homicides", lambda: city_homicides("lapd_homicides", "Los Angeles (LAPD)", _lapd,
            "https://data.lacity.org/d/2nrs-mtv8", "Los Angeles Police Department via City of Los Angeles Open Data", yes, color=2,
            before=2024, note=" — City of Los Angeles only (LAPD area, about 40% of the county's people), 2010–2023; the 2015 count is about 60 below its neighbours in the source")),
        *[(k, f) for k, f in new_city_jobs() if k in _live_layers()],  # a new city layer is built only once its registry entry is `live` (owner approval)
        ("detroit_homicides", lambda: city_homicides("detroit_homicides", "Detroit", _detroit,
            "https://data.detroitmi.gov/", "Detroit Police Department via Detroit Open Data", lambda v: [3], color=2, show={"homicide": 3})),
    ]
    prev_index = {}
    idx_path = out_dir / "points" / "index.json"
    if idx_path.exists():
        prev_index = {l["key"]: l for l in json.loads(idx_path.read_text())}
    for key, fn in jobs:
        if key in FROZEN:
            log(f"  = {key} not refreshed: {FROZEN[key]}")
            status[key] = {"ok": True, "frozen": True}
            if key in prev_index:
                layers.append({**prev_index[key], "stale": True})
            continue
        try:
            layer = fn()
            prev = prev_index.get(key)
            if prev and prev.get("cases") and layer.get("cases", 0) < SHRINK_LIMIT * prev["cases"]:
                raise RuntimeError(f"refresh returned {layer.get('cases', 0):,} deaths against {prev['cases']:,} last time; keeping the previous file")
            (out_dir / "points" / f"{layer['key']}.json").write_text(
                json.dumps({"died": layer.pop("died"), "lived": layer.pop("lived")}, separators=(",", ":")))
            monthly = layer.pop("monthly", None)
            if monthly:  # month-by-month dots, loaded only when the viewer switches to months
                (out_dir / "points" / f"{layer['key']}_m.json").write_text(json.dumps(monthly, separators=(",", ":")))
                layer["hasMonthly"] = True
            layer["fetched"] = datetime.utcnow().strftime("%Y-%m-%d")
            layers.append(layer)
            status[key] = {"ok": True, "latest": layer.get("latest")}
        except Exception as e:  # noqa: BLE001
            log(f"  ! {key} failed: {e}")
            status[key] = {"ok": False, "error": str(e)[:200]}
            if key in prev_index:
                layers.append({**prev_index[key], "stale": True})
    idx_path.write_text(json.dumps(layers, separators=(",", ":")))
    return layers
