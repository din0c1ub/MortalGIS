#!/usr/bin/env python3
"""MortalGIS v2 data pipeline.

Downloads county-level mortality data from official public sources, validates it,
and writes compact static JSON files for the map in site/data/.

Every number in the output comes straight from a source table. Nothing is
invented, jittered or imputed. Values the source suppresses stay null/flagged.

Usage:  python pipeline/build_data.py            (writes to site/data)
        python pipeline/build_data.py --out DIR
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOCRATA = "https://data.cdc.gov/resource/{id}.json"
UA = {"User-Agent": "MortalGIS-pipeline/2.0 (+https://huggingface.co/spaces/dinoclub/mortal-gis)"}
COUNTIES_TOPO = "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"
CHR_URL = "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data{year}.csv"

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- helpers
def get(url: str, retries: int = 4, timeout: int = 120) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def socrata(dataset: str, where: str | None = None, select: str | None = None, page: int = 50000):
    """Yield every row of a Socrata dataset, paging until exhausted."""
    offset = 0
    while True:
        q = {"$limit": page, "$offset": offset, "$order": ":id"}
        if where:
            q["$where"] = where
        if select:
            q["$select"] = select
        rows = json.loads(get(SOCRATA.format(id=dataset) + "?" + urllib.parse.urlencode(q)))
        yield from rows
        if len(rows) < page:
            return
        offset += page


def num(x):
    if x in (None, "", "NA"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def r1(x):
    return None if x is None else round(x, 1)


def fips5(x) -> str:
    return str(int(float(x))).zfill(5)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- sources
def load_counties():
    """County list from the us-atlas TopoJSON (2017 Census cartographic boundaries,
    the same county set CDC NVSS uses: pre-2022 Connecticut counties, 02261)."""
    topo = json.loads(get(COUNTIES_TOPO))
    geoms = topo["objects"]["counties"]["geometries"]
    states = {g["id"]: g["properties"]["name"] for g in topo["objects"]["states"]["geometries"]}
    counties = sorted(
        ({"fips": g["id"], "name": g["properties"]["name"], "state": states.get(g["id"][:2], "")}
         for g in geoms if not g["id"].startswith("72")),  # Puerto Rico: not in these CDC/CHR tables
        key=lambda c: c["fips"],
    )
    return topo, counties


def cdc_injury():
    """CDC 'Mapping Injury, Overdose, and Violence - County' (psx4-wq38).
    Yearly 2019-2024 + trailing twelve months. Crude rate per 100k by county of residence.
    Counts 1-9 are suppressed by CDC; for those the rate is CDC's Bayesian modeled estimate."""
    log("• CDC psx4-wq38 injury/overdose/violence …")
    out = defaultdict(lambda: defaultdict(dict))  # intent -> period -> fips -> rec
    ttm_range = None
    as_of = None
    n = 0
    for r in socrata("psx4-wq38"):
        n += 1
        f = r["geoid"].zfill(5)
        c = r.get("count_sup")
        if c in (None, ""):
            count = None
        elif c == "1-9":
            count = -1  # CDC suppressed
        else:
            try:
                count = int(float(c))
            except ValueError:
                count = c  # a range such as "10-50" (CDC complementary suppression)
        out[r["intent"]][r["period"]][f] = {
            "rate": r1(num(r.get("rate"))),
            "count": count,
            "modeled": r.get("rate_m") in ("1", "1.0", "1.000000000000000"),
            "ci": r.get("rate_m_ci"),
        }
        if r["period"] == "TTM" and r.get("ttm_date_range"):
            ttm_range = r["ttm_date_range"]
        as_of = r.get("data_as_of", as_of)
    log(f"  {n:,} rows; TTM = {ttm_range}")
    return out, ttm_range, (as_of or "")[:10]


def cdc_drug_poisoning_modeled():
    """NCHS Drug Poisoning Mortality by County (rpvx-m2md), 2003-2021.
    Model-based age-adjusted death rate per 100k (no suppression)."""
    log("• NCHS rpvx-m2md modeled drug poisoning 2003-2021 …")
    out = defaultdict(dict)
    for r in socrata("rpvx-m2md", select="fips,year,model_based_death_rate,population"):
        out[r["year"]][fips5(r["fips"])] = {"rate": r1(num(r.get("model_based_death_rate"))), "pop": num(r.get("population"))}
    log(f"  years {min(out)}–{max(out)}")
    return out


def cdc_monthly_overdose():
    """VSRR Provisional County-Level Drug Overdose Death Counts (gb4e-yj24).
    12-month-ending provisional counts by month, 2020-present. Counts 1-9 suppressed (null)."""
    log("• NCHS gb4e-yj24 monthly provisional overdose …")
    series = defaultdict(dict)  # fips -> 'YYYY-MM' -> count
    months = set()
    as_of = ""
    for r in socrata("gb4e-yj24", select="fips,year,month,provisional_drug_overdose,data_as_of"):
        key = f"{int(r['year']):04d}-{int(r['month']):02d}"
        months.add(key)
        v = r.get("provisional_drug_overdose")
        series[fips5(r["fips"])][key] = int(float(v)) if v not in (None, "") else None
        as_of = max(as_of, r.get("data_as_of", "")[:10])
    months = sorted(months)
    log(f"  {len(series):,} counties, {months[0]} → {months[-1]}")
    return series, months, as_of


def cdc_cardio(dataset: str, label: str):
    """CDC Interactive Atlas of Heart Disease & Stroke: county, adults 35+,
    age-adjusted, spatially smoothed 3-year average rate per 100k."""
    log(f"• CDC {dataset} {label} …")
    out = {}
    year = None
    for r in socrata(
        dataset,
        where="geographiclevel='County' AND stratification1='Overall' AND stratification2='Overall'",
        select="locationid,data_value,year",
    ):
        out[r["locationid"].zfill(5)] = r1(num(r.get("data_value")))
        year = r.get("year", year)
    log(f"  {len(out):,} counties ({year})")
    return out, year


def chr_measures(year: int):
    """County Health Rankings & Roadmaps analytic data. One snapshot; each measure
    pools several data years (see CHR documentation)."""
    log(f"• County Health Rankings {year} …")
    raw = get(CHR_URL.format(year=year)).decode("latin-1")
    rows = list(csv.reader(io.StringIO(raw)))
    head, codes, data = rows[0], rows[1], rows[2:]
    ix = {c: i for i, c in enumerate(codes)}
    want = {
        "life_expectancy": "v147",
        "premature_aamr": "v127",
        "ypll": "v001",
        "injury": "v135",
        "motor_vehicle": "v039",
        "child_mortality": "v128",
        "infant_mortality": "v129",
        "population": "v051",
    }
    out = {k: {} for k in want}
    years = {}
    for k, code in want.items():
        yi = ix.get(f"{code}_cihigh")  # just to confirm presence
        vi = ix[f"{code}_rawvalue"]
        for r in data:
            if r[ix["countycode"]] in ("000",) or not r[ix["fipscode"]]:
                continue
            v = num(r[vi])
            if v is not None:
                out[k][r[ix["fipscode"]].zfill(5)] = round(v, 1) if k != "population" else int(v)
        # find the data-year column, named like "v001_" + ... 'Premature Death' has year info in docs only
        _ = yi
    log("  " + ", ".join(f"{k}={len(v):,}" for k, v in out.items()))
    return out


# ---------------------------------------------------------------- build
def build(out_dir: Path, chr_year: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "monthly").mkdir(exist_ok=True)

    topo, counties = load_counties()
    fips_list = [c["fips"] for c in counties]
    idx = {f: i for i, f in enumerate(fips_list)}
    log(f"• {len(counties):,} counties in boundary file")

    injury, ttm_range, injury_as_of = cdc_injury()
    poison = cdc_drug_poisoning_modeled()
    monthly, months, monthly_as_of = cdc_monthly_overdose()
    heart, heart_year = cdc_cardio("mri7-5jtw", "heart disease")
    stroke, stroke_year = cdc_cardio("y5ii-knwc", "stroke")
    chr_ = chr_measures(chr_year)

    unmatched = defaultdict(set)

    def aligned(d: dict, src: str, field=None):
        arr = [None] * len(fips_list)
        for f, v in d.items():
            i = idx.get(f)
            if i is None:
                if not f.endswith("000"):
                    unmatched[src].add(f)
                continue
            arr[i] = v if field is None else v.get(field)
        return arr

    measures = []
    values = {}

    intents = [
        ("Drug_OD", "overdose", "Drug overdose deaths", "Deaths from drug overdose of any intent (unintentional, suicide, homicide, undetermined)."),
        ("All_Suicide", "suicide", "Suicide deaths", "Deaths by suicide, all mechanisms."),
        ("All_Homicide", "homicide", "Homicide deaths", "Deaths by homicide, all mechanisms."),
        ("FA_Deaths", "firearm", "Firearm deaths", "Deaths involving a firearm, all intents."),
        ("FA_Suicide", "firearm_suicide", "Firearm suicides", "Suicides involving a firearm."),
        ("FA_Homicide", "firearm_homicide", "Firearm homicides", "Homicides involving a firearm."),
    ]
    for intent, key, label, desc in intents:
        periods = sorted(p for p in injury[intent] if p != "TTM") + ["TTM"]
        values[key] = {
            "rate": {p: aligned(injury[intent][p], key, "rate") for p in periods},
            "count": {p: aligned(injury[intent][p], key, "count") for p in periods},
            "modeled": {p: [1 if (v or {}).get("modeled") else 0 for v in aligned(injury[intent][p], key)] for p in periods},
        }
        measures.append({
            "key": key, "label": label, "group": "Injury & violence", "description": desc,
            "unit": "per 100k residents", "rateType": "crude",
            "periods": periods, "periodLabels": {"TTM": f"Last 12 mo ({ttm_range})"} if ttm_range else {},
            "defaultPeriod": periods[-2],
            "hasCounts": True,
            "source": "CDC NCHS, National Vital Statistics System — Mapping Injury, Overdose, and Violence (county)",
            "sourceUrl": "https://data.cdc.gov/d/psx4-wq38", "asOf": injury_as_of,
            "notes": "County of residence. Where CDC suppresses counts of 1–9, the rate shown is CDC's Bayesian modeled estimate (marked 'modeled').",
        })

    pyears = sorted(poison)
    values["overdose_modeled"] = {"rate": {y: aligned(poison[y], "overdose_modeled", "rate") for y in pyears}}
    measures.append({
        "key": "overdose_modeled", "label": "Drug poisoning, long-run (modeled)", "group": "Injury & violence",
        "description": "Model-based estimates of drug poisoning death rates for every county, 2003–2021. Use for long-run trends; for recent years prefer 'Drug overdose deaths'.",
        "unit": "per 100k (age-adjusted)", "rateType": "age-adjusted, modeled",
        "periods": pyears, "defaultPeriod": pyears[-1], "hasCounts": False,
        "source": "CDC NCHS — Drug Poisoning Mortality by County (small-area model)",
        "sourceUrl": "https://data.cdc.gov/d/rpvx-m2md", "asOf": "",
        "notes": "Every value is a statistical model estimate, not a direct count.",
    })

    for key, d, yr, label, ds in [
        ("heart", heart, heart_year, "Heart disease deaths (adults 35+)", "mri7-5jtw"),
        ("stroke", stroke, stroke_year, "Stroke deaths (adults 35+)", "y5ii-knwc"),
    ]:
        values[key] = {"rate": {yr: aligned(d, key)}}
        measures.append({
            "key": key, "label": label, "group": "Natural causes",
            "description": f"{label.split(' (')[0]} among adults 35 and older, {int(yr)-1}–{int(yr)+1} three-year average.",
            "unit": "per 100k adults 35+ (age-adjusted)", "rateType": "age-adjusted, spatially smoothed",
            "periods": [yr], "defaultPeriod": yr, "hasCounts": False,
            "periodLabels": {yr: f"{int(yr)-1}–{int(yr)+1} avg"},
            "source": "CDC Interactive Atlas of Heart Disease and Stroke (NVSS)",
            "sourceUrl": f"https://data.cdc.gov/d/{ds}", "asOf": "",
            "notes": "Rates are spatially smoothed by CDC, so small counties borrow strength from neighbours.",
        })

    chr_defs = [
        ("life_expectancy", "Life expectancy", "years", "Average years a newborn is expected to live at current death rates.", True),
        ("premature_aamr", "Premature death rate (under 75)", "per 100k (age-adjusted)", "Age-adjusted deaths before age 75, all causes.", False),
        ("ypll", "Years of potential life lost", "years lost per 100k", "Years of life lost before age 75, per 100k people (age-adjusted). CHR's headline mortality measure.", False),
        ("injury", "Injury deaths (all)", "per 100k", "All injury deaths: overdose, crashes, falls, suicide, homicide and more.", False),
        ("motor_vehicle", "Motor vehicle crash deaths", "per 100k", "Deaths from motor vehicle crashes.", False),
        ("child_mortality", "Child mortality (under 18)", "per 100k", "Deaths among children under 18.", False),
        ("infant_mortality", "Infant mortality", "per 1,000 live births", "Deaths before age one.", False),
    ]
    snap = f"CHR {chr_year}"
    for key, label, unit, desc, higher_better in chr_defs:
        values[key] = {"rate": {snap: aligned(chr_[key], key)}}
        measures.append({
            "key": key, "label": label, "group": "All-cause & age",
            "description": desc, "unit": unit, "rateType": "see source",
            "periods": [snap], "defaultPeriod": snap, "hasCounts": False, "higherIsBetter": higher_better,
            "source": f"County Health Rankings & Roadmaps {chr_year} (NCHS mortality files, multi-year pooled)",
            "sourceUrl": "https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation",
            "asOf": str(chr_year),
            "notes": "Each CHR measure pools several recent years (typically 3) to stabilise small counties. Connecticut uses 2022 planning regions in CHR and is not shown.",
        })

    population = aligned(chr_["population"], "population")

    # monthly overdose series, split by state so the browser loads only what it needs
    by_state = defaultdict(dict)
    for f, s in monthly.items():
        if f not in idx:
            unmatched["monthly"].add(f)
            continue
        by_state[f[:2]][f] = [s.get(m) for m in months]
    for st, d in by_state.items():
        (out_dir / "monthly" / f"{st}.json").write_text(json.dumps({"months": months, "series": d}, separators=(",", ":")))

    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "counties": [[c["fips"], c["name"], c["state"]] for c in counties],
        "population": population,
        "measures": measures,
        "monthly": {"months": [months[0], months[-1]], "asOf": monthly_as_of,
                    "source": "CDC NCHS VSRR Provisional County-Level Drug Overdose Death Counts",
                    "sourceUrl": "https://data.cdc.gov/d/gb4e-yj24"},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    for k, v in values.items():
        (out_dir / f"m_{k}.json").write_text(json.dumps(v, separators=(",", ":")))
    (out_dir / "counties-10m.json").write_text(json.dumps(topo, separators=(",", ":")))

    # ------------------------------------------------ validation report
    report = {"unmatched_fips": {k: sorted(v) for k, v in unmatched.items()}, "coverage": {}}
    for m in measures:
        p = m["defaultPeriod"]
        arr = values[m["key"]]["rate"][p]
        report["coverage"][m["key"]] = {"period": p, "counties_with_value": sum(v is not None for v in arr), "of": len(arr)}
    (out_dir / "validation.json").write_text(json.dumps(report, indent=1))
    log("\nCoverage:")
    for k, v in report["coverage"].items():
        log(f"  {k:18s} {v['period']:>10}  {v['counties_with_value']:5d}/{v['of']}")
    if unmatched:
        log("Unmatched FIPS (not in boundary file): " + "; ".join(f"{k}: {len(v)}" for k, v in unmatched.items()))
    # Hard failure if a core source collapses — prevents silently shipping an empty map.
    if report["coverage"]["overdose"]["counties_with_value"] < 2500:
        sys.exit("FAIL: overdose coverage collapsed; not publishing")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site" / "data"))
    ap.add_argument("--chr-year", type=int, default=2025)
    a = ap.parse_args()
    build(Path(a.out), a.chr_year)
