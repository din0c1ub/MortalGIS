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
