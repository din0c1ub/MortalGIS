# MortalGIS v2

An atlas of US county death rates built only from official public data.

**Live:** https://huggingface.co/spaces/dinoclub/mortal-gis

## What changed from v1

v1 showed ~15,800 "records" that were mostly not deaths: CDC article headlines pinned to San Francisco,
the same items re-added every night, state totals turned into single dots with invented ages and genders,
and a generated 1980s–2010s backlog. v2 throws all of that away. Every number on the map comes straight from
a source table; suppressed values stay suppressed.

## Data sources

| Measure | Source | Years | Notes |
|---|---|---|---|
| Overdose, suicide, homicide, firearm (all / suicide / homicide) | CDC NCHS *Mapping Injury, Overdose, and Violence – County* ([psx4-wq38](https://data.cdc.gov/d/psx4-wq38)) | 2019–2024 + trailing 12 months | Crude rate per 100k, county of residence. Counts 1–9 suppressed; rate is CDC's Bayesian modeled estimate (hatched on map). |
| Overdose, monthly rolling 12-month counts | CDC NCHS VSRR provisional ([gb4e-yj24](https://data.cdc.gov/d/gb4e-yj24)) | 2020–present | Provisional; counts 1–9 suppressed. County panel chart. |
| Drug poisoning, long-run | CDC NCHS small-area model ([rpvx-m2md](https://data.cdc.gov/d/rpvx-m2md)) | 2003–2021 | Age-adjusted, every value modeled. |
| Heart disease, stroke (adults 35+) | CDC Atlas of Heart Disease & Stroke ([mri7-5jtw](https://data.cdc.gov/d/mri7-5jtw), [y5ii-knwc](https://data.cdc.gov/d/y5ii-knwc)) | 2022–2024 avg | Age-adjusted, spatially smoothed. |
| Life expectancy, premature death, YPLL, injury, motor vehicle, child & infant mortality, population | [County Health Rankings & Roadmaps](https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation) 2025 | Multi-year pooled | CT uses 2022 planning regions in CHR, so CT is blank for these. |
| County boundaries | us-atlas 3 (Census 2017 cartographic boundaries) | | Matches the county set NVSS uses. |

CDC WONDER's API only returns national data, so it is not used for county figures.

## Layout

```
pipeline/build_data.py   download + validate + write site/data/*.json (stdlib only)
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

1. **Phase 1 (this):** county choropleth, Michigan default, county panel with trends and ranks.
2. **Phase 2:** incident layers with real coordinates (Cook County Medical Examiner, NHTSA FARS crashes),
   hex-binned with small-cell suppression — this is where v1's privacy work belongs.
3. **Phase 3:** history back to 1980 (IHME county mortality by cause, 1980–2014) and CDC WONDER exports for all-cause deaths by year.
