"""Settle Table 19 state totals (White, Other) using the four derivations per cell AND the row sum (total deaths = sum of the 37 cause columns).

Step 1 (as resolve3): a cell's value is decided when at least two of its derivations (printed total; male + female; population groups;
groups by sex) agree and no other value has as much support.
Step 2: in a row whose cells are not all decided, or whose decided cells do not add up, look for values that make the row add up:
  open cells may take any value one of their derivations supports; if that is not enough, ONE decided cell held by only two derivations
  may also take another supported value. A solution is kept only if it is the only one. Every value kept is still one some reading supports.
Rows that still do not add up are listed for a look at the page (with the candidates), and their cells are not used.
usage: python3 resolve4_t19.py <assembled json> <out json> [manual json]
  manual json: {"STATE": {"W|col": value, ...}} values read by eye on the page; they replace the OCR derivations for those cells."""
import itertools, json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import COLS, STATES, val

d = json.load(open(sys.argv[1]))
manual = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else {}


def cands(b, key, c):
    row = b["rows"].get(key)
    if row is None:
        return None
    vals = []
    v1 = val(row.get(c))
    vals.append(v1 if v1 is not None else (0 if not (row.get(c) or "").strip() else None))
    for t, txt in sorted(b.get("reads", {}).get(key, {}).get(c, {}).items()):
        vals.append(val(txt) if txt else 0)
    rr = b.get("reread", {}).get(key, {}).get(c)
    if rr is not None:
        vals.append(val(rr["second"]) if rr["second"] else 0)
    vals = [v for v in vals if v is not None]
    if not vals:
        return {0}
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


def support(b, race, c, groups):
    der = {"ocr": cands(b, race, c), "sex": sums([cands(b, "M" + race, c), cands(b, "F" + race, c)])}
    der["pop"] = sums([cands(b, g + race, c) for g in groups]) if groups else None
    der["popsex"] = sums([cands(b, g + s + race, c) for g in groups for s in "MF"]) if groups else None
    sup = {}
    for k, vs in der.items():
        for v in vs or ():
            sup.setdefault(v, set()).add(k)
    return sorted(sup.items(), key=lambda kv: (-len(kv[1]), kv[0]))


out, todo, how = {}, [], Counter()
for st in (["UNITED STATES"] if "UNITED STATES" in d["blocks"] else []) + STATES:
    b = d["blocks"].get(st)
    if not b:
        continue
    present = set(b["rows"])
    groups = [g for g in ("C10", "C2", "R") if g + "W" in present]
    res, src = {}, {}
    for race in ("W", "O"):
        sups = {}
        for c in COLS:
            mk = f"{race}|{c}"
            if mk in manual.get(st, {}):
                sups[c] = [(manual[st][mk], {"page"})]
                res[(race, c)] = manual[st][mk]
                src[mk] = "page"
                continue
            r = support(b, race, c, groups)
            sups[c] = r
            if r and len(r[0][1]) >= 2 and (len(r) == 1 or len(r[0][1]) > len(r[1][1])):
                res[(race, c)] = r[0][0]
                src[mk] = "+".join(sorted(r[0][1]))
            else:
                res[(race, c)] = None
        # step 2: the row sum
        def adds(vals):
            return None not in vals.values() and vals["total"] == sum(vals[c] for c in COLS[1:])
        cur = {c: res[(race, c)] for c in COLS}
        if None in cur.values() or not adds(cur):
            opened = [c for c in COLS if cur[c] is None]
            opts = {c: [v for v, _ in sups[c][:4]] for c in opened}
            if any(not opts[c] for c in opened):
                sols = []
            else:
                sols = []
                for combo in itertools.product(*[opts[c] for c in opened]):
                    t = dict(cur); t.update(zip(opened, combo))
                    if adds(t):
                        sols.append(t)
                        if len(sols) > 1:
                            break
            step = "open cells"
            if not sols and len(opened) <= 3:
                weak = [c for c in COLS if cur[c] is not None and src.get(f"{race}|{c}") != "page" and len(sups[c][0][1]) == 2 and len(sups[c]) > 1]
                for w in weak:
                    for alt, why in sups[w][1:4]:
                        for combo in itertools.product(*[opts[c] for c in opened]) if opened else [()]:
                            t = dict(cur); t.update(zip(opened, combo)); t[w] = alt
                            if adds(t):
                                sols.append(t)
                    if len(sols) > 1:
                        break
                step = "one weak cell changed"
            if len(sols) == 1:
                for c in COLS:
                    if res[(race, c)] != sols[0][c]:
                        src[f"{race}|{c}"] = f"row sum ({step})"
                    res[(race, c)] = sols[0][c]
                how[step] += 1
            else:
                todo.append({"state": st, "race": race, "solutions": len(sols), "open": opened,
                             "decided_sum": None if None in cur.values() else [cur["total"], sum(cur[c] for c in COLS[1:])],
                             "candidates": {c: {str(v): sorted(k) for v, k in sups[c][:4]} for c in COLS if c in opened or len(sups[c]) > 1}})
                for c in COLS:  # an unsettled row is not used
                    res[(race, c)] = None
    rowcheck = {}
    for race in ("W", "O"):
        vs = [res[(race, c)] for c in COLS]
        if None not in vs:
            rowcheck[race] = [vs[0], sum(vs[1:])]
    out[st] = {"values": {f"{r}|{c}": v for (r, c), v in res.items()}, "how": src, "rowcheck": rowcheck, "pages": b["pages"]}
json.dump({"states": out, "todo": todo}, open(sys.argv[2], "w"), indent=0)
nrows = sum(1 for st in out if st != "UNITED STATES" for r in out[st]["rowcheck"])
print(f"rows settled {nrows} of {2 * len([s for s in out if s != 'UNITED STATES'])}; by the row sum: {dict(how)}; unsettled rows {len(todo)}")
print("unsettled:", [(t["state"], t["race"], t["solutions"], t["open"][:5]) for t in todo])
