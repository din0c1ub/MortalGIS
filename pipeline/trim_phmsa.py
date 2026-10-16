"""Trim PHMSA's pipeline incident files to a point snapshot of deaths (run by hand; the weekly build reads the result).

PHMSA (Pipeline and Hazardous Materials Safety Administration) publishes flat files per system and period at
https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data
(the site refuses scripted downloads; save the zips by hand). Unzip each into a folder of the same name, then:
    python3 pipeline/trim_phmsa.py <folder with the unzipped sets>
writes data_manual/points/phmsa_pipeline_deaths.csv: one row per incident with at least one death, with the month, a point snapped to the
map's 0.01-degree grid, the deaths, the system (gas distribution, gas transmission/gathering, hazardous liquid, LNG) and how the point was
placed: "site" (the reported coordinates; files from 2002/2004 on), "zip" (the Census ZCTA centroid of the reported ZIP Code) or "town"
(the Census place or county-subdivision centroid of the reported city). No operator names, addresses, report numbers or narratives.
Incidents that cannot be placed are left out and counted."""
import csv
import io
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from trim_ntsb_pre1982 import gazetteer, GAZ_COUSUB, norm, snap  # noqa: E402

ZCTA = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"
csv.field_size_limit(10**9)
SYSTEM = [("gas_distribution", "gas distribution"), ("gas_transmission", "gas transmission or gathering"), ("gas_gathering", "gas transmission or gathering"),
          ("hazardous_liquid", "hazardous liquid"), ("liquefied_natural_gas", "LNG facility")]
DEATHS = [["FATAL"], ["TFAT"], ["FAT"], ["TOTAL_FATALITIES"], ["EMPLOYEE_FATALITIES", "NON_EMPLOYEE_FATALITIES"],
          ["EMPLOYEE_FATALITIES", "NON_EMPLOYEE_FAT"]]
LAT = ["LOCATION_LATITUDE", "FACILITY_LATITUDE", "LATITUDE"]
LON = ["LOCATION_LONGITUDE", "FACILITY_LONGITUDE", "LONGITUDE"]
CITY = ["LOCATION_CITY_NAME", "ONSHORE_CITY_NAME", "FACILITY_CITY", "ACCITY", "ACCTY", "INCIDENT_CITY", "ACCIDENT_CITY"]
STATE = ["LOCATION_STATE_ABBREVIATION", "ONSHORE_STATE_ABBREVIATION", "FACILITY_STATE", "ACSTATE", "ACCST", "INCIDENT_STATE", "ACCIDENT_STATE"]
ZIP = ["LOCATION_POSTAL_CODE", "ONSHORE_POSTAL_CODE", "FACILITY_ZIP_CODE", "ACZIP"]
DATE = ["LOCAL_DATETIME", "IDATE", "INCIDENT_DATE", "ACCIDENT_DATE"]


def first(r, names):
    for n in names:
        if r.get(n):
            return r[n]
    return ""


def coord(v: str):
    """Decimal degrees, or degrees-minutes-seconds as the 2002-2009 files write them ('N36 19 08.874', "W 84 23'.49")."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    neg = bool(re.search(r"[SWsw]", v))
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", v.replace("'.", "."))]
    if not nums:
        return None
    d = nums[0] + (nums[1] / 60 if len(nums) > 1 else 0) + (nums[2] / 3600 if len(nums) > 2 else 0)
    return -d if neg else d


def month(r):
    y = (r.get("IYEAR") or "").strip()
    d = first(r, DATE)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", d) or None
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", d)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})\b", d)
    if m and y:
        return f"{y}-{int(m.group(1)):02d}"
    return f"{y}-01" if y else None


def zctas():
    raw = urllib.request.urlopen(urllib.request.Request(ZCTA, headers={"User-Agent": "MortalGIS-pipeline/2.0"}), timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")), delimiter="\t")
    head = [h.strip() for h in next(rows)]
    gi, la, lo = head.index("GEOID"), head.index("INTPTLAT"), head.index("INTPTLONG")
    return {r[gi]: (snap(float(r[lo])), snap(float(r[la]))) for r in rows}


def main(folder):
    places = gazetteer()
    for k, v in gazetteer(GAZ_COUSUB).items():
        places.setdefault(k, v)
    zips = zctas()
    rows, stats = [], Counter()
    for f in sorted(Path(folder).glob("*/*.txt")):
        if "Data fields" in f.name:
            continue
        system = next(lbl for key, lbl in SYSTEM if key in f.name)
        txt = f.read_bytes().decode("latin-1")
        delim = "\t" if txt.splitlines()[0].count("\t") > txt.splitlines()[0].count(",") else ","
        rd = csv.DictReader(io.StringIO(txt), delimiter=delim)
        head = {h.strip().upper() for h in rd.fieldnames if h}
        dcols = next((c for c in DEATHS if all(x in head for x in c)), None)
        if not dcols:
            print(f"! {f.name}: no death columns")
            continue
        for r in rd:
            r = {k.strip().upper(): (v or "").strip() for k, v in r.items() if k}
            dead = 0
            for c in dcols:
                try:
                    dead += int(float(r.get(c) or 0))
                except ValueError:
                    pass
            if dead <= 0:
                continue
            stats["incidents"] += 1
            stats["dead"] += dead
            mo = month(r)
            lat, lon = coord(first(r, LAT)), coord(first(r, LON))
            if lat is not None and lon is not None and lon > 0:
                lon = -lon
            how, pt = None, None
            if lat is not None and lon is not None and 15 < lat < 72 and -180 < lon < -60:
                how, pt = "site", (snap(lon), snap(lat))
            if not pt:
                z = re.sub(r"\D", "", first(r, ZIP))[:5]
                if len(z) == 5 and z in zips:
                    how, pt = "zip", zips[z]
            if not pt:
                st = first(r, STATE).upper()[:2]
                key = (norm(first(r, CITY)), st)
                if key in places:
                    how, pt = "town", places[key]
            if not pt or not mo:
                stats["unplaced_incidents"] += 1
                stats["unplaced_dead"] += dead
                continue
            stats[f"placed_{how}_dead"] += dead
            rows.append((mo, pt[0], pt[1], dead, system, how))
    rows.sort()
    out = Path(__file__).resolve().parents[1] / "data_manual" / "points" / "phmsa_pipeline_deaths.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["month", "lon", "lat", "dead", "system", "placed"])
        w.writerows(rows)
    print(out.name, len(rows), "rows;", dict(stats))


if __name__ == "__main__":
    main(sys.argv[1])
