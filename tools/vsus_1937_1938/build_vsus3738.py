"""Build data_manual/hist_state/hist_vsus_1937_1938_state.json from the resolved Table 19 readings and the Table 18 lines.

For each state and year a Miller column gets a value only when every Table 19 column it needs is settled for both White and Other
(two of the table's four derivations agree, or a value read by eye on the page), and that state's White and Other rows both add across
(total deaths = sum of the cause columns). DC is read but left out (Miller's panel is 48 states).
Checks printed: the states (with DC) add up to the United States line, column by column; each value against Miller's 1936 value.
usage: python3 build_vsus3738.py <out json> <miller bundle> <table18 json> <year>:<final json> ...
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import COLS, STATES

MILLER = {  # Miller column: Table 19 columns added (White + Other); smallpox and 196-198 come from Table 18
    "total_mortality": ["total"], "typhoid": ["c1_2"], "measles": ["c7"], "scarlet_fever": ["c8"], "whooping_cough": ["c9"],
    "diphtheria": ["c10"], "influenza": ["c11"], "meningitis": ["c18"], "all_tb": ["c23", "c24_32"], "malaria": ["c38"],
    "cancer_tumor": ["c45_53"], "diabetes": ["c59"], "circulatory_disease": ["c90r", "c94", "c95"], "pneumonia": ["c107_109"],
    "diarrhea_under_2": ["c119"], "brights_nephritis": ["c130_132"], "childbirth_puerperal": ["c140s", "c141s"], "suicide": ["c163_171"],
    "accidents_violence": ["c172_175", "c210", "c206s", "c176s"],  # + Table 18 list 196-198
    "small_pox": [],  # Table 18 only
}
out_p, miller_p, t18_p = sys.argv[1:4]
runs = [a.split(":") for a in sys.argv[4:]]  # year:final json (from final_t19.py)
M = json.load(open(miller_p))
T18 = json.load(open(t18_p))
code = {v.upper(): k for k, v in M["state_names"].items()}
code["DISTRICT OF COLUMBIA"] = "DC"
data, checks, report = {}, {}, []
from collections import Counter
for y, fin_p in runs:
    F = json.load(open(fin_p))
    nat = F["national"]
    okc = sum(1 for v in nat.values() if v["ok"])
    report.append(f"{y}: national check {okc} of {len(nat)} White/Other columns: the states (with DC) add up to the United States line")
    hows = Counter(h for st, hs in F["how"].items() if st != "UNITED STATES" for h in hs.values())
    report.append(f"{y}: cells settled by the row sum {hows.get('row sum', 0)}, checked by eye on the page {hows.get('ocr+eye', 0) + hows.get('eye', 0)} "
                  f"(of which {hows.get('eye', 0)} read by eye where the OCR was wrong or blank), missing {hows.get('missing', 0) + hows.get('unchecked', 0)}")
    if okc != len(nat):
        raise SystemExit(f"! {y}: national check fails; fix the readings first")
    for st in STATES:
        if st == "DISTRICT OF COLUMBIA":
            continue
        cd = code[st]
        v = F["values"][st]
        row = {}
        for mc, cols in MILLER.items():
            if mc == "small_pox":
                row[mc] = T18["smallpox"][y].get(cd, 0)
                continue
            xs = [v.get(f"{r}|{c}") for c in cols for r in "WO"]
            row[mc] = None if None in xs else sum(xs)
            if mc == "accidents_violence" and row[mc] is not None:
                row[mc] += T18["list_196_198"][y].get(cd, 0)
        data.setdefault(cd, {})[y] = row
    checks[y] = {"national_columns_agreeing": okc, "how": dict(hows)}
# comparison with Miller 1936 (a gross-error screen: ratio outside 0.6-1.6 on values of 50 or more is listed)
flags = []
for cd, ys in data.items():
    m36 = M["data"].get(cd, {}).get("1936", {})
    for y, row in ys.items():
        for mc, x in row.items():
            a = m36.get(mc)
            if x is None or a is None or max(a, x) < 50:
                continue
            r = x / a if a else 9
            if not 0.6 <= r <= 1.6:
                flags.append(f"{cd} {y} {mc}: {x} vs 1936 {a}")
report.append(f"Miller 1936 screen: {len(flags)} values outside 0.6-1.6x " + "; ".join(flags[:40]))
filled = sum(1 for ys in data.values() for row in ys.values() for x in row.values() if x is not None)
total = sum(len(row) for ys in data.values() for row in ys.values())
bundle = {
    "id": "vsus_tables_1937_1938", "kind": "state-year",
    "geography": "state (48 states; the District of Columbia is read but left out, as in Miller's panel)",
    "source": "Vital Statistics of the United States, 1937 and 1938, Part I (US Bureau of the Census): Table 19, deaths from selected causes by race, sex "
              "and population groups, each state (White + Other); Table 18 for smallpox (List No. 6) and List Nos. 196-198",
    "url": "https://www.cdc.gov/nchs/products/vsus.htm",
    "terms": "US federal publication; no terms stated on the CDC/NCHS page.",
    "method": "Read by OCR (tesseract) from the CDC/NCHS scans, cell by cell, then settled with the table's own sums: a state total is kept when at least "
              "two of four derivations agree (the printed total; male + female; the three population groups; the groups' male + female), and a state "
              "is kept only when its White and Other rows both add across (total deaths = the sum of the cause columns). Cells the sums could not "
              "settle were read by eye on the page (contact sheets of every unsettled row, and of every column whose states did not add up "
              "to the United States line). Every column used adds up across the 48 states and DC to the printed United States line, "
              "for White and for Other, in both years. Table 18 lines were read by eye.",
    "columns": list(MILLER), "column_map": {k: (v if v else "Table 18") for k, v in MILLER.items()},
    "checks": {"filled": f"{filled} of {total} state-year-column values", "report": report, "by_year": checks},
    "note": "Miller's accidents_violence (List 172-198) = homicide 172-175 + motor vehicle 210, 206/208/211 + other accidents 176-195/201-214 + "
            "Table 18 List 196-198. circulatory_disease = diseases of the heart 90-95 (three Table 19 columns). Not used by the build until approved.",
    "data": data,
}
json.dump(bundle, open(out_p, "w"), indent=1)
print("\n".join(report))
print(f"wrote {out_p}: {filled} of {total} values")
