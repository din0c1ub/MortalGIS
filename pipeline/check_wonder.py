"""Check CDC WONDER exports before uploading: python pipeline/check_wonder.py file1.csv file2.txt …
(no arguments = everything in data_manual/wonder/).

  --record   also add each JSON bundle to data_manual/wonder/manifest.jsonl (one line per distinct file
             version: export date, query, causes, years, counties, hidden cells, sha256), so every pull is
             documented and can be repeated. coverage.py reads the manifest to tell when a pull is due.
"""
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_data as b

args = [a for a in sys.argv[1:] if not a.startswith("--")]
record = "--record" in sys.argv
paths = [Path(p) for p in args] or sorted(p for p in b.WONDER_DIR.glob("*.*") if p.name != "manifest.jsonl" and p.suffix != ".md")
tmp = Path(tempfile.mkdtemp())
for p in paths:
    shutil.copy(p, tmp / p.name)
real_dir, b.WONDER_DIR = b.WONDER_DIR, tmp
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


def manifest_entry(p: Path):
    raw = p.read_bytes()
    bundle = json.loads(raw)
    data = bundle.get("data") or {}
    periods = sorted({str(y) for c in data.values() for y in c})
    cells = [v for c in data.values() for y in c.values() for v in y.values()]
    m = re.search(r"exported (\S+)", bundle.get("source", ""))
    return {
        "file": p.name, "sha256": hashlib.sha256(raw).hexdigest()[:16],
        "exported": bundle.get("exported") or (m.group(1) if m else ""),
        "source": re.sub(r",? exported \S+", "", bundle.get("source", "")),
        "place": bundle.get("place", "res"), "level": bundle.get("level", "county"),
        "causes": sorted(data), "first": periods[0] if periods else "", "last": periods[-1] if periods else "",
        "cells": len(cells), "hiddenCells": sum(1 for v in cells if v == -1),
        "query": bundle.get("query"), "note": bundle.get("note"),
    }


if record:
    man = real_dir / "manifest.jsonl"
    have = set()
    if man.exists():
        have = {json.loads(l)["sha256"] for l in man.read_text().splitlines() if l.strip()}
    added = 0
    with man.open("a") as fh:
        for p in paths:
            if p.suffix.lower() != ".json":
                continue
            e = manifest_entry(p)
            if e["sha256"] in have:
                continue
            fh.write(json.dumps(e) + "\n")
            added += 1
            print(f"recorded {p.name} (exported {e['exported'][:10]}, {e['cells']:,} cells, {e['hiddenCells']:,} hidden)")
    print(f"manifest: {added} new entr{'y' if added == 1 else 'ies'} in {man}")
