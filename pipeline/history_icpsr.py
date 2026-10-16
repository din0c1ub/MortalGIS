#!/usr/bin/env python3
"""MortalGIS county history 1959-1967 (run by hand; not part of the weekly build).

Source: NCHS Multiple Cause of Death public-use files 1959-1967 as distributed by ICPSR (study 20680, Stata package), one record per death.
The ICPSR files are never put in the repo or on the site: ICPSR's terms bar redistribution. Save the Stata package by hand (it needs an ICPSR
sign-in) and point MORTALGIS_ICPSR_DIR at the unzipped ICPSR_20680 folder. This script writes only county sums:
  .cache/icpsr_counts_<year>.json  (same layout as history.py's nber_counts_<year>.json)
  site/data/hist/icpsr_<measure>_<res|occ>.json  (counts and, once county populations are saved, rates; same layout as nber_*.json)
  site/data/hist/icpsr_report.json  (coverage, the code conversion used for 1959-1961, checks)

Years: 1959-1962 and 1964-1967. 1963 is left out: ICPSR's 1963 file holds 508,976 records, about 28% of that year's deaths.

Causes (ICD-7, the Seventh Revision used for US deaths 1958-1967), chosen to match history.py's ICD-8 definitions as closely as the codes allow:
  heart     400-402, 410-443 (NCHS "Diseases of heart")
  stroke    330-334 (vascular lesions affecting the central nervous system)
  suicide   E963, E970-E979
  homicide  E964, E980-E983 (ICD-7 files E984 police intervention and E985 execution under homicide; ICD-8 keeps legal intervention apart,
            and so does this series)
  firearm   E919 (accident), E976 (suicide), E981 (assault); police intervention (E984) is not split by means in ICD-7, so it is left out
  overdose  E870-E878 (accidental poisoning by drugs) and E970 (suicide by analgesic and soporific substances). ICD-7 has no
            "undetermined" category, and suicide by other drugs sits in E971 with non-drug substances, so this undercounts against ICD-8.

Geography:
  1962-1967 use the NCHS county codes of 1968 (checked code by code against the 1968 NBER file), mapped to FIPS with
  history.build_crosswalk("1960s").
  1959-1961 use older two-digit county codes, with two to three state codes for the seven states that have more than 100 counties. They are
  converted to the 1962 codes by aligning each state's sorted code list (see align_1961()): for 49 states the lists have the same length and
  match in order; Wisconsin (Menominee County, 1961) and Virginia (Fairfax and Franklin cities, 1961) have codes only in 1962.
  In ICPSR's 1967 file the columns labelled county of occurrence and county of residence hold residence and occurrence the other way round
  (checked against 1966 and 1968: Hinds County MS, a hospital centre, has more deaths by "residence" than by "occurrence" only in 1967).
  Nonresident aliens are counted where they died (the files give them that county as residence).
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import history as H  # noqa: E402
from build_data import log  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
OUT = ROOT / "site" / "data" / "hist"
ICPSR_DIR = Path(os.environ.get("MORTALGIS_ICPSR_DIR") or CACHE / "ICPSR_20680")
YEARS = {1959: "0001", 1960: "0002", 1961: "0003", 1962: "0004", 1964: "0006", 1965: "0007", 1966: "0008", 1967: "0009"}
MEASURES = H.MEASURES
# 1959-1961: states with more than 100 counties carry two or three state codes (codebook, "State of Occurrence for 1959-61")
SPLIT = {"60": "11", "61": "11", "62": "14", "63": "14", "64": "17", "65": "17", "66": "18", "67": "18", "68": "26", "69": "26",
         "70": "44", "71": "44", "72": "44", "73": "47", "74": "47"}

OLD = {"YEAR": "year", "RESISTAT": "restatus", "STATEOCC": "ost", "CONTYOCC": "octy", "RESIDST": "rst", "CNTYRSID": "rcty", "ICD9": "icd"}
NEW = {"DATAYEAR": "year", "RESTATUS": "restatus", "STATEOC": "ost", "COUNTYOC": "octy", "STATERS": "rst", "COUNTYRS": "rcty", "UCOD": "icd"}


def read_year(y: int) -> pd.DataFrame:
    ds = YEARS[y]
    p = ICPSR_DIR / f"DS{ds}" / f"20680-{ds}-Data.dta"
    if not p.exists():
        raise SystemExit(f"! {p} is missing. Save ICPSR study 20680 (Stata) by hand and set MORTALGIS_ICPSR_DIR to the ICPSR_20680 folder.")
    it = pd.read_stata(p, iterator=True, convert_categoricals=False, chunksize=250_000)
    names = list(it.variable_labels())
    cmap = OLD if "YEAR" in names else NEW
    parts = []
    for df in it:
        df = df[list(cmap)].rename(columns=cmap)
        for c in df.columns:
            df[c] = df[c].astype(str).str.strip()
        parts.append(df)
    d = pd.concat(parts, ignore_index=True)
    if y == 1967:  # columns swapped in ICPSR's 1967 file (see module notes)
        d = d.rename(columns={"octy": "rcty", "rcty": "octy", "ost": "rst", "rst": "ost"})
    return d


def cause_flags_icd7(icd: pd.Series) -> dict:
    c3 = pd.to_numeric(icd.str[:3], errors="coerce")
    inr = lambda lo, hi: (c3 >= lo) & (c3 <= hi)  # noqa: E731
    return {
        "heart": inr(400, 402) | inr(410, 443),
        "stroke": inr(330, 334),
        "suicide": (c3 == 963) | inr(970, 979),
        "homicide": (c3 == 964) | inr(980, 983),
        "firearm": (c3 == 919) | (c3 == 976) | (c3 == 981),
        "overdose": inr(870, 878) | (c3 == 970),
    }


def old_keys(st: pd.Series, cty: pd.Series) -> pd.Series:
    """1959-1961 (state code, 2-digit county) -> 'SS|p-CC' with the state recoded to the 1962 code and p the part of a split state."""
    st = st.str.zfill(2)
    base = st.map(lambda s: SPLIT.get(s, s))
    part = st.map(lambda s: sorted(k for k, v in SPLIT.items() if v == SPLIT[s]).index(s) if s in SPLIT else 0)
    return base + "|" + part.astype(str) + "-" + cty.str.zfill(2)


def new_keys(st: pd.Series, cty: pd.Series) -> pd.Series:
    """NCHS 'SSCCC'. The 1967 file already carries state and county in one five-digit field."""
    return (st.str.zfill(2) + cty.str.zfill(3)).where(cty.str.len() < 4, cty.str.zfill(5))


def _align(a: list, b: list, ca: dict, cb: dict, gap=2.5) -> dict:
    """Monotone alignment of sorted code lists a (1961) and b (1962), scored on log-ratios of residence and occurrence counts."""
    def sim(x, y):
        (r1, o1), (r2, o2) = ca.get(x, (0, 0)), cb.get(y, (0, 0))
        return -abs(math.log((r1 + 1) / (r2 + 1))) - abs(math.log((o1 + 1) / (o2 + 1)))
    n, m = len(a), len(b)
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    T = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        S[i][0], T[i][0] = -gap * i, 1
    for j in range(1, m + 1):
        S[0][j], T[0][j] = -gap * j, 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opts = [(S[i - 1][j - 1] + sim(a[i - 1], b[j - 1]), 0), (S[i - 1][j] - gap, 1), (S[i][j - 1] - gap, 2)]
            S[i][j], T[i][j] = max(opts)
    i, j, out = n, m, {}
    while i > 0 or j > 0:
        t = T[i][j]
        if t == 0:
            out[a[i - 1]] = b[j - 1]
            i, j = i - 1, j - 1
        elif t == 1:
            i -= 1
        else:
            j -= 1
    return out


def align_1961(d61: pd.DataFrame, d62: pd.DataFrame) -> tuple[dict, dict]:
    """Conversion table from 1959-1961 keys to 1962 NCHS codes, and a per-state report."""
    r61, o61 = old_keys(d61.rst, d61.rcty).value_counts(), old_keys(d61.ost, d61.octy).value_counts()
    r62, o62 = new_keys(d62.rst, d62.rcty).value_counts(), new_keys(d62.ost, d62.octy).value_counts()
    ca = {k: (int(r61.get(k, 0)), int(o61.get(k, 0))) for k in set(r61.index) | set(o61.index)}
    cb = {k: (int(r62.get(k, 0)), int(o62.get(k, 0))) for k in set(r62.index) | set(o62.index)}
    table, report = {}, {}
    for st in sorted({k[:2] for k in cb}):
        a = sorted(k for k in ca if k[:2] == st)
        b = sorted(k for k in cb if k[:2] == st)
        dp = _align(a, b, ca, cb)
        rank = dict(zip(a, b)) if len(a) == len(b) else None
        table.update(dp)
        report[st] = {"codes_1961": len(a), "codes_1962": len(b), "matched": len(dp), "same_as_rank_order": rank == dp if rank else None,
                      "only_1962": [k for k in b if k not in set(dp.values())], "only_1961": [k for k in a if k not in dp]}
    return table, report


def count_year(d: pd.DataFrame, y: int, atlas: set, xw: dict, conv: dict | None):
    if conv is not None:
        rk, ok = old_keys(d.rst, d.rcty).map(conv), old_keys(d.ost, d.octy).map(conv)
    else:
        rk, ok = new_keys(d.rst, d.rcty), new_keys(d.ost, d.octy)
    rf, of = rk.map(xw), ok.map(xw)
    lut = {u: H.norm(u, atlas) for u in set(rf.dropna()) | set(of.dropna())}
    rf, of = rf.map(lut), of.map(lut)
    flags = cause_flags_icd7(d.icd.fillna(""))
    flags["all"] = pd.Series(True, index=d.index)
    out = {(m, p): defaultdict(int) for m in MEASURES for p in ("res", "occ")}
    for m in MEASURES:
        f = flags[m].fillna(False)
        for k, v in rf[f].value_counts().items():
            out[(m, "res")][k] += int(v)
        for k, v in of[f].value_counts().items():
            out[(m, "occ")][k] += int(v)
    matched = float(rf.notna().mean())
    unmatched = rk[rf.isna()].value_counts().head(12).to_dict()
    totals = {m: int(flags[m].fillna(False).sum()) for m in MEASURES}
    log(f"  {y}: {len(d):,} deaths; residence county placed for {matched:.2%}")
    return {k: dict(v) for k, v in out.items()}, matched, unmatched, totals


# Cells the source itself codes wrongly, left blank rather than shown. 1966-1967: about 2,100 deaths a year of Baltimore County residents
# are coded to Baltimore city (residence: county 2,217 and 2,355 against 4,344 in 1965 and 4,420 in 1968; the city rises by the same amount).
SOURCE_ISSUES = {("res", 1966): ["24005", "24510"], ("res", 1967): ["24005", "24510"]}
POP_FILE = ROOT / "data_manual" / "hist" / "census_county_population_1960_1970.json"


def population_groups(y: int, fips_list: list, atlas: set):
    """[(members, population)] for year y from the 1960 and 1970 censuses (straight line between the two April counts, at July 1 of y), or
    None while data_manual/hist/census_county_population_1960_1970.json is missing (counts only, no rates)."""
    if not POP_FILE.exists():
        return None
    P = json.loads(POP_FILE.read_text())
    t = (y + 0.5 - 1960.25) / 10.0
    out = []
    for g in P["groups"]:  # each: {"members": [fips...], "p1960": n, "p1970": n}
        members = [m for m in g["members"] if m in atlas]
        if members and g.get("p1960") and g.get("p1970"):
            out.append((members, round(g["p1960"] + (g["p1970"] - g["p1960"]) * t)))
    return out


def write_site(years=None):
    """site/data/hist/icpsr_<measure>_<res|occ>.json from the cached county sums. Counts of 1-9 are hidden (-1) as in history.py."""
    fips_list = H.atlas_counties()
    atlas = set(fips_list)
    idx = {f: i for i, f in enumerate(fips_list)}
    years = years or sorted(YEARS)
    caches = {y: json.loads((CACHE / f"icpsr_counts_{y}.json").read_text())["out"] for y in years}
    rates = False
    for m in MEASURES:
        for p in ("res", "occ"):
            data = {"count": {}, "rate": {}}
            for y in years:
                counts = caches[y].get(f"{m}|{p}", {})
                groups = population_groups(y, fips_list, atlas)
                rates = rates or groups is not None
                c, r = H.rate_arrays(counts, groups or [([f], 0) for f in fips_list], fips_list, idx)
                H.blank_early(c, r, y, fips_list, idx)
                for f in SOURCE_ISSUES.get((p, y), []):
                    if f in idx:
                        c[idx[f]] = r[idx[f]] = None
                data["count"][str(y)], data["rate"][str(y)] = c, r
            (OUT / f"icpsr_{m}_{p}.json").write_text(json.dumps(data, separators=(",", ":")))
    log(f"  wrote site/data/hist/icpsr_*.json ({'with' if rates else 'without'} rates)")


def main(years=None):
    fips_list = H.atlas_counties()
    atlas = set(fips_list)
    xw = H.build_crosswalk("1960s")
    years = years or sorted(YEARS)
    report = {"years": years, "left_out": {"1963": "ICPSR file holds 508,976 records (about 28% of the year's deaths)"}}
    conv = None
    if any(y <= 1961 for y in years):
        log("• converting 1959-1961 county codes to the 1962 codes …")
        d61, d62 = read_year(1961), read_year(1962)
        conv, rep = align_1961(d61, d62)
        report["conversion_1961_to_1962"] = rep
        (CACHE / "icpsr_conv_1959-1961.json").write_text(json.dumps(conv, indent=0))
        del d61, d62
    coverage, unmatched, totals = {}, {}, {}
    for y in years:
        cfile = CACHE / f"icpsr_counts_{y}.json"
        d = read_year(y)
        out, matched, um, tot = count_year(d, y, atlas, xw, conv if y <= 1961 else None)
        cfile.write_text(json.dumps({"out": {"|".join(k): v for k, v in out.items()}, "matched": matched}))
        coverage[y], unmatched[y], totals[y] = round(matched, 4), um, tot
    report.update({"residence_placed": coverage, "unplaced_codes_top": unmatched, "national_totals": totals})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icpsr_report.json").write_text(json.dumps(report, indent=1))
    write_site(years)
    log("done")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--site-only", action="store_true", help="only rewrite the site files from the cached county sums")
    a = ap.parse_args()
    write_site(a.years) if a.site_only else main(a.years)
