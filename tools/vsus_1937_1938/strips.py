import sys, csv, io, re, subprocess
import numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from rules import vrules

def ocr_lines(img, whitelist=None, psm=6):
    """[(y_center, text)] for each text line tesseract finds in a PIL image."""
    buf = io.BytesIO(); img.save(buf, format="PNG")
    args = ["tesseract", "stdin", "stdout", "--psm", str(psm)]
    if whitelist:
        args += ["-c", f"tessedit_char_whitelist={whitelist}"]
    out = subprocess.run(args + ["tsv"], input=buf.getvalue(), capture_output=True).stdout.decode()
    rows = list(csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE))
    lines = {}
    for r in rows:
        if r["level"] != "5" or not r["text"].strip():
            continue
        k = (r["block_num"], r["par_num"], r["line_num"])
        lines.setdefault(k, []).append(r)
    res = []
    for ws in lines.values():
        ws.sort(key=lambda w: int(w["left"]))
        y = np.mean([int(w["top"]) + int(w["height"]) / 2 for w in ws])
        res.append((y, " ".join(w["text"] for w in ws), min(float(w["conf"]) for w in ws)))
    return sorted(res)

# Column rule spacing of Table 19 (VSUS 1937 and 1938, 300 dpi): left pages carry the row labels and 17 numeric columns, right pages 21.
LEFT_GAPS = [131, 97, 88, 89, 101, 89, 101, 89, 113, 102, 114, 114, 102, 88, 114, 89, 114]
RIGHT_GAPS = [100, 114, 102, 102, 115, 115, 103, 89, 102, 102, 102, 115, 102, 101, 116, 102, 89, 102, 89, 102]


def fit_rules(det, w):
    """Snap the detected rules to the known column template (handles missing, doubled or stray rules)."""
    best = None
    for side, gaps in (("left", LEFT_GAPS), ("right", RIGHT_GAPS)):
        rel = [0]
        for g in gaps:
            rel.append(rel[-1] + g)
        for x0 in range(0, w - rel[-1]):
            hits = sum(1 for r in rel if any(abs(x0 + r - d) <= 6 for d in det))
            if best is None or hits > best[0]:
                best = (hits, side, x0, rel)
    hits, side, x0, rel = best
    out = []
    for r in rel:
        near = [d for d in det if abs(x0 + r - d) <= 6]
        out.append(min(near, key=lambda d: abs(x0 + r - d)) if near else x0 + r)
    return side, out, hits


LEFT_CODES = ["1,2", "7", "8", "9", "10", "11", "15", "16", "18", "23", "24-32", "34", "38", "45-53", "56", "57"]


def fit_by_codes(im, w, h):
    """Column template placed by the printed column codes ('1,2  7  8 ... 57'); left pages only have them in this form."""
    band = im.crop((0, int(h * 0.17), w, int(h * 0.26)))
    buf = io.BytesIO(); band.save(buf, format="PNG")
    out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "11", "tsv"], input=buf.getvalue(), capture_output=True).stdout.decode()
    toks = [r for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE) if r["level"] == "5" and r["text"].strip()]
    centers = {}
    for t in toks:
        txt = t["text"].strip().replace(".", ",")
        if txt in LEFT_CODES and txt not in centers:
            centers[txt] = int(t["left"]) + int(t["width"]) / 2
    rel = [0]
    for g in LEFT_GAPS:
        rel.append(rel[-1] + g)
    mids = [(rel[i] + rel[i + 1]) / 2 for i in range(1, len(rel) - 1)] + [rel[-1] + 57]  # codes sit over columns 2..17
    best = None
    for x0 in range(0, w - rel[-1]):
        err = sum(min(abs(x0 + mids[LEFT_CODES.index(k)] - c), 40) for k, c in centers.items())
        if best is None or err < best[0]:
            best = (err, x0)
    x0 = best[1]
    return "left", [x0 + r for r in rel], len(centers)


def page_cells(path, top=None, bottom=None, scale=2):
    im = Image.open(path).convert("L")
    w, h = im.size
    det, _ = vrules(path)
    if len(det) < 6:  # faint scan: lower the bar
        det, _ = vrules(path, thr=205, minrun=250)
    side, rules, hits = fit_rules(det, w)
    if hits < 4:  # pages printed without column rules: place the template by the column code row under the headings
        side, rules, hits = fit_by_codes(im, w, h)
    if top is None:  # just below the last full-width rule under the column headings
        a = np.array(im) < 150
        x0, x1 = rules[0], rules[-1]
        frac = a[:, x0:x1].mean(axis=1)
        ys = [y for y in range(int(h * 0.15), int(h * 0.245)) if frac[y] > 0.6]
        top = (max(ys) + 6) if ys else int(h * 0.215)
    bottom = bottom or int(h * 0.97)
    cols = []
    # label strip (left of the first rule), only on pages that have one
    if side == "left":
        lab = im.crop((0, top, rules[0] - 2, bottom))
        cols.append(("label", [(top + y, t, c) for y, t, c in ocr_lines(lab)]))
    edges = rules + [min(w - 20, rules[-1] + (115 if side == "left" else 105))]
    for i in range(len(edges) - 1):
        x0, x1 = edges[i] + 4, edges[i + 1] - 3
        strip = im.crop((x0, top, x1, bottom))
        strip = strip.resize((strip.width * scale, strip.height * scale), Image.LANCZOS)
        ls = ocr_lines(strip, whitelist="0123456789,-")
        cols.append((i, [(top + y / scale, t, c) for y, t, c in ls]))
    return rules, cols, side, hits

if __name__ == "__main__":
    rules, cols = page_cells(sys.argv[1])
    for k, ls in cols[:4]:
        print(k, [(int(y), t) for y, t, c in ls][:30])
