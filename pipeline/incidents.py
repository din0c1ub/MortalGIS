"""Incident layers: where deaths happened (and, where published, where the person lived).

Sources
- Cook County (IL) Medical Examiner case archive: incident coordinates + residence ZIP. Daily.
- Santa Clara County (CA) Medical Examiner-Coroner: coordinates + residence ZIP. Daily.
- Connecticut accidental drug-related deaths: injury town + residence town. Annual.

Privacy rules applied here (the source tables are more detailed than what we publish):
- Medical examiner incident points are snapped to a ~1 km grid (0.01 degree) and only counts per
  cell, year and manner of death are kept. No ages, names, addresses, causes or exact times.
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


CATS = ["all", "overdose", "suicide", "homicide", "firearm"]
DRUG_TERMS = ("drug", "fentanyl", "heroin", "cocaine", "methamphetamine", "amphetamine", "opioid", "opiate",
              "oxycodone", "hydrocodone", "morphine", "methadone", "benzodiazepine", "alprazolam", "xylazine",
              "tramadol", "overdose", "buprenorphine", "carfentanil")
GUN_TERMS = ("gunshot", "firearm", "shotgun", "rifle", "handgun")


def categories(manner: str, cause: str, gun_flag=None, opioid_flag=None) -> list[int]:
    m, c = (manner or "").lower(), (cause or "").lower()
    out = [0]
    if not m.startswith("natural") and (any(t in c for t in DRUG_TERMS) or str(opioid_flag).lower() == "true"):
        out.append(1)
    if m.startswith("suicide"):
        out.append(2)
    if m.startswith("homicide"):
        out.append(3)
    if str(gun_flag).lower() == "true" or any(t in c for t in GUN_TERMS):
        out.append(4)
    return out


def medical_examiner(name, domain, dataset, cols, since_year, area, url):
    """Generic ME source → died (~1 km grid) + lived (ZIP) counts per year and category."""
    log(f"• {name} medical examiner …")
    z = zcta_centroids()
    died, lived, zlabel = defaultdict(lambda: [0] * 5), defaultdict(lambda: [0] * 5), {}
    n = latest = 0
    years = set()
    where = f"{cols['date']} >= '{since_year}-01-01'"
    fields = [cols[k] for k in ("date", "manner", "lat", "lon", "rzip", "cause") if cols.get(k)] + [cols[k] for k in ("gun", "opioid") if cols.get(k)]
    for r in socrata_all(domain, dataset, ",".join(fields), where):
        try:
            y = int(str(r.get(cols["date"]))[:4])
        except ValueError:
            continue
        if y > datetime.now().year:  # a few source rows carry impossible future dates
            continue
        n += 1
        years.add(y)
        latest = max(latest, int(str(r[cols["date"]])[:10].replace("-", "")))
        cats = categories(r.get(cols["manner"]), r.get(cols.get("cause", ""), ""), r.get(cols.get("gun", "")), r.get(cols.get("opioid", "")))
        try:
            lat, lon = float(r[cols["lat"]]), float(r[cols["lon"]])
            if lat and lon:
                cell = died[(snap(lon), snap(lat), y)]
                for k in cats:
                    cell[k] += 1
        except (KeyError, TypeError, ValueError):
            pass
        zp = str(r.get(cols["rzip"]) or "")[:5]
        if zp in z:
            cell = lived[(*z[zp], y)]
            for k in cats:
                cell[k] += 1
            zlabel[z[zp]] = f"ZIP {zp}"
    years = sorted(years)
    log(f"  {n:,} cases {years[0]}–{years[-1]}; {len(died):,} grid cells, {len(lived):,} ZIP cells")
    lat_s = str(latest)
    return {
        "key": name.lower().replace(" ", "_"), "label": f"{name} Medical Examiner", "kind": "me", "area": area,
        "years": years, "cats": CATS, "hasLived": True,
        "latest": f"{lat_s[:4]}-{lat_s[4:6]}-{lat_s[6:]}", "cases": n,
        "died": _pack(died, years), "lived": _pack(lived, years, zlabel),
        "diedNote": "where the injury or death happened (~1 km squares)",
        "livedNote": "where the person lived (ZIP Codes)",
        "source": f"{name} Medical Examiner open data", "sourceUrl": url,
    }


def ct_drug_deaths():
    log("• Connecticut accidental drug-related deaths …")
    died, lived, labels = defaultdict(lambda: [0] * 5), defaultdict(lambda: [0] * 5), {}
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
        "key": "ct_drug", "label": "Connecticut drug deaths", "kind": "town", "area": "Connecticut",
        "years": years, "cats": CATS, "hasLived": True, "latest": f"{years[-1]}", "cases": n,
        "died": _pack(died, years, labels), "lived": _pack(lived, years, labels),
        "diedNote": "town where the drug use happened",
        "livedNote": "town where the person lived",
        "source": "CT Office of the Chief Medical Examiner via data.ct.gov", "sourceUrl": "https://data.ct.gov/d/rybz-nyjw",
    }


def build_incidents(out_dir, status: dict):
    """Build every incident layer. A failing source keeps its previous file and is reported."""
    (out_dir / "points").mkdir(exist_ok=True)
    layers = []
    jobs = [
        ("cook_county", lambda: medical_examiner(
            "Cook County", "datacatalog.cookcountyil.gov", "cjeq-bs86",
            {"date": "death_date", "manner": "manner", "lat": "latitude", "lon": "longitude", "rzip": "residence_zip",
             "cause": "primarycause", "gun": "gunrelated", "opioid": "opioids"},
            2014, "Cook County, IL (Chicago)", "https://datacatalog.cookcountyil.gov/d/cjeq-bs86")),
        ("santa_clara_county", lambda: medical_examiner(
            "Santa Clara County", "data.sccgov.org", "s3fb-yrjp",
            {"date": "death_date", "manner": "manner_of_death", "lat": "latitude", "lon": "longitude", "rzip": "resident_zip",
             "cause": "cause_of_death"},
            2018, "Santa Clara County, CA (San Jose)", "https://data.sccgov.org/d/s3fb-yrjp")),
        ("ct_drug", ct_drug_deaths),
    ]
    prev_index = {}
    idx_path = out_dir / "points" / "index.json"
    if idx_path.exists():
        prev_index = {l["key"]: l for l in json.loads(idx_path.read_text())}
    for key, fn in jobs:
        try:
            layer = fn()
            if True:
                (out_dir / "points" / f"{layer['key']}.json").write_text(
                    json.dumps({"died": layer.pop("died"), "lived": layer.pop("lived")}, separators=(",", ":")))
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
