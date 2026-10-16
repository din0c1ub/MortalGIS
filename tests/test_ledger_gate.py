"""master/ledger.csv gates the state fills: only approved or released rows are read, a missing ledger stops the build."""
import csv, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import statefill  # noqa: E402

COLS = ["source_id", "bundle", "measure", "place", "status", "verdict"]


def write_ledger(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(dict(zip(COLS, r)))


COUNTIES = [{"fips": "17031", "name": "Cook"}, {"fips": "17001", "name": "Adams"}, {"fips": "18001", "name": "Adams"}]
BUNDLE = {"state": "17", "data": {"heart": {"2010": {"Cook": 9000, "Adams": 4}}, "suicide": {"2010": {"Cook": 300, "Adams": 3}},
                                  "accidents": {"2010": {"Cook": 500, "Adams": 2}}}}

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "il_causes_county_2008-2023.json").write_text(json.dumps(BUNDLE))
    L = d / "ledger.csv"

    # nothing approved: the bundle is not even opened, so a missing file does not matter
    write_ledger(L, [("il_idph_causes", "il_causes", "heart", "residence", "staged", "USE")])
    out, labels, notes = statefill.staged(COUNTIES, statefill.read_ledger(L), bundle_dir=d / "nowhere")
    assert out == {} and labels == {}, out

    # approved + USE: heart is read, suicide (staged) and accidents (no map measure) are not
    write_ledger(L, [("il_idph_causes", "il_causes", "heart", "residence", "approved", "USE"),
                     ("il_idph_causes", "il_causes", "suicide", "residence", "staged", "USE")])
    out, labels, notes = statefill.staged(COUNTIES, statefill.read_ledger(L), bundle_dir=d)
    assert out == {"IL/il_causes": {"heart": {"2010": {"17031": 9000, "17001": 4}}}}, out   # Adams matched inside Illinois only
    assert labels == {"IL/il_causes": "Illinois DPH"}, labels

    # approved but the agreement verdict is not USE: not used, and the reason is reported
    write_ledger(L, [("il_idph_causes", "il_causes", "heart", "residence", "approved", "SKIP")])
    out, labels, notes = statefill.staged(COUNTIES, statefill.read_ledger(L), bundle_dir=d)
    assert out == {} and any("verdict is SKIP" in n for n in notes), (out, notes)

    # approved but the bundle file is gone: stop, never fill silently from nothing
    write_ledger(L, [("il_idph_causes", "il_causes", "heart", "residence", "released", "USE")])
    try:
        statefill.staged(COUNTIES, statefill.read_ledger(L), bundle_dir=d / "nowhere")
        raise AssertionError("expected SystemExit for a missing bundle")
    except SystemExit:
        pass

    # allowed(): default-deny, and held/rejected rows stay off
    led = {("mi_mdhhs", "live", "cancer", "residence"): {"status": "released", "verdict": "USE"},
           ("mi_mdhhs", "live", "stroke", "residence"): {"status": "held", "verdict": "USE"}}
    assert statefill.allowed(led, "mi_mdhhs", "live", "cancer")[0]
    assert not statefill.allowed(led, "mi_mdhhs", "live", "stroke")[0]
    assert not statefill.allowed(led, "mi_mdhhs", "live", "heart")[0]           # no row = not allowed

    # a missing or broken ledger stops the build
    for bad in (d / "absent.csv",):
        try:
            statefill.read_ledger(bad)
            raise AssertionError("expected SystemExit for a missing ledger")
        except SystemExit:
            pass
    write_ledger(L, [("a", "b", "c", "residence", "approved", "USE"), ("a", "b", "c", "residence", "approved", "USE")])
    try:
        statefill.read_ledger(L)
        raise AssertionError("expected SystemExit for a duplicate row")
    except SystemExit:
        pass
    write_ledger(L, [("a", "b", "c", "residence", "maybe", "USE")])
    try:
        statefill.read_ledger(L)
        raise AssertionError("expected SystemExit for an unknown status")
    except SystemExit:
        pass

# the shipped ledger parses, and every approved non-live row names a bundle the loader knows
shipped = statefill.read_ledger()
known = {(sid, bundle) for _f, sid, bundle, _st, _ab in statefill.STAGED}
known.add(statefill.NBER_SMALL)  # the NCHS-file small counts have their own reader (tests/test_nber_small.py)
known.add(statefill.ICPSR)  # the 1959-1967 county history has its own reader (pipeline/history_icpsr.py, statefill.icpsr_approved)
import hist_series  # noqa: E402  the state-level historical series have their own reader too (pipeline/hist_state.py, tests/test_hist_state.py)
known |= {(src["id"], hist_series.BUNDLE) for src in hist_series.SOURCES.values()}
for (sid, bundle, _m, _p), r in shipped.items():
    if r["status"] in statefill.APPROVED and bundle != "live":
        assert (sid, bundle) in known or (sid, bundle.removesuffix("_5yr")) in known, f"approved row the loader does not know: {sid}/{bundle}"
print("ok: ledger gate")
