"""Resolve White and Other state totals per column from two OCR reads per cell, using the table's own sums.
Each cell may carry two readings (strip OCR, single-cell OCR); an empty reading counts as a dash (0). For each total we form the possible
values of four derivations (the total row itself; male + female; the population groups; the groups' male + female) and accept a value only
when at least two derivations can produce it and no other value is supported as well. The White and Other rows must then also add across:
total deaths = the sum of all cause columns. Unsettled items are listed for a look at the page.
usage: python3 resolve2_t19.py <assembled json> <out json>"""
import itertools, json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from assemble_t19 import COLS, STATES, val

d = json.load(open(sys.argv[1]))


def cands(b, key, c):
    """Possible values of one cell: if two of its readings agree, that value; otherwise every reading (empty = dash = 0)."""
    row = b["rows"].get(key)
    if row is None:
        return None
    vals = []
    v1 = val(row.get(c))
    vals.append(v1 if v1 is not None else (0 if not (row.get(c) or "").strip() else None))
    for t, txt in sorted(b.get("reads", {}).get(key, {}).get(c, {}).items()):
        v = val(txt) if txt else 0
        vals.append(v)
    rr = b.get("reread", {}).get(key, {}).get(c)
    if rr is not None:
        vals.append(val(rr["second"]) if rr["second"] else 0)
    vals = [v for v in vals if v is not None]
    if not vals:
        return {0}
    from collections import Counter
    cnt = Counter(vals).most_common()
    if len(vals) >= 2 and cnt[0][1] >= 2 and (len(cnt) == 1 or cnt[0][1] > cnt[1][1]):
        return {cnt[0][0]}
    return set(vals)


def sums(sets):
    if any(x is None for x in sets):
        return None
    out = set()
    for combo in itertools.product(*sets):
        out.add(sum(combo))
        if len(out) > 64:
            break
    return out


out, todo = {}, []
for st in (["UNITED STATES"] if "UNITED STATES" in d["blocks"] else []) + STATES:
    b = d["blocks"].get(st)
    if not b:
        continue
    present = set(b["rows"])
    groups = [g for g in ("C10", "C2", "R") if g + "W" in present]
    res = {}
    for race in ("W", "O"):
        for c in COLS:
            der = {"ocr": cands(b, race, c)}
            der["sex"] = sums([cands(b, "M" + race, c), cands(b, "F" + race, c)])
            der["pop"] = sums([cands(b, g + race, c) for g in groups]) if groups else None
            der["popsex"] = sums([cands(b, g + s + race, c) for g in groups for s in "MF"]) if groups else None
            support = {}
            for k, vs in der.items():
                for v in vs or ():
                    support.setdefault(v, set()).add(k)
            ranked = sorted(support.items(), key=lambda kv: -len(kv[1]))
            if ranked and len(ranked[0][1]) >= 2 and (len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1])):
                res[(race, c)] = ranked[0][0]
            else:
                res[(race, c)] = None
                todo.append({"state": st, "race": race, "col": c, "support": {str(v): sorted(k) for v, k in ranked[:4]}})
    rowcheck = {}
    for race in ("W", "O"):
        vs = [res[(race, c)] for c in COLS]
        if None not in vs:
            rowcheck[race] = [vs[0], sum(vs[1:])]
    out[st] = {"values": {f"{r}|{c}": v for (r, c), v in res.items()}, "rowcheck": rowcheck, "pages": b["pages"]}
json.dump({"states": out, "todo": todo}, open(sys.argv[2], "w"), indent=0)
ok = sum(1 for st in out for v in out[st]["values"].values() if v is not None)
print("resolved", ok, "of", len(out) * 2 * len(COLS), "; open", len(todo))
print("row-sum failures:", {st: v["rowcheck"] for st, v in out.items() if any(a != b for a, b in v["rowcheck"].values())})
