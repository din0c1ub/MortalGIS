"""Parse the Census Bureau's intercensal state population estimates for 1900-1949 into data_manual/hist_state/census_state_population_1900_1949.json.
Inputs (saved by hand from www2.census.gov/programs-surveys/popest/tables/1980-1990/state/asrh/): st0009ts.txt, st1019ts_v2.txt, st2029ts.txt,
st3039ts.txt, st4049ts.txt. July 1 estimates in thousands (the files' own unit), the 48 states plus DC (Alaska and Hawaii are not in these files). Check: for every year the states (with DC)
add up to the printed U.S. figure within rounding (one unit per state at most).
    python3 pipeline/census_states_parse.py <folder with the five files>"""
import hashlib, json, re, sys
from pathlib import Path

FILES = ["st0009ts.txt", "st1019ts_v2.txt", "st2029ts.txt", "st3039ts.txt", "st4049ts.txt"]


def parse(path):
    out, years = {}, []
    for line in open(path, encoding="latin-1"):
        s = line.strip()
        if re.fullmatch(r"(\d{4}\s+)+\d{4}", s):
            years = [int(x) for x in s.split()]
            continue
        m = re.match(r"^([A-Z][A-Za-z. ]*?)\s{2,}([\d,\s]+)$", s)
        if m and years:
            vals = [int(v.replace(",", "")) for v in m.group(2).split()]
            if len(vals) == len(years):
                for y, v in zip(years, vals):
                    out.setdefault(m.group(1).strip(), {})[y] = v
    return out


def main(folder):
    folder = Path(folder)
    data, sha = {}, {}
    for f in FILES:
        p = folder / f
        sha[f] = hashlib.sha256(p.read_bytes()).hexdigest()
        for k, ys in parse(p).items():
            data.setdefault(k, {}).update(ys)
    states = {k: v for k, v in data.items() if re.fullmatch(r"[A-Z]{2}", k)}
    us = data["U.S."]
    report = []
    for y in range(1900, 1950):
        tot = sum(v[y] for v in states.values())
        report.append((y, us[y], tot, tot - us[y]))
        assert abs(tot - us[y]) <= len(states), (y, us[y], tot)
    assert len(states) == 49 and all(len(v) == 50 for v in states.values()), (len(states), [k for k, v in states.items() if len(v) != 50])
    out = {"source": "US Census Bureau, Population Distribution Branch: Intercensal Estimates of the Total Resident Population of States, 1900-1949 (July 1 estimates, thousands; includes Armed Forces residing in each State)",
           "url": "https://www2.census.gov/programs-surveys/popest/tables/1980-1990/state/asrh/", "unit": "persons (the files' thousands times 1,000)",
           "files_sha256": sha, "check": "states + DC add up to the printed U.S. total within one unit per state in every year (largest gap %d thousand)" % max(abs(r[3]) for r in report),
           "data": {k: {str(y): v * 1000 for y, v in sorted(ys.items())} for k, ys in sorted(states.items())}}
    dest = Path(__file__).resolve().parents[1] / "data_manual" / "hist_state" / "census_state_population_1900_1949.json"
    dest.write_text(json.dumps(out, indent=1))
    print(dest.name, len(states), "states;", out["check"])


if __name__ == "__main__":
    main(sys.argv[1])
