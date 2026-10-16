"""Estimate page skew (degrees) of a rendered Table 19 page from the horizontal projection of its numeric area."""
import sys
import numpy as np
from PIL import Image

def skew(path, lo=-1.2, hi=1.2, step=0.05):
    im = Image.open(path).convert("L")
    w, h = im.size
    im = im.crop((int(w * 0.25), int(h * 0.25), int(w * 0.95), int(h * 0.9)))
    small = im.resize((im.width // 2, im.height // 2))
    best = (-1, 0)
    for a in np.arange(lo, hi + 1e-9, step):
        r = np.array(small.rotate(a, resample=Image.BILINEAR, fillcolor=255)) < 140
        prof = r.sum(axis=1).astype(float)
        v = prof.var()
        if v > best[0]:
            best = (v, round(float(a), 2))
    return best[1]

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, skew(p))
