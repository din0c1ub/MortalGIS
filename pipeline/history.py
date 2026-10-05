#!/usr/bin/env python3
"""MortalGIS history build (run once, or when a source publishes a revision).

Writes site/data/hist/*.json, which build_data.py merges with the weekly sources.

Sources
- NCHS Multiple Cause of Death public-use files 1968–2004, hosted by NBER (one record per death).
  County of residence AND county of occurrence. 1968–1988: every county. 1989–2004: NCHS only
  identifies counties of 100,000+ people in the public files; smaller counties are blank.
- NCI SEER county population estimates 1969–2024 (denominators).
- NHTSA FARS 1975–2024: deaths by county where the crash happened; crash points 2001+.
- NOAA Storm Events 1950–present: direct + indirect deaths by county (zone events via NWS
  zone–county correlation, split evenly across a zone's counties) and event points.

Privacy: county counts of 1–9 are suppressed (CDC/NCHS standard). Rates are not shown for them.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_data import get as _get, log  # noqa: E402
import subprocess  # noqa: E402


def get(url, retries=4, timeout=120):
    """build_data.get, with a curl fallback (some hosts refuse Python's HTTP client)."""
    try:
        return _get(url, retries=retries, timeout=timeout)
    except RuntimeError:
        return subprocess.run(["curl", "-sSfL", "--retry", "3", "--max-time", str(timeout), url],
                              check=True, capture_output=True).stdout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "hist"
CACHE = Path(__file__).resolve().parents[1] / ".cache"

NBER = "https://data.nber.org/mortality/{y}/mort{y}.csv.zip"
XWALK = "https://data.nber.org/mortality/nchs2fips_county1990.csv"
SEER = "https://seer.cancer.gov/popdata/yr1969_2024.20ages/us.1969_2024.20ages.adjusted.txt.gz"

MEASURES = ["all", "overdose", "suicide", "homicide", "firearm", "heart", "stroke"]

# Old / changed county codes → county on the current map
REMAP = {"12025": "12086", "51780": "51083", "51560": "51005", "51515": "51019", "46113": "46102",
         "02270": "02158", "51123": "51800", "51695": "51800", "51785": "51710"}
DROP = {"30113"}
# SEER combined areas → member counties on the map (rates are shared across members)
SEER_COMBOS = {
    "04910": ["04027", "04012"], "15900": ["15009", "15005"], "35910": ["35061", "35006"],
    "08911": ["08001"], "08912": ["08013"], "08913": ["08059"], "08914": ["08123"],
    "51910": ["51153", "51683", "51685"], "51911": ["51165", "51660"], "51913": ["51089", "51690"],
    "51914": ["51199", "51735", "51095", "51830"], "51915": ["51177", "51630", "51179"],
    "51916": ["51005", "51580"], "51917": ["51019"],
    "51918": ["51013", "51510", "51059", "51600", "51610"],
    "36910": ["36005", "36047", "36061", "36081", "36085"],
}
POSTAL = {"AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "DC": "11",
          "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
          "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
          "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
          "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
          "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"}


def atlas_counties():
    topo = json.loads((ROOT / "site" / "data" / "counties-10m.json").read_text())
    return sorted(g["id"] for g in topo["objects"]["counties"]["geometries"] if not g["id"].startswith("72"))


NYC = ["36005", "36047", "36061", "36081", "36085"]


def norm(f: str | None, atlas: set) -> str | None:
    if f == "NYC":
        return "NYC"
    if not isinstance(f, str) or len(f) != 5 or f.endswith("999") or f.endswith("000"):
        return None
    f = REMAP.get(f, f)
    if f in DROP or f not in atlas:
        return None
    return f


# ---------------------------------------------------------------- causes
def _num3(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str[:3], errors="coerce")


def _num4(s: pd.Series) -> pd.Series:
    """4th digit (0–9) or -1 when the code has only 3 characters."""
    return pd.to_numeric(s.str[3:4].where(s.str.len() >= 4), errors="coerce").fillna(-1)


def cause_flags_icd89(ucod: pd.Series, ucr34: pd.Series, icd8: bool) -> dict:
    """ICD-8 (1968–78) / ICD-9 (1979–98). External causes are stored without the 'E' (800–999)."""
    c3, c4 = _num3(ucod), _num4(ucod)
    r34 = pd.to_numeric(ucr34, errors="coerce")
    inr = lambda lo, hi: (c3 >= lo) & (c3 <= hi)  # noqa: E731
    sub = lambda code, lo, hi: (c3 == code) & (c4 >= lo) & (c4 <= hi)  # noqa: E731
    if icd8:
        overdose = inr(850, 859) | sub(950, 0, 5) | sub(962, 0, 0) | sub(980, 0, 5)
        firearm = (c3 == 922) | (c3 == 955) | (c3 == 965) | (c3 == 970) | (c3 == 985)
    else:
        overdose = inr(850, 858) | sub(950, 0, 5) | sub(962, 0, 0) | sub(980, 0, 5)
        firearm = (c3 == 922) | sub(955, 0, 4) | sub(965, 0, 4) | (c3 == 970) | sub(985, 0, 4)
    return {
        "overdose": overdose, "suicide": inr(950, 959), "homicide": inr(960, 969), "firearm": firearm,
        "heart": inr(390, 398) | (c3 == 402) | (c3 == 404) | inr(410, 429),
        "stroke": r34 == 200,  # NCHS 34-cause recode "Cerebrovascular diseases" (matches published totals exactly)
    }


def cause_flags_icd10(ucod: pd.Series) -> dict:
    L = ucod.str[:1]
    n2 = pd.to_numeric(ucod.str[1:3], errors="coerce")
    d4 = _num4(ucod)

    def rng(letter, lo, hi):
        return (L == letter) & (n2 >= lo) & (n2 <= hi)

    def code(letter, n, lo=-1, hi=9):
        return (L == letter) & (n2 == n) & (d4 >= lo) & (d4 <= hi)

    return {
        "overdose": rng("X", 40, 44) | rng("X", 60, 64) | code("X", 85) | rng("Y", 10, 14),
        "suicide": rng("X", 60, 84) | code("Y", 87, 0, 0) | code("U", 3),
        "homicide": rng("X", 85, 99) | rng("Y", 0, 9) | code("Y", 87, 1, 1) | rng("U", 1, 2),
        "firearm": rng("W", 32, 34) | rng("X", 72, 74) | rng("X", 93, 95) | rng("Y", 22, 24) | code("Y", 35, 0, 0) | code("U", 1, 4, 4),
        "heart": rng("I", 0, 9) | code("I", 11) | code("I", 13) | rng("I", 20, 51),
        "stroke": rng("I", 60, 69),
    }


# ---------------------------------------------------------------- NBER
def nber_year(y: int, atlas: set, xw: dict):
    path = CACHE / f"mort{y}.zip"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(get(NBER.format(y=y), timeout=900))
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    head = pd.read_csv(z.open(name), nrows=1, dtype=str, encoding="latin-1").columns
    if "fipsctyr" in head:
        cols = ["restatus", "fipsctyr", "fipsctyo", "ucod"]
    else:
        cols = ["restatus", "countyrs", "countyoc", "ucod"]
    if "ucr34" in head:
        cols.append("ucr34")
    out = {(m, p): defaultdict(int) for m in MEASURES for p in ("res", "occ")}
    lut = {}
    n_all = n_res = n_res_ok = 0
    for df in pd.read_csv(z.open(name), usecols=cols, dtype=str, chunksize=250_000, encoding="latin-1"):
        n_all += len(df)
        if "fipsctyr" in cols:
            res, occ = df["fipsctyr"], df["fipsctyo"]
        elif y >= 2003:  # postal state + FIPS county, e.g. "MA025"
            conv = lambda s: s.str[:2].map(POSTAL) + s.str[2:5]  # noqa: E731
            res, occ = conv(df["countyrs"]), conv(df["countyoc"])
        else:  # 1968–1981: NCHS codes
            res, occ = df["countyrs"].map(xw), df["countyoc"].map(xw)
        for u in set(res.dropna().unique()) | set(occ.dropna().unique()):
            if u not in lut:
                lut[u] = norm(u, atlas)
        res, occ = res.map(lut), occ.map(lut)
        ucod = df["ucod"].fillna("").str.strip()
        if y >= 1999:
            flags = cause_flags_icd10(ucod)
        else:
            flags = cause_flags_icd89(ucod, df["ucr34"] if "ucr34" in df else pd.Series(index=df.index, dtype=str), icd8=(y <= 1978))
        flags["all"] = pd.Series(True, index=df.index)
        resident = df["restatus"].astype(str) != "4"  # 4 = foreign resident
        n_res += int(resident.sum())
        n_res_ok += int(res[resident].notna().sum())
        for m in MEASURES:
            f = flags[m].fillna(False)
            for k, v in res[f & resident].value_counts().items():
                out[(m, "res")][k] += int(v)
            for k, v in occ[f].value_counts().items():
                out[(m, "occ")][k] += int(v)
    out = {k: dict(v) for k, v in out.items()}
    matched = n_res_ok / max(n_res, 1)
    log(f"  {y}: {n_all:,} deaths; residence county identified for {matched:.1%}")
    return out, matched


def build_crosswalk() -> dict:
    """NCHS → FIPS county codes for the 1968–1981 files (which predate FIPS fields).
    Base: NBER's NCHS-to-FIPS crosswalk (1982 geography), plus fixes found by testing the files:
    - DC (NCHS 09-001) is missing from the crosswalk.
    - New York City is one NCHS area (33-029) until 1982 → pseudo-code NYC (rate shared by the 5 boroughs).
    - Virginia used an older scheme before 1982: counties = 3 × alphabetical index (003–285),
      independent cities = 300 + 3 × alphabetical index (excluding Manassas, Manassas Park, Poquoson).
      Verified against 1982 death counts county by county."""
    path = CACHE / "nchs2fips.csv"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(get(XWALK))
    rows = list(csv.DictReader(open(path)))
    xw = {r["nchs_state"] + r["nchs_county"]: r["fipsco"].strip().zfill(5) for r in rows if r["fipsco"].strip().isdigit()}
    xw["09001"] = "11001"
    xw["33029"] = "NYC"
    va = [r for r in rows if r["nchs_state"] == "47"]
    counties = []
    # The old scheme still reserves slots for counties merged into cities in 1963–1974.
    defunct_before = {"Nelson": "51800", "Northampton": "51550", "Pulaski": "51810"}  # Nansemond→Suffolk, Norfolk Co.→Chesapeake, Princess Anne→Virginia Beach
    for r in va:
        if "city" in r["countyname"]:
            continue
        if r["countyname"] in defunct_before:
            counties.append(defunct_before[r["countyname"]])
        counties.append(r["fipsco"])
    cities = [r["fipsco"] for r in va if "city" in r["countyname"] and r["countyname"] not in ("Manassas city", "Manassas Park city", "Poquoson city")]
    for k in list(xw):
        if k.startswith("47"):
            del xw[k]
    for i, f in enumerate(counties, 1):
        xw[f"47{3 * i:03d}"] = f
    for i, f in enumerate(cities):
        xw[f"47{300 + 3 * i:03d}"] = f
    return xw


# ---------------------------------------------------------------- population
def seer_population(atlas: set):
    log("• SEER county population 1969–2024 …")
    path = CACHE / "seer.txt.gz"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(get(SEER, timeout=900))
    pop = defaultdict(lambda: defaultdict(int))
    with gzip.open(path, "rt") as f:
        for line in f:
            pop[int(line[0:4])][line[6:11]] += int(line[18:26])
    groups = {}  # year -> list of (members, pop)
    for y, d in pop.items():
        g = []
        for code, p in d.items():
            if code in SEER_COMBOS:
                members = [m for m in SEER_COMBOS[code] if m in atlas]
            else:
                c = REMAP.get(code, code)
                members = [c] if c in atlas else []
            if members:
                g.append((members, p))
        groups[y] = g
    return groups


# ---------------------------------------------------------------- FARS
def fars_history(atlas: set, first=1975, last=2024):
    county = defaultdict(lambda: defaultdict(int))
    points = defaultdict(lambda: defaultdict(list))  # state -> year -> rows
    for y in range(first, last + 1):
        url = f"https://static.nhtsa.gov/nhtsa/downloads/FARS/{y}/National/FARS{y}NationalCSV.zip"
        cpath = CACHE / f"fars{y}.zip"
        try:
            raw = cpath.read_bytes() if cpath.exists() else get(url, retries=3, timeout=600)
            if not cpath.exists():
                CACHE.mkdir(exist_ok=True)
                cpath.write_bytes(raw)
        except RuntimeError as e:
            log(f"  FARS {y} unavailable: {e}")
            continue
        zf = zipfile.ZipFile(io.BytesIO(raw))
        name = next(n for n in zf.namelist() if n.lower().endswith("accident.csv"))
        rows = csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="latin-1"))
        n = deaths = 0
        for r in rows:
            r = {(k or "").replace("\ufeff", "").replace("ï»¿", "").upper().strip(): v for k, v in r.items()}
            fat = int(r.get("FATALS") or 0)
            f = norm(str(r["STATE"]).zfill(2) + str(r["COUNTY"]).zfill(3), atlas)
            if f:
                county[y][f] += fat
            deaths += fat
            try:
                lat, lon = float(r.get("LATITUDE", "")), float(r.get("LONGITUD", ""))
            except ValueError:
                continue
            if 17 < lat < 72 and -180 < lon < -60:
                points[str(r["STATE"]).zfill(2)][y].append([round(lon, 3), round(lat, 3), fat, int(r.get("MONTH") or 0)])
                n += 1
        log(f"  FARS {y}: {deaths:,} deaths; {n:,} crashes with coordinates")
    return county, points


# ---------------------------------------------------------------- NOAA
def noaa_history(atlas: set, first=1950, last=None):
    idx = get("https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/").decode()
    files = dict(re.findall(r'(StormEvents_details-ftp_v1\.0_d(\d{4})_c\d+\.csv\.gz)', idx))
    by_year = {}
    for fn, yr in re.findall(r'(StormEvents_details-ftp_v1\.0_d(\d{4})_c\d+\.csv\.gz)', idx):
        by_year[int(yr)] = fn  # last listed wins (newest)
    zone = defaultdict(list)
    for line in get("https://www.weather.gov/source/gis/Shapefiles/County/bp16ap26.dbx").decode("latin-1").splitlines():
        p = line.split("|")
        if len(p) > 6 and p[6].isdigit():
            zone[p[4]].append(p[6].zfill(5))
    county = defaultdict(lambda: defaultdict(float))
    points = defaultdict(list)
    unplaced = 0
    for y in sorted(by_year):
        if y < first or (last and y > last):
            continue
        raw = gzip.decompress(get("https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/" + by_year[y], timeout=600))
        for r in csv.DictReader(io.StringIO(raw.decode("latin-1"))):
            d = int(r.get("DEATHS_DIRECT") or 0) + int(r.get("DEATHS_INDIRECT") or 0)
            if not d:
                continue
            st = str(r.get("STATE_FIPS") or "").zfill(2)
            cz = str(r.get("CZ_FIPS") or "").zfill(3)
            targets = []
            if r.get("CZ_TYPE") == "C":
                f = norm(st + cz, atlas)
                targets = [f] if f else []
            elif r.get("CZ_TYPE") == "Z":
                code = (r.get("STATE") or "")
                ab = next((k for k, v in POSTAL.items() if v == st), None)
                targets = [f for f in (norm(c, atlas) for c in zone.get(f"{ab}{cz}", [])) if f]
            if targets:
                for f in targets:
                    county[y][f] += d / len(targets)
            else:
                unplaced += d
            try:
                lat, lon = float(r["BEGIN_LAT"]), float(r["BEGIN_LON"])
                points[y].append([round(lon, 3), round(lat, 3), d, (r.get("EVENT_TYPE") or "")[:24]])
            except (ValueError, KeyError):
                pass
        log(f"  NOAA {y}: {sum(county[y].values()):,.0f} deaths placed in counties")
    log(f"  NOAA deaths that could not be placed in a county (old/marine zones): {unplaced:,}")
    return county, points


# ---------------------------------------------------------------- assemble
def rate_arrays(counts: dict, groups: list, fips_list: list, idx: dict, suppress=True):
    """counts {fips: n}; groups [(members, pop)] → (count array, rate array) with suppression."""
    cnt = [None] * len(fips_list)
    rate = [None] * len(fips_list)
    for f, n in counts.items():
        i = idx.get(f)
        if i is not None:
            cnt[i] = n
    if "NYC" in counts:  # NYC reported as one area: share the rate across the five boroughs
        nyc_pop = sum(p for members, p in groups if any(m in NYC for m in members)) or None
        ii = [idx[m] for m in NYC]
        tot = counts["NYC"] + sum((cnt[i] or 0) for i in ii)
        groups = [g for g in groups if not any(m in NYC for m in g[0])] + [(NYC, nyc_pop)]
        for i in ii:
            cnt[i] = None  # borough counts unknown
        nyc_total = tot
    else:
        nyc_total = None
    for members, p in groups:
        ii = [idx[m] for m in members if m in idx]
        if members is NYC and nyc_total is not None:
            tot = nyc_total
        else:
            tot = sum((cnt[i] or 0) for i in ii)
            for i in ii:
                if cnt[i] is None:
                    cnt[i] = 0
        if not p:
            continue
        if suppress and 0 < tot < 10:
            continue
        r = round(tot / p * 1e5, 1)
        for i in ii:
            rate[i] = r
    if suppress:
        cnt = [(-1 if (c is not None and 0 < c < 10) else c) for c in cnt]
    return cnt, rate


def main(first=1968, last=2004, skip=(), redo=()):
    OUT.mkdir(parents=True, exist_ok=True)
    fips_list = atlas_counties()
    atlas = set(fips_list)
    idx = {f: i for i, f in enumerate(fips_list)}
    groups = seer_population(atlas)
    popyears = sorted(groups)

    def grp(y):
        return groups.get(y) or groups[min(popyears, key=lambda p: abs(p - y))]

    # population per county per year (sum of group pop split for display only where single)
    pop_out = {}
    for y in popyears:
        arr = [None] * len(fips_list)
        for members, p in groups[y]:
            if len(members) == 1:
                arr[idx[members[0]]] = p
        pop_out[str(y)] = arr
    (OUT / "pop.json").write_text(json.dumps({"source": "NCI SEER county population estimates", "pop": pop_out}, separators=(",", ":")))

    report = {}
    if "nber" not in skip:
        log("• NCHS mortality files (NBER) …")
        xw = build_crosswalk()
        acc = {(m, p): {} for m in MEASURES for p in ("res", "occ")}
        coverage = {}
        for y in range(first, last + 1):
            cfile = CACHE / f"nber_counts_{y}.json"
            if cfile.exists() and y not in redo:
                c = json.loads(cfile.read_text())
                out = {tuple(k.split("|")): v for k, v in c["out"].items()}
                matched = c["matched"]
            else:
                out, matched = nber_year(y, atlas, xw)
                cfile.write_text(json.dumps({"out": {"|".join(k): v for k, v in out.items()}, "matched": matched}))
            coverage[y] = round(matched, 3)
            for k, v in out.items():
                acc[k][y] = v
        report["nber_residence_identified"] = coverage
        for (m, p), years in acc.items():
            data = {"count": {}, "rate": {}}
            for y, counts in years.items():
                c, r = rate_arrays(counts, grp(y), fips_list, idx)
                if y >= 1989:  # small counties are not identified in public files: blank, not zero
                    ident = set(acc[("all", p)][y])
                    for i, f in enumerate(fips_list):
                        if f not in ident:
                            c[i] = None
                            r[i] = None
                data["count"][str(y)], data["rate"][str(y)] = c, r
            (OUT / f"nber_{m}_{p}.json").write_text(json.dumps(data, separators=(",", ":")))
        log("  wrote NBER county series")

    if "fars" not in skip:
        log("• NHTSA FARS history …")
        county, points = fars_history(atlas)
        data = {"count": {}, "rate": {}}
        for y, counts in county.items():
            c, r = rate_arrays(counts, grp(y), fips_list, idx, suppress=False)  # FARS publishes every crash
            data["count"][str(y)], data["rate"][str(y)] = c, r
        (OUT / "fars_county.json").write_text(json.dumps(data, separators=(",", ":")))
        pdir = ROOT / "site" / "data" / "points"
        pdir.mkdir(parents=True, exist_ok=True)
        for st, yrs in points.items():
            (pdir / f"fars_{st}.json").write_text(json.dumps({str(y): rows for y, rows in yrs.items()}, separators=(",", ":")))
        report["fars_years"] = [min(county), max(county)]

    if "noaa" not in skip:
        log("• NOAA Storm Events history …")
        county, points = noaa_history(atlas)
        data = {"count": {}, "rate": {}}
        for y, counts in county.items():
            cc = {f: round(v, 1) for f, v in counts.items()}
            c, r = rate_arrays(cc, grp(max(min(y, popyears[-1]), popyears[0])), fips_list, idx, suppress=False)
            data["count"][str(y)], data["rate"][str(y)] = c, r
        (OUT / "noaa_county.json").write_text(json.dumps(data, separators=(",", ":")))
        (ROOT / "site" / "data" / "points" / "noaa.json").write_text(json.dumps({str(y): v for y, v in points.items()}, separators=(",", ":")))
        report["noaa_years"] = [min(county), max(county)]

    prev = json.loads((OUT / "report.json").read_text()) if (OUT / "report.json").exists() else {}
    prev.update(report)
    (OUT / "report.json").write_text(json.dumps(prev, indent=1))
    log("done")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[], help="nber fars noaa")
    ap.add_argument("--first", type=int, default=1968)
    ap.add_argument("--last", type=int, default=2004)
    ap.add_argument("--redo", nargs="*", type=int, default=[], help="years to re-read from the NBER files (others come from .cache)")
    a = ap.parse_args()
    main(a.first, a.last, set(a.skip), set(a.redo))
