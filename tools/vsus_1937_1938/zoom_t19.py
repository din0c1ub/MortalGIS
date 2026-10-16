"""Zoomed crops of single Table 19 cells (with the neighbouring cells for context), stacked with labels.
usage: python3 zoom_t19.py <ocr dir> <assembled> <out png> STATE:RACE:col ..."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import LEFT, RIGHT
odir, asmp, outp = sys.argv[1:4]
A = json.load(open(asmp))
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
tiles = []
for spec in sys.argv[4:]:
    st, race, c = spec.split(":")
    row = A["blocks"][st]["rows"][race]
    if c in LEFT:
        p, y, ci = row["_page"], row["_y"], LEFT.index(c)
    else:
        p, y, ci = row["_page"] + 1, row["_ry"], RIGHT.index(c)
    im = Image.open(os.path.join(odir, f"re_{p}.png")).convert("L")
    rules = json.load(open(os.path.join(odir, f"p{p}.json")))["rules"]
    edges = rules + [rules[-1] + 110]
    x0, x1 = edges[max(0, ci - 1)], edges[min(len(edges) - 1, ci + 2)]
    crop = im.crop((x0, int(y - 45), x1, int(y + 40)))
    crop = crop.resize((crop.width * 2, crop.height * 2))
    t = Image.new("RGB", (max(crop.width, 500), crop.height + 26), "white")
    t.paste(crop.convert("RGB"), (0, 26))
    d = ImageDraw.Draw(t)
    d.text((4, 2), f"{st} {race} {c} (middle column; row in the middle)", fill="blue", font=font)
    cx = (edges[ci] - x0) * 2
    d.rectangle([cx, 26 + 45 * 2 - 34, (edges[ci + 1] - x0) * 2, 26 + 45 * 2 + 26], outline="red", width=2)
    tiles.append(t)
W = max(t.width for t in tiles); H = sum(t.height for t in tiles)
out = Image.new("RGB", (W, H), "white"); yy = 0
for t in tiles:
    out.paste(t, (0, yy)); yy += t.height
out.save(outp)
print(out.size)
