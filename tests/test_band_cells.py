"""1-4 bands (WISH, MICA, MSTAHRS, SCAN say only "1-4"): shown in the tooltip for a cell CDC hides, under the same ledger gate as the exact fills.
Never a number, never a rate; a staged row, a SKIP verdict, a skipped year, a published count or an exact fill all keep a cell un-banded."""
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


# WISH covers Wisconsin (55); Adams exists in Illinois (17001) and Wisconsin (55001): names resolve inside the bundle's state only
COUNTIES = [{"fips": "55025", "name": "Dane"}, {"fips": "55001", "name": "Adams"}, {"fips": "55005", "name": "Barron"}, {"fips": "55007", "name": "Bayfield"},
            {"fips": "17001", "name": "Adams"}]
BUNDLE = {"state": "55",
          "data": {"cancer": {"2010": {"Dane": 900, "Barron": 6}, "2011": {"Dane": 910}}},      # Barron 2010 is an exact count (>= 5): not a band
          "masked": {"cancer": {"2010": ["Adams", "Barron", "Bayfield"], "2011": ["Adams"]}, "accidents": {"2010": ["Adams"]}},
          "narrow_1_4": {"heart": {"2010": ["Bayfield"]}}}

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "wi_wish_county_1999-2024.json").write_text(json.dumps(BUNDLE))
    L = d / "ledger.csv"

    # nothing approved: not even opened
    write_ledger(L, [("wi_wish", "wi_wish", "cancer", "residence", "staged", "USE")])
    out, notes = statefill.staged_bands(COUNTIES, statefill.read_ledger(L), bundle_dir=d / "nowhere")
    assert out == {}, out

    # approved + USE: cancer bands are read; heart (not approved) and accidents (no map measure) are not; Barron's exact 2010 count is not a band
    write_ledger(L, [("wi_wish", "wi_wish", "cancer", "residence", "approved", "USE"), ("wi_wish", "wi_wish", "heart", "residence", "staged", "USE")])
    out, notes = statefill.staged_bands(COUNTIES, statefill.read_ledger(L), bundle_dir=d)
    assert out == {"WI/wi_wish": {"cancer": {"2010": {"55001", "55007"}, "2011": {"55001"}}}}, out   # Adams = Wisconsin's, not Illinois'

    # approved, verdict not USE: not used and the reason is reported
    write_ledger(L, [("wi_wish", "wi_wish", "cancer", "residence", "approved", "SKIP")])
    out, notes = statefill.staged_bands(COUNTIES, statefill.read_ledger(L), bundle_dir=d)
    assert out == {} and any("bands not used" in n for n in notes), (out, notes)

    # MICA-style narrow_1_4 is a band too
    write_ledger(L, [("wi_wish", "wi_wish", "heart", "residence", "released", "USE")])
    out, notes = statefill.staged_bands(COUNTIES, statefill.read_ledger(L), bundle_dir=d)
    assert out == {"WI/wi_wish": {"heart": {"2010": {"55007"}}}}, out

    # approved but the bundle file is gone: stop
    try:
        statefill.staged_bands(COUNTIES, statefill.read_ledger(L), bundle_dir=d / "nowhere")
        raise AssertionError("expected SystemExit for a missing bundle")
    except SystemExit:
        pass

# band_hits: only cells still hidden (-1), never a published count or an exact fill, and never a skipped year
idx = {"55001": 0, "55005": 1, "55007": 2, "55025": 3}
counts = {"2010": [-1, 6, -1, 900], "2011": [-1, -1, -1, 910], "2012": [-1, -1, -1, 5]}
bands = {"2010": {"55001", "55005", "55007", "99999"}, "2011": {"55001"}, "2012": {"55001"}, "2013": {"55001"}}
hits = statefill.band_hits(counts, bands, {"2012"}, idx)
assert hits == {"2010": [0, 2], "2011": [0]}, hits       # 55005 is filled exactly (6), 2012 is a skipped year, 2013 has no counts, 99999 is not a county
assert statefill.band_hits(counts, None, set(), idx) == {}
assert statefill.band_hits({}, bands, set(), idx) == {}
# two states band cells of the same measure and year: both stay (a plain dict update would drop the first state's cells)
band = {}
statefill.merge_bands(band, {"2010": [3, 7], "2011": [3]})
statefill.merge_bands(band, {"2010": [5, 7], "2012": [9]})
assert band == {"2010": [3, 5, 7], "2011": [3], "2012": [9]}, band
print("test_band_cells: ok")
