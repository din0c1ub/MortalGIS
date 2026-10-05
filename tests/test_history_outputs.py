"""Sanity checks on site/data/hist after a history build.
- Virginia's pre-1982 code scheme maps correctly: county rates in 1981 (old codes) are close to 1986
  (FIPS codes). 1982–85 is skipped because the source files misplace some Pulaski/Salem deaths then.
- DC and New York City are present before 1982.
- National identified share is ~100% for 1968–1988."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "site" / "data" / "hist"
meta = json.loads((ROOT / "site" / "data" / "meta.json").read_text())
fips = [c[0] for c in meta["counties"]]
idx = {f: i for i, f in enumerate(fips)}
d = json.loads((H / "nber_all_res.json").read_text())
pop = json.loads((H / "pop.json").read_text())["pop"]
sys.path.insert(0, str(ROOT / "pipeline"))
from history import SEER_COMBOS  # noqa: E402
combined = {m for members in SEER_COMBOS.values() for m in members}  # these share a rate before 1982
bad = []
for f in fips:
    if not f.startswith("51") or f in combined:
        continue
    i = idx[f]
    a, b = d["rate"]["1981"][i], d["rate"]["1986"][i]
    p = pop["1986"][i]
    if a and b and p and p > 20000 and not (0.67 < a / b < 1.5):
        bad.append((f, a, b))
assert not bad, f"Virginia 1981 vs 1986 jumps: {bad}"
assert d["rate"]["1970"][idx["11001"]], "DC missing in 1970"
nyc = [d["rate"]["1975"][idx[f]] for f in ["36005", "36047", "36061", "36081", "36085"]]
assert len(set(nyc)) == 1 and nyc[0], f"NYC boroughs should share one 1975 rate: {nyc}"
rep = json.loads((H / "report.json").read_text())["nber_residence_identified"]
low = {y: v for y, v in rep.items() if int(y) <= 1988 and v < 0.99}
assert not low, f"years with <99% of deaths placed in a county: {low}"
print("ok: history outputs (Virginia crosswalk, DC, NYC, coverage)")
