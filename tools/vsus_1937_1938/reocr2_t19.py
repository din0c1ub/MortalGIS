"""Extra single-cell readings for Table 19 (adds to b['reads'][row][col] a list of readings; never overwrites the first read).
usage: python3 reocr2_t19.py <pdf> <ocr dir> <assembled json> <resolved json> <tag> [all]
tag 'b' = cell scaled x3, psm 7; tag 'c' = binarised, scaled x4, psm 7. With 'all', every needed column of every state is read."""
import io, json, os, subprocess, sys
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import COLS, LEFT, RIGHT

NEED = ["total", "c1_2", "c7", "c8", "c9", "c10", "c11", "c18", "c23", "c24_32", "c38", "c45_53", "c59", "c90r", "c94", "c95", "c107_109",
        "c119", "c130_132", "c140s", "c141s", "c163_171", "c172_175", "c210", "c206s", "c176s"]
pdf, odir, asmp, resp, tag = sys.argv[1:6]
every = len(sys.argv) > 6 and sys.argv[6] == "all"
A = json.load(open(asmp))
R = json.load(open(resp))
cache = {}


def page(p):
    if p not in cache:
        base = os.path.join(odir, f"re_{p}")
        if not os.path.exists(base + ".png"):
            subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", "300", "-gray", "-png", "-singlefile", pdf, base], check=True)
        cache[p] = (Image.open(base + ".png").convert("L"), json.load(open(os.path.join(odir, f"p{p}.json")))["rules"])
    return cache[p]


def read(p, y, ci):
    im, rules = page(p)
    edges = rules + [rules[-1] + 110]
    crop = im.crop((edges[ci] + 4, int(y - 15), edges[ci + 1] - 3, int(y + 15)))
    if tag == "c":
        crop = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS).point(lambda v: 255 if v > 150 else 0)
        crop = ImageOps.expand(crop, border=20, fill=255)
    else:
        crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    buf = io.BytesIO(); crop.save(buf, format="PNG")
    return subprocess.run(["tesseract", "stdin", "stdout", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789,-"],
                          input=buf.getvalue(), capture_output=True).stdout.decode().strip()


todo = set()
only = os.environ.get("ONLY_BLOCK")
if every:
    for st in A["blocks"]:
        if only and st != only:
            continue
        for c in NEED:
            todo.add((st, c, "W")); todo.add((st, c, "O"))
else:
    for t in R["todo"]:
        if t["col"] in NEED or os.environ.get("ALLCOLS"):
            todo.add((t["state"], t["col"], t["race"]))
    for st, v in R["states"].items():
        for race, (a, b) in v["rowcheck"].items():
            if a != b:
                for c in NEED:
                    todo.add((st, c, race))
n = 0
for st, c, race in sorted(todo):
    b = A["blocks"].get(st)
    if not b:
        continue
    for key, row in b["rows"].items():
        if not key.endswith(race):
            continue
        reads = b.setdefault("reads", {}).setdefault(key, {}).setdefault(c, {})
        if tag in reads:
            continue
        if c in LEFT:
            p, y, ci = row["_page"], row["_y"], LEFT.index(c)
        elif row.get("_ry") is not None:
            p, y, ci = row["_page"] + 1, row["_ry"], RIGHT.index(c)
        else:
            continue
        reads[tag] = read(p, y, ci)
        n += 1
        if n % 300 == 0:
            json.dump(A, open(asmp, "w"))
json.dump(A, open(asmp, "w"))
print("read", n, "cells,", len(todo), "state-columns, tag", tag)
