# MortalGIS data coverage

Generated 2026-10-07 19:01 UTC by `pipeline/coverage.py` from `pipeline/sources.yml` and the built data. Don't edit by hand.

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
| Drug overdose deaths | lived | 1968–2024 | 49% | 42% | 29% (2014-2018) | – |
| Drug overdose deaths | died | 1968–2004 | 20% | 36% | – | large counties only 1989–2004 |
| Suicide deaths | lived | 1968–2024 | 57% | 62% | 21% (2019-2023) | – |
| Suicide deaths | died | 1968–2004 | 4% | 38% | – | large counties only 1989–2004 |
| Homicide deaths | lived | 1968–2024 | 48% | 49% | 49% (2019-2023) | – |
| Homicide deaths | died | 1968–2004 | 51% | 45% | – | large counties only 1989–2004 |
| Firearm deaths | lived | 1968–2024 | 59% | 63% | 27% (2014-2018) | – |
| Firearm deaths | died | 1968–2004 | 20% | 43% | – | large counties only 1989–2004 |
| Heart disease deaths | lived | 1968–2025 | 7% | 5% | 1% (2019-2023) | – |
| Heart disease deaths | died | 1968–2004 | 0% | 4% | – | large counties only 1989–2004 |
| Stroke deaths | lived | 1968–2025 | 32% | 28% | 6% (2019-2023) | – |
| Stroke deaths | died | 1968–2004 | 0% | 16% | – | large counties only 1989–2004 |
| Cancer deaths | lived | 1999–2025 | 8% | 8% | 1% (2019-2023) | – |
| Cancer deaths | died | 2018–2025 | 11% | 11% | – | – |
| Alzheimer's disease deaths | lived | 1999–2025 | 39% | 45% | 10% (2019-2023) | – |
| Alzheimer's disease deaths | died | 2018–2025 | 38% | 38% | – | – |
| Diabetes deaths | lived | 1999–2025 | 43% | 48% | 10% (2019-2023) | – |
| Diabetes deaths | died | 2018–2025 | 46% | 46% | – | – |
| Liver disease & cirrhosis deaths | lived | 1999–2025 | 55% | 59% | 22% (2019-2023) | – |
| Liver disease & cirrhosis deaths | died | 2018–2025 | 55% | 54% | – | – |
| Chronic lung disease deaths (COPD, asthma) | lived | 1999–2025 | 27% | 30% | 5% (2019-2023) | – |
| Chronic lung disease deaths (COPD, asthma) | died | 2018–2025 | 32% | 32% | – | – |
| Flu & pneumonia deaths | lived | 1999–2025 | 55% | 56% | 21% (2019-2023) | – |
| Flu & pneumonia deaths | died | 2018–2025 | 48% | 48% | – | – |
| Kidney disease deaths | lived | 1999–2025 | 54% | 57% | 20% (2019-2023) | – |
| Kidney disease deaths | died | 2018–2025 | 53% | 54% | – | – |
| COVID-19 deaths | lived | 2020–2025 | 58% | 39% | 4% (2019-2023) | – |
| COVID-19 deaths | died | 2020–2025 | 43% | 41% | – | – |
| Fall deaths (accidental) | lived | 1999–2025 | 57% | 60% | 36% (2014-2018) | – |
| Fall deaths (accidental) | died | 2018–2025 | 48% | 48% | – | – |
| Alcohol-induced deaths | lived | 1999–2025 | 57% | 59% | 36% (2014-2018) | – |
| Alcohol-induced deaths | died | 2018–2025 | 55% | 54% | – | – |
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
| [WONDER UCD 1999-2018, county x 5-year totals](https://wonder.cdc.gov/ucd-icd10.html) (`wonder_ucd_5yr`) | wonder-manual | static | 2014-2018 | 2026-10-07 |

## Research queue (candidates)

Ranked by value ÷ effort. Each one has a GitHub issue labelled `candidate`.

| Candidate | Value | Effort | Fills |
|---|---|---|---|
| `wonder_prov_5yr` WONDER Provisional, county x 5-year totals (2019-2023, 2021-2025) | 5 | 2 | Same as wonder_ucd_5yr for recent years, and makes the "where they died" map readable in small counties. |
| `mpv` Mapping Police Violence | 3 | 2 | Police killings after 2024, since the Washington Post database stopped. |
| `ihme_county` IHME US county cause-specific mortality estimates | 4 | 3 | Modeled rates for every county and many causes, filling hidden cells (shown hatched as modeled). |
| `more_me_portals` More medical examiner / coroner open-data portals | 4 | 3 | Death locations outside the 7 counties we have. Not held back like CDC counts. |
| `gva` Gun Violence Archive | 4 | 4 | Located gun deaths nationwide, beyond the 4 cities we have. |
| `state_portals` State vital statistics query portals with lower small-number thresholds | 3 | 4 | Some states publish county counts below 10 (e.g. hide only 1-4 or 1-5), un-hiding small counties in those states. |

## Set aside

- `nchs_restricted` NCHS restricted-use mortality files with full geography (rejected): Researchers only, under a data-use agreement; results can't be published at small-count county level. Not usable for a public map.
- `nvdrs` National Violent Death Reporting System (rejected): Public WISQARS views are state-level; case-level data is restricted.
- `okf` Google Cloud Open Knowledge Format (dataset publishing) (parked): Possible publishing format for the SNLd project. Revisit after the coverage file exists; the site already has schema.org Dataset markup.
