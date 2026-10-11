"""The exact 1-9 counts from the NCHS files (ledger source nber_small) are read only for approved measure/place pairs."""
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


FILE = {"data": {"suicide": {"res": {"1975": {"01005": 4, "01007": 12}, "1980": {"01005": 9}}, "occ": {"1975": {"01005": 3}}},
                 "all": {"res": {"1975": {"01005": 2}}}}}

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    f, L = d / "nber_exact_small.json", d / "ledger.csv"
    f.write_text(json.dumps(FILE))
    S = ("nber_small", "nber_small")

    # nothing approved: the file is not even opened
    write_ledger(L, [(*S, "suicide", "residence", "staged", "n/a")])
    out, notes = statefill.nber_small(statefill.read_ledger(L), path=d / "nowhere.json")
    assert out == {} and notes == [], (out, notes)

    # residence approved, occurrence staged: only residence cells, and only values 1-9
    write_ledger(L, [(*S, "suicide", "residence", "approved", "n/a"), (*S, "suicide", "occurrence", "staged", "n/a")])
    out, notes = statefill.nber_small(statefill.read_ledger(L), path=f)
    assert out == {("suicide", "res"): {"1975": {"01005": 4}, "1980": {"01005": 9}}}, out   # 12 is not a small count; occ is not approved

    # all_deaths is the ledger's name for the file's 'all'
    write_ledger(L, [(*S, "all_deaths", "residence", "released", "n/a"), (*S, "suicide", "occurrence", "approved", "n/a")])
    out, notes = statefill.nber_small(statefill.read_ledger(L), path=f)
    assert out == {("all", "res"): {"1975": {"01005": 2}}, ("suicide", "occ"): {"1975": {"01005": 3}}}, out

    # approved but no such cells in the file: reported, not silent
    write_ledger(L, [(*S, "heart", "residence", "approved", "n/a")])
    out, notes = statefill.nber_small(statefill.read_ledger(L), path=f)
    assert out == {} and any("no such cells" in n for n in notes), (out, notes)

    # approved but the file is gone: stop
    write_ledger(L, [(*S, "suicide", "residence", "approved", "n/a")])
    try:
        statefill.nber_small(statefill.read_ledger(L), path=d / "nowhere.json")
        raise AssertionError("expected SystemExit for a missing file")
    except SystemExit:
        pass

    # a state source's rows with the same measure name never switch the NCHS cells on
    write_ledger(L, [("il_idph_causes", "il_causes", "suicide", "residence", "approved", "USE")])
    out, notes = statefill.nber_small(statefill.read_ledger(L), path=d / "nowhere.json")
    assert out == {}, out

# the shipped ledger and file agree: every cell is 1-9, every approved row has cells, terms are on record
shipped = statefill.read_ledger()
rows = {k: r for k, r in shipped.items() if (k[0], k[1]) == statefill.NBER_SMALL}
if rows:
    assert all(r["terms_status"] == "stated_review" for r in rows.values() if "terms_status" in r), "nber_small rows must carry stated_review"
    out, notes = statefill.nber_small(shipped)
    assert not notes, notes
    for cells in out.values():
        for y, cs in cells.items():
            assert all(1 <= n <= 9 for n in cs.values())
print("ok")
