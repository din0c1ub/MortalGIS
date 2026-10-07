# MortalGIS v2

An atlas of US county death rates built only from official public data.

**Live:** https://huggingface.co/spaces/dinoclub/mortal-gis

## What changed from v1

v1 showed ~15,800 "records" that were mostly not deaths: CDC article headlines pinned to San Francisco,
the same items re-added every night, state totals turned into single dots with invented ages and genders,
and a generated 1980s–2010s backlog. v2 throws all of that away. Every number on the map comes straight from
a source table; suppressed values stay suppressed.

## How far back each measure goes

| Measure | Years | Sources (in order of priority) |
|---|---|---|
| All deaths — where they lived | 1968–2025 | WONDER exports (CMF 1989–98, UCD 1999–2020) · CDC 2020 table · NCHS death files 1968–88 · Census estimates 2021–25 |
| All deaths — where they died | 1968–2004, 2020 (2018–25 once the Provisional occurrence file is added) | WONDER export · CDC 2020 table · NCHS death files |
| Overdose, suicide, homicide, firearm — lived | 1968–now (overdose 1989–98: large counties only) | WONDER exports 1989–2020 · CDC Mapping Injury, Overdose & Violence 2021–now · NCHS death files |
| Same four — where they died | 1968–2004 (2018–25 pending, see above) | WONDER export · NCHS death files |
| Heart disease, stroke (all ages) — lived | 1968–2025 | WONDER exports (CMF, UCD, Provisional 2021–25) · NCHS death files |
| Heart disease, stroke — where they died | 1968–2004, 2018–2025 | WONDER Provisional (occurrence) · NCHS death files |
| Cancer, Alzheimer's, diabetes, liver disease, chronic lung disease, flu & pneumonia, kidney disease, falls, alcohol-induced — lived | 1999–2025 | WONDER UCD 1999–2020 + Provisional 2021–25 |
| Same — where they died | 2018–2025 | WONDER Provisional (occurrence) |
| COVID-19 — lived / died | 2020–2025 | WONDER Provisional |
| Heart disease, stroke, adults 35+ | 2015–2023 | CDC Atlas of Heart Disease and Stroke (each year = middle of a 3-year average) |
| Firearm suicides / homicides | 2019–now | CDC Mapping Injury, Overdose & Violence |
| Drug poisoning (modeled) | 2003–2021 | CDC NCHS small-area model |
| Traffic crash deaths (where the crash happened) | 1975–2024 | NHTSA FARS (crash dots 2001–2024) |
| Weather deaths (where the event happened) | 1950–now | NOAA Storm Events (event dots where located) |
| Life expectancy, premature death, YPLL, injury, child & infant mortality | one pooled release (to 2022) | County Health Rankings 2025 |

**NCHS death files (1968–2004).** One record per death, from the NCHS Multiple Cause of Death public-use files
hosted by NBER, with both the county of residence and the county of occurrence. Counts are exact; counties
with 1–9 deaths are hidden. From 1989 the public files only name counties of 100,000+ people, so smaller
counties are blank for 1989–2004. Population: NCI SEER county estimates 1969–2024 (1968 uses 1969).
Cause definitions follow ICD-8 (1968–78), ICD-9 (1979–98) and ICD-10 (1999–); `tests/test_history_causes.py`
checks them against published US totals (all, suicide, firearm, heart, stroke match exactly; homicide is
within 1.5% because NCHS's older totals include legal intervention).

Fixes needed to place pre-1982 records (`pipeline/history.py: build_crosswalk`): DC is missing from NBER's
crosswalk; New York City is one area until 1982 (the five boroughs share its rate); Virginia used an older
numbering scheme (counties = 3 × alphabetical index, cities from 300). SEER combines a few counties
(e.g. some Virginia cities with their counties, Maui with Kalawao); those members share one rate.

**CDC WONDER fills the gaps.** Step-by-step export instructions are in
[`data_manual/wonder/README.md`](data_manual/wonder/README.md). Exports saved there take priority.

## Death locations (points follow the selected measure and year)

| Shown with | Source | Years | Where they died | Where they lived |
|---|---|---|---|---|
| Traffic crash deaths | NHTSA FARS | 2001–2024 | crash coordinates (zoom in to a state) | — |
| Weather deaths | NOAA Storm Events | 1950–now | event start point, where recorded | — |
| All deaths, overdose, suicide, homicide, firearm, heart | Cook County (IL) Medical Examiner | 2014–now | ~1 km squares | residence ZIP |
| same | Santa Clara County (CA) Medical Examiner-Coroner | 2018–now | ~1 km squares | residence ZIP |
| same | Orange County (FL) District 9 Medical Examiner (Orange + Osceola) | 2020–now | ~1 km squares | — |
| same | San Diego County (CA) Medical Examiner | 1997–now | ZIP of death (often a hospital) | residence ZIP |
| Overdose, homicide, firearm, traffic | Sacramento County (CA) Coroner | 2021–now | incident ZIP | — |
| Overdose | Allegheny County (PA) Medical Examiner, accidental overdoses (WPRDC, CC0) | 2007–now | incident ZIP | residence ZIP |
| Overdose | Connecticut accidental drug-related deaths | 2012–2024 | town of injury | town of residence |
| All deaths | Rail accidents (FRA, coordinates from ~2000) and mine accidents (MSHA, 2000–) | 2000–now | ~1 km squares | — |
| All deaths, homicide, firearm | Mother Jones mass shootings database (newest rows placed at the city centroid from the Census places gazetteer) | 1982–now | ~1 km squares | — |
| All deaths, firearm, traffic | People killed by police: Fatal Encounters 2000–21, Washington Post Fatal Force 2022–24 (CC BY-NC-SA) | 2000–2024 | ~1 km squares | — |
| Homicide, firearm | Chicago Police (1991–2013; Cook ME covers later), NYPD murders (2006–24), Philadelphia fatal shootings (2015–now), Detroit Police homicides (2010–now, homicide only) | varies | ~1 km squares | — |

Every layer keeps only counts per square/ZIP, year and category; names, case numbers, ages and addresses are dropped in the pipeline. Police killings are not shown on the homicide map because CDC counts them as legal intervention, not homicide.

## Month by month

The year slider has month buttons (J F M …) wherever monthly data is real:
- **Overdose, where they lived (2020–):** county colors show deaths in the 12 months ending that month (CDC provisional county counts, `site/data/monthly/`).
- **17 causes, 1999–:** the map switches to states, since monthly county counts are mostly under 10 and hidden. Data: WONDER state × month (`data_manual/wonder/*state_month*.json` → `site/data/state_month/`). The newest two provisional months are dropped while they fill in. The county panel shows the state's monthly line.
- **Death locations:** every dated layer also has a `*_m.json` file, so dots step month by month in the "Where they died" view, and fatal crashes do the same.

Links keep the view: `index.html#m=overdose&y=2023&w=lived&v=state&c=26049&mo=3`.

## Weekly refresh

`.github/workflows/refresh.yml` runs `pipeline/build_data.py` every Monday: CDC (monthly updates), Census,
County Health Rankings, medical examiners (daily updates) and any WONDER exports, merged with the stored
history in `site/data/hist/`. Run `python pipeline/history.py` by hand to rebuild the history (downloads
~3 GB once into `.cache/`; `--skip nber fars noaa` to rebuild parts). FARS adds a year each spring and NOAA
each month, so rerun `history.py --skip nber` a few times a year.

Reliability: each source is fetched on its own. A failing medical examiner layer keeps last week's file and
is marked stale; if the core CDC overdose table comes back nearly empty, the build stops and nothing is
published. `site/data/validation.json` lists county coverage for every measure and year.

## Layout

```
pipeline/build_data.py   county measures: download + validate + write site/data/*.json (stdlib only)
pipeline/incidents.py    medical examiner layers with privacy aggregation
pipeline/history.py      one-time history build: NCHS 1968–2004, SEER population, FARS, NOAA
data_manual/wonder/      CDC WONDER exports (manual; instructions inside)
tests/                   cause-definition, history and WONDER-parser checks
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
2. **Phase 2 (done):** "where they lived / where they died" switch; death-location layers.
3. **Phase 3 (done):** history back to 1968 (NCHS death files), traffic deaths 1975+, weather deaths 1950+,
   one year slider for everything with coverage strip; all overlay checkboxes removed.
4. **Next:** load the CDC WONDER exports (2005–2018); San Diego ME at ZIP level.
