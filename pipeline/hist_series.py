"""Definitions shared by pipeline/hist_state.py (builds the state-level historical mode) and master/master.py (ledger rows).

Plain data, standard library only. Nothing here reads a file.

The historical mode draws STATES, not counties, for 1900-1945, from two staged bundles:
  miller_vsh_1900_1936   Grant Miller's digitized Vital Statistics Deaths, state by cause, age and sex (NBER), 48 states
  nber_infant_1920_1945  Infant deaths and births by state (Douglas Norton / Karen Norberg workbook, NBER)
The causes are the printed volumes' causes, not today's ICD groups. Each series carries a comparability grade instead of a new name.
Approval is per series: ledger rows (source_id, bundle 'hist_state', measure = the series key, place 'state').
"""
from __future__ import annotations

BUNDLE = "hist_state"
SOURCES = {
    "miller": dict(id="miller_vsh_1900_1936", file="hist_miller_vsh_1900_1936_state.json",
                   label="Grant Miller, Vital Statistics Deaths, Historical 1900-1936 (NBER Public Use Data Archive; digitized from the Census Bureau and Public Health Service mortality volumes)",
                   url="https://www.nber.org/research/data/vital-statistics-deaths-historical-1900-1936",
                   terms="NBER page: the author encourages use and sharing; no licence or citation format is stated beyond naming the source."),
    "vsus3738": dict(id="vsus_tables_1937_1938", file="hist_vsus_1937_1938_state.json",
                     label="Vital Statistics of the United States, 1937 and 1938, Part I (US Bureau of the Census): Table 19, deaths from selected causes by state, and Table 18 for smallpox and legal executions (transcribed by MortalGIS)",
                     url="https://www.cdc.gov/nchs/products/vsus.htm",
                     terms="A US federal publication; no terms stated. Transcribed from the CDC/NCHS scans; each value agrees with the table's own sums by sex and by population group."),
    "infant": dict(id="nber_infant_1920_1945", file="hist_infant_deaths_births_1920_1945_state.json",
                   label="Infant Births and Deaths by State, 1920-1945 (workbook by Douglas Norton, from Karen Norberg's transcription of the printed volumes; NBER)",
                   url="https://www.nber.org/research/data",
                   terms="No terms stated in the workbook; it names its author and marks imputed values."),
}

# Years added after a source's own span: (source key, first year, last year, the source whose series it continues). A series gets them only when
# its own ledger row for the extending source is approved; the extending source uses the same printed causes (International List, 4th revision).
EXTENSIONS = [("vsus3738", 1937, 1938, "miller")]

GROUPS = [
    ("graded", "Comparable to today (graded)"),
    ("printed", "As printed, no modern equivalent"),
    ("historical", "Historical causes"),
    ("infants", "Infants"),
]
GRADE_TEXT = {
    "A": "Same meaning as today's measure.",
    "B": "Same disease or concept as today's measure; revisions of the classification move the numbers by small amounts.",
    "B-": "Older grouping that is close to today's measure but not the same (it also holds kidney disease that followed heart disease).",
    "C": "No modern equivalent: shown exactly as the printed volumes grouped it, never on today's scale.",
    "H": "A cause the printed volumes counted separately that has no place in today's list.",
}

# key, label, group, grade, nearest map measure, source columns that are added, note
SERIES = [
    dict(key="all_deaths", label="All registered deaths", group="graded", grade="A", nearest="all_deaths", source="miller", cols=["total_mortality"], share=False,
         note="Deaths from every cause in the states that registered deaths that year. A state outside the registration area has no data, which is not the same as no deaths."),
    dict(key="diabetes", label="Diabetes", group="graded", grade="B", nearest="diabetes", source="miller", cols=["diabetes"], share=True, note=""),
    dict(key="suicide", label="Suicide", group="graded", grade="B", nearest="suicide", source="miller", cols=["suicide"], share=True,
         note="Early under-recording is likely."),
    dict(key="cancer", label="Cancer and tumors", group="graded", grade="B", nearest="cancer", source="miller", cols=["cancer_tumor"], share=True,
         note="The printed group includes some tumors that are not malignant. Not verified."),
    dict(key="flu_pneumonia", label="Influenza and pneumonia", group="graded", grade="B", nearest="flu_pneumonia", source="miller", cols=["influenza", "pneumonia"], share=True,
         note="The two printed columns, influenza and pneumonia, added together for the same state and year. The 1918 pandemic shows in 1918 and 1919."),
    dict(key="kidney", label="Bright's disease and nephritis", group="graded", grade="B-", nearest="kidney", source="miller", cols=["brights_nephritis"], share=True, note=""),
    dict(key="circulatory", label="Circulatory disease (as printed)", group="printed", grade="C", nearest=None, source="miller", cols=["circulatory_disease"], share=True,
         note="Heart disease and stroke are narrower groups; do not compare this with the heart or stroke maps."),
    dict(key="accidents_violence", label="Accidents and violence (as printed)", group="printed", grade="C", nearest=None, source="miller", cols=["accidents_violence"], share=True,
         note="One combined series: falls, motor vehicle, firearm and homicide deaths cannot be split in these tables."),
    dict(key="tuberculosis", label="Tuberculosis, all forms", group="historical", grade="H", nearest=None, source="miller", cols=["all_tb"], share=True, note=""),
    dict(key="typhoid", label="Typhoid fever", group="historical", grade="H", nearest=None, source="miller", cols=["typhoid"], share=True, note=""),
    dict(key="malaria", label="Malaria", group="historical", grade="H", nearest=None, source="miller", cols=["malaria"], share=True, note=""),
    dict(key="small_pox", label="Smallpox", group="historical", grade="H", nearest=None, source="miller", cols=["small_pox"], share=True, note=""),
    dict(key="measles", label="Measles", group="historical", grade="H", nearest=None, source="miller", cols=["measles"], share=True, note=""),
    dict(key="scarlet_fever", label="Scarlet fever", group="historical", grade="H", nearest=None, source="miller", cols=["scarlet_fever"], share=True, note=""),
    dict(key="whooping_cough", label="Whooping cough", group="historical", grade="H", nearest=None, source="miller", cols=["whooping_cough"], share=True, note=""),
    dict(key="diphtheria", label="Diphtheria", group="historical", grade="H", nearest=None, source="miller", cols=["diphtheria"], share=True, note=""),
    dict(key="meningitis", label="Meningitis", group="historical", grade="H", nearest=None, source="miller", cols=["meningitis"], share=True, note=""),
    dict(key="diarrhea_under_2", label="Diarrhea, children under 2", group="historical", grade="H", nearest=None, source="miller", cols=["diarrhea_under_2"], share=True, note=""),
    dict(key="childbirth", label="Childbirth and puerperal causes", group="historical", grade="H", nearest=None, source="miller", cols=["childbirth_puerperal"], share=True, note=""),
    dict(key="infant_deaths", label="Infant deaths (under 1 year)", group="infants", grade="A", nearest="infant_mortality", source="infant", cols=[], share=False,
         note="Deaths before the first birthday, with live births from the same volumes. The birth registration area was smaller than the death area until 1928, so early states may show deaths but no rate."),
]
SERIES_BY_KEY = {s["key"]: s for s in SERIES}

# International List of Causes of Death revisions, adoption years in the US (CDC/NCHS Health, United States, ICD table, read 2026-10-10:
# 1st 1900-1909, 2nd 1910-1920, 3rd 1921-1929, 4th 1930-1938, 5th 1939-1948; https://www.cdc.gov/nchs/hus/sources-definitions/icd.htm).
# A series draws a thin line at each adoption year inside its years and is never spliced across it.
REVISION_YEARS = [1900, 1910, 1921, 1930, 1939]
REVISION_NOTE = ("The classification of causes of death was revised about 1900, 1910, 1921, 1930 and 1939. A line on the chart marks each one inside the years shown. "
                 "No adjustment is applied: a change at a line can come from the new coding, not from health.")

# The publisher's own notes (anomalies_listed_by_publisher in the bundle) that point at a state and year. Our own check adds every state-year where
# the age groups do not add to the printed total (computed by hist_state.py). Those state-years get a marker; the ones whose total is in doubt
# are left out of 'share of deaths'.
PUBLISHER_STATE_NOTES = {
    ("OH", 1916): "The publisher lists Ohio's female ages in 1916 as not adding to the total.",
    ("KY", 1919): "The publisher lists Kentucky's male ages in 1919 as not adding to the total.",
    ("CA", 1920): "The publisher lists California's male ages in 1920 as not agreeing.",
    ("IN", 1920): "The publisher lists Indiana's female ages in 1920 as not agreeing.",
    ("KY", 1920): "The publisher lists Kentucky in 1920 as not agreeing.",
    ("MA", 1935): "The publisher lists Massachusetts in 1935 as having causes that do not sum to the total.",
}
EXTENSION_NOTES = {
    "vsus3738": "1937 and 1938 are not in Miller's file: MortalGIS transcribed them from the printed 1937 and 1938 volumes (Table 19; smallpox and legal "
                "executions from Table 18). Each value was checked against the table's own totals, and every column adds up across the states to the "
                "printed United States total.",
}
YEAR_NOTES = {
    1902: "In the 1902 volume the printed totals by cause and by age and sex do not agree (the publisher's note).",
    1912: "Ages are not split by sex in 1912 and 1913 (not used here).",
}
SHARE_MIN_DEATHS = 20      # a share or rate is not shown on fewer than 20 deaths; the exact count still is
STATE_NAMES = {"AL": "Alabama", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
               "FL": "Florida", "GA": "Georgia", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
               "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
               "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
               "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
               "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
               "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
STATE_FIPS = {"AL": "01", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13", "ID": "16", "IL": "17", "IN": "18",
              "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
              "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42",
              "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"}
