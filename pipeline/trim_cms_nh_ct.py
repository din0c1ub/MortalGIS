"""Trim the CMS COVID-19 Nursing Home public file (Connecticut subset) to the point layers' snapshot (run by hand; the file is final).

CMS no longer serves the national file on data.cms.gov; Connecticut's open-data portal keeps its state subset (data.ct.gov w8wc-65i5,
public domain). This script asks that portal for per-facility, per-year sums of resident COVID-19 deaths and resident deaths from all
causes (rows that passed CMS quality assurance only), and the CMS Nursing Home Provider Information file (provider-data 4pq5-n9py)
for each facility's coordinates, then writes data_manual/points/cms_nh_ct.csv: year, the facility's ~1 km square, COVID-19 deaths,
all deaths. No facility names, addresses or CMS numbers are kept. Facilities no longer in the provider file (closed) are counted
and left out.
    python3 pipeline/trim_cms_nh_ct.py"""
import csv, json, sys, urllib.parse, urllib.request
from pathlib import Path

GRID = 0.01
snap = lambda v: round(round(v / GRID) * GRID, 4)  # noqa: E731


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MortalGIS (non-commercial mortality map)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    q = urllib.parse.urlencode({
        "$select": "federal_provider_number,date_extract_y(week_ending) as y,sum(residents_weekly_covid_19) as covid,"
                   "sum(residents_weekly_all_deaths) as alld",
        "$where": "passed_quality_assurance='Y'", "$group": "federal_provider_number,y", "$limit": 50000})
    fac = get("https://data.ct.gov/resource/w8wc-65i5.json?" + q)
    q = urllib.parse.urlencode({"conditions[0][property]": "state", "conditions[0][value]": "CT", "limit": 500})
    info = get("https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0?" + q)["results"]
    pos = {}
    for r in info:
        try:
            pos[r["cms_certification_number_ccn"]] = (snap(float(r["longitude"])), snap(float(r["latitude"])))
        except (KeyError, ValueError):
            pass
    cells, st = {}, {"facilities": len({r["federal_provider_number"] for r in fac}), "unplaced_facilities": set(),
                     "unplaced_covid": 0, "unplaced_all": 0}
    for r in fac:
        c, a = int(float(r.get("covid") or 0)), int(float(r.get("alld") or 0))
        p = pos.get(r["federal_provider_number"])
        if not p:
            st["unplaced_facilities"].add(r["federal_provider_number"]); st["unplaced_covid"] += c; st["unplaced_all"] += a
            continue
        k = (int(r["y"]), *p)
        v = cells.setdefault(k, [0, 0]); v[0] += c; v[1] += a
    out = Path(__file__).resolve().parents[1] / "data_manual" / "points" / "cms_nh_ct.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["year", "lon", "lat", "covid", "all_deaths"])
        for (y, lon, lat), (c, a) in sorted(cells.items()):
            if c or a:
                w.writerow([y, lon, lat, c, a])
    st["unplaced_facilities"] = len(st["unplaced_facilities"])
    print(out.name, len(cells), "rows;", st)


if __name__ == "__main__":
    main()
