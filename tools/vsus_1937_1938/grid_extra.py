"""Contact sheets for rows that are neither settled by the row sum nor already reviewed (wraps grid_t19 by filtering).
usage: python3 grid_extra.py <year>"""
import json, subprocess, sys
y = sys.argv[1]; yy = y[2:]
S = "/tmp/claude-0/-home-claude/741ee30c-0c9d-58b3-a771-db0c95965534/scratchpad"
rev = {tuple(r) for r in json.load(open(f"{S}/view/g{yy}/rows.json"))}
R4 = json.load(open(f"{S}/t19_{y}_v4r4m.json"))
todo = [[st, r] for st, v in R4["states"].items() for r in "WO" if r not in v["rowcheck"] and (st, r) not in rev]
json.dump(todo, open(f"{S}/view/g{yy}/extra_rows.json", "w"))
print(todo)
