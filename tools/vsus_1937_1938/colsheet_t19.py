"""One contact sheet per (race, column): every state's printed cell with the final value under it, for columns whose states do not add up
to the United States line. usage: python3 colsheet_t19.py <ocr dir> <assembled> <final json> <out prefix> RACE|col ..."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_t19 import LEFT, RIGHT, STATES
odir, asmp, finp, outp = sys.argv[1:5]
A, F = json.load(open(asmp)), json.load(open(finp))
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
pages = {}
def page(p):
    if p not in pages:
        pages[p] = (Image.open(os.path.join(odir, f"re_{p}.png")).convert("L"), json.load(open(os.path.join(odir, f"p{p}.json")))["rules"])
    return pages[p]
for spec in sys.argv[5:]:
    race, c = spec.split("|")
    sts = ["UNITED STATES"] + STATES
    ncol, CW, CH = 7, 220, 78
    img = Image.new("RGB", (ncol * CW, 24 + CH * ((len(sts) + ncol - 1) // ncol)), "white")
    d = ImageDraw.Draw(img)
    nat = F["national"][spec]
    d.text((4, 3), f"{spec}: US {nat['us']} states {nat['states']} diff {None if nat['us'] is None else nat['us'] - nat['states']}", fill="blue", font=font)
    for i, st in enumerate(sts):
        x0, y0 = (i % ncol) * CW, 24 + (i // ncol) * CH
        row = A["blocks"][st]["rows"].get(race)
        d.rectangle([x0, y0, x0 + CW - 1, y0 + CH - 1], outline=(210, 210, 210))
        d.text((x0 + 3, y0 + 2), st[:22], fill="black", font=small)
        if row is None:
            continue
        if c in LEFT:
            p, yy, ci = row["_page"], row["_y"], LEFT.index(c)
        else:
            p, yy, ci = row["_page"] + 1, row["_ry"], RIGHT.index(c)
        im, rules = page(p)
        edges = rules + [rules[-1] + 110]
        crop = im.crop((edges[ci] - 30, int(yy - 22), edges[ci + 1] + 2, int(yy + 18))).convert("RGB")
        img.paste(crop, (x0 + 4, y0 + 16))
        v = F["values"][st][spec]
        h = F["how"][st][spec]
        col = {"row sum": "black", "eye": "green", "ocr+eye": "darkorange"}.get(h, "red")
        d.text((x0 + 150, y0 + 58), f"{v}", fill=col, font=font)
    img.save(f"{outp}_{race}_{c}.png")
print("ok")
