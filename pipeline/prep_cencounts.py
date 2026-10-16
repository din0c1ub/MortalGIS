"""Make data_manual/hist/census_county_population_1960_1970.json from the NBER copy of the Census Bureau's county population counts
(cencounts.dta, 1900-1990 decennial counts by county). Used by pipeline/history_icpsr.py for 1959-1967 rates (straight line between the
April 1960 and April 1970 counts).

Counties whose borders changed between the two censuses are grouped so that deaths and population cover the same land in every year:
  Chesapeake city (1963) = Norfolk County + South Norfolk city; Virginia Beach city (1963) = Princess Anne County + the old city;
  Fairfax city (1961) with Fairfax County; Franklin city (1961) with Southampton; Emporia (1967) with Greensville; Lexington (1966) with
  Rockbridge; Salem (1968) with Roanoke County; Bedford city (1968) with Bedford County; Menominee County, WI (1961) with Shawano and Oconto.
Units that later merged follow the map's own remaps (Nansemond County and Suffolk -> Suffolk; Clifton Forge -> Alleghany; South Boston ->
Halifax; Washabaugh -> Jackson, SD; Shannon -> Oglala Lakota; Dade -> Miami-Dade). Alaska is left out (the map blanks it before 1982).
usage: python3 pipeline/prep_cencounts.py <cencounts.dta> [out json]
"""
import hashlib, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import history as H  # noqa: E402

ROWMAP = {"51129": "51550", "51785": "51550", "51151": "51810", "51123": "51800", "51560": "51005", "51780": "51083",
          "51515": "51019", "46113": "46102", "12025": "12086", "46131": "46071"}
UNIONS = [("51059", "51600"), ("51175", "51620"), ("51081", "51595"), ("51163", "51678"), ("51161", "51775"),
          ("55078", "55115", "55083")]


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data_manual" / "hist" / "census_county_population_1960_1970.json"
    d = pd.read_stata(src)
    atlas = set(H.atlas_counties())
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x

    for u in UNIONS:
        for m in u[1:]:
            parent[find(m)] = find(u[0])
    pops, left = {}, []
    for r in d.itertuples():
        f = r.fips
        if f.endswith("000") or f.startswith("02"):
            continue
        t = ROWMAP.get(f, H.REMAP.get(f, f))
        if t not in atlas:
            if (r.pop1960 or 0) > 0 or (r.pop1970 or 0) > 0:
                left.append(f"{f} {r.name} ({r.pop1960}, {r.pop1970})")
            continue
        g = find(t)
        p = pops.setdefault(g, {"members": set(), "p1960": 0, "p1970": 0})
        p["members"].add(t)
        p["p1960"] += 0 if pd.isna(r.pop1960) else int(r.pop1960)
        p["p1970"] += 0 if pd.isna(r.pop1970) else int(r.pop1970)
    # union members that had no row of their own still belong to the group
    for u in UNIONS:
        g = find(u[0])
        if g in pops:
            pops[g]["members"].update(m for m in u if m in atlas)
    groups = [{"members": sorted(p["members"]), "p1960": p["p1960"], "p1970": p["p1970"]} for g, p in sorted(pops.items())]
    nopop = [g for g in groups if not (g["p1960"] and g["p1970"])]
    groups = [g for g in groups if g["p1960"] and g["p1970"]]
    covered = {m for g in groups for m in g["members"]}
    body = {
        "what": "County population, April 1 1960 and April 1 1970 censuses, in groups of map counties that cover the same land in both years",
        "source": "US Census Bureau decennial county population counts 1900-1990 (cencounts), NBER copy; saved by the owner from his browser 2026-10-15",
        "source_url": "https://www.nber.org/research/data/census-us-decennial-county-population-data-1900-1990",
        "file": {"name": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest()},
        "grouping": __doc__.split("\n\n")[1].strip(),
        "checks": {"groups": len(groups), "map_counties_covered": len(covered),
                   "map_counties_without_population": sorted(atlas - covered),
                   "rows_not_on_the_map": left, "groups_missing_a_year": nopop,
                   "us_1960": int(d.loc[d.fips == "00000", "pop1960"].iloc[0]), "us_1970": int(d.loc[d.fips == "00000", "pop1970"].iloc[0]),
                   "sum_1960": sum(g["p1960"] for g in groups), "sum_1970": sum(g["p1970"] for g in groups)},
        "groups": groups,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1))
    print(f"wrote {out}: {len(groups)} groups, {len(covered)} map counties; 1960 {body['checks']['sum_1960']:,} of {body['checks']['us_1960']:,}, "
          f"1970 {body['checks']['sum_1970']:,} of {body['checks']['us_1970']:,}")
    print("not on the map:", left)
    print("missing a year:", nopop)
    print("map counties without population:", sorted(atlas - covered))


if __name__ == "__main__":
    main()
