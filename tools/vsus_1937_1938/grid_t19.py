"""Contact sheets for checking Table 19 cells by eye: one line per (state, race) row that the sums have not settled, one cell per needed
column, the printed cell with the current value under it (red '?' = no value; orange = value held by a single cell decision).
usage: python3 grid_t19.py <ocr dir> <assembled> <resolve3> <resolve4> <L|R> <out prefix> [rows per sheet] [manual json]"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import LEFT, RIGHT, STATES
from reocr2_need import NEED

odir, asmp, r3p, r4p, side, outp = sys.argv[1:7]
per = int(sys.argv[7]) if len(sys.argv) > 7 else 24
man = json.load(open(sys.argv[8])) if len(sys.argv) > 8 and os.path.exists(sys.argv[8]) else {}
A, R3, R4 = json.load(open(asmp)), json.load(open(r3p)), json.load(open(r4p))
cols = [c for c in NEED if c in (LEFT if side == "L" else RIGHT)]
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
pages = {}


def page(p):
    if p not in pages:
        pages[p] = (Image.open(os.path.join(odir, f"re_{p}.png")).convert("L"), json.load(open(os.path.join(odir, f"p{p}.json")))["rules"])
    return pages[p]


rows = []
only = {tuple(r) for r in json.load(open(os.environ["ROWS_FILE"]))} if os.environ.get("ROWS_FILE") else None
for st in ["UNITED STATES"] + STATES:
    if st not in A["blocks"]:
        continue
    for race in "WO":
        settled = st in R4["states"] and race in R4["states"][st]["rowcheck"]
        if only is not None:
            if (st, race) not in only:
                continue
        elif settled and st != "UNITED STATES":
            continue
        rows.append((st, race))
CW, CH, LW = 118, 52, 150
sheets = [rows[i:i + per] for i in range(0, len(rows), per)]
for n, chunk in enumerate(sheets):
    img = Image.new("RGB", (LW + CW * len(cols), 22 + CH * len(chunk)), "white")
    dr = ImageDraw.Draw(img)
    for j, c in enumerate(cols):
        dr.text((LW + j * CW + 4, 3), c, fill="blue", font=font)
    for i, (st, race) in enumerate(chunk):
        y0 = 22 + i * CH
        dr.line([(0, y0), (img.width, y0)], fill=(200, 200, 200))
        dr.text((3, y0 + 8), f"{st[:14]}", fill="black", font=small)
        dr.text((3, y0 + 26), f"  {race}", fill="black", font=font)
        b = A["blocks"][st]
        row = b["rows"].get(race)
        for j, c in enumerate(cols):
            x0 = LW + j * CW
            k = f"{race}|{c}"
            if row is None:
                continue
            if c in LEFT:
                p, yy, ci = row["_page"], row["_y"], LEFT.index(c)
            else:
                if row.get("_ry") is None:
                    continue
                p, yy, ci = row["_page"] + 1, row["_ry"], RIGHT.index(c)
            im, rules = page(p)
            edges = rules + [rules[-1] + 110]
            crop = im.crop((edges[ci] + 2, int(yy - 17), edges[ci + 1] - 2, int(yy + 13)))
            if crop.width > CW - 4:
                crop = crop.resize((CW - 4, int(crop.height * (CW - 4) / crop.width)))
            img.paste(crop.convert("RGB"), (x0 + 2, y0 + 2))
            if k in man.get(st, {}):
                v, col = man[st][k], "green"
            else:
                v4 = R4["states"].get(st, {}).get("values", {}).get(k)
                v3 = R3["states"].get(st, {}).get("values", {}).get(k)
                v, col = (v4, "black") if v4 is not None else ((v3, "darkorange") if v3 is not None else ("?", "red"))
            dr.text((x0 + 6, y0 + 33), f"{v:,}" if isinstance(v, int) else v, fill=col, font=font)
            dr.line([(x0, y0), (x0, y0 + CH)], fill=(220, 220, 220))
    img.save(f"{outp}_{side}{n + 1}.png")
print(len(rows), "rows,", len(sheets), "sheets")
