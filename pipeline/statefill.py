"""County death counts that states publish themselves without hiding 1-9.

CDC hides county counts of 1-9. Some state health departments publish the same counts in full. build_data uses
them ONLY to fill cells CDC hid (count -1), and only for causes whose state definition matches CDC's: before
filling, it checks the state numbers against every county-year CDC does publish (10+) and skips the cause if they
disagree. Filled cells are flagged so the map and tooltips say where the number came from.

Sources
- Michigan DHHS Division for Vital Records & Health Statistics, county-of-residence tables 2000- (HTML).
"""
from __future__ import annotations

import html
import json
import unicodedata
import re

from build_data import get, log

def norm(name: str) -> str:
    """County name key: lowercase, no accents or periods, 'Saint' -> 'st' (Doña Ana -> dona ana)."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace(".", "").strip()
    return n.replace("saint ", "st ")


MI_BASE = "https://www.mdch.state.mi.us/osr/deaths/{}.asp"
# MortalGIS cause -> MDHHS table. Drug-induced and diabetes-related are NOT used: wider definitions than CDC's.
MI_TABLES = {"all": "DeathNoTrends", "alcohol": "AlcoholNoTrends", "alzheimers": "AlzheimersNoTrends", "cancer": "CancerNoTrends",
             "clrd": "COPDNoTrends", "heart": "HeartDiseaseNoTrends", "stroke": "StrokeNoTrends"}


def _cells(page: str):
    """Rows of the county x year table as lists of cell texts."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
        if cells:
            rows.append(cells)
    return rows


def michigan(name_to_fips: dict):
    """{cause: {year: {fips: count}}} for Michigan counties. name_to_fips: lowercased county name -> FIPS."""
    out = {}
    for cause, table in MI_TABLES.items():
        try:
            page = get(MI_BASE.format(table)).decode("latin-1")
        except Exception as e:  # noqa: BLE001
            log(f"  ! Michigan {cause}: {e}")
            continue
        rows = _cells(page)
        head = next((r for r in rows if r and r[0] == "County" and any(c.isdigit() for c in r)), None)
        if not head:
            log(f"  ! Michigan {cause}: table header not found")
            continue
        years = [c if c.isdigit() else None for c in head]
        got = {}
        for r in rows:
            f = name_to_fips.get(norm(r[0]))
            if not f:
                continue
            for y, v in zip(years, r):
                if not y:
                    continue
                v = v.replace(",", "")
                n = 0 if v in ("-", "") else (int(v) if v.isdigit() else None)
                if n is not None:
                    got.setdefault(y, {})[f] = n
        if got:
            out[cause] = got
            log(f"  Michigan DHHS {cause}: {len(got)} years × {max(len(v) for v in got.values())} counties")
    return out


NY_URL = "https://healthweb-back.health.ny.gov/statistics/vital_statistics/{}/table38.htm"
NY_COLS = [("heart", "heart"), ("malignant", "cancer"), ("cerebro", "stroke"), ("diabetes", "diabetes"), ("cirrhosis", "liver"),
           ("clrd", "clrd"), ("covid", "covid"), ("homicide", "homicide"), ("suicide", "suicide")]


def new_york(name_to_fips: dict, first=2001, last=None):
    """NYS DOH vital statistics Table 38: deaths by selected causes by county of residence, one page per year.
    Column order changes between years, so columns are matched by name. 'Alcohol poisoning' and 'Pneumonia' are
    not used (narrower than CDC's alcohol-induced and flu & pneumonia)."""
    import datetime as dt
    out = {}
    for y in range(first, (last or dt.date.today().year) + 1):
        try:
            page = get(NY_URL.format(y), retries=1).decode("latin-1")
        except Exception:  # noqa: BLE001  (future years 404)
            continue
        rows = _cells(page)
        head = next((r for r in rows if any("heart" in c.lower() for c in r)), None)
        if not head:
            continue
        names = head[1:] if head[0].lower() == "county" else head
        colmap = {}  # position counted from the RIGHT end of each data row (some years have an unlabeled Total column)
        for k, h in enumerate(names):
            hl = re.sub(r"\s+", " ", h.lower())
            back = len(names) - k
            if hl.startswith("total") and "accident" not in hl and "injur" not in hl:
                colmap[back] = "all"
            for key, cause in NY_COLS:
                if key in hl:
                    colmap[back] = cause
        for r in rows:
            f = name_to_fips.get(norm(r[0]))
            if not f or len(r) - 1 < len(names):
                continue
            for back, cause in colmap.items():
                v = r[len(r) - back].replace(",", "")
                if v.isdigit():
                    out.setdefault(cause, {}).setdefault(str(y), {})[f] = int(v)
    for cause, years in out.items():
        log(f"  New York DOH {cause}: {len(years)} years")
    return out


STATES_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "data_manual" / "states"


def from_bundles(prefix: str, name_to_fips: dict):
    """State query exports saved by the Chrome scripts: data_manual/states/<prefix>*.json,
    {"data": {cause: {year: {county name: count (-1 = suppressed)}}}}. Used for portals without an API
    (New Mexico IBIS)."""
    out = {}
    for p in sorted(STATES_DIR.glob(f"{prefix}*.json")):
        b = json.loads(p.read_text())
        for cause, years in (b.get("data") or {}).items():
            for y, cells in years.items():
                for name, v in cells.items():
                    f = name_to_fips.get(norm(name))
                    if f and isinstance(v, int) and v >= 0:
                        out.setdefault(cause, {}).setdefault(str(y), {})[f] = v
        log(f"  {p.name}: {', '.join(sorted(b.get('data') or {}))}")
    return out


# ---------------------------------------------------------------- ledger-gated fills
# master/ledger.csv decides which sources may fill CDC-hidden cells. A row is usable only when its status is approved or released.
# Nothing here is a second agreement gate: build_data.py still checks every source against CDC's published counts before it fills a cell.
import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = Path(os.environ.get("MORTALGIS_LEDGER") or ROOT / "master" / "ledger.csv")
BUNDLE_DIR = Path(os.environ.get("MORTALGIS_BUNDLES") or STATES_DIR)
APPROVED = {"approved", "released"}
STATUSES = {"staged", "approved", "released", "held", "rejected", "candidate", "blocked", "parked"}
LEDGER_NEEDS = {"source_id", "bundle", "measure", "place", "status", "verdict"}

# Sources the build has always read itself (the ledger rows are source_id / bundle "live").
LIVE_SOURCE = {"MI": "mi_mdhhs", "NY": "ny_vitals", "NM": "nm_ibis", "PA": "pa_eddie"}

# Staged bundles: (registry source id, ledger bundle, files in the bundle folder (later file wins on a repeated cell), state FIPS, state letters).
STAGED = [(("mi_injury_county_2000-2024.json",), "mi_fatal_injuries", "mi_injury", "26", "MI"),
          (("nc_vital_stats_county_2019-2023.json",), "nc_schs_lcd", "nc_lcd", "37", "NC"),
          (("il_causes_county_2008-2023.json",), "il_idph_causes", "il_causes", "17", "IL"),
          (("il_injury_county_2010-2023.json",), "il_idph_injury", "il_injury", "17", "IL"),
          (("il_overdose_county_2020-2023.json",), "il_idph_overdose", "il_overdose", "17", "IL"),
          (("in_mortality_county_2000-2002.json", "in_mortality_county_2000-2017.json"), "in_isdh_mortality", "in_table5", "18", "IN"),
          (("in_injury_county_2000-2002.json", "in_injury_county_2000-2017.json"), "in_isdh_mortality", "in_table9", "18", "IN"),
          (("tn_county_2009-2022.json",), "tn_health_county", "tn_county", "47", "TN"),
          (("wi_wish_county_1999-2024.json",), "wi_wish", "wi_wish", "55", "WI"),
          (("mo_mica_county_1999-2024.json",), "mo_mica", "mo_mica", "29", "MO"),
          (("al_113causes_county_2015-2024.json",), "al_dph", "al_113causes", "01", "AL"),
          (("fl_charts_county_1970-2024.json",), "fl_charts", "fl_charts", "12", "FL"),
          (("ga_oasis_county_1999-2024.json",), "ga_oasis", "ga_oasis", "13", "GA"),
          (("md_vsa_county_1999-2024.json",), "md_vsa", "md_vsa", "24", "MD"),
          (("ms_mstahrs_county_1999-2024.json",), "ms_mstahrs", "ms_mstahrs", "28", "MS"),
          (("sc_scan_county_1999-2024.json",), "sc_scan", "sc_scan", "45", "SC"),
          (("ok_ok2share_county_2010-2024.json",), "ok_ok2share", "ok_ok2share", "40", "OK"),
          (("co_cdphe_county_2025.json",), "co_cdphe", "co_cdphe", "08", "CO"),
          (("nj_shad_county_2000-2024.json",), "nj_shad", "nj_shad", "34", "NJ"),
          (("mn_mdh_county_2021-2024.json",), "mn_mdh_county", "mn_mdh_county", "27", "MN"),
          (("wv_hsc_vital_1999-2006.json",), "wv_hsc_vital", "wv_hsc_vital", "54", "WV"),
          (("va_vdh_profiles_1997-2013.json",), "va_vdh_profiles", "va_vdh_profiles", "51", "VA"),
          (("va_ocme_annual_county_2014-2023.json",), "va_ocme_annual", "va_ocme_annual", "51", "VA"),
          (("wv_hsc_vital_2016-2020.json",), "wv_hsc_vital", "wv_hsc_recent", "54", "WV"),
          (("vt_vdh_annual_2009-2024.json",), "vt_vdh_annual", "vt_vdh_annual", "50", "VT"),
          (("vt_vdh_early_county_2000-2005.json",), "vt_vdh_annual", "vt_vdh_early", "50", "VT"),
          (("ma_deaths_report_county_2020-2022.json",), "ma_deaths_report", "ma_deaths_report", "25", "MA"),
          (("ne_dhhs_vital_report_county_2008-2016.json",), "ne_dhhs_vital_report", "ne_dhhs_vital_report", "31", "NE"),
          (("ne_dhhs_vital_early_county_2005-2007.json",), "ne_dhhs_vital_report", "ne_dhhs_vital_early", "31", "NE"),
          (("ks_kdhe_d25_county_2016.json",), "ks_kdhe_d25", "ks_kdhe_d25", "20", "KS"),
          (("ks_kdhe_annual_county_2001-2024.json",), "ks_kdhe_annual", "ks_kdhe_annual", "20", "KS")]
# The publisher's cause label -> the map's measure key. Causes not listed here (accidents, motor vehicle ...) have no map measure.
MEASURE = {"falls": "falls", "homicide": "homicide", "suicide": "suicide", "cancer": "cancer", "heart": "heart", "stroke": "stroke",
           "alzheimers": "alzheimers", "diabetes": "diabetes", "liver": "liver", "clrd": "clrd", "flu": "flu_pneumonia", "flu_pneumonia": "flu_pneumonia", "kidney": "kidney",
           "covid": "covid", "all": "all_deaths", "firearm": "firearm", "overdose": "overdose", "alcohol": "alcohol"}
# How the map names the source on a filled cell (site/app.html FILLSRC is keyed by state FIPS).
LABEL = {"MI": "Michigan DHHS", "NY": "New York State DOH", "NM": "New Mexico DOH", "PA": "Pennsylvania DOH", "IL": "Illinois DPH",
         "IN": "Indiana Department of Health", "MO": "Missouri DHSS", "NC": "North Carolina SCHS", "TN": "Tennessee Department of Health",
         "WI": "Wisconsin DHS", "AL": "Alabama DPH", "FL": "Florida DOH", "GA": "Georgia DPH", "MD": "Maryland VSA", "MS": "Mississippi MSDH",
         "SC": "South Carolina DPH", "OK": "Oklahoma State Department of Health", "CO": "Colorado CDPHE", "NJ": "New Jersey DOH (NJSHAD)", "MN": "Minnesota Department of Health", "WV": "West Virginia Health Statistics Center", "VA": "Virginia Department of Health", "VT": "Vermont Department of Health", "MA": "Massachusetts Department of Public Health", "NE": "Nebraska DHHS", "KS": "Kansas Department of Health and Environment"}


def read_ledger(path=None) -> dict:
    """{(source_id, bundle, measure, place): row} from master/ledger.csv. A missing or malformed ledger stops the build:
    with no ledger every fill would silently disappear from the map."""
    p = Path(path or LEDGER_PATH)
    if not p.exists():
        raise SystemExit(f"! ledger not found: {p}. Fills are gated by it; commit master/ledger.csv or set MORTALGIS_LEDGER.")
    rows = {}
    with p.open(newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        missing = LEDGER_NEEDS - set(rd.fieldnames or [])
        if missing:
            raise SystemExit(f"! ledger {p} lacks columns: {sorted(missing)}")
        for r in rd:
            k = (r["source_id"], r["bundle"], r["measure"], r["place"])
            if k in rows:
                raise SystemExit(f"! ledger {p}: duplicate row {k}")
            if r["status"] not in STATUSES:
                raise SystemExit(f"! ledger {p}: unknown status {r['status']!r} on {k}")
            rows[k] = r
    return rows


def allowed(ledger: dict, source_id: str, bundle: str, measure: str, need_verdict: bool = False):
    """(True, '') when the ledger row is approved or released, else (False, why). need_verdict also requires the agreement
    verdict the ledger last recorded to be USE (staged bundles; the live sources keep the build's own gate only)."""
    r = ledger.get((source_id, bundle, measure, "residence"))
    if r is None:
        return False, "no ledger row"
    if r["status"] not in APPROVED:
        return False, f"ledger status is {r['status']}"
    if need_verdict and r["verdict"] != "USE":
        return False, f"ledger verdict is {r['verdict']} (run master.py ledger to refresh it)"
    return True, ""


def staged(counties: list, ledger: dict, bundle_dir=None):
    """Approved staged bundles, shaped like the other fill sources.
    Returns ({'IL/il_causes': {cause: {year: {fips: count}}}}, {'IL/il_causes': 'Illinois DPH'}, [notes]).
    Only single-year exact counts are returned. 5-year totals and 1-4 bands are not wired into the map yet; approved rows
    that carry them are noted, not used."""
    d = Path(bundle_dir or BUNDLE_DIR)
    by_state = {}
    for c in counties:
        by_state.setdefault(c["fips"][:2], {})[norm(c["name"])] = c["fips"]
    out, labels, notes = {}, {}, []
    for files, sid, bundle, st, ab in STAGED:
        approved = {m for (s, b, m, pl), r in ledger.items() if s == sid and b == bundle and pl == "residence" and r["status"] in APPROVED}
        if f"{bundle}_5yr" in {b for (s, b, m, pl), r in ledger.items() if s == sid and r["status"] in APPROVED}:
            notes.append(f"{sid}/{bundle}_5yr approved but 5-year totals are not wired into the map yet; ignored")
        if not approved:
            continue
        paths = [d / fn for fn in files]
        gone = [p.name for p in paths if not p.exists()]
        if gone:
            raise SystemExit(f"! ledger approves {sid}/{bundle} but its bundle file is missing in {d}: {gone}")
        n2f = dict(by_state.get(st, {}))
        cells = {}  # bundle cause -> year -> county name -> count
        for p in paths:
            b = json.loads(p.read_text())
            if b.get("state") != st:
                raise SystemExit(f"! {p.name}: bundle says state {b.get('state')}, ledger bundle {bundle} expects {st}")
            for k, v in (b.get("fips_alias") or {}).items():
                n2f[norm(k)] = v
            for cause, years in (b.get("data") or {}).items():
                for y, cs in years.items():
                    cells.setdefault(cause, {}).setdefault(str(y), {}).update(cs)
        key = f"{ab}/{bundle}"
        for cause, years in sorted(cells.items()):
            measure = MEASURE.get(cause)
            if not measure:
                continue
            if measure not in approved:
                continue
            ok, why = allowed(ledger, sid, bundle, measure, need_verdict=True)
            if not ok:
                notes.append(f"{sid}/{bundle}/{measure}: not used ({why})")
                continue
            build_cause = "all" if measure == "all_deaths" else measure
            for y, cs in years.items():
                for name, n in cs.items():
                    f = n2f.get(norm(name))
                    if f and isinstance(n, int) and n >= 0:
                        out.setdefault(key, {}).setdefault(build_cause, {}).setdefault(y, {})[f] = n
            labels[key] = LABEL[ab]
        for m in sorted(approved - {MEASURE.get(c) for c in cells}):
            notes.append(f"{sid}/{bundle}/{m}: approved but the bundle has no such cause")
    return out, labels, notes


def staged_bands(counties: list, ledger: dict, bundle_dir=None):
    """1-4 bands for cells CDC hides. Four staged sources (WISH, MICA, MSTAHRS, SCAN) do not give the count of a small cell but say it is
    1-4 ("masked" = WISH/MSTAHRS/SCAN 'X', "narrow_1_4" = MICA tables where every x is a trigger cell). build_data shows such a cell, and only
    one CDC hides, as a band in the tooltip ("1-4 deaths (state band)") under the same gate as the exact fills: an approved ledger row with
    verdict USE for that measure, and the cause/year passing the CDC agreement test. A band is never turned into a number or a rate.
    Returns ({'WI/wi_wish': {cause: {year: {fips, ...}}}}, [notes]); a cell the bundle also gives exactly is not a band."""
    d = Path(bundle_dir or BUNDLE_DIR)
    by_state = {}
    for c in counties:
        by_state.setdefault(c["fips"][:2], {})[norm(c["name"])] = c["fips"]
    out, notes = {}, []
    for files, sid, bundle, st, ab in STAGED:
        approved = {m for (s, b, m, pl), r in ledger.items() if s == sid and b == bundle and pl == "residence" and r["status"] in APPROVED}
        if not approved:
            continue
        paths = [d / fn for fn in files]
        gone = [p.name for p in paths if not p.exists()]
        if gone:
            raise SystemExit(f"! ledger approves {sid}/{bundle} but its bundle file is missing in {d}: {gone}")
        n2f = dict(by_state.get(st, {}))
        bands, exact = {}, {}
        for p in paths:
            b = json.loads(p.read_text())
            if b.get("state") != st:
                raise SystemExit(f"! {p.name}: bundle says state {b.get('state')}, ledger bundle {bundle} expects {st}")
            for k, v in (b.get("fips_alias") or {}).items():
                n2f[norm(k)] = v
            for cause, years in (b.get("data") or {}).items():
                for y, cs in years.items():
                    exact.setdefault(cause, {}).setdefault(str(y), set()).update(norm(n) for n, v in cs.items() if v is not None)
            for field in ("masked", "narrow_1_4"):
                for cause, years in (b.get(field) or {}).items():
                    for y, names in years.items():
                        bands.setdefault(cause, {}).setdefault(str(y), set()).update(str(n) for n in names)
        for cause, years in sorted(bands.items()):
            measure = MEASURE.get(cause)
            if not measure or measure not in approved:
                continue
            ok, why = allowed(ledger, sid, bundle, measure, need_verdict=True)
            if not ok:
                notes.append(f"{sid}/{bundle}/{measure}: bands not used ({why})")
                continue
            build_cause = "all" if measure == "all_deaths" else measure
            for y, names in years.items():
                for name in names:
                    f = n2f.get(norm(name))
                    if f and norm(name) not in exact.get(cause, {}).get(y, set()):
                        out.setdefault(f"{ab}/{bundle}", {}).setdefault(build_cause, {}).setdefault(y, set()).add(f)
    return out, notes


def band_hits(counts: dict, bands: dict, bad_years, idx: dict):
    """Cells to mark as a 1-4 band: {year: sorted county indexes}. Only cells whose published count is still hidden (-1) after the exact
    fills, in years not skipped by the CDC agreement test. counts: {year: [count per county]}; bands: {year: {fips}}; idx: fips -> index."""
    out = {}
    for y, fs in (bands or {}).items():
        cnt = counts.get(y)
        if not cnt or y in bad_years:
            continue
        hit = sorted(idx[f] for f in fs if f in idx and cnt[idx[f]] == -1)
        if hit:
            out[y] = hit
    return out


def merge_bands(into: dict, hits: dict):
    """Add one source's band cells ({year: [county index]}) to a measure's `band` dict. Several states share a measure and a year, so cells are
    merged, never replaced."""
    for y, h in hits.items():
        into[y] = sorted(set(into.get(y, [])) | set(h))
    return into


# ---------------------------------------------------------------- exact 1-9 counts from the NCHS files themselves
# The 1968-2004 county series are built from NCHS public-use death certificate files (via NBER), which carry every death. pipeline/history.py
# hides counts of 1-9, so the cells it hides are cells the file can fill exactly. Owner decision 2026-10-10 ("build it and approve now"): show
# them unless a source forbids it. NCHS's data use agreement sets no minimum cell size; CDC WONDER advises against publishing counts of 9 or
# fewer for sub-national areas, so the ledger rows carry the warning wonder_9_or_fewer and terms stated_review.
# Used only in years the map itself takes from these files (series src nber / nber_partial). Years the map takes from CDC (WONDER, 1999-) keep CDC's suppression.
NBER_SMALL = ("nber_small", "nber_small")  # (ledger source_id, ledger bundle)
NBER_SMALL_FILE = Path(os.environ.get("MORTALGIS_NBER_SMALL") or ROOT / "data_manual" / "nber_exact_small_1968-2004.json")
NBER_SMALL_LABEL = "NCHS death-certificate files (via NBER)"
NBER_PLACE = {"res": "residence", "occ": "occurrence"}


def nber_small(ledger: dict, path=None):
    """Approved exact 1-9 cells: ({(cause, 'res'|'occ'): {year: {fips: n}}}, notes). A (cause, place) is returned only when its ledger row
    (nber_small / nber_small / <measure> / residence|occurrence) is approved or released. File: {data: {cause: {res|occ: {year: {fips: n}}}}}."""
    p = Path(path or NBER_SMALL_FILE)
    rows = {(m, pl): r for (s, b, m, pl), r in ledger.items() if (s, b) == NBER_SMALL}
    approved = {k for k, r in rows.items() if r["status"] in APPROVED}
    if not approved:
        return {}, []
    if not p.exists():
        raise SystemExit(f"! ledger approves {NBER_SMALL[0]} but its file is missing: {p}")
    data = json.loads(p.read_text()).get("data") or {}
    out, notes = {}, []
    for cause, places in sorted(data.items()):
        measure = MEASURE.get(cause)
        for pl, years in sorted(places.items()):
            if (measure, NBER_PLACE.get(pl)) not in approved:
                continue
            for y, cells in years.items():
                for f, n in cells.items():
                    if isinstance(n, int) and 1 <= n <= 9:
                        out.setdefault((cause, pl), {}).setdefault(str(y), {})[f] = n
    for k in sorted(approved):
        if not any(MEASURE.get(c) == k[0] and NBER_PLACE.get(pl) == k[1] for (c, pl) in out):
            notes.append(f"{NBER_SMALL[0]}/{k[0]}/{k[1]}: approved but the file has no such cells")
    return out, notes
