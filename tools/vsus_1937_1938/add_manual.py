"""Merge eye-read values into a manual json. usage: python3 add_manual.py <manual json> 'STATE|R|col=value' ..."""
import json, os, sys
p = sys.argv[1]
m = json.load(open(p)) if os.path.exists(p) else {}
for a in sys.argv[2:]:
    k, v = a.split("=")
    st, r, c = k.split("|")
    old = m.setdefault(st, {}).get(f"{r}|{c}")
    if old is not None and old != int(v):
        print("changed", k, old, "->", v)
    m[st][f"{r}|{c}"] = int(v)
json.dump(m, open(p, "w"), indent=1, sort_keys=True)
print(sum(len(x) for x in m.values()), "values")
