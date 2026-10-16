"""Final Table 19 values for the needed columns, and the national check.
A value is used when its row adds up (resolve4 with the eye-read cells), or when its row was checked by eye on the contact sheets
(eye-read value where it differed, else the OCR value shown on the sheet, which the eye check confirmed).
usage: python3 final_t19.py <resolve3> <resolve4 with manual> <manual> <reviewed rows json> <out json>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import STATES
from reocr2_need import NEED
r3, r4, man, rev, outp = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), json.load(open(sys.argv[4])), sys.argv[5]
reviewed = {tuple(x) for x in rev}
vals, how = {}, {}
for st in ["UNITED STATES"] + STATES:
    for race in "WO":
        settled = race in r4["states"].get(st, {}).get("rowcheck", {})
        for c in NEED:
            k = f"{race}|{c}"
            if settled:
                v, h = r4["states"][st]["values"][k], "row sum"
            elif (st, race) in reviewed:
                v = man.get(st, {}).get(k)
                h = "eye" if v is not None else "ocr+eye"
                if v is None:
                    v = r4["states"][st]["values"].get(k)
                    if v is None:
                        v = r3["states"][st]["values"].get(k)
            else:
                v, h = None, "unchecked"
            vals.setdefault(st, {})[k] = v
            how.setdefault(st, {})[k] = h if v is not None else "missing"
nat = {}
for race in "WO":
    for c in NEED:
        k = f"{race}|{c}"
        us = vals["UNITED STATES"][k]
        parts = [vals[st][k] for st in STATES]
        miss = [st for st in STATES if vals[st][k] is None]
        s = sum(p for p in parts if p is not None)
        nat[k] = {"us": us, "states": s, "missing": miss, "ok": not miss and us == s}
bad = {k: v for k, v in nat.items() if not v["ok"]}
print("national check:", len(nat) - len(bad), "of", len(nat), "columns agree")
for k, v in bad.items():
    print(f"  {k}: US {v['us']} states {v['states']} diff {None if v['us'] is None else v['us'] - v['states']} missing {v['missing']}")
from collections import Counter
print("how:", Counter(h for st in how for h in how[st].values()))
json.dump({"values": vals, "how": how, "national": nat}, open(outp, "w"), indent=0)
