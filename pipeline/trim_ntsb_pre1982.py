"""Trim NTSB's 1962-1981 aviation accident file to a point snapshot placed at the named town (run by hand; the weekly build reads the result).

NTSB publishes PRE1982.zip (https://data.ntsb.gov/avdata) as a Microsoft Access file. Its records carry no coordinates, only the nearest
town as text ("MEMPHIS,TENN") and a state code. Save and unzip it, then:
    mdb-export PRE1982.MDB tblFirstHalf > pre1982_first.csv
    python3 pipeline/trim_ntsb_pre1982.py pre1982_first.csv
writes data_manual/points/ntsb_fatal_events_1962_1981.csv: one row per aircraft record with at least one death aboard or on the ground
in the 50 states and DC, with the month, the town's Census place centroid (or, failing that, the county subdivision's: New England towns,
townships) snapped to the map's 0.01-degree grid, and the deaths.
No docket numbers, aircraft, people or narratives. Towns not found in the Census places gazetteer are left out and counted.
Deaths aboard are per aircraft (a collision is two records, each with its own occupants); ground deaths are counted once per date and town.
The file holds only a few events before 1964."""
import csv
import io
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

GRID = 0.01
snap = lambda v: round(round(v / GRID) * GRID, 4)  # noqa: E731
GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip"
GAZ_COUSUB = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cousubs_national.zip"  # towns and townships, fallback
# LOCAT_STATE_TERR: 01-50 are the states in alphabetical order, 51 is DC; higher codes are territories, foreign places and oceans.
STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
          "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
          "VT", "VA", "WA", "WV", "WI", "WY", "DC"]
ABBR = [(r"\bFT\.?\s*", "FORT "), (r"\bMT\.?\s*", "MOUNT "), (r"\bPT\.?\s*", "POINT "), (r"\bNO\.\s*", "NORTH "), (r"\bSO\.\s*", "SOUTH "),
        (r"\bN\.\s*", "NORTH "), (r"\bS\.\s*", "SOUTH "), (r"\bE\.\s*", "EAST "), (r"\bW\.\s*", "WEST "), (r"\bSPGS?\b", "SPRINGS"),
        (r"\bFLS\b", "FALLS"), (r"\bHTS\b", "HEIGHTS"), (r"\bBCH\b", "BEACH"), (r"\bJCT\b", "JUNCTION"), (r"\bCTY\b", "CITY"),
        (r"\bSTA\b", "STATION"), (r"\bLK\b", "LAKE"), (r"\bVLY\b", "VALLEY")]


def gazetteer(url=GAZ):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MortalGIS-pipeline/2.0"}), timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")), delimiter="\t")
    head = [h.strip() for h in next(rows)]
    ui, ni, la, lo = head.index("USPS"), head.index("NAME"), head.index("INTPTLAT"), head.index("INTPTLONG")
    places = {}
    for r in rows:
        name = re.sub(r" \(balance\)$", "", r[ni].strip())
        name = re.sub(r" (city|town|village|CDP|borough|municipality|city and borough|comunidad|zona urbana|urban county|"
                      r"metropolitan government|unified government|consolidated government|township|charter township|plantation|"
                      r"gore|grant|location|purchase|reservation|unorganized territory)$", "", name)
        names = {name, name.replace("St. ", "Saint "), name.replace("Saint ", "St. ")}
        if "-" in name:
            names.add(name.split("-")[0])  # Nashville-Davidson, Lexington-Fayette, Macon-Bibb County, Butte-Silver Bow
        m = re.match(r"(.+) \((.+)\)$", name)  # San Buenaventura (Ventura)
        if m:
            names |= {m.group(1), m.group(2)}
        if name.startswith("Urban "):
            names.add(name[6:])  # Urban Honolulu
        if name.endswith(" City") and r[ui] == "ID":
            names.add(name[:-5])  # Boise City
        pt = (snap(float(r[lo])), snap(float(r[la])))
        for n in names:
            places.setdefault((norm(n), r[ui]), pt)
    for (t, st), parent in ALIAS.items():
        if (norm(parent), st) in places:
            places.setdefault((norm(t), st), places[(norm(parent), st)])
    return places


# Neighbourhoods and old names that sit inside a gazetteer place (placed at that place's centroid).
ALIAS = {("JAMAICA", "NY"): "New York", ("FLUSHING", "NY"): "New York", ("BROOKLYN", "NY"): "New York", ("BRONX", "NY"): "New York",
         ("QUEENS", "NY"): "New York", ("STATEN ISLAND", "NY"): "New York", ("NEW YORK CITY", "NY"): "New York",
         ("VAN NUYS", "CA"): "Los Angeles", ("PACOIMA", "CA"): "Los Angeles", ("SAN PEDRO", "CA"): "Los Angeles",
         ("NORTH HOLLYWOOD", "CA"): "Los Angeles", ("HOLLYWOOD", "CA"): "Los Angeles", ("CANOGA PARK", "CA"): "Los Angeles",
         ("CHATSWORTH", "CA"): "Los Angeles", ("SYLMAR", "CA"): "Los Angeles", ("ENCINO", "CA"): "Los Angeles", ("RESEDA", "CA"): "Los Angeles",
         ("NORTHRIDGE", "CA"): "Los Angeles", ("SUN VALLEY", "CA"): "Los Angeles", ("TUJUNGA", "CA"): "Los Angeles",
         ("WOODLAND HILLS", "CA"): "Los Angeles", ("WILMINGTON", "CA"): "Los Angeles", ("NEWHALL", "CA"): "Santa Clarita",
         ("GRND CANYON", "AZ"): "Grand Canyon Village", ("GRAND CANYON", "AZ"): "Grand Canyon Village"}


def norm(s: str) -> str:
    s = s.upper().replace("'", "").replace("-", " ")
    for pat, rep in ABBR:
        s = re.sub(pat, rep, s)
    s = re.sub(r"^([NSEW]) ", lambda m: {"N": "NORTH ", "S": "SOUTH ", "E": "EAST ", "W": "WEST "}[m.group(1)], s)
    s = re.sub(r"\bST\.?\s+", "ST ", s)
    s = re.sub(r"\bSAINT\b", "ST", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def town(location: str, st: str) -> str:
    loc = (location or "").strip()
    city = loc.rsplit(",", 1)[0] if "," in loc else loc
    city = re.sub(r"\s+(" + "|".join([st, "ALA", "ALAS", "ARIZ", "ARK", "CALIF", "CAL", "COLO", "CONN", "DEL", "FLA", "ILL", "IND", "KANS", "MASS",
                                       "MICH", "MINN", "MISS", "MONT", "NEBR", "NEB", "NEV", "N MEX", "N DAK", "S DAK", "OKLA", "OREG", "ORE",
                                       "TENN", "TEX", "WASH", "W VA", "WIS", "WYO", "IOWA", "OHIO", "UTAH", "IDAHO", "MAINE", "HAWAII"]) + r")\.?$", "", city.strip())
    return norm(city)


def main(path):
    places = gazetteer()
    for k, v in gazetteer(GAZ_COUSUB).items():  # a place of that name wins over a township of the same name
        places.setdefault(k, v)
    num = lambda v: int(float(v)) if v not in ("", None) else 0  # noqa: E731
    rows, ground_seen, stats, miss = [], set(), Counter(), Counter()
    for r in csv.DictReader(open(path, newline="", encoding="latin-1")):
        aboard, ground = num(r.get("TOTAL_ABRD_FATAL")), num(r.get("OTHER_GRND_FATAL"))
        code = (r.get("LOCAT_STATE_TERR") or "").strip()
        if aboard + ground <= 0:
            continue
        stats["fatal_records"] += 1
        stats["dead"] += aboard + ground
        if not code.isdigit() or not 1 <= int(code) <= 51:
            stats["outside_states_records"] += 1
            stats["outside_states_dead"] += aboard + ground
            continue
        st = STATES[int(code) - 1]
        d = (r.get("DATE_OCCURRENCE") or "").strip()  # mm/dd/yy
        m = re.match(r"(\d\d)/(\d\d)/(\d\d)", d)
        if not m:
            stats["no_date_records"] += 1
            continue
        y = 1900 + int(m.group(3))
        key = (d[:8], (r.get("LOCATION") or "").strip())
        if ground and key in ground_seen:
            ground = 0  # second aircraft of a collision: its ground deaths were counted with the first record
        if ground:
            ground_seen.add(key)
        t = town(r.get("LOCATION"), st)
        pt = places.get((t, st))
        if not pt:
            stats["unplaced_records"] += 1
            stats["unplaced_dead"] += aboard + ground
            miss[(t, st)] += 1
            continue
        stats["placed_records"] += 1
        stats["placed_dead"] += aboard + ground
        rows.append((f"{y}-{m.group(1)}", pt[0], pt[1], aboard + ground, ground))
    rows.sort()
    out = Path(__file__).resolve().parents[1] / "data_manual" / "points" / "ntsb_fatal_events_1962_1981.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["month", "lon", "lat", "dead", "dead_ground"])
        w.writerows(rows)
    print(out.name, len(rows), "rows;", dict(stats))
    print("most common unplaced towns:", miss.most_common(25))


if __name__ == "__main__":
    main(sys.argv[1])
