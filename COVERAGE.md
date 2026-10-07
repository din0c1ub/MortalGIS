# MortalGIS data coverage

Generated 2026-10-07 20:25 UTC by `pipeline/coverage.py` from `pipeline/sources.yml` and the built data. Don't edit by hand.

## Needs attention

- **ct_ocme**: newest data is 645 days old for a yearly source
- **nyc_homicides**: newest data is 646 days old for a yearly source

## County measures

Hidden = share of counties whose count is 1–9 and therefore not published (CDC confidentiality rule).

5-year = the same share when deaths are added up over five-year spans (latest span shown).

| Measure | Counted where | Years | Hidden, latest year | Hidden, average | Hidden, 5-year | Gaps |
|---|---|---|---|---|---|---|
| All deaths | lived | 1968–2025 | 1% | 1% | – | – |
| All deaths | died | 1968–2020 | 0% | 2% | – | large counties only 1989–2004; no data 2005–2019 |
| Drug overdose deaths | lived | 1968–2024 | 49% | 42% | 24% (2021-2025) | – |
| Drug overdose deaths | died | 1968–2004 | 20% | 36% | 27% (2021-2025) | large counties only 1989–2004 |
| Suicide deaths | lived | 1968–2024 | 57% | 62% | 21% (2021-2025) | – |
| Suicide deaths | died | 1968–2004 | 4% | 38% | 21% (2021-2025) | large counties only 1989–2004 |
| Homicide deaths | lived | 1968–2024 | 48% | 49% | 48% (2021-2025) | – |
| Homicide deaths | died | 1968–2004 | 51% | 45% | 50% (2021-2025) | large counties only 1989–2004 |
| Firearm deaths | lived | 1968–2024 | 59% | 63% | 24% (2021-2025) | – |
| Firearm deaths | died | 1968–2004 | 20% | 43% | 26% (2021-2025) | large counties only 1989–2004 |
| Heart disease deaths | lived | 1968–2025 | 7% | 5% | 1% (2021-2025) | – |
| Heart disease deaths | died | 1968–2004 | 0% | 4% | 1% (2021-2025) | large counties only 1989–2004 |
| Stroke deaths | lived | 1968–2025 | 32% | 28% | 6% (2021-2025) | – |
| Stroke deaths | died | 1968–2004 | 0% | 16% | 13% (2021-2025) | large counties only 1989–2004 |
| Cancer deaths | lived | 1999–2025 | 8% | 8% | 1% (2021-2025) | – |
| Cancer deaths | died | 2018–2025 | 11% | 11% | 2% (2021-2025) | – |
| Alzheimer's disease deaths | lived | 1999–2025 | 39% | 44% | 11% (2021-2025) | – |
| Alzheimer's disease deaths | died | 2018–2025 | 38% | 38% | 13% (2021-2025) | – |
| Diabetes deaths | lived | 1999–2025 | 43% | 48% | 10% (2021-2025) | – |
| Diabetes deaths | died | 2018–2025 | 46% | 46% | 14% (2021-2025) | – |
| Liver disease & cirrhosis deaths | lived | 1999–2025 | 55% | 58% | 20% (2021-2025) | – |
| Liver disease & cirrhosis deaths | died | 2018–2025 | 55% | 54% | 33% (2021-2025) | – |
| Chronic lung disease deaths (COPD, asthma) | lived | 1999–2025 | 27% | 30% | 5% (2021-2025) | – |
| Chronic lung disease deaths (COPD, asthma) | died | 2018–2025 | 32% | 32% | 7% (2021-2025) | – |
| Flu & pneumonia deaths | lived | 1999–2025 | 55% | 56% | 21% (2021-2025) | – |
| Flu & pneumonia deaths | died | 2018–2025 | 48% | 48% | 40% (2021-2025) | – |
| Kidney disease deaths | lived | 1999–2025 | 54% | 57% | 20% (2021-2025) | – |
| Kidney disease deaths | died | 2018–2025 | 53% | 54% | 32% (2021-2025) | – |
| COVID-19 deaths | lived | 2020–2025 | 58% | 39% | 6% (2021-2025) | – |
| COVID-19 deaths | died | 2020–2025 | 43% | 41% | 21% (2021-2025) | – |
| Fall deaths (accidental) | lived | 1999–2025 | 57% | 60% | 29% (2021-2025) | – |
| Fall deaths (accidental) | died | 2018–2025 | 48% | 48% | 47% (2021-2025) | – |
| Alcohol-induced deaths | lived | 1999–2025 | 57% | 57% | 27% (2021-2025) | – |
| Alcohol-induced deaths | died | 2018–2025 | 55% | 54% | 36% (2021-2025) | – |
| Firearm suicides | lived | 2019–2024 | 62% | 63% | – | – |
| Firearm homicides | lived | 2019–2024 | 43% | 44% | – | – |
| Traffic crash deaths | died | 1975–2024 | 0% | 0% | – | – |
| Weather deaths | died | 1950–2026 | 0% | 0% | – | – |
| Drug poisoning (modeled) | lived | 2003–2021 | – | – | – | – |
| Heart disease, adults 35+ (CDC atlas) | lived | 2015–2023 | – | – | – | no data 2021 |
| Stroke, adults 35+ (CDC atlas) | lived | 2015–2023 | – | – | – | no data 2021 |
| Life expectancy | lived | 2022–2022 | – | – | – | – |
| Premature death rate (under 75) | lived | 2022–2022 | – | – | – | – |
| Years of potential life lost | lived | 2022–2022 | – | – | – | – |
| Injury deaths (all) | lived | 2022–2022 | – | – | – | – |
| Child mortality (under 18) | lived | 2022–2022 | – | – | – | – |
| Infant mortality | lived | 2022–2022 | – | – | – | – |

## Sources in use

| Source | Access | Cadence | Data through | Last pulled |
|---|---|---|---|---|
| [NCHS multiple-cause-of-death public-use files (via NBER)](https://www.nber.org/research/data/mortality-data-vital-statistics-nchs-multiple-cause-death-data) (`nber`) | download | static | – | – |
| [CDC WONDER Compressed Mortality 1979-1998 (D16)](https://wonder.cdc.gov/cmf-icd9.html) (`wonder_cmf`) | wonder-manual | static | 1998 | 2026-10-07 |
| [CDC WONDER Underlying Cause of Death 1999-2020 (D76)](https://wonder.cdc.gov/ucd-icd10.html) (`wonder_ucd`) | wonder-manual | static | 2020 | 2026-10-07 |
| [CDC WONDER Provisional Mortality 2018+ (D176), by county](https://wonder.cdc.gov/mcd-icd10-provisional.html) (`wonder_prov`) | wonder-manual | manual-yearly | 2025 | 2026-10-07 |
| [CDC WONDER deaths by state x month (D76 1999-2020, D176 2018+)](https://wonder.cdc.gov/) (`wonder_state_month`) | wonder-manual | manual-yearly | 2026-10 | 2026-10-07 |
| [CDC Mapping Injury, Overdose, and Violence (county)](https://data.cdc.gov/d/psx4-wq38) (`psx4`) | api | weekly | – | – |
| [CDC provisional county death counts, 2020](https://data.cdc.gov/d/6vqh-esgs) (`cdc2020`) | api | static | – | – |
| [Census Bureau population estimates components (county deaths, Jul-Jun years)](https://www.census.gov/programs-surveys/popest/data/data-sets.html) (`census_deaths`) | download | yearly | – | – |
| [CDC provisional county drug overdose deaths (12 months ending each month)](https://data.cdc.gov/d/gb4e-yj24) (`cdc_monthly_overdose`) | api | monthly | – | – |
| [CDC NCHS drug poisoning mortality, county small-area model](https://data.cdc.gov/d/rpvx-m2md) (`rpvx`) | api | static | – | – |
| [CDC Atlas of Heart Disease and Stroke (ages 35+, 3-year averages)](https://www.cdc.gov/heart-disease-stroke-atlas/) (`atlas`) | api | yearly | – | – |
| [County Health Rankings & Roadmaps (multi-year pooled measures)](https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation) (`chr`) | download | yearly | – | – |
| [CDC occurrence vs residence county tables](https://data.cdc.gov/) (`cdc_occ_res`) | api | yearly | – | – |
| [SEER county population estimates 1969-2024](https://seer.cancer.gov/popdata/) (`seer_pop`) | download | yearly | – | – |
| [Census county boundaries (us-atlas TopoJSON) and Gazetteer places/ZCTAs](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) (`geo`) | download | yearly | – | – |
| [Cook County Medical Examiner case archive](https://datacatalog.cookcountyil.gov/d/cjeq-bs86) (`cook_me`) | api | weekly | 2026-10-07 | – |
| [Santa Clara County Medical Examiner-Coroner cases](https://data.sccgov.org/d/s3fb-yrjp) (`santa_clara_me`) | api | weekly | 2026-10-06 | – |
| [District Nine Medical Examiner (Orange & Osceola, FL)](https://services1.arcgis.com/0U8EQ1FrumPeIqDb/arcgis/rest/services/Cases_DeathAddress/FeatureServer/0) (`orange_fl_me`) | api | weekly | 2026-09-26 | – |
| [San Diego County Medical Examiner deaths by ZIP](https://data.sandiegocounty.gov/d/jkvb-n4p7) (`san_diego_me`) | api | monthly | 2026-07-31 | – |
| [Sacramento County Coroner cases by ZIP](https://data.saccounty.gov/) (`sacramento_coroner`) | api | weekly | 2026-10-05 | – |
| [Allegheny County fatal accidental overdoses](https://data.wprdc.org/dataset/allegheny-county-fatal-accidental-overdoses) (`allegheny_me`) | api | monthly | 2026-08-03 | – |
| [Connecticut accidental drug-related deaths](https://data.ct.gov/d/rybz-nyjw) (`ct_ocme`) | api | yearly | 2024-12-31 | – |
| [Fatal Encounters (2000-2021) + Washington Post Fatal Force (2022-2024)](https://fatalencounters.org/) (`police_killings`) | download | static | 2024-12-31 | – |
| [FRA rail accidents + MSHA mine accidents](https://data.transportation.gov/d/85tf-25kj) (`fra_msha`) | api | monthly | 2026-09-23 | – |
| [Mother Jones US mass shootings database](https://www.motherjones.com/politics/2012/12/mass-shootings-mother-jones-full-data/) (`mother_jones`) | download | monthly | 2026-08-01 | – |
| [Chicago homicides (CPD), before 2014](https://data.cityofchicago.org/d/gumc-mgzr) (`chicago_homicides`) | api | static | 2013-12-31 | – |
| [NYPD shooting incidents (murders)](https://data.cityofnewyork.us/d/833y-fsy8) (`nyc_homicides`) | api | yearly | 2024-12-30 | – |
| [Philadelphia fatal shooting victims](https://opendataphilly.org/datasets/shooting-victims/) (`philly_homicides`) | api | weekly | 2026-10-05 | – |
| [Detroit Police RMS crime incidents (homicide)](https://data.detroitmi.gov/) (`detroit_homicides`) | api | weekly | 2026-09-27 | – |
| [NHTSA Fatality Analysis Reporting System](https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars) (`fars`) | download | yearly | 2024-12-31 | – |
| [NOAA Storm Events Database](https://www.ncdc.noaa.gov/stormevents/) (`noaa`) | download | monthly | 2026-12-31 | – |
| [Milwaukee County Medical Examiner case data (snapshot)](https://github.com/UK-IPOP/open-data-pipeline/releases/tag/2025-12-01) (`milwaukee_me`) | download | static | 2025-11-30 | – |
| [Pima County OME drug-related deaths](https://github.com/UK-IPOP/open-data-pipeline) (`pima_ome`) | download | monthly | 2026-07-28 | – |
| [Cuyahoga County ME drug-related deaths](https://github.com/UK-IPOP/open-data-pipeline) (`cuyahoga_me`) | download | monthly | 2026-07-01 | – |
| [Michigan DHHS county death tables (no small-number hiding)](https://www.mdch.state.mi.us/osr/deaths/DeathNoTrends.asp) (`mi_mdhhs`) | download | yearly | – | – |
| [WONDER UCD 1999-2018, county x 5-year totals](https://wonder.cdc.gov/ucd-icd10.html) (`wonder_ucd_5yr`) | wonder-manual | static | 2014-2018 | 2026-10-07 |
| [WONDER Provisional, county x 5-year totals (2019-2023, 2021-2025)](https://wonder.cdc.gov/mcd-icd10-provisional.html) (`wonder_prov_5yr`) | wonder-manual | manual-yearly | 2021-2025 | 2026-10-07 |
| [New York State vital statistics Table 38 (county deaths by selected cause, no small-number hiding)](https://healthweb-back.health.ny.gov/statistics/vital_statistics/2023/table38.htm) (`ny_vitals`) | download | yearly | – | – |

## Research queue (candidates)

Ranked by value ÷ effort. Each one has a GitHub issue labelled `candidate`.

| Candidate | Value | Effort | Fills |
|---|---|---|---|
| `mpv` Mapping Police Violence | 3 | 2 | Police killings after 2024, since the Washington Post database stopped. |
| `oh_odh` Ohio Public Health Data Warehouse, mortality | 4 | 3 | Ohio's disclosure rule doesn't hide small death counts, so all 88 counties x every cause could be filled, 2007 on. |
| `nm_ibis` New Mexico IBIS death queries | 3 | 3 | Small-numbers rule says county counts by standard cause lists are not suppressed - fills New Mexico's many small counties. |
| `pa_eddie` Pennsylvania EDDIE death statistics | 3 | 3 | Rules hide rates, not counts - may fill Pennsylvania's 67 counties. |
| `nc_databook` North Carolina County Health Data Book (5-year counts) | 2 | 3 | 5-year county counts shown unsuppressed for 20 causes incl. suicide and homicide - fills NC cells in the 5-year view. |
| `more_me_portals` More medical examiner / coroner open data | 2 | 3 | Death locations outside the counties we have. |

## Set aside

- `nchs_restricted` NCHS restricted-use mortality files with full geography (rejected): Researchers only, under a data-use agreement; results can't be published at small-count county level. Not usable for a public map.
- `nvdrs` National Violent Death Reporting System (rejected): Public WISQARS views are state-level; case-level data is restricted.
- `ihme_county` IHME US county cause-specific mortality estimates (rejected): Releases: 1980-2014 (21 causes, 5-yearly), 2000-2019 by race/ethnicity (19 causes, annual), single-cause follow-ups. License is non-commercial and forbids redistributing the data or derivative works (user agreement section 6); MortalGIS republishes per-county values in its JSON files, so it can't use them. Revisit only with written permission from IHME.
- `gva` Gun Violence Archive (rejected): Copyrighted, proprietary aggregation; use limited to the query tool or a licensing agreement. Scraped copies on GitHub/Kaggle are unlicensed. The Trace's data hub forbids redistribution too. No openly licensed nationwide located gun-death dataset exists; for gun suicides and totals use state sources.
- `state_portals` State vital statistics portals with lower small-number thresholds (parked): Researched 2026-10-07 and split into per-state entries: mi_mdhhs (live), ny_vitals, oh_odh, nm_ibis, pa_eddie, nc_databook. Thresholds elsewhere: WI and MO hide under 5; KY overdose hides 1-4; MN, TX, IL hide under 10; WA CHAT not public.
- `okf` Google Cloud Open Knowledge Format (dataset publishing) (parked): Possible publishing format for the SNLd project. Revisit after the coverage file exists; the site already has schema.org Dataset markup.
