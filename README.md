# MortalGIS v2

An atlas of US county death rates built only from official public data.

**Live:** https://huggingface.co/spaces/dinoclub/mortal-gis

## What changed from v1

v1 showed ~15,800 "records" that were mostly not deaths: CDC article headlines pinned to San Francisco,
the same items re-added every night, state totals turned into single dots with invented ages and genders,
and a generated 1980s–2010s backlog. v2 throws all of that away. Every number on the map comes straight from
a source table; suppressed values stay suppressed.

## Data sources (refreshed weekly by `.github/workflows/refresh.yml`)

### County rates (choropleth)

| Measure | Source | Coverage | Publisher updates | Notes |
|---|---|---|---|---|
| Overdose, suicide, homicide, firearm (all / suicide / homicide) | CDC NCHS *Mapping Injury, Overdose, and Violence – County* ([psx4-wq38](https://data.cdc.gov/d/psx4-wq38)) | 2019–2024 + trailing 12 months | Monthly | Crude rate per 100k, county of residence. Counts 1–9 suppressed; rate is CDC's Bayesian modeled estimate (hatched). |
| Overdose, monthly rolling 12-month counts | CDC NCHS VSRR provisional ([gb4e-yj24](https://data.cdc.gov/d/gb4e-yj24)) | 2020–present | Monthly | County panel chart. Counts 1–9 suppressed. |
| All deaths — **where they lived** | US Census Bureau Population Estimates, components of change ([co-est{year}-alldata.csv](https://www.census.gov/programs-surveys/popest/data/data-sets.html)) | Jul 2020–Jun 2025 | Yearly (March) | Pipeline finds the newest vintage automatically. CT published by planning region (blank). |
| All deaths — **where they died** | CDC NCHS county-of-occurrence tables ([6vqh-esgs](https://data.cdc.gov/d/6vqh-esgs) 2020, [kn79-hsxy](https://data.cdc.gov/d/kn79-hsxy) Jan 2020–Jun 2023) | 2020; 2020–23 avg | Archived 2023 | Residence counterpart for the 2020 comparison: [75vb-d79q](https://data.cdc.gov/d/75vb-d79q). |
| Drug poisoning, long-run | CDC NCHS small-area model ([rpvx-m2md](https://data.cdc.gov/d/rpvx-m2md)) | 2003–2021 | Archived | Age-adjusted, every value modeled. |
| Heart disease, stroke (adults 35+) | CDC Atlas of Heart Disease & Stroke ([mri7-5jtw](https://data.cdc.gov/d/mri7-5jtw), [y5ii-knwc](https://data.cdc.gov/d/y5ii-knwc)) | 2022–2024 avg | Yearly | Age-adjusted, spatially smoothed. |
| Life expectancy, premature death, YPLL, injury, motor vehicle, child & infant mortality | [County Health Rankings & Roadmaps](https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation) | 2025 release | Yearly | Multi-year pooled. CT blank (planning regions). |
| County boundaries | us-atlas 3 (Census 2017 cartographic boundaries) | | | Matches the county set NVSS uses. |

### Death locations (points)

| Layer | Source | Coverage | Publisher updates | Where they died | Where they lived |
|---|---|---|---|---|---|
| Traffic crashes | [NHTSA FARS](https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars) national CSV | Latest 2 years (2023–2024) | Yearly | Crash coordinates, rounded to ~100 m | not published |
| Cook County, IL | [Medical Examiner Case Archive](https://datacatalog.cookcountyil.gov/d/cjeq-bs86) | 2019–present | Daily | ~1 km grid squares | Residence ZIP |
| Santa Clara County, CA | [Medical Examiner-Coroner full dataset](https://data.sccgov.org/d/s3fb-yrjp) | 2019–present | Daily | ~1 km grid squares (source coordinates are often the hospital) | Residence ZIP |
| Connecticut | [Accidental drug-related deaths](https://data.ct.gov/d/rybz-nyjw) | 2012–2024 | Yearly | Town of injury | Town of residence |

Privacy: medical examiner files include street addresses, ages and causes. MortalGIS publishes only counts per
~1 km square or ZIP Code, by year and manner of death.

### Researched but not automated (candidates)

- **CDC WONDER provisional mortality** — county of residence *or occurrence*, any cause, recent weeks. The API
  only returns national data, so county figures need a manual export (could be dropped into the pipeline as a CSV).
- **San Diego County ME** ([jkvb-n4p7](https://internal-sandiegocounty.data.socrata.com/d/jkvb-n4p7)) — 90k cases with
  death/residence ZIP but no coordinates; would work as a ZIP-level lived/died layer.
- **IHME US county mortality by cause, 1980–2014** (GHDx) — historical layer; requires a manual download.
- **Milwaukee County ME** — public data moved off its old ArcGIS service; recheck.

### Reliability

Each source is fetched independently. If a point layer fails, the previous week's file is kept and the layer is
marked stale on the map; if the core CDC overdose table collapses, the build stops and nothing is published.
`site/data/validation.json` records coverage and per-source status for every run.

## Layout

```
pipeline/build_data.py   county measures: download + validate + write site/data/*.json (stdlib only)
pipeline/incidents.py    death-location layers (FARS, medical examiners) with privacy aggregation
pipeline/wrap_index.py   wrap site/app.html into site/index.html
site/                    static site (d3 + topojson from CDN), deploys as-is
site/data/validation.json  coverage per measure + unmatched FIPS from the last run
.github/workflows/refresh.yml  weekly rebuild, commit, push to the HF Space
```

Run locally:

```bash
python pipeline/build_data.py && python pipeline/wrap_index.py
cd site && python -m http.server 8000   # open http://localhost:8000
```

To enable auto-deploy: add an `HF_TOKEN` repository secret (Hugging Face write token).

## Roadmap

1. **Phase 1 (done):** county choropleth, Michigan default, county panel with trends and ranks.
2. **Phase 2 (done):** "where they lived / where they died" switch; death-location layers (FARS, Cook and Santa Clara
   medical examiners, Connecticut drug deaths) aggregated for privacy.
3. **Phase 3:** history back to 1980 (IHME county mortality by cause, 1980–2014) and CDC WONDER exports for all-cause deaths by year.
