"""Trim the NTSB aviation accident database to the point layer's snapshot (run by hand; the weekly build only reads the result).

NTSB publishes Microsoft Access files (https://data.ntsb.gov/avdata): avall.zip (2008 on, refreshed monthly) and Pre2008.zip
(1982-2007). Save them, unzip, then:
    mdb-export avall.mdb events > avall_events.csv
    mdb-export Pre2008.mdb events > pre2008_events.csv
    python3 pipeline/trim_ntsb.py avall_events.csv pre2008_events.csv
writes data_manual/points/ntsb_fatal_events.csv: one row per US event with at least one death aboard or on the ground, 1982 on,
with only the month, the coordinates snapped to the map's ~1 km grid (0.01 degree) and the number of deaths. No case numbers,
places, aircraft or narratives. Events without decimal coordinates are left out and counted."""
import csv, sys
from pathlib import Path

GRID = 0.01
snap = lambda v: round(round(v / GRID) * GRID, 4)  # noqa: E731


def main(paths):
    seen, rows, stats = set(), [], {"events": 0, "dead": 0, "no_coords_events": 0, "no_coords_dead": 0}
    num = lambda v: int(float(v)) if v not in ("", None) else 0  # noqa: E731
    for p in paths:
        for r in csv.DictReader(open(p, newline="", encoding="latin-1")):
            if r["ev_country"] != "USA" or r["ev_id"] in seen:
                continue
            seen.add(r["ev_id"])
            aboard, ground = num(r["inj_tot_f"]), num(r["inj_f_grnd"])
            y = int(r["ev_year"] or 0)
            if aboard + ground <= 0 or y < 1982:
                continue
            stats["events"] += 1; stats["dead"] += aboard + ground
            try:
                lat, lon = float(r["dec_latitude"]), float(r["dec_longitude"])
            except ValueError:
                stats["no_coords_events"] += 1; stats["no_coords_dead"] += aboard + ground
                continue
            mo = r["ev_date"][:2]
            rows.append((f"{y}-{mo}", snap(lon), snap(lat), aboard + ground, ground))
    rows.sort()
    out = Path(__file__).resolve().parents[1] / "data_manual" / "points" / "ntsb_fatal_events.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["month", "lon", "lat", "dead", "dead_ground"])
        w.writerows(rows)
    print(out.name, len(rows), "rows;", stats)


if __name__ == "__main__":
    main(sys.argv[1:])
