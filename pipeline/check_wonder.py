"""Check CDC WONDER exports before uploading: python pipeline/check_wonder.py file1.csv file2.txt …
(no arguments = everything in data_manual/wonder/)."""
import sys, shutil, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import build_data as b

paths = [Path(p) for p in sys.argv[1:]] or sorted(b.WONDER_DIR.glob("*.*"))
tmp = Path(tempfile.mkdtemp())
for p in paths:
    shutil.copy(p, tmp / p.name)
b.WONDER_DIR = tmp
out = b.wonder_imports()
print()
for r in b.wonder_imports.report:
    if r["ok"]:
        print(f"OK    {r['file']}: {r['cause']} ({'where they lived' if r['place']=='res' else 'where they died'}), {r['countyYears']:,} county-years")
    else:
        print(f"FIX   {r['file']}: {r.get('cause','?')} — {r['why']}")
for (cause, place), years in sorted(out.items()):
    ys = sorted(years)
    print(f"      {cause}/{place}: years {ys[0]}–{ys[-1]}, {max(len(v) for v in years.values()):,} counties")
