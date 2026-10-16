"""Assemble OCR'd Table 19 spreads into state blocks and check them against the table's own sums.
usage: python3 assemble_t19.py <ocr dir> <out json>"""
import glob, json, re, sys
from collections import defaultdict

LEFT = ["total", "c1_2", "c7", "c8", "c9", "c10", "c11", "c15", "c16", "c18", "c23", "c24_32", "c34", "c38", "c45_53", "c56", "c57"]
RIGHT = ["c59", "c82", "c90r", "c94", "c95", "c107_109", "c119", "c120", "c121", "c122", "c124", "c130_132", "c140s", "c141s", "c157",
         "c163_171", "c172_175", "c210", "c206s", "c176s", "other"]
COLS = LEFT + RIGHT
STATES = ["ALABAMA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT", "DELAWARE", "DISTRICT OF COLUMBIA", "FLORIDA", "GEORGIA",
          "IDAHO", "ILLINOIS", "INDIANA", "IOWA", "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", "MINNESOTA",
          "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA",
          "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS",
          "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING"]
ROWS = ["W", "O", "MW", "MO", "FW", "FO", "C10W", "C10O", "C10MW", "C10MO", "C10FW", "C10FO", "C2W", "C2O", "C2MW", "C2MO", "C2FW", "C2FO",
        "RW", "RO", "RMW", "RMO", "RFW", "RFO"]
IDENT = [("W", ["MW", "FW"]), ("O", ["MO", "FO"]), ("W", ["C10W", "C2W", "RW"]), ("O", ["C10O", "C2O", "RO"]),
         ("C10W", ["C10MW", "C10FW"]), ("C10O", ["C10MO", "C10FO"]), ("C2W", ["C2MW", "C2FW"]), ("C2O", ["C2MO", "C2FO"]),
         ("RW", ["RMW", "RFW"]), ("RO", ["RMO", "RFO"]), ("MW", ["C10MW", "C2MW", "RMW"]), ("FW", ["C10FW", "C2FW", "RFW"]),
         ("MO", ["C10MO", "C2MO", "RMO"]), ("FO", ["C10FO", "C2FO", "RFO"])]


def val(s):
    s = (s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"[-\s]+", s):
        return 0
    t = s.replace(",", "").replace(" ", "").strip("-")
    return int(t) if t.isdigit() else None


import difflib


def classify(label):
    """Kind of a row label: O (Other), M, F, C10, C2, R, or skip (footnotes)."""
    raw = label.strip().lstrip(",.'`‘’ :;|")
    if not raw or raw[0].isdigit() or raw.startswith(("*", "Refer", "Exclu", "1/", "2/")) or "Refer to" in raw or "xclu" in raw:
        return "skip"
    word = re.sub(r"[^A-Za-z]", "", raw.split("-")[0].split(" ")[0]).upper()
    if not word:
        return "skip"
    scores = {k: difflib.SequenceMatcher(None, word, k).ratio() for k in ("OTHER", "MALE", "FEMALE", "CITIES", "RURAL")}
    best = max(scores, key=scores.get)
    if scores[best] < 0.5:
        return "skip"
    if best == "CITIES":
        u = raw.upper()
        return "C10" if ("MORE" in u or "10,000 OR" in u or "OR MO" in u) else "C2"
    return {"OTHER": "O", "MALE": "M", "FEMALE": "F", "RURAL": "R"}[best]


def norm_label(l):
    u = re.sub(r"[^A-Z ]", " ", l.upper())
    return re.sub(r"\s+", " ", u).strip()


def state_of(label):
    """State named at the start of a label written in capitals ('ALABAMA----White'), allowing OCR slips ('KENTUCEY', '¥FLORIDA')."""
    m = re.match(r"\W*([A-Z][A-Z .]{2,}?)\s*[-~—=_.]{2,}", label.strip().lstrip("¥X*#,.'` ") if not label.strip().startswith(("X", "¥")) else label.strip()[1:])
    cands = []
    for raw in {label.strip(), label.strip()[1:]}:
        m = re.match(r"\W*([A-Z][A-Z .]{2,}?)\s*[-~—=_.:,]{2,}", raw)
        if m and m.group(1).replace(" ", "").replace(".", "").isupper() and len(m.group(1).replace(" ", "")) >= 4:
            cands.append(m.group(1).replace(".", " ").strip())
    best = (0, None)
    for c in cands:
        if "CON" == c[-3:] and len(c) > 6:
            c = c[:-3].strip()
        for s in STATES:
            r = difflib.SequenceMatcher(None, c.replace(" ", ""), s.replace(" ", "")).ratio()
            if r > best[0]:
                best = (r, s)
    return best[1] if best[0] >= 0.8 else None


def pair_rows(L, R):
    """Match right-page rows to left-page rows: y_right = a * y_left + b (the two pages are scanned separately)."""
    ly = [r["y"] for r in L]
    ry = [r["y"] for r in R]
    best = (-1, 1.0, 0)
    for a in [0.97 + 0.0025 * i for i in range(25)]:
        for b in range(-260, 261, 2):
            n = sum(1 for y in ly if any(abs(a * y + b - z) < 7 for z in ry))
            if n > best[0]:
                best = (n, a, b)
    n, a, b = best
    out = []
    for r in L:
        t = a * r["y"] + b
        cand = [z for z in R if abs(t - z["y"]) < 10]
        out.append(min(cand, key=lambda z: abs(t - z["y"])) if cand else None)
    return out, f"{a:.4f}*y{b:+d}", n


def main(d, outp):
    pages = {json.load(open(f))["page"]: json.load(open(f)) for f in glob.glob(f"{d}/p*.json")}
    blocks = {}
    log = []
    cur, pos, started, last = None, 0, False, None
    log_ = log
    for p in sorted(pages):
        P = pages[p]
        if P["side"] != "left" or (p + 1) not in pages or pages[p + 1]["side"] != "right":
            continue
        L, R = P["rows"], pages[p + 1]["rows"]
        matched, dy, n = pair_rows(L, R)
        log.append(f"spread {p}-{p+1}: dy {dy}, {n}/{len(L)} rows paired")
        for lr, rr in zip(L, matched):
            lab = lr["label"].strip()
            if re.search(r"ontin|ontim|\bCon\b|Exclu|xclu|xelus|clusive|Refer|efer to", lab) or re.match(r"\W*\d+\s*/", lab) or not re.search(r"[A-Za-z]", lab):
                continue
            st = state_of(lab)
            if st == "ALABAMA":
                started = True
            if not started:
                continue
            need = 6 if cur == "DISTRICT OF COLUMBIA" else len(ROWS)
            kind = classify(lab) if not st else "S"
            if st:
                if st == cur and pos == 1 and blocks[cur]["rows"].get("W", {}).get("_label", "") == lab:
                    pass
                else:
                    cur, pos = st, 0  # a header read clearly always starts its block (undoes a wrong guess)
            elif cur is None or pos >= need:
                if kind in ("O", "M", "F", "C10", "C2", "R"):
                    log(f"  extra row after {cur} complete, dropped: page {p} y {lr['y']} ({lab[:30]})") if False else log_.append(f"  extra row after {cur}, dropped: page {p} y {lr['y']} ({lab[:30]})")
                    continue
                nxt = STATES[STATES.index(cur) + 1] if cur and STATES.index(cur) + 1 < len(STATES) else None
                if nxt is None:
                    continue
                log.append(f"  header not read, taken as {nxt}: page {p} y {lr['y']} ({lab[:30]})")
                cur, pos = nxt, 0
            if pos == 0:
                blocks[cur] = {"pages": [p, p + 1], "rows": {}}
            need = 6 if cur == "DISTRICT OF COLUMBIA" else len(ROWS)
            # a population-group heading read clearly fixes the position: rows lost at a page break are left empty, not shifted
            strict = ("R" if re.match(r"\W*R[uo]r[ae]l", lab) else "C10" if re.search(r"ities.*10,0|10,000 or", lab)
                      else "C2" if re.search(r"ities.*2,5|2,500 to", lab) else None)
            # a gap of two or more row heights on the same page means rows were not read: leave them empty
            if pos > 0 and last and last[0] == p and lr["y"] - last[1] > 40:
                miss = round((lr["y"] - last[1]) / 25.5) - 1
                if miss > 0 and pos + miss < need:
                    log.append(f"  {cur}: {miss} row(s) {ROWS[pos:pos + miss]} not read (gap on page {p} at y {lr['y']}), left empty")
                    pos += miss
            if strict and need == len(ROWS):
                start = {"C10": 6, "C2": 12, "R": 18}[strict]
                if pos < start:
                    log.append(f"  {cur}: rows {ROWS[pos:start]} not read (page {p}), left empty")
                    pos = start
            if pos >= need:
                continue
            key = ROWS[pos]
            pos += 1
            last = (p, lr["y"])
            lv = lr["vals"][:len(LEFT)]
            rv = rr["vals"][:len(RIGHT)] if rr else [""] * len(RIGHT)
            blocks[cur]["rows"][key] = {c: v for c, v in zip(COLS, lv + rv)}
            blocks[cur]["rows"][key].update({"_label": lab, "_page": p, "_y": lr["y"], "_ry": rr["y"] if rr else None})
    # parse and check
    report = {}
    for st, b in blocks.items():
        R_ = {r: {c: val(b["rows"].get(r, {}).get(c)) for c in COLS} for r in ROWS}
        bad = []
        for c in COLS:
            for parent, kids in IDENT:
                vals = [R_[parent][c]] + [R_[k][c] for k in kids]
                if None in vals:
                    continue
                if vals[0] != sum(vals[1:]):
                    bad.append((c, parent, kids, vals))
        # row sums: total = all causes
        rowbad = []
        for r in ROWS:
            vs = [R_[r][c] for c in COLS[1:]]
            if R_[r]["total"] is not None and None not in vs and sum(vs) != R_[r]["total"]:
                rowbad.append((r, R_[r]["total"], sum(vs)))
        missing = [(r, c) for r in ROWS for c in COLS if R_[r][c] is None]
        report[st] = {"rows_found": len(b["rows"]), "identity_fail": len(bad), "rowsum_fail": len(rowbad), "missing": len(missing),
                      "examples": bad[:4], "rowbad": rowbad[:4]}
        b["parsed"] = R_
    json.dump({"blocks": blocks, "report": report, "log": log}, open(outp, "w"))
    for line in log:
        print(line)
    for st in STATES:
        r = report.get(st)
        print(st, r and {k: r[k] for k in ("rows_found", "identity_fail", "rowsum_fail", "missing")})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
