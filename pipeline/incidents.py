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

    def add(self, y, cats, died=None, lived=None, dlabel=None, llabel=None, date=""):
        if not y or y > datetime.now().year:
            return
        self.n += 1
        self.years.add(y)
        self.latest = max(self.latest, str(date)[:10])
        mo = str(date)[5:7]
        if died and mo.isdigit() and 1 <= int(mo) <= 12 and str(date)[:4] == str(y):
            c = self.monthly[(*died, y, int(mo))]
            for k in cats:
                c[k] += 1
        for pt, bucket, lab in ((died, self.died, dlabel), (lived, self.lived, llabel)):
            if pt:
                c = bucket[(*pt, y)]
                for k in cats:
                    c[k] += 1
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


def arcgis_all(url, where="1=1", fields="*", geometry=True, page=2000):
    import urllib.parse
    off = 0
    while True:
        q = urllib.parse.urlencode({"where": where, "outFields": fields, "returnGeometry": str(geometry).lower(), "outSR": 4326,
                                    "resultOffset": off, "resultRecordCount": page, "orderByFields": "OBJECTID" if fields == "*" else "", "f": "json"})
        j = json.loads(get(f"{url}/query?{q}"))
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
    log("• People killed by police (Fatal Encounters, Washington Post) …")
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
        if y > 2021:
            continue
        cats = [0] + ([4] if "gunshot" in force else []) + ([5] if "vehicle" in force else [])
        acc.add(y, cats, pt, None, date=f"{yy}-{int(mo):02d}-{int(dd):02d}")
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
    return layer("police", "Killed by police", "United States", acc, kind="me", what="killed by police,",
                 show={"all": 0, "firearm": 4, "traffic": 5}, color=4,
                 source="Fatal Encounters (2000–2021) and The Washington Post Fatal Force (2022–2024, CC BY-NC-SA)",
                 url="https://fatalencounters.org/", died_note="where the person was killed (~1 km squares); shootings, vehicle pursuits and other force")


def city_homicides(key, city, fetch, url, source, cats_fn, color=2, show=None, before=None, note=""):
    log(f"• {city} homicides …")
    acc = Acc()
    for y, lon, lat, extra, d in fetch():
        try:
            pt = (snap(float(lon)), snap(float(lat)))
        except (TypeError, ValueError):
            continue
        if not (-180 < pt[0] < -60 and 15 < pt[1] < 72) or (before and y and y >= before):
            continue
        acc.add(y, cats_fn(extra), pt, None, date=d)
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


def build_incidents(out_dir, status: dict):
    """Build every incident layer. A failing source keeps its previous file and is reported."""
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
        ("ct_drug", ct_drug_deaths),
        ("police", police_killings),
        ("chicago_homicides", lambda: city_homicides("chicago_homicides", "Chicago", _chicago,
            "https://data.cityofchicago.org/d/gumc-mgzr", "Chicago Police Department via City of Chicago Data Portal", yes, color=2,
            before=2014, note=" — before 2014; the Cook County ME layer covers later years")),
        ("nyc_homicides", lambda: city_homicides("nyc_homicides", "New York City", _nypd,
            "https://data.cityofnewyork.us/d/833y-fsy8", "NYPD shooting incidents (murders) via NYC Open Data", yes, color=2)),
        ("philly_homicides", lambda: city_homicides("philly_homicides", "Philadelphia", _philly,
            "https://opendataphilly.org/datasets/shooting-victims/", "Philadelphia Police fatal shootings via OpenDataPhilly", yes, color=2)),
        ("detroit_homicides", lambda: city_homicides("detroit_homicides", "Detroit", _detroit,
            "https://data.detroitmi.gov/", "Detroit Police Department via Detroit Open Data", lambda v: [3], color=2, show={"homicide": 3})),
    ]
    prev_index = {}
    idx_path = out_dir / "points" / "index.json"
    if idx_path.exists():
        prev_index = {l["key"]: l for l in json.loads(idx_path.read_text())}
    for key, fn in jobs:
        try:
            layer = fn()
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
