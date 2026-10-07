# Mapping Police Violence (people killed by police, 2013–)

`mpv_killings_trimmed.csv` is a trimmed copy of the Mapping Police Violence database
(https://mappingpoliceviolence.org/methodology → "View the data" → "…" → Download CSV).
Only date, location and use of force are kept — no names, ages, races, agencies, officers or links —
and locations are already snapped to the site's ~1 km grid (0.01°).

Airtable can't be downloaded by the weekly job, so refresh this by hand every month or two:
download the CSV, then run `python pipeline/trim_mpv.py "Mapping Police Violence.csv"` (writes this file).
Data: Campaign Zero / Mapping Police Violence. No license is stated; attributed on the site.
