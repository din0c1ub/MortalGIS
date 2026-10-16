#!/usr/bin/env python3
"""MortalGIS: build the state-level historical mode (1900-1945) from the staged bundles, only for series the ledger has approved.

  python3 pipeline/hist_state.py            writes site/data/hist_state/ (index.json, registration_area.json, series_<key>.json)
  python3 pipeline/hist_state.py --check    runs the checks and prints what would be written; writes nothing

What it reads
  master/ledger.csv         rows (source_id, bundle 'hist_state', measure = series key, place 'state'); only status approved or released is built.
                            A missing ledger stops the build. MORTALGIS_LEDGER overrides the path (used to preview with a scratch ledger).
  data_manual/hist_state/   the two bundle files (MORTALGIS_HIST_BUNDLES overrides the folder). An approved series whose bundle file is missing stops the build.
What it writes
  site/data/hist_state/     the map's historical mode looks for index.json there; with no approved series the folder is removed and the mode is hidden.

This is not part of the weekly build: the sources are static. Run it by hand after approving rows and commit the output.
The county gate (agreement with CDC) does not apply: there is no CDC overlap before 1959. The checks here are internal: the age groups add to the printed total
(1,102 of 1,109 state-years; the 7 that do not are marked and kept out of 'share of deaths'), infant deaths equal Miller's under-1 column where both exist, every
value is a non-negative whole number, and every state in the data is a known state. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hist_series as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = Path(os.environ.get("MORTALGIS_LEDGER") or ROOT / "master" / "ledger.csv")
BUNDLE_DIR = Path(os.environ.get("MORTALGIS_HIST_BUNDLES") or ROOT / "data_manual" / "hist_state")
OUT_DIR = ROOT / "site" / "data" / "hist_state"
APPROVED = {"approved", "released"}
AGE_KEYS = ["under_1", "1_4", "1_2", "2_3", "3_4", "4_5", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59",
            "60_64", "65_69", "70_74", "75_79", "80_84", "85_89", "90_94", "95_over", "age_unknown"]


def read_ledger(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"! ledger not found: {path}. The historical mode is gated by it; commit master/ledger.csv or set MORTALGIS_LEDGER.")
    rows = {}
    with path.open(newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for need in ("source_id", "bundle", "measure", "place", "status"):
            if need not in (rd.fieldnames or []):
                raise SystemExit(f"! ledger {path} lacks column {need}")
        for r in rd:
            rows[(r["source_id"], r["bundle"], r["measure"], r["place"])] = r
    return rows


def approved_series(ledger: dict) -> list:
    out = []
    for s in H.SERIES:
        sid = H.SOURCES[s["source"]]["id"]
        r = ledger.get((sid, H.BUNDLE, s["key"], "state"))
        if r and r["status"] in APPROVED:
            out.append(s)
    return out


def age_sum(row: dict):
    """Sum of the all-persons age groups (ages 1-4 combined from 1924, single years before), or None if a group is missing."""
    get = lambda k: row.get("all_" + k)  # noqa: E731
    parts = [get("under_1")]
    parts += [get("1_4")] if get("1_4") is not None else [get(k) for k in ("1_2", "2_3", "3_4", "4_5")]
    parts += [get(k) for k in AGE_KEYS[6:]]
    return None if any(p is None for p in parts) else sum(parts)


def whole(v):
    return int(round(v))


def build(miller: dict | None, infant: dict | None, series: list, generated: str, population: dict | None = None, ext: dict | None = None):
    """Returns ({filename: obj}, report lines). Raises SystemExit on a failed check.
    population: the Census intercensal state estimates (census_state_population_1900_1949.json); when given, every Miller series also gets a
    rate per 100,000 people (shown only on 20 or more deaths, like the share).
    ext: {extension source key: (bundle, set of approved series keys)} for years after a source's own span (hist_series.EXTENSIONS)."""
    ext = ext or {}
    out, rep = {}, []
    reg_years = list(range(1900, 1937))
    anomalies = []
    spans = {}
    n_states = {}
    if miller:
        data = miller["data"]
        unknown = sorted(set(data) - set(H.STATE_NAMES))
        if unknown:
            raise SystemExit(f"! unknown state codes in the Miller bundle: {unknown}")
        for st, ys in data.items():
            present = sorted(int(y) for y in ys)
            run = []
            for y in present:
                if run and y == run[-1][1] + 1:
                    run[-1][1] = y
                else:
                    run.append([y, y])
            spans[st] = run
            for y in present:
                n_states[y] = n_states.get(y, 0) + 1
            for y, row in ys.items():
                tot = row.get("total_mortality")
                if not isinstance(tot, int) or tot < 0:
                    raise SystemExit(f"! {st} {y}: total_mortality is not a whole number")
                s = age_sum(row)
                note = H.PUBLISHER_STATE_NOTES.get((st, int(y)))
                if s is not None and s != tot:
                    txt = f"The age groups add to {s:,} but the printed total is {tot:,}."
                    anomalies.append(dict(state=st, year=int(y), text=txt + (" " + note if note else ""), excludeShare=True))
                elif note:
                    anomalies.append(dict(state=st, year=int(y), text=note, excludeShare=False))
        mism = [a for a in anomalies if a["excludeShare"]]
        rep.append(f"Miller: {sum(len(v) for v in data.values())} state-years, {len(data)} states; age groups add to the total in {sum(len(v) for v in data.values()) - len(mism)}, "
                   f"differ in {len(mism)}: {', '.join(a['state'] + ' ' + str(a['year']) for a in mism)}")
        known = (miller.get("checks") or {}).get("age_sum_differs")   # the exceptions the staging step recorded; a different count means the bundle changed
        if known is not None and len(mism) != len(known):
            raise SystemExit(f"! the staged bundle records {len(known)} age-sum exceptions, this run finds {len(mism)}")
        for k, (eb, _keys) in ext.items():  # the extension years count as registration years where the extension reports the state
            for st, ys in eb["data"].items():
                for y in sorted(int(y) for y in ys):
                    run = spans.setdefault(st, [])
                    if run and y == run[-1][1] + 1:
                        run[-1][1] = y
                    elif not run or y > run[-1][1]:
                        run.append([y, y])
                    n_states[y] = n_states.get(y, 0) + 1
                    reg_years.append(y) if y not in reg_years else None
        gaps = {st: [tuple(r) for r in run] for st, run in spans.items() if len(run) > 1 or run[-1][1] != max(reg_years)}
        rep.append(f"registration gaps: {gaps}")
        out["registration_area.json"] = dict(
            years=reg_years, nStates={str(y): n_states.get(y, 0) for y in reg_years},
            spans={st: spans[st] for st in sorted(spans)}, entry={st: spans[st][0][0] for st in sorted(spans)},
            note="A state is in the registration area for a year when the printed volume reports its deaths. Entry years are Miller's panel; DC is not in it. "
                 "A state outside the area has no data, which is not the same as no deaths. Texas joins in 1933 (48 states from then).")
    # infant bundle
    idata = infant["data"] if infant else {}
    if infant:
        unknown = sorted(set(idata) - set(H.STATE_NAMES))
        if unknown:
            raise SystemExit(f"! unknown state codes in the infant bundle: {unknown}")
    series_out = []
    for s in series:
        key = s["key"]
        if s["source"] == "miller":
            if not miller:
                raise SystemExit(f"! series {key} is approved but its bundle {H.SOURCES['miller']['file']} is missing")
            y0, y1 = 1900, 1936
            exts = [(k, a, b) for k, a, b, base in H.EXTENSIONS if base == "miller" and k in ext and key in ext[k][1]]
            for k, a, b in exts:
                y1 = max(y1, b)
            n = y1 - y0 + 1
            v = {}
            for st, ys in miller["data"].items():
                arr = [None] * n
                for y, row in ys.items():
                    vals = [row.get(c) for c in s["cols"]]
                    if any(x is None for x in vals):
                        continue
                    if any((not isinstance(x, (int, float))) or x < 0 for x in vals):
                        raise SystemExit(f"! {st} {y} {key}: negative or non-numeric value")
                    arr[int(y) - y0] = whole(sum(vals))
                v[st] = arr
            for k, a, b in exts:
                for st, ys in ext[k][0]["data"].items():
                    if st not in v:
                        raise SystemExit(f"! {k}: state {st} is not in the Miller panel")
                    for y, row in ys.items():
                        if not a <= int(y) <= b:
                            continue
                        vals = [row.get(c) for c in s["cols"]]
                        if any(x is None for x in vals):
                            continue
                        if any((not isinstance(x, int)) or x < 0 for x in vals):
                            raise SystemExit(f"! {k} {st} {y} {key}: negative or non-numeric value")
                        v[st][int(y) - y0] = sum(vals)
            body = dict(key=key, y0=y0, y1=y1, v=v)
            if exts:
                body["ext"] = {k: [a, b] for k, a, b in exts}
        else:
            if not infant:
                raise SystemExit(f"! series {key} is approved but its bundle {H.SOURCES['infant']['file']} is missing")
            y0, y1 = 1920, 1945
            n = y1 - y0 + 1
            v, b, imp = {}, {}, {}
            for st, ys in idata.items():
                da, ba = [None] * n, [None] * n
                for y, row in ys.items():
                    i = int(y) - y0
                    if not 0 <= i < n:
                        continue
                    if row.get("infant_deaths") is not None:
                        da[i] = whole(row["infant_deaths"])
                    if row.get("births") is not None:
                        ba[i] = whole(row["births"])
                    f = (1 if row.get("infant_deaths_imputed") else 0) | (2 if row.get("births_imputed") else 0)
                    if f:
                        imp.setdefault(st, {})[y] = f
                v[st], b[st] = da, ba
            body = dict(key=key, y0=y0, y1=y1, v=v, births=b, imputed=imp)
            if miller:   # internal cross-check: infant deaths equal Miller's under-1 column on the overlapping, non-imputed state-years
                same = diff = 0
                for st, ys in idata.items():
                    for y, row in ys.items():
                        if row.get("infant_deaths_imputed") or int(y) > 1936:
                            continue
                        mr = miller["data"].get(st, {}).get(y)
                        if mr and mr.get("all_under_1") is not None and row.get("infant_deaths") is not None:
                            if int(round(row["infant_deaths"])) == mr["all_under_1"]:
                                same += 1
                            else:
                                diff += 1
                rep.append(f"infant deaths vs Miller all_under_1: {same} equal, {diff} differ")
                if diff:
                    raise SystemExit("! infant deaths disagree with Miller's under-1 column")
        out[f"series_{key}.json"] = body
        cnt = sum(1 for arr in body["v"].values() for x in arr if x is not None)
        measures = ["deaths"] + (["share"] if s["share"] else []) + (["per1000"] if s["source"] == "infant" else []) \
            + (["rate"] if population and s["source"] == "miller" else [])
        series_out.append(dict(key=key, label=s["label"], group=s["group"], grade=s["grade"], gradeText=H.GRADE_TEXT[s["grade"]], nearest=s["nearest"],
                               years=[body["y0"], body["y1"]], measures=measures, file=f"series_{key}.json", note=s["note"], source=s["source"],
                               revisionYears=[y for y in H.REVISION_YEARS if body["y0"] < y <= body["y1"]], stateYears=cnt,
                               **({"extendedBy": body["ext"]} if body.get("ext") else {})))
        rep.append(f"series {key}: {body['y0']}-{body['y1']}, {cnt:,} state-year values")
    if not series_out:
        return {}, rep
    used_src = {s["source"] for s in series} | {k for so in series_out for k in so.get("extendedBy", {})}
    year_notes = dict(H.YEAR_NOTES)
    for k, a, b, base in H.EXTENSIONS:
        if k in used_src:
            for y in range(a, b + 1):
                year_notes[y] = H.EXTENSION_NOTES[k]
    if population:
        pdata = population["data"]
        missing = sorted(set(H.STATE_NAMES) - set(pdata))
        if missing:
            raise SystemExit(f"! population file lacks states: {missing}")
        out["population.json"] = dict(y0=1900, y1=1949, v={c: [pdata[c].get(str(y)) for y in range(1900, 1950)] for c in sorted(H.STATE_NAMES)})
        rep.append(f"population: {len(H.STATE_NAMES)} states 1900-1949 ({population['check']})")
    out["index.json"] = dict(
        version=1, generated=generated, years=[min(s["years"][0] for s in series_out), max(s["years"][1] for s in series_out)],
        states=[dict(code=c, fips=H.STATE_FIPS[c], name=H.STATE_NAMES[c]) for c in sorted(H.STATE_NAMES, key=lambda c: H.STATE_NAMES[c])],
        groups=[dict(key=k, label=lab) for k, lab in H.GROUPS if any(s["group"] == k for s in series_out)],
        series=series_out, revisionYears=H.REVISION_YEARS, revisionNote=H.REVISION_NOTE,
        anomalies=sorted(anomalies, key=lambda a: (a["year"], a["state"])) if "miller" in used_src else [],
        yearNotes={str(k): v for k, v in year_notes.items()}, shareMinDeaths=H.SHARE_MIN_DEATHS,
        sources={k: dict(label=H.SOURCES[k]["label"], url=H.SOURCES[k]["url"], terms=H.SOURCES[k]["terms"]) for k in used_src},
        registration="registration_area.json" if miller else None,
        population="population.json" if population else None,
        populationSource=dict(label=population["source"], url=population["url"]) if population else None)
    return out, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="run the checks, print the report, write nothing")
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args()
    ledger = read_ledger(LEDGER_PATH)
    series = approved_series(ledger)
    print(f"ledger {LEDGER_PATH}: {len(series)} of {len(H.SERIES)} historical series approved")
    miller = infant = None
    need = {s["source"] for s in series}
    for src, name in (("miller", "miller"), ("infant", "infant")):
        if src in need:
            p = BUNDLE_DIR / H.SOURCES[src]["file"]
            if not p.exists():
                raise SystemExit(f"! ledger approves {H.SOURCES[src]['id']} but its bundle file is missing: {p}")
            b = json.loads(p.read_text())
            if b.get("id") != H.SOURCES[src]["id"]:
                raise SystemExit(f"! {p.name}: bundle id {b.get('id')!r}, expected {H.SOURCES[src]['id']!r}")
            if src == "miller":
                miller = b
            else:
                infant = b
    # the infant cross-check wants Miller too when its file is there, even if no Miller series is approved
    if infant and not miller and (BUNDLE_DIR / H.SOURCES["miller"]["file"]).exists():
        miller = json.loads((BUNDLE_DIR / H.SOURCES["miller"]["file"]).read_text())
    pop_path = BUNDLE_DIR / "census_state_population_1900_1949.json"
    population = json.loads(pop_path.read_text()) if pop_path.exists() else None
    ext = {}
    for k, y_from, y_to, base in H.EXTENSIONS:
        sid = H.SOURCES[k]["id"]
        keys = {m for (s_, b_, m, pl), r in ledger.items() if s_ == sid and b_ == H.BUNDLE and r["status"] in ("approved", "released")}
        keys &= {s["key"] for s in series}
        if keys:
            p = BUNDLE_DIR / H.SOURCES[k]["file"]
            if not p.exists():
                raise SystemExit(f"! ledger approves {sid} but its bundle file is missing: {p}")
            eb = json.loads(p.read_text())
            if eb.get("id") != sid:
                raise SystemExit(f"! {p.name}: bundle id {eb.get('id')!r}, expected {sid!r}")
            ext[k] = (eb, keys)
            print(f"extension {sid}: {len(keys)} series get {y_from}-{y_to}")
    files, rep = build(miller, infant, series, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"), population, ext)
    for line in rep:
        print("  " + line)
    out = Path(a.out)
    if a.check:
        print(f"check only: would write {len(files)} files to {out}")
        return
    if not files:
        if out.exists():
            shutil.rmtree(out)
            print(f"no approved series: removed {out} (the map hides the historical mode)")
        else:
            print("no approved series: nothing to write")
        return
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        if old.name not in files:
            old.unlink()
    for name, obj in files.items():
        (out / name).write_text(json.dumps(obj, separators=(",", ":")))
    total = sum((out / n).stat().st_size for n in files)
    print(f"wrote {len(files)} files, {total/1024:.0f} KB, to {out}")


if __name__ == "__main__":
    main()
