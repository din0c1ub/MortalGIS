"""The state-level historical mode (pipeline/hist_state.py) is built only from series the ledger has approved, and its internal checks stop a bad bundle.

Synthetic bundles only: no real data is read. Run: python3 -I tests/test_hist_state.py
"""
import csv, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import hist_series as H  # noqa: E402
import hist_state as HS  # noqa: E402

AGES = ["under_1", "1_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64", "65_69", "70_74",
        "75_79", "80_84", "85_89", "90_94", "95_over", "age_unknown"]


def mrow(total, off=0, **cols):
    """A Miller state-year: every age group zero except under-1, which carries the total (minus 'off', to make the age groups disagree)."""
    r = {"total_mortality": total}
    for a in AGES:
        r["all_" + a] = 0
    r["all_under_1"] = total - off
    r.update(cols)
    return r


MILLER = {"id": "miller_vsh_1900_1936", "checks": {"age_sum_differs": [["IN", 1901]]},
          "data": {"NY": {"1900": mrow(1000, suicide=10, influenza=30, pneumonia=70, tuberculosis=0),
                          "1901": mrow(1100, suicide=12, influenza=None, pneumonia=80),
                          "1902": mrow(1200, suicide=3, influenza=20, pneumonia=90)},
                   "IN": {"1900": mrow(500, suicide=5, influenza=1, pneumonia=2),
                          "1901": mrow(600, off=7, suicide=6, influenza=1, pneumonia=2),
                          "1903": mrow(700, suicide=7, influenza=1, pneumonia=2)},
                   "KY": {"1919": mrow(900, suicide=9, influenza=1, pneumonia=2)}}}
INFANT = {"id": "nber_infant_1920_1945",
          "data": {"NY": {"1920": {"infant_deaths": 100, "births": 2000}, "1921": {"infant_deaths": 90, "births": 2100, "births_imputed": True},
                           "1922": {"infant_deaths": 80, "infant_deaths_imputed": True, "births": 2200, "births_imputed": True}},
                   "IN": {"1920": {"infant_deaths": 50, "births": None}}}}


def ledger(path, status_by_key, extra=None):
    cols = ["source_id", "bundle", "measure", "place", "status"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for s in H.SERIES:
            sid = H.SOURCES[s["source"]]["id"]
            w.writerow(dict(source_id=sid, bundle=H.BUNDLE, measure=s["key"], place="state", status=status_by_key.get(s["key"], "staged")))
        for r in extra or []:
            w.writerow(r)


def keys(series):
    return [s["key"] for s in series]


def must_stop(fn, text):
    try:
        fn()
    except SystemExit as e:
        assert text in str(e), (text, str(e))
        return
    raise AssertionError("expected the build to stop with: " + text)


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    L = d / "ledger.csv"

    # 1. nothing approved: no series, nothing to write
    ledger(L, {})
    led = HS.read_ledger(L)
    assert HS.approved_series(led) == []
    files, rep = HS.build(MILLER, INFANT, [], "2026-10-10")
    assert files == {}, files

    # 2. only approved or released rows count; staged, held, rejected, candidate do not
    ledger(L, {"all_deaths": "approved", "suicide": "released", "diabetes": "staged", "cancer": "held", "kidney": "rejected", "measles": "candidate"})
    sel = HS.approved_series(HS.read_ledger(L))
    assert keys(sel) == ["all_deaths", "suicide"], keys(sel)
    # a row for another place or bundle never approves a series
    ledger(L, {}, extra=[dict(source_id="miller_vsh_1900_1936", bundle="live", measure="all_deaths", place="state", status="approved"),
                         dict(source_id="miller_vsh_1900_1936", bundle=H.BUNDLE, measure="all_deaths", place="county", status="approved")])
    assert HS.approved_series(HS.read_ledger(L)) == []

    # 3. a Miller build: values, registration gaps, anomalies, flu = influenza + pneumonia, a missing column leaves the year empty
    series = [H.SERIES_BY_KEY[k] for k in ("all_deaths", "suicide", "flu_pneumonia")]
    files, rep = HS.build(MILLER, None, series, "2026-10-10")
    assert set(files) == {"index.json", "registration_area.json", "series_all_deaths.json", "series_suicide.json", "series_flu_pneumonia.json"}, set(files)
    ad = files["series_all_deaths.json"]
    assert ad["y0"] == 1900 and ad["y1"] == 1936 and len(ad["v"]["NY"]) == 37
    assert ad["v"]["NY"][:4] == [1000, 1100, 1200, None] and ad["v"]["IN"][:4] == [500, 600, None, 700] and ad["v"]["KY"][19] == 900
    fl = files["series_flu_pneumonia.json"]["v"]
    assert fl["NY"][0] == 100 and fl["NY"][1] is None and fl["NY"][2] == 110, fl["NY"][:3]   # 1901 has no influenza column: not 80
    reg = files["registration_area.json"]
    assert reg["spans"]["IN"] == [[1900, 1901], [1903, 1903]] and reg["entry"]["KY"] == 1919, reg["spans"]
    assert reg["nStates"]["1900"] == 2 and reg["nStates"]["1919"] == 1 and reg["nStates"]["1936"] == 0
    ix = files["index.json"]
    assert [a["state"] + str(a["year"]) for a in ix["anomalies"]] == ["IN1901", "KY1919"], ix["anomalies"]
    an = {(a["state"], a["year"]): a for a in ix["anomalies"]}
    assert an[("IN", 1901)]["excludeShare"] is True and "add to 593" in an[("IN", 1901)]["text"], an[("IN", 1901)]
    assert [s["key"] for s in ix["series"]] == ["all_deaths", "suicide", "flu_pneumonia"]
    assert ix["series"][0]["measures"] == ["deaths"] and ix["series"][1]["measures"] == ["deaths", "share"]
    assert ix["series"][1]["revisionYears"] == [1910, 1921, 1930], ix["series"][1]["revisionYears"]   # a line at 1900 would sit on the first year
    assert ix["shareMinDeaths"] == 20 and ix["registration"] == "registration_area.json" and set(ix["sources"]) == {"miller"}
    assert {g["key"] for g in ix["groups"]} == {"graded"}

    # 4. the publisher's own note and our age-sum check, one state-year each
    m2 = json.loads(json.dumps(MILLER))
    m2["data"]["KY"]["1919"] = mrow(900, suicide=9, influenza=1, pneumonia=2)
    files, rep = HS.build(m2, None, series, "x")
    an = {(a["state"], a["year"]): a for a in files["index.json"]["anomalies"]}
    assert an[("KY", 1919)]["excludeShare"] is False and "Kentucky" in an[("KY", 1919)]["text"]

    # 5. checks that stop the build
    bad = json.loads(json.dumps(MILLER)); bad["data"]["NY"]["1900"]["total_mortality"] = -3
    must_stop(lambda: HS.build(bad, None, series, "x"), "total_mortality is not a whole number")
    bad = json.loads(json.dumps(MILLER)); bad["data"]["ZZ"] = {"1900": mrow(10, suicide=1)}
    must_stop(lambda: HS.build(bad, None, series, "x"), "unknown state codes")
    bad = json.loads(json.dumps(MILLER)); bad["data"]["NY"]["1900"]["suicide"] = -1
    must_stop(lambda: HS.build(bad, None, series, "x"), "negative or non-numeric")
    bad = json.loads(json.dumps(MILLER)); bad["checks"]["age_sum_differs"] = []
    must_stop(lambda: HS.build(bad, None, series, "x"), "records 0 age-sum exceptions")
    must_stop(lambda: HS.build(None, None, series[:1], "x"), "is approved but its bundle")

    # 6. infant series: births, imputed flags (bit 1 deaths, bit 2 births), per-1000 measure, and the cross-check with Miller's under-1 column
    inf = [H.SERIES_BY_KEY["infant_deaths"]]
    files, rep = HS.build(None, INFANT, inf, "x")
    s = files["series_infant_deaths.json"]
    assert s["y0"] == 1920 and s["y1"] == 1945 and s["v"]["NY"][:3] == [100, 90, 80] and s["births"]["NY"][:3] == [2000, 2100, 2200]
    assert s["births"]["IN"][0] is None and s["imputed"] == {"NY": {"1921": 2, "1922": 3}}, s["imputed"]
    ix = files["index.json"]
    assert ix["series"][0]["measures"] == ["deaths", "per1000"] and ix["anomalies"] == [] and ix["registration"] is None and set(ix["sources"]) == {"infant"}
    m3 = json.loads(json.dumps(MILLER)); m3["data"]["NY"]["1920"] = mrow(2000, suicide=1, influenza=1, pneumonia=1)   # under-1 = 2000, infant says 100
    must_stop(lambda: HS.build(m3, INFANT, inf, "x"), "disagree with Miller's under-1")
    m4 = json.loads(json.dumps(MILLER)); m4["data"]["NY"]["1920"] = mrow(900, suicide=1, influenza=1, pneumonia=1)
    m4["data"]["NY"]["1920"]["all_under_1"] = 100
    m4["data"]["NY"]["1920"]["all_age_unknown"] = 800
    HS.build(m4, INFANT, inf, "x")   # equal on the overlap: fine

    # 7. command line: a scratch ledger and bundle folder, --check writes nothing, a build writes only approved series, and no approval removes the folder
    bdir = d / "bundles"; bdir.mkdir()
    (bdir / H.SOURCES["miller"]["file"]).write_text(json.dumps(MILLER))
    (bdir / H.SOURCES["infant"]["file"]).write_text(json.dumps(INFANT))
    out = d / "out"
    env = dict(os.environ, MORTALGIS_LEDGER=str(L), MORTALGIS_HIST_BUNDLES=str(bdir))
    run = lambda *a: subprocess.run([sys.executable, "-I", str(ROOT / "pipeline" / "hist_state.py"), *a], env=env, capture_output=True, text=True)  # noqa: E731
    ledger(L, {"all_deaths": "approved", "suicide": "approved", "infant_deaths": "released", "flu_pneumonia": "staged"})
    r = run("--check", "--out", str(out)); assert r.returncode == 0 and not out.exists(), r.stdout + r.stderr
    assert "3 of 20 historical series approved" in r.stdout, r.stdout
    r = run("--out", str(out)); assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(p.name for p in out.glob("*.json")) == ["index.json", "registration_area.json", "series_all_deaths.json", "series_infant_deaths.json", "series_suicide.json"]
    (out / "series_stale.json").write_text("{}")   # a series that is no longer approved must not linger
    r = run("--out", str(out)); assert not (out / "series_stale.json").exists()
    ledger(L, {})
    r = run("--out", str(out)); assert r.returncode == 0 and not out.exists(), r.stdout + r.stderr
    # an approved source whose bundle file is missing stops the build
    ledger(L, {"all_deaths": "approved"}); (bdir / H.SOURCES["miller"]["file"]).unlink()
    r = run("--out", str(out)); assert r.returncode != 0 and "bundle file is missing" in (r.stderr + r.stdout), r.stdout + r.stderr
    # a bundle with the wrong id stops it
    (bdir / H.SOURCES["miller"]["file"]).write_text(json.dumps(dict(MILLER, id="something_else")))
    r = run("--out", str(out)); assert r.returncode != 0 and "bundle id" in (r.stderr + r.stdout), r.stdout + r.stderr
    # no ledger: stop, never build everything
    env["MORTALGIS_LEDGER"] = str(d / "nope.csv")
    r = run("--out", str(out)); assert r.returncode != 0 and "ledger not found" in (r.stderr + r.stdout)

# 8. the definitions themselves: 20 unique series, every one resolvable, and the source column names exist in the real bundle when it is present
assert len(H.SERIES) == 20 and len({s["key"] for s in H.SERIES}) == 20
assert all(s["grade"] in H.GRADE_TEXT and s["group"] in dict(H.GROUPS) and s["source"] in H.SOURCES for s in H.SERIES)
assert set(H.STATE_NAMES) == set(H.STATE_FIPS) and len(H.STATE_NAMES) == 48
real = ROOT / "data_manual" / "hist_state" / H.SOURCES["miller"]["file"]
if real.exists():
    cols = set()
    for ys in json.loads(real.read_text())["data"].values():
        for row in ys.values():
            cols |= set(row)
    missing = sorted({c for s in H.SERIES if s["source"] == "miller" for c in s["cols"]} - cols)
    assert not missing, f"series columns not in the Miller bundle: {missing}"
print("test_hist_state: ok")
