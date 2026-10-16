"""Add the UNITED STATES block (24 rows: W, O, MW, MO, FW, FO, C10W ... RFO) of Table 19 to an assembled json, from the first spread.
The national figures are used only as a check: the states' resolved values must add up to them, column by column.
usage: python3 us_block_t19.py <ocr dir> <assembled json> <left page>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import COLS, LEFT, RIGHT, ROWS, pair_rows, val

odir, asmp, lp = sys.argv[1], sys.argv[2], int(sys.argv[3])
L = json.load(open(os.path.join(odir, f"p{lp}.json")))["rows"]
R = json.load(open(os.path.join(odir, f"p{lp + 1}.json")))["rows"]
start = next(i for i, r in enumerate(L) if "Both" in r["label"] or "sexes" in r["label"])
rows = L[start:start + len(ROWS)]
matched, dy, n = pair_rows(L, R)
mm = dict(zip([id(r) for r in L], matched))
A = json.load(open(asmp))
b = {"pages": [lp, lp + 1], "rows": {}}
for key, lr in zip(ROWS, rows):
    rr = mm[id(lr)]
    lv = lr["vals"][:len(LEFT)]
    rv = rr["vals"][:len(RIGHT)] if rr else [""] * len(RIGHT)
    b["rows"][key] = {c: v for c, v in zip(COLS, lv + rv)}
    b["rows"][key].update({"_label": lr["label"], "_page": lp, "_y": lr["y"], "_ry": rr["y"] if rr else None})
b["parsed"] = {r: {c: val(b["rows"].get(r, {}).get(c)) for c in COLS} for r in ROWS}
old = A["blocks"].get("UNITED STATES", {})
if "reads" in old:
    b["reads"] = old["reads"]
A["blocks"]["UNITED STATES"] = b
json.dump(A, open(asmp, "w"))
print("US block:", dy, n, "paired;", [(k, b["rows"][k]["_label"][:22]) for k in ("W", "O", "C10W", "RFO")])
