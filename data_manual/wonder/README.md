# CDC WONDER exports (fills 2005–2018 and small counties in 1989–2004)

CDC WONDER has county-level death counts for every year, but its API only returns national
figures and it asks a person to accept its data use terms. So these exports are made by hand,
once, and saved in this folder. The weekly build picks them up automatically and they take
priority over every other source for the years they cover.

## File names

`<cause>_<residence|occurrence>_<anything>.txt`

- cause: `all`, `overdose`, `suicide`, `homicide`, `firearm`, `heart`, `stroke`
- residence = counted where the person lived; occurrence = where the death happened

Examples: `overdose_residence_1999-2009.txt`, `all_occurrence_2018-2025.txt`

## Export A — where people lived, 1999–2020 (7 files, the important ones)

1. Open <https://wonder.cdc.gov/ucd-icd10.html> → **I Agree** to the data use restrictions.
2. **Section 1 (Organize table layout)**
   - Group Results By: **County**, then **Year**
   - Measures: leave **Deaths** checked (Population and Crude Rate can stay checked)
3. **Section 2 (Select location)**: leave "The United States" selected.
4. **Section 4 (Select year)**: leave **All Years** (1999–2020). If WONDER says the result is too
   large, run it twice: 1999–2009 and 2010–2020.
5. **Section 6 (Select cause of death)** — one export per cause:
   | File | What to pick |
   |---|---|
   | `all_residence` | leave "All Causes of Death" |
   | `overdose_residence` | choose **Drug/Alcohol Induced Causes** → select the four *Drug poisonings (overdose)* lines: Unintentional (X40–X44), Suicide (X60–X64), Homicide (X85), Undetermined (Y10–Y14) (Ctrl/Cmd-click) |
   | `suicide_residence` | choose **Injury Intent and Mechanism** → Injury Intent = **Suicide**, Mechanism = All |
   | `homicide_residence` | **Injury Intent and Mechanism** → Injury Intent = **Homicide** |
   | `firearm_residence` | **Injury Intent and Mechanism** → Intent = All, Injury Mechanism = **Firearm** |
   | `heart_residence` | **ICD-10 113 Cause List** → **#Diseases of heart (I00-I09,I11,I13,I20-I51)** |
   | `stroke_residence` | **ICD-10 113 Cause List** → **#Cerebrovascular diseases (I60-I69)** |
6. **Other options** (last section): check **Export Results**, uncheck **Show Totals**, check
   **Show Zero Values** (so counties with no deaths show 0 instead of blank), and check
   **Show Suppressed Values** if that box is offered.
7. Click **Send**. Your browser downloads a `.txt` file. Rename it as in the table and save it here.

## Export B — where people died, 2018–latest (optional, 7 files)

Same steps at <https://wonder.cdc.gov/mcd-icd10-provisional.html> (Provisional Mortality, 2018 through
last week), with two differences:
- Section 1: Group Results By **Occurrence County**, then **Year**.
- Section 2: switch the location type to **Occurrence** (the radio button above the location list).
- Section 6 is called **Select underlying cause of death**; make the same picks.
Name the files `<cause>_occurrence_2018-latest.txt`.

## Export C — small counties for 1989–1998 (optional, 5 files)

<https://wonder.cdc.gov/cmf-icd9.html> (Compressed Mortality, 1979–1998). Group by **County** and
**Year**, years 1989–1998, export with suppressed values shown. Causes from the **72 cause list**:
All causes (`all_residence_cmf`), Diseases of heart (`heart_…`), Cerebrovascular diseases (`stroke_…`),
Suicide (`suicide_…`), Homicide and legal intervention (`homicide_…`).

## After saving

Upload the files to `data_manual/wonder/` on GitHub (Add file → Upload files). The next weekly run,
or a manual run of the "Refresh data & deploy" workflow, adds them to the map.
