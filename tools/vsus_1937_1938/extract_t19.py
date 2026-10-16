"""OCR one Table 19 page (VSUS 1937/1938 Part I) into blocks of rows of column values.
usage: python3 extract_t19.py <pdf> <page> <outdir>
Writes <outdir>/p<page>.json: {page, rules, label_side, rows: [{y, label, vals:[str per column]}]}"""
import json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strips import page_cells

pdf, page, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(outdir, exist_ok=True)
png = os.path.join(outdir, f"p{page}")
subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "300", "-gray", "-png", "-singlefile", pdf, png], check=True)
png += ".png"
# deskew: pages scanned at an angle of 0.25 degrees or more are rotated level first; the levelled page is kept as re_<page>.png for the
# single-cell readings and the contact sheets
from PIL import Image
from skew import skew
angle = skew(png, -3, 3, 0.05)
if abs(angle) >= 0.25:
    im = Image.open(png).convert("L").rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    im.save(png)
    im.save(os.path.join(outdir, f"re_{page}.png"))
rules, cols, side, hits = page_cells(png)
label = dict(cols).get("label")
numcols = [ls for k, ls in cols if k != "label"]

# per-column vertical offset relative to the first numeric column (scans can be slightly rotated)
ref = [y for y, t, c in numcols[0]]
def best_offset(ls):
    ys = [y for y, t, c in ls]
    best, bo = -1, 0
    for o in range(-14, 15):
        n = sum(1 for y in ys if min((abs(y + o - r) for r in ref), default=99) < 7)
        if n > best:
            best, bo = n, o
    return bo
offs = [0] + [best_offset(ls) for ls in numcols[1:]]
# row anchors: label lines on a left page, else the union of all column lines
anchors = []
if label:
    lo = best_offset([(y, t, c) for y, t, c in label])
    anchors = [(y + lo, t) for y, t, c in label]
else:
    ys = sorted(y + offs[i] for i, ls in enumerate(numcols) for y, t, c in ls)
    groups = []
    for y in ys:
        if groups and y - groups[-1][-1] < 9:
            groups[-1].append(y)
        else:
            groups.append([y])
    anchors = [(float(np.median(g)), "") for g in groups if len(g) >= 2]
rows = []
for ya, lab in anchors:
    vals = []
    for i, ls in enumerate(numcols):
        hit = [t for y, t, c in ls if abs(y + offs[i] - ya) < 9]
        vals.append(" ".join(hit))
    rows.append({"y": round(ya, 1), "label": lab, "vals": vals})
json.dump({"page": page, "deskew": angle, "rules": rules, "side": side, "rule_hits": hits, "label_side": bool(label), "offsets": offs, "rows": rows},
          open(os.path.join(outdir, f"p{page}.json"), "w"), indent=0)
os.remove(png)
print(page, "rows", len(rows), "cols", len(numcols), "label" if label else "right")
