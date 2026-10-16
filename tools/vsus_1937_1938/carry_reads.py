"""Carry single-cell readings from an older assembled json to a re-assembled one, matching rows by (page, y) rather than by row name.
usage: python3 carry_reads.py <old assembled> <new assembled>"""
import json, sys
old, new = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
moved = changed = 0
for st, ob in old["blocks"].items():
    nb = new["blocks"].get(st)
    if nb is None:
        if st == "UNITED STATES":
            new["blocks"][st] = ob
        continue
    pos = {(r["_page"], r["_y"]): k for k, r in nb["rows"].items()}
    for k, cols in ob.get("reads", {}).items():
        r = ob["rows"].get(k)
        nk = pos.get((r["_page"], r["_y"])) if r else None
        if nk is None:
            continue
        nb.setdefault("reads", {})[nk] = cols
        moved += 1
        changed += nk != k
json.dump(new, open(sys.argv[2], "w"))
print("rows with readings carried:", moved, "renamed:", changed)
