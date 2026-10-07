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
import re
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
UA = {"User-Agent": "Mozilla/5.0 (compatible; MortalGIS-pipeline/2.0; +https://huggingface.co/spaces/dinoclub/mortal-gis)"}
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


CENSUS_MERGE = {"51515": "51019", "02270": "02158", "46113": "46102", "51560": "51005", "51780": "51083"}


def census_pep():
    """Census Population Estimates, county components of change (deaths by county of residence) and
    population. Estimate years run July 1 to June 30. Three releases cover 2000–present:
    co-est2009 (2001–2009), co-est2020 (2011–2020) and the newest vintage (2021–). The first year of
    each release covers only April–June, so it is skipped."""
    this = datetime.now().year
    sources = [("2000-2009", 2009), ("2010-2020", 2020)]
    for v in range(this, this - 4, -1):
        try:
            get(f"https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/counties/totals/co-est{v}-alldata.csv", retries=1)
            sources.append((f"2020-{v}", v))
            break
        except RuntimeError:
            continue
    deaths, pop = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    vintage = None
    for span, v in sources:
        start = int(span[:4])
        raw = get(f"https://www2.census.gov/programs-surveys/popest/datasets/{span}/counties/totals/co-est{v}-alldata.csv", retries=2).decode("latin-1")
        rows = list(csv.DictReader(io.StringIO(raw)))
        years = [y for y in range(start + 1, v + 1) if f"DEATHS{y}" in rows[0]]
        for r in rows:
            if r["SUMLEV"] != "050":
                continue
            f = r["STATE"].zfill(2) + r["COUNTY"].zfill(3)
            f = CENSUS_MERGE.get(f, f)
            for y in years:
                d, pp = num(r.get(f"DEATHS{y}")), num(r.get(f"POPESTIMATE{y}"))
                if d is not None:
                    deaths[str(y)][f] += int(d)
                if pp:
                    pop[str(y)][f] += int(pp)
        vintage = v
        log(f"• Census estimates {span}: years {years[0]}–{years[-1]}")
    return {y: dict(d) for y, d in deaths.items()}, {y: dict(d) for y, d in pop.items()}, vintage


def cdc_occurrence_residence():
    """All-cause deaths in calendar 2020 by county where the death happened (6vqh-esgs) and where the
    person lived (75vb-d79q). Counties with 1-9 deaths are suppressed by CDC (left blank)."""
    log("• CDC all-cause deaths by county of occurrence / residence …")
    def table(ds, fcol, dcol):
        rows = json.loads(get(SOCRATA.format(id=ds) + "?" + urllib.parse.urlencode({"$select": f"{fcol},{dcol}", "$limit": 10000})))
        return {fips5(r[fcol]): {"count": int(float(r[dcol]))} for r in rows if r.get(dcol) and r.get(fcol)}
    occ = {"2020": table("6vqh-esgs", "fips_code", "total_deaths")}
    res = {"2020": table("75vb-d79q", "fips_code", "total_deaths")}
    log(f"  occurrence 2020: {len(occ['2020']):,}; residence 2020: {len(res['2020']):,}")
    return occ, res


# ---------------------------------------------------------------- WONDER drop-in
WONDER_DIR = ROOT / "data_manual" / "wonder"
CAUSES = ["all", "overdose", "suicide", "homicide", "firearm", "heart", "stroke",
          "cancer", "alzheimers", "diabetes", "liver", "clrd", "flu_pneumonia", "kidney", "covid", "falls", "alcohol"]


def wonder_cause_from_notes(text):
    """Work out cause and place from the "Query Parameters" notes WONDER appends to every export,
    so files can keep their downloaded names (e.g. "Underlying Cause of Death 1999-2020 3.csv")."""
    notes = text.split('"---"', 1)[1] if '"---"' in text else ""
    params = " ".join(l.strip().strip('"') for l in notes.splitlines())
    group = re.search(r"Group By: ([^\n]*?)(?:\s{2,}|Show |Calculate|$)", params)
    group = group.group(1) if group else ""
    place = "occ" if re.search(r"Occurrence (County|State)", params) else "res"
    intent = re.search(r"Injury Intent: (\w+)", params)
    mech = re.search(r"Injury Mechanism[^:]*: (\w+)", params)
    if "Drug poisonings (overdose)" in params:
        cause = "overdose"
    elif intent and mech and mech.group(1) != "All":
        cause = None  # e.g. firearm suicides: not a map measure
    elif intent:
        cause = {"Suicide": "suicide", "Homicide": "homicide"}.get(intent.group(1))
    elif mech:
        cause = "firearm" if mech.group(1) == "Firearm" else None
    elif re.search(r"Diseases of heart", params):
        cause = "heart"
    elif re.search(r"Cerebrovascular diseases", params):
        cause = "stroke"
    elif re.search(r"(ICD-10 Codes|Cause List|Causes?:|Chapter)", params):
        cause = None  # some other cause selection we don't map
    else:
        cause = "all"
    return cause, place, group


def wonder_imports():
    """Exports from CDC WONDER saved in data_manual/wonder/ (tab-delimited .txt or comma .csv).
    Cause and residence/occurrence come from the file name (<cause>_<residence|occurrence>_*.txt)
    or, failing that, from the query notes WONDER writes at the bottom of each file.
    Needs a county code column, a year column ("Year Code" or "Year") and "Deaths"."""
    out = defaultdict(lambda: defaultdict(dict))  # (cause, place) -> year -> fips -> count
    spans = defaultdict(dict)  # (cause, place) -> "1999-2003" -> fips -> count (multi-year totals)
    report = []
    files = []
    if WONDER_DIR.exists():
        files = sorted(p for p in WONDER_DIR.iterdir() if p.suffix.lower() in (".txt", ".tsv", ".csv", ".json"))
    for path in files:
        if path.suffix.lower() == ".json":
            # Bundle saved by the in-browser WONDER export script: {"data": {cause: {year: {fips: deaths}}}}
            # (-1 = suppressed). County of residence.
            try:
                bundle = json.loads(path.read_text())
            except ValueError:
                log(f"  ! {path.name}: not valid JSON")
                continue
            if bundle.get("level") == "state":  # state × month bundles are read separately
                continue
            place = bundle.get("place", "res")
            if bundle.get("grain") == "multi-year":  # county totals over spans of years (fewer hidden counties)
                for cause, by_span in (bundle.get("data") or {}).items():
                    if cause not in CAUSES:
                        continue
                    for span, cells in by_span.items():
                        cell = spans[(cause, place)].setdefault(span, {})
                        for f, v in cells.items():
                            f = CENSUS_MERGE.get(f.zfill(5), f.zfill(5))
                            v = int(v)
                            cell[f] = (cell[f] + v if (cell[f] >= 0 and v >= 0) else -1) if f in cell else v
                    log(f"  WONDER {path.name}: {cause} multi-year totals for {', '.join(sorted(by_span))}")
                report.append({"file": path.name, "cause": "multi-year", "place": place, "ok": True, "countyYears": sum(len(c) for b in bundle["data"].values() for c in b.values())})
                continue
            for cause, years in (bundle.get("data") or {}).items():
                if cause not in CAUSES:
                    continue
                n = 0
                for y, cells in years.items():
                    cell = out[(cause, place)][str(y)]
                    for f, v in cells.items():
                        f = CENSUS_MERGE.get(f.zfill(5), f.zfill(5))
                        v = int(v)
                        cell[f] = (cell[f] + v if (cell[f] >= 0 and v >= 0) else -1) if f in cell else v
                        n += 1
                log(f"  WONDER {path.name}: {n:,} county-years ({cause}, {'residence' if place == 'res' else 'occurrence'})")
                report.append({"file": path.name, "cause": cause, "place": place, "ok": True, "countyYears": n})
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        m = re.match(r"(all|overdose|suicide|homicide|firearm|heart|stroke)_(residence|occurrence)", path.stem.lower())
        if m:
            cause, place = m.group(1), ("res" if m.group(2) == "residence" else "occ")
        else:
            cause, place, _ = wonder_cause_from_notes(text)
        if not cause:
            log(f"  ! skipped {path.name}: could not tell which cause it is (name it <cause>_<residence|occurrence>_….txt)")
            report.append({"file": path.name, "ok": False, "why": "unknown cause"})
            continue
        body = text.split('"---"')[0]
        first = body.splitlines()[0] if body else ""
        delim = "\t" if first.count("\t") > first.count(",") else ","
        rows = list(csv.DictReader(io.StringIO(body), delimiter=delim))
        if not rows:
            log(f"  ! {path.name}: no rows")
            report.append({"file": path.name, "ok": False, "why": "no rows"})
            continue
        cols = [c for c in rows[0].keys() if c]
        ccol = next((c for c in cols if "County Code" in c), None)
        ycol = next((c for c in cols if c in ("Year Code", "Year")), None)
        if not ccol or not ycol or "Deaths" not in cols:
            why = "no Year column (Group By must be County, then Year)" if ccol and not ycol else f"needs County Code, Year and Deaths (found {cols})"
            log(f"  ! skipped {path.name} ({cause}): {why}")
            report.append({"file": path.name, "cause": cause, "ok": False, "why": why})
            continue
        n = 0
        for r in rows:
            f, y, d = (r.get(ccol) or "").strip(), (r.get(ycol) or "").strip()[:4], (r.get("Deaths") or "").strip()
            if not (f.isdigit() and y.isdigit()):
                continue  # Total rows, blank lines
            f = CENSUS_MERGE.get(f.zfill(5), f.zfill(5))
            if d.lower() == "suppressed":
                v = -1
            elif d.replace(",", "").isdigit():
                v = int(d.replace(",", ""))
            else:
                continue
            cell = out[(cause, place)][y]
            if f in cell:  # two old codes merged into one county (e.g. Bedford city → Bedford County)
                cell[f] = cell[f] + v if (cell[f] >= 0 and v >= 0) else -1
            else:
                cell[f] = v
            n += 1
        log(f"  WONDER {path.name}: {n:,} county-years ({cause}, {'residence' if place == 'res' else 'occurrence'})")
        report.append({"file": path.name, "cause": cause, "place": place, "ok": True, "countyYears": n})
    wonder_imports.report = report
    wonder_imports.spans = spans
    return out


SOURCES = {
    "nber": {"label": "NCHS death certificates (public-use files, via NBER)", "url": "https://www.nber.org/research/data/mortality-data-vital-statistics-nchs-multiple-cause-death-data"},
    "nber_partial": {"label": "NCHS public-use files — only counties of 100,000+ people are identified", "url": "https://www.nber.org/research/data/mortality-data-vital-statistics-nchs-multiple-cause-death-data", "partial": True},
    "psx4": {"label": "CDC Mapping Injury, Overdose, and Violence", "url": "https://data.cdc.gov/d/psx4-wq38"},
    "census": {"label": "Census Bureau population estimates (Jul–Jun years)", "url": "https://www.census.gov/programs-surveys/popest/data/data-sets.html"},
    "cdc2020": {"label": "CDC provisional county death counts, 2020", "url": "https://data.cdc.gov/d/6vqh-esgs"},
    "wonder": {"label": "CDC WONDER export", "url": "https://wonder.cdc.gov/"},
    "fars": {"label": "NHTSA Fatality Analysis Reporting System", "url": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars"},
    "noaa": {"label": "NOAA Storm Events Database", "url": "https://www.ncdc.noaa.gov/stormevents/"},
    "atlas": {"label": "CDC Atlas of Heart Disease and Stroke (3-year averages)", "url": "https://www.cdc.gov/heart-disease-stroke-atlas/"},
    "rpvx": {"label": "CDC NCHS drug poisoning small-area model", "url": "https://data.cdc.gov/d/rpvx-m2md"},
    "chr": {"label": "County Health Rankings & Roadmaps 2025 (multi-year pooled)", "url": "https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation"},
}

ATLAS = {
    "heart": [("48mw-5apu", "2015"), ("mfvi-hkb9", "2016"), ("6x7h-usvx", "2017"), ("s6p7-fvbw", "2018"),
              ("jiwm-ppbh", "2019"), ("55yu-xksw", "2020"), ("th8y-thx5", "2022"), ("mri7-5jtw", "2023")],
    "stroke": [("kgsi-35re", "2015"), ("v246-z5tb", "2016"), ("tqwu-4a7k", "2017"), ("ua33-yiiu", "2018"),
               ("g5fg-bgtw", "2019"), ("vutr-sfkh", "2020"), ("cpdh-8cna", "2022"), ("y5ii-knwc", "2023")],
}


# ---------------------------------------------------------------- build
def build(out_dir: Path, chr_year: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "monthly").mkdir(exist_ok=True)
    hist_dir = out_dir / "hist"

    topo, counties = load_counties()
    fips_list = [c["fips"] for c in counties]
    idx = {f: i for i, f in enumerate(fips_list)}
    N = len(fips_list)
    log(f"• {N:,} counties in boundary file")

    def hist(name):
        p = hist_dir / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else None

    injury, ttm_range, injury_as_of = cdc_injury()
    poison = cdc_drug_poisoning_modeled()
    monthly, months, monthly_as_of = cdc_monthly_overdose()
    atlas = {k: [(yr, cdc_cardio(ds, f"{k} {yr}")[0]) for ds, yr in v] for k, v in ATLAS.items()}
    chr_ = chr_measures(chr_year)
    pep_deaths, pep_pop, pep_vintage = census_pep()
    occ2020, res2020 = cdc_occurrence_residence()
    wonder = wonder_imports()
    hpop = (hist("pop") or {}).get("pop", {})
    if not hpop:
        log("! site/data/hist/pop.json missing — run pipeline/history.py once to add 1968–2004 history")

    unmatched = defaultdict(set)

    def aligned(d: dict, src: str, field=None):
        arr = [None] * N
        for f, v in d.items():
            i = idx.get(f)
            if i is None:
                if not f.endswith("000"):
                    unmatched[src].add(f)
                continue
            arr[i] = v if field is None else v.get(field)
        return arr

    def pop_at(y: str, i: int):
        arr = hpop.get(y)
        v = arr[i] if arr else None
        if v is None:
            v = pep_pop.get(y, {}).get(fips_list[i])
        if v is None and hpop:  # nearest SEER year (e.g. 2025)
            last = max(hpop, key=int)
            if int(y) > int(last):
                v = hpop[last][i]
        return v

    def from_counts(counts: dict, y: str, suppress=True):
        """{fips: count (-1 = suppressed)} → (count array, rate array)."""
        c = aligned(counts, "counts")
        r = [None] * N
        for i, v in enumerate(c):
            if v is None:
                continue
            if suppress and 0 < v < 10:
                c[i] = -1
                continue
            if v < 0:
                continue
            p = pop_at(y, i)
            if p:
                r[i] = round(v / p * 1e5, 1)
        return c, r

    class Series:
        def __init__(self):
            self.rate, self.count, self.modeled, self.src = {}, {}, {}, {}

        def add(self, y, rate, count, src, modeled=None):
            if y in self.src:
                return  # earlier (higher-priority) source wins
            self.rate[y], self.src[y] = rate, src
            if count is not None:
                self.count[y] = count
            if modeled is not None and any(modeled):
                self.modeled[y] = modeled

        def periods(self):
            return sorted((p for p in self.src if p != "TTM"), key=int) + (["TTM"] if "TTM" in self.src else [])

        def dump(self):
            d = {"rate": self.rate, "src": self.src}
            if self.count:
                d["count"] = self.count
            if self.modeled:
                d["modeled"] = self.modeled
            return d

    measures, values = [], {}

    def add_measure(key, series, **m):
        per = series.periods()
        if not per:
            log(f"! {key}: no data, skipped")
            return
        values[key] = series.dump()
        nums = [p for p in per if p != "TTM"]
        if not m.get("defaultPeriod"):
            m["defaultPeriod"] = nums[-1] if nums else per[-1]
        measures.append({"key": key, "periods": per, **m})

    psx4_key = {"overdose": "Drug_OD", "suicide": "All_Suicide", "homicide": "All_Homicide", "firearm": "FA_Deaths"}
    labels = {"all": "All deaths", "overdose": "Drug overdose deaths", "suicide": "Suicide deaths", "homicide": "Homicide deaths",
              "firearm": "Firearm deaths", "heart": "Heart disease deaths", "stroke": "Stroke deaths",
              "cancer": "Cancer deaths", "alzheimers": "Alzheimer's disease deaths", "diabetes": "Diabetes deaths",
              "liver": "Liver disease & cirrhosis deaths", "clrd": "Chronic lung disease deaths (COPD, asthma)",
              "flu_pneumonia": "Flu & pneumonia deaths", "kidney": "Kidney disease deaths", "covid": "COVID-19 deaths",
              "falls": "Fall deaths (accidental)", "alcohol": "Alcohol-induced deaths"}
    descs = {"all": "Deaths from any cause.", "overdose": "Drug overdose (poisoning) deaths of any intent.",
             "suicide": "Deaths by suicide, all methods.", "homicide": "Deaths by homicide, all methods.",
             "firearm": "Deaths involving a firearm, all intents.", "heart": "Deaths with heart disease as the underlying cause, all ages.",
             "stroke": "Deaths with stroke as the underlying cause, all ages.",
             "cancer": "Deaths with a malignant cancer (ICD-10 C00–C97) as the underlying cause.",
             "alzheimers": "Deaths with Alzheimer's disease (G30) as the underlying cause.",
             "diabetes": "Deaths with diabetes (E10–E14) as the underlying cause.",
             "liver": "Chronic liver disease and cirrhosis (K70, K73–K74), including alcoholic liver disease.",
             "clrd": "Chronic lower respiratory diseases (J40–J47): COPD, emphysema, chronic bronchitis and asthma.",
             "flu_pneumonia": "Influenza and pneumonia (J09–J18) as the underlying cause.",
             "kidney": "Nephritis, nephrotic syndrome and nephrosis (N00–N07, N17–N19, N25–N27): mostly kidney failure.",
             "covid": "Deaths with COVID-19 (U07.1) as the underlying cause, 2020 onward.",
             "falls": "Unintentional falls (W00–W19), counted where the person lived. Most are adults over 75.",
             "alcohol": "Deaths caused directly by alcohol: alcoholic liver disease, alcohol poisoning and other alcohol-induced causes."}
    groups_of = {"all": "All causes", "overdose": "Injury & violence", "suicide": "Injury & violence", "homicide": "Injury & violence",
                 "firearm": "Injury & violence", "heart": "Natural causes", "stroke": "Natural causes",
                 "cancer": "Natural causes", "alzheimers": "Natural causes", "diabetes": "Natural causes", "liver": "Natural causes",
                 "clrd": "Natural causes", "flu_pneumonia": "Natural causes", "kidney": "Natural causes", "covid": "Natural causes",
                 "falls": "Injury & violence", "alcohol": "Injury & violence"}
    me_cat = {"all": 0, "overdose": 1, "suicide": 2, "homicide": 3, "firearm": 4}
    ttm_label = {"TTM": f"Last 12 mo ({ttm_range})"} if ttm_range else {}

    for cause in CAUSES:
        key = "all_deaths" if cause == "all" else cause
        nb_res, nb_occ = hist(f"nber_{cause}_res"), hist(f"nber_{cause}_occ")
        pts = []  # point layers are attached after the incident layers are built (see attach_points)
        for place in ("res", "occ"):
            s_ = Series()
            for y, counts in sorted(wonder.get((cause, place), {}).items()):
                if cause == "covid" and int(y) < 2020:  # the U07.1 code did not exist before 2020
                    continue
                c, r = from_counts(counts, y)
                s_.add(y, r, c, "wonder")
            if place == "res":
                if cause in psx4_key:
                    inj = injury[psx4_key[cause]]
                    for y in inj:
                        s_.add(y, aligned(inj[y], key, "rate"), aligned(inj[y], key, "count"), "psx4",
                               [1 if (v or {}).get("modeled") else 0 for v in aligned(inj[y], key)])
                if cause == "all":
                    c, r = from_counts(res2020["2020"] and {f: v["count"] for f, v in res2020["2020"].items()}, "2020")
                    s_.add("2020", r, c, "cdc2020")
            else:
                if cause == "all":
                    c, r = from_counts({f: v["count"] for f, v in occ2020["2020"].items()}, "2020")
                    s_.add("2020", r, c, "cdc2020")
            nb = nb_res if place == "res" else nb_occ
            if nb:
                for y in nb["count"]:
                    if int(y) <= 1988:
                        s_.add(y, nb["rate"][y], nb["count"][y], "nber")
            if place == "res" and cause == "all":
                for y in sorted(pep_deaths):
                    if y in ("2000", "2010", "2020"):  # partial estimate years
                        continue
                    c, r = from_counts(pep_deaths[y], y, suppress=False)
                    s_.add(y, r, c, "census")
            if nb:
                for y in nb["count"]:
                    if int(y) >= 1989:
                        s_.add(y, nb["rate"][y], nb["count"][y], "nber_partial")
            died = place == "occ"
            n_before = len(measures)
            add_measure(
                f"{key}_died" if died else key, s_,
                label=labels[cause], group=groups_of[cause],
                description=descs[cause] + (" Counted in the county where the death happened." if died else " Counted in the county where the person lived."),
                unit="per 100k residents", rateType="crude", hasCounts=True,
                place="occurrence" if died else "residence", pair=(key if died else f"{key}_died"),
                periodLabels=({} if died else ttm_label), points=pts,
                icdBreaks=[1979, 1999], flagLabel="Modeled by CDC (1–9 deaths)",
                notes=("Rates use the county's population (NCI SEER estimates; Census for 2025). Counts of 1–9 are suppressed. "
                       "Cause definitions follow ICD-8 (1968–78), ICD-9 (1979–98) and ICD-10 (1999–); small jumps at those years are coding changes."),
            )
            # Multi-year county totals (WONDER): far fewer counties hidden. Rate = deaths ÷ person-years × 100k (an average yearly rate).
            sp = getattr(wonder_imports, "spans", {}).get((cause, place))
            mk = f"{key}_died" if died else key
            if sp and len(measures) > n_before:
                packed = {}
                for span, cells in sorted(sp.items()):
                    a, b = (int(x) for x in span.split("-"))
                    c = aligned(cells, "spans")
                    r = [None] * N
                    for i, v in enumerate(c):
                        if v is None or v < 0:
                            continue
                        pops = [pop_at(str(y), i) for y in range(a, b + 1)]
                        if all(pops):
                            r[i] = r1(v / sum(pops) * 1e5)
                    packed[span] = {"count": c, "rate": r}
                values[mk]["spans"] = packed
                measures[-1]["spans"] = sorted(packed)

    # Firearm suicides / homicides (CDC 2019+ only)
    for intent, key, label, desc in [("FA_Suicide", "firearm_suicide", "Firearm suicides", "Suicides involving a firearm."),
                                     ("FA_Homicide", "firearm_homicide", "Firearm homicides", "Homicides involving a firearm.")]:
        s_ = Series()
        for y in injury[intent]:
            s_.add(y, aligned(injury[intent][y], key, "rate"), aligned(injury[intent][y], key, "count"), "psx4",
                   [1 if (v or {}).get("modeled") else 0 for v in aligned(injury[intent][y], key)])
        add_measure(key, s_, label=label, group="Injury & violence", description=desc + " Counted where the person lived.",
                    unit="per 100k residents", rateType="crude", hasCounts=True, place="residence", periodLabels=ttm_label,
                    flagLabel="Modeled by CDC (1–9 deaths)", notes="CDC publishes this split by county from 2019 only.")

    # Traffic deaths (FARS) — where the crash happened
    fc = hist("fars_county")
    if fc:
        s_ = Series()
        for y in fc["count"]:
            s_.add(y, fc["rate"][y], fc["count"][y], "fars")
        add_measure("traffic", s_, label="Traffic crash deaths", group="Injury & violence",
                    description="Everyone killed in a crash on a public road, counted in the county where the crash happened.",
                    unit="per 100k residents", rateType="crude", hasCounts=True, place="occurrence",
                    points=[{"layer": "fars"}], notes="Every fatal crash is published, so small counts are shown. Crash locations exist from 2001.")

    # Weather deaths (NOAA) — where the event happened
    nc = hist("noaa_county")
    if nc:
        s_ = Series()
        for y in nc["count"]:
            s_.add(y, nc["rate"][y], nc["count"][y], "noaa")
        this_year = str(datetime.now().year)
        add_measure("weather", s_, label="Weather deaths", group="Natural causes",
                    periodLabels={this_year: f"{this_year} so far"} if this_year in s_.src else {},
                    defaultPeriod=str(int(this_year) - 1) if this_year in s_.src else None,
                    description="Deaths caused directly or indirectly by heat, cold, floods, tornadoes, storms and other weather, counted where the event happened.",
                    unit="deaths", rateType="count", colorBy="count", hasCounts=True, place="occurrence",
                    points=[{"layer": "noaa"}],
                    notes="NOAA logged only tornadoes 1950–54 and tornadoes, wind and hail until 1996; all event types after. Deaths from forecast-zone events are split evenly across the zone's counties, so some counts have decimals.")

    # Drug poisoning, modeled 2003–2021
    s_ = Series()
    for y in poison:
        s_.add(y, aligned(poison[y], "overdose_modeled", "rate"), None, "rpvx")
    add_measure("overdose_modeled", s_, label="Drug poisoning (modeled)", group="Injury & violence",
                description="Model-based estimates for every county, 2003–2021. Fills the years the county death records don't cover.",
                unit="per 100k (age-adjusted)", rateType="age-adjusted, modeled", hasCounts=False, place="residence",
                notes="Every value is a statistical model estimate, not a direct count.")

    # Heart disease / stroke, adults 35+ (CDC atlas, 3-year averages)
    for k, label in [("heart", "Heart disease, adults 35+ (CDC atlas)"), ("stroke", "Stroke, adults 35+ (CDC atlas)")]:
        s_ = Series()
        for yr, d in atlas[k]:
            s_.add(yr, aligned(d, f"{k}35"), None, "atlas")
        add_measure(f"{k}35", s_, label=label, group="Natural causes",
                    description=f"{label.split(',')[0]} deaths among adults 35+, age-adjusted and smoothed by CDC; each year is the middle of a 3-year average.",
                    unit="per 100k adults 35+ (age-adjusted)", rateType="age-adjusted, smoothed", hasCounts=False, place="residence",
                    periodLabels={yr: f"{int(yr)-1}–{int(yr)+1}" for yr, _ in atlas[k]},
                    notes="CDC skipped the 2020–2022 release.")

    # County Health Rankings (one release, pooled years) — placed at its latest data year
    chr_defs = [
        ("life_expectancy", "Life expectancy", "years", "Average years a newborn is expected to live at current death rates.", True, "All causes"),
        ("premature_aamr", "Premature death rate (under 75)", "per 100k (age-adjusted)", "Age-adjusted deaths before age 75, all causes.", False, "All causes"),
        ("ypll", "Years of potential life lost", "years lost per 100k", "Years of life lost before age 75, per 100k people (age-adjusted).", False, "All causes"),
        ("injury", "Injury deaths (all)", "per 100k", "All injury deaths: overdose, crashes, falls, suicide, homicide and more.", False, "Injury & violence"),
        ("child_mortality", "Child mortality (under 18)", "per 100k", "Deaths among children under 18.", False, "All causes"),
        ("infant_mortality", "Infant mortality", "per 1,000 live births", "Deaths before age one.", False, "All causes"),
    ]
    for key, label, unit, desc, higher_better, grp in chr_defs:
        s_ = Series()
        s_.add("2022", aligned(chr_[key], key), None, "chr")
        add_measure(key, s_, label=label, group=grp, description=desc, unit=unit, rateType="see source", hasCounts=False,
                    higherIsBetter=higher_better, place="residence", periodLabels={"2022": f"to 2022 (CHR {chr_year})"},
                    notes="One release that pools several years (typically 2020–2022). Connecticut uses planning regions in CHR and is blank.")

    # monthly overdose series, split by state so the browser loads only what it needs
    by_state = defaultdict(dict)
    for f, s in monthly.items():
        if f not in idx:
            unmatched["monthly"].add(f)
            continue
        by_state[f[:2]][f] = [s.get(m) for m in months]
    for st, d in by_state.items():
        (out_dir / "monthly" / f"{st}.json").write_text(json.dumps({"months": months, "series": d}, separators=(",", ":")))

    status = {}
    try:
        from incidents import build_incidents
        incident_layers = build_incidents(out_dir, status)
    except Exception as e:  # noqa: BLE001
        log(f"! incident layers failed: {e}")
        incident_layers = []
    pdir = out_dir / "points"
    if any(pdir.glob("fars_*.json")):
        incident_layers.append({"key": "fars", "label": "Fatal crashes", "kind": "fars", "perState": True,
                                "years": list(range(2001, 2025)), "hasLived": False, "area": "United States",
                                "diedNote": "fatal crash locations (zoom in to a state)", "source": SOURCES["fars"]["label"],
                                "sourceUrl": SOURCES["fars"]["url"], "latest": "2024"})
    if (pdir / "noaa.json").exists():
        incident_layers.append({"key": "noaa", "label": "Deadly weather events", "kind": "noaa", "hasLived": False,
                                "years": sorted(int(y) for y in json.loads((pdir / "noaa.json").read_text())),
                                "area": "United States", "diedNote": "deadly weather events with a recorded location",
                                "source": SOURCES["noaa"]["label"], "sourceUrl": SOURCES["noaa"]["url"]})

    # drop "where they died" pairs whose partner measure had no data
    keys = {m["key"] for m in measures}
    for m in measures:
        if m.get("pair") and m["pair"] not in keys:
            m.pop("pair")

    # attach point layers to the measures they match, from each layer's "show" {cause: category}
    for m in measures:
        base = m["key"].removesuffix("_died")
        cause = "all" if base == "all_deaths" else base
        extra = [{"layer": l["key"], "cat": l["show"][cause]} for l in incident_layers if cause in (l.get("show") or {})]
        if extra:
            m["points"] = (m.get("points") or []) + extra

    population = aligned(chr_["population"], "population")
    meta = {
        "incidents": incident_layers,
        "sources": SOURCES,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "counties": [[c["fips"], c["name"], c["state"]] for c in counties],
        "population": population,
        "measures": measures,
        "wonderFiles": sorted(f"{c}_{'residence' if p == 'res' else 'occurrence'}" for c, p in wonder),
        "monthly": {"months": [months[0], months[-1]], "asOf": monthly_as_of,
                    "source": "CDC NCHS VSRR Provisional County-Level Drug Overdose Death Counts",
                    "sourceUrl": "https://data.cdc.gov/d/gb4e-yj24"},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    for old in out_dir.glob("m_*.json"):
        if old.stem[2:] not in values:
            old.unlink()
    for k, v in values.items():
        (out_dir / f"m_{k}.json").write_text(json.dumps(v, separators=(",", ":")))
    (out_dir / "counties-10m.json").write_text(json.dumps(topo, separators=(",", ":")))

    # state × month death counts by cause (WONDER state_month bundles) → site/data/state_month/<cause>.json
    sm_dir = out_dir / "state_month"
    sm_dir.mkdir(exist_ok=True)
    sm = defaultdict(lambda: defaultdict(dict))  # cause -> "YYYY-MM" -> state -> deaths (-1 suppressed)
    if WONDER_DIR.exists():
        for f in sorted(WONDER_DIR.glob("*state_month*.json")):  # later files (Provisional 2018+) override earlier ones
            try:
                b = json.loads(f.read_text())
            except ValueError:
                continue
            for cause, months in (b.get("data") or {}).items():
                ms_sorted = sorted(months)
                if "provisional" in (b.get("note") or "").lower():
                    ms_sorted = ms_sorted[:-2]  # the newest provisional months are still filling in
                for mo in ms_sorted:
                    sm[cause][mo].update(months[mo])
    st_pop = defaultdict(int)
    seer = (hist("pop") or {}).get("pop") or {}
    seer_latest = seer[max(seer)] if seer else None  # SEER covers every county (CHR lacks Connecticut)
    for j, c in enumerate(counties):
        pop = (seer_latest[j] if seer_latest and j < len(seer_latest) else None) or population[j]
        if pop:
            st_pop[c["fips"][:2]] += pop
    for cause, months in sm.items():
        ms = sorted(months)
        sts = sorted({s for m_ in ms for s in months[m_]})
        series = {s: [months[m_].get(s) for m_ in ms] for s in sts}
        (sm_dir / f"{cause}.json").write_text(json.dumps({"months": ms, "series": series, "pop": {s: st_pop.get(s) for s in sts}}, separators=(",", ":")))
    if sm:
        log(f"  state × month: {len(sm)} causes, {min(min(v) for v in sm.values())}–{max(max(v) for v in sm.values())}")
        meta["stateMonth"] = {c: [min(v), max(v)] for c, v in sm.items()}
        (out_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))

    # latest.json: each measure's default period only, so the county panel's "every measure" list
    # doesn't have to download every measure file (~40 MB) when a county is clicked
    latest = {}
    for m in measures:
        if m.get("place") == "occurrence" and m.get("pair"):
            continue
        v, p = values[m["key"]], m["defaultPeriod"]
        arr = (v.get("rate") or {}).get(p)
        if arr is None and m.get("colorBy") == "count":
            arr = (v.get("count") or {}).get(p)
        if arr is not None:
            latest[m["key"]] = {"p": p, "v": arr}
    (out_dir / "latest.json").write_text(json.dumps(latest, separators=(",", ":")))

    # ------------------------------------------------ validation report
    report = {"unmatched_fips": {k: sorted(v)[:50] for k, v in unmatched.items()}, "coverage": {}, "incident_sources": status}
    for m in measures:
        yrs = {}
        for p in m["periods"]:
            arr = values[m["key"]]["rate"][p]
            cnt = values[m["key"]].get("count", {}).get(p)
            yrs[p] = sum(1 for i, v in enumerate(arr) if v is not None or (cnt and cnt[i] is not None))
        report["coverage"][m["key"]] = {"periods": f"{m['periods'][0]}–{m['periods'][-1]}", "n_periods": len(m["periods"]),
                                        "default": m["defaultPeriod"], "counties_default": yrs[m["defaultPeriod"]], "by_year": yrs}
    (out_dir / "validation.json").write_text(json.dumps(report, indent=1))
    log("\nCoverage (default year):")
    for k, v in report["coverage"].items():
        log(f"  {k:18s} {v['periods']:>11} ({v['n_periods']:2d})  default {v['default']:>5}: {v['counties_default']:5d}/{N}")
    if unmatched:
        log("Unmatched FIPS (not in boundary file): " + "; ".join(f"{k}: {len(v)}" for k, v in unmatched.items()))
    # Hard failure if a core source collapses — prevents silently shipping an empty map.
    if report["coverage"]["overdose"]["by_year"].get("2024", 0) < 2500:
        sys.exit("FAIL: overdose coverage collapsed; not publishing")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site" / "data"))
    ap.add_argument("--chr-year", type=int, default=2025)
    a = ap.parse_args()
    build(Path(a.out), a.chr_year)
