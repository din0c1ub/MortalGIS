"""The WONDER drop-in parser reads a real-format export (tab-delimited, quoted, notes footer)."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import build_data  # noqa: E402

SAMPLE = '''"Notes"\t"County"\t"County Code"\t"Year"\t"Year Code"\t"Deaths"\t"Population"\t"Crude Rate"
\t"Genesee County, MI"\t"26049"\t"2010"\t"2010"\t"68"\t"425790"\t"16.0"
\t"Alcona County, MI"\t"26001"\t"2010"\t"2010"\tSuppressed\t"10942"\tSuppressed
\t"Keweenaw County, MI"\t"26083"\t"2010"\t"2010"\t"0"\t"2156"\t"0.0"
\t"Bedford city, VA"\t"51515"\t"2010"\t"2010"\t"12"\t"6222"\t"Unreliable"
"Total"\t\t\t\t\t"38329"\t"309346863"\t"12.4"
"---"
"Dataset: Underlying Cause of Death, 1999-2020"
'''
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "overdose_residence_1999-2020.txt"
    p.write_text(SAMPLE)
    (Path(d) / "notes.txt").write_text("ignored")
    build_data.WONDER_DIR = Path(d)
    out = build_data.wonder_imports()
    got = out[("overdose", "res")]["2010"]
    assert got["26049"] == 68, got
    assert got["26001"] == -1, got          # Suppressed
    assert got["26083"] == 0, got           # zero kept
    assert got["51019"] == 12, got          # Bedford city merged into Bedford County
    assert len(got) == 4, got               # Total row and footer ignored
print("ok: WONDER parser")
