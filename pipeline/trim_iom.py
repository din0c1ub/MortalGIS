"""Trim IOM's Missing Migrants Project workbook to the point layer's snapshot (run by hand; the weekly build only reads the result).

Save "Missing_Migrants_Global_Figures_allData.xlsx" from https://missingmigrants.iom.int/downloads in a browser (the site refuses
scripted downloads), then:
    python3 pipeline/trim_iom.py Missing_Migrants_Global_Figures_allData.xlsx
writes data_manual/points/iom_us_deaths.csv: incidents in the United States with at least one death (the missing are not mapped),
with only the month, the coordinates snapped to the map's ~1 km grid (0.01 degree) and the number of dead. No sex, age, origin,
source names or place names. A west longitude stored as positive is flipped (as for MSHA mines); rows outside the US box are left out.
Licence CC BY 4.0: credit "IOM's Missing Migrants Project"; changes made: US deaths only, coordinates rounded, counts per month."""
import csv, sys
from pathlib import Path

import openpyxl

GRID = 0.01
snap = lambda v: round(round(v / GRID) * GRID, 4)  # noqa: E731


def main(path):
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    ix = {k: i for i, k in enumerate(next(it))}
    rows, stats = [], {"incidents": 0, "dead": 0, "lon_flipped": 0, "dropped_dead": 0}
    for r in it:
        if r[ix["Country of Incident"]] != "United States of America":
            continue
        dead = int(r[ix["Number of Dead"]] or 0)
        if dead <= 0:
            continue
        try:
            lat, lon = [float(x) for x in str(r[ix["Coordinates"]]).split(",")]
        except ValueError:
            stats["dropped_dead"] += dead
            continue
        if lon > 0 and 15 < lat < 72:
            lon = -lon; stats["lon_flipped"] += 1
        if not (15 < lat < 72 and -180 < lon < -60):
            stats["dropped_dead"] += dead
            continue
        stats["incidents"] += 1; stats["dead"] += dead
        rows.append((str(r[ix["Incident Date"]])[:7], snap(lon), snap(lat), dead))
    rows.sort()
    out = Path(__file__).resolve().parents[1] / "data_manual" / "points" / "iom_us_deaths.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["month", "lon", "lat", "dead"])
        w.writerows(rows)
    print(out.name, len(rows), "rows;", stats)


if __name__ == "__main__":
    main(sys.argv[1])
