"""Check the cause definitions in pipeline/history.py against published US totals (NCHS).
Counts every US-resident death in the cached NBER file, regardless of county.
Run: python tests/test_history_causes.py  (needs .cache/mort{year}.zip from a history build)"""
import sys, zipfile
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import history  # noqa: E402

# Published counts, US residents (NCHS Health, United States; NVSR final data)
PUBLISHED = {
    1980: {"all": 1989841, "suicide": 26869, "homicide": 24278, "heart": 761085, "stroke": 170225, "firearm": 33780},
    1995: {"all": 2312132, "suicide": 31284, "homicide": 22895, "heart": 737563, "stroke": 157991, "firearm": 35957},
    2004: {"all": 2397615, "suicide": 32439, "homicide": 17357, "heart": 652486, "stroke": 150074, "firearm": 29569},
}
TOL = 0.04

def totals(y):
    z = zipfile.ZipFile(history.CACHE / f"mort{y}.zip"); name = z.namelist()[0]
    head = pd.read_csv(z.open(name), nrows=1, dtype=str, encoding="latin-1").columns
    cols = ["restatus", "ucod"] + (["ucr34"] if "ucr34" in head else [])
    out = {k: 0 for k in ["all"] + list(PUBLISHED[y]) }
    for df in pd.read_csv(z.open(name), usecols=cols, dtype=str, chunksize=300_000, encoding="latin-1"):
        df = df[df.restatus != "4"]
        u = df.ucod.fillna("").str.strip()
        f = history.cause_flags_icd10(u) if y >= 1999 else history.cause_flags_icd89(u, df["ucr34"], icd8=y <= 1978)
        out["all"] += len(df)
        for k in out:
            if k != "all":
                out[k] += int(f[k].fillna(False).sum())
    return out

ok = True
for y, pub in PUBLISHED.items():
    got = totals(y)
    for k, v in pub.items():
        err = (got[k] - v) / v
        flag = "ok " if abs(err) <= TOL else "OFF"
        ok &= abs(err) <= TOL
        print(f"{flag} {y} {k:9s} ours {got[k]:>9,}  published {v:>9,}  {err:+.1%}")
sys.exit(0 if ok else 1)
