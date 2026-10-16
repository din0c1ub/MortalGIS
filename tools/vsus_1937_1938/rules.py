import sys
import numpy as np
from PIL import Image

def vrules(path, thr=170, minrun=400):
    im = np.array(Image.open(path).convert("L")); h, w = im.shape
    dark = im < thr
    # allow small gaps: dilate vertically by 3 px
    d = dark.copy()
    for k in (1, 2, 3):
        d[k:] |= dark[:-k]
    best = np.zeros(w, dtype=int)
    for x in range(w):
        c = d[:, x]
        # longest run
        if not c.any(): continue
        idx = np.flatnonzero(np.diff(np.concatenate(([0], c.astype(np.int8), [0]))))
        runs = idx[1::2] - idx[0::2]
        best[x] = runs.max()
    xs = [x for x in range(w) if best[x] >= minrun]
    groups = []
    for x in xs:
        if groups and x - groups[-1][-1] <= 4: groups[-1].append(x)
        else: groups.append([x])
    return [(g[0] + g[-1]) // 2 for g in groups], best

if __name__ == "__main__":
    r, best = vrules(sys.argv[1])
    print(r)
