# Point-layer snapshots (refreshed by hand)

The weekly build reads these files; it does not fetch their sources, because the sources cannot be fetched by a script
(NTSB publishes Microsoft Access files; IOM's site refuses scripted downloads). Every file keeps only what the map shows:
the month, the place snapped to the map's ~1 km grid (0.01 degree) and the number of deaths.

| File | Source | Refresh |
|---|---|---|
| `ntsb_fatal_events.csv` | NTSB aviation accident database, avall.zip (2008 on, updated monthly) and Pre2008.zip (1982-2007), https://data.ntsb.gov/avdata | Save both zips, unzip, `mdb-export avall.mdb events > avall_events.csv` and the same for Pre2008.mdb, then `python3 pipeline/trim_ntsb.py avall_events.csv pre2008_events.csv` |
| `iom_us_deaths.csv` | IOM's Missing Migrants Project, "Missing_Migrants_Global_Figures_allData.xlsx", https://missingmigrants.iom.int/downloads (CC BY 4.0) | Save the workbook in a browser, then `python3 pipeline/trim_iom.py Missing_Migrants_Global_Figures_allData.xlsx` |

IOM's licence asks for credit and a note of changes: credit "IOM's Missing Migrants Project"; changed by keeping deaths in the
United States only, rounding coordinates to about 1 km and counting per month.
