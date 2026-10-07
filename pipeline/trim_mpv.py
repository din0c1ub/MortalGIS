"""Trim a Mapping Police Violence CSV download to what the site needs: date, ~1 km grid cell, use of force.
Usage: python pipeline/trim_mpv.py "Mapping Police Violence.csv"   → data_manual/mpv/mpv_killings_trimmed.csv"""
import csv
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data_manual" / "mpv" / "mpv_killings_trimmed.csv"
g = lambda v: round(round(v / 0.01) * 0.01, 4)  # noqa: E731
out = []
for x in csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")):
    try:
        m, d, y = x["date"].split("/")
        out.append([f"{int(y):04d}-{int(m):02d}-{int(d):02d}", g(float(x["longitude"])), g(float(x["latitude"])), x["use_of_force"].strip()])
    except (ValueError, KeyError):
        continue
out.sort()
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "lon", "lat", "use_of_force"])
    w.writerows(out)
print(f"wrote {len(out):,} rows, {out[0][0]} to {out[-1][0]} → {OUT}")
