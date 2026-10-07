"""What have we got, what's hidden or missing, what's next.

Run after build_data.py. Reads pipeline/sources.yml, site/data/* and data_manual/wonder/manifest.jsonl.
Writes:
  site/data/coverage.json   machine-readable (the app and the research-queue workflow read it)
  COVERAGE.md               the same, for people, at the repo root
Prints a short summary and, when $GITHUB_STEP_SUMMARY is set, writes it to the Actions run page.
"""
import datetime as dt
import fnmatch
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
MANUAL = ROOT / "data_manual"
MANIFEST = MANUAL / "wonder" / "manifest.jsonl"

# How long after its newest data a source counts as due for a refresh, by cadence (days).
DUE_AFTER = {"weekly": 45, "monthly": 120, "quarterly": 200, "yearly": 550, "manual-yearly": 400}
# WONDER pulls go stale by export date, not data date (provisional years fill in).
WONDER_DUE = {"wonder_prov": 150, "wonder_state_month": 100}


def today():
    return dt.date.today()


def parse_date(s):
    s = str(s or "")
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            d = dt.datetime.strptime(s[:n], fmt).date()
            if n == 4:
                d = dt.date(d.year, 12, 31)
            return d
        except ValueError:
            pass
    return None


def load_manifest():
    rows = []
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def hidden_share(d, p):
    c = (d.get("count") or {}).get(p)
    if not c:
        return None
    hid = sum(1 for v in c if v == -1)
    pub = sum(1 for v in c if v is not None and v != -1)
    return round(hid / (hid + pub), 3) if hid + pub else None


def measure_rows(meta):
    srcs = meta.get("sources", {})
    out = []
    for m in meta["measures"]:
        try:
            d = json.loads((DATA / f"m_{m['key']}.json").read_text())
        except (OSError, ValueError):
            continue
        nums = sorted(int(p) for p in m["periods"] if str(p).isdigit())
        if not nums:
            continue
        years = {}
        for y in range(nums[0], nums[-1] + 1):
            p = str(y)
            s = (d.get("src") or {}).get(p)
            have = p in (d.get("rate") or {}) or p in (d.get("count") or {})
            cell = {"src": s} if s else {}
            if not have:
                cell["missing"] = True
                if m.get("place") == "occurrence" and 2005 <= y <= 2017:
                    cell["why"] = "not published: no national county-of-occurrence data 2005-2017"
            else:
                h = hidden_share(d, p)
                if h is not None:
                    cell["hidden"] = h
                if s and srcs.get(s, {}).get("partial"):
                    cell["partial"] = True
                if (d.get("modeled") or {}).get(p):
                    cell["modeled"] = True
            years[p] = cell
        hs = [c["hidden"] for c in years.values() if "hidden" in c]
        out.append({
            "key": m["key"], "label": m["label"], "place": m.get("place", "residence"),
            "first": nums[0], "last": nums[-1],
            "missingYears": [int(y) for y, c in years.items() if c.get("missing")],
            "partialYears": [int(y) for y, c in years.items() if c.get("partial")],
            "hiddenLatest": next((years[str(y)].get("hidden") for y in reversed(nums) if "hidden" in years.get(str(y), {})), None),
            "hiddenAvg": round(sum(hs) / len(hs), 3) if hs else None,
            "years": years,
        })
    return out


def source_rows(reg, meta, manifest):
    layers = {l["key"]: l for l in meta.get("incidents", [])}
    out = []
    for s in reg:
        r = {k: s.get(k) for k in ("id", "name", "status", "access", "kind", "cadence", "url", "gap", "value", "effort", "notes")}
        r = {k: v for k, v in r.items() if v is not None}
        if s.get("status") == "live":
            newest, why = None, None
            if s.get("layer") in layers:
                l = layers[s["layer"]]
                newest = parse_date(l.get("latest")) or (dt.date(max(l["years"]), 12, 31) if l.get("years") else None)
                if l.get("stale"):
                    why = "the last build could not refresh this layer (kept the previous file)"
            if s.get("files"):
                pulls = [m for m in manifest if any(fnmatch.fnmatch("wonder/" + m["file"], g) for g in s["files"])]
                if pulls:
                    r["lastPulled"] = max(m["exported"][:10] for m in pulls)
                    age = (today() - parse_date(r["lastPulled"])).days
                    lim = WONDER_DUE.get(s["id"])
                    if lim and age > lim:
                        why = why or f"last pulled {age} days ago; pull again to add newer provisional data"
                    r["dataThrough"] = max(m.get("last", "") for m in pulls)
            if newest:
                r["dataThrough"] = newest.isoformat()
                lim = s.get("due_after") or DUE_AFTER.get(s.get("cadence"))
                if lim and (today() - newest).days > lim and not why:
                    why = f"newest data is {(today() - newest).days} days old for a {s['cadence']} source"
            if why:
                r["due"] = why
        out.append(r)
    return out


def unclaimed_files(reg):
    """data_manual files no registry entry owns (they load, but nothing documents them)."""
    globs = [g for s in reg for g in (s.get("files") or [])]
    return [p.relative_to(MANUAL).as_posix() for p in sorted(MANUAL.rglob("*"))
            if p.is_file() and p.suffix.lower() in (".json", ".txt", ".csv", ".tsv")
            and not any(fnmatch.fnmatch(p.relative_to(MANUAL).as_posix(), g) for g in globs)]


def pct(v):
    return "–" if v is None else f"{v * 100:.0f}%"


def markdown(cov):
    L = [f"# MortalGIS data coverage", "",
         f"Generated {cov['generated'][:16].replace('T', ' ')} UTC by `pipeline/coverage.py` from `pipeline/sources.yml` and the built data. Don't edit by hand.", ""]
    due = [s for s in cov["sources"] if s.get("due")]
    L += ["## Needs attention", ""]
    if due or cov["unclaimed"]:
        L += [f"- **{s['id']}**: {s['due']}" for s in due]
        L += [f"- **Unregistered file** `data_manual/{f}`: add it to a `files:` list in sources.yml" for f in cov["unclaimed"]]
    else:
        L.append("Nothing due.")
    L += ["", "## County measures", "",
          "Hidden = share of counties whose count is 1–9 and therefore not published (CDC confidentiality rule).", "",
          "| Measure | Counted where | Years | Hidden, latest year | Hidden, average | Gaps |", "|---|---|---|---|---|---|"]
    for m in cov["measures"]:
        gaps = []
        if m["partialYears"]:
            gaps.append(f"large counties only {span(m['partialYears'])}")
        if m["missingYears"]:
            gaps.append(f"no data {span(m['missingYears'])}")
        L.append(f"| {m['label']} | {'died' if m['place'] == 'occurrence' else 'lived'} | {m['first']}–{m['last']} | {pct(m['hiddenLatest'])} | {pct(m['hiddenAvg'])} | {'; '.join(gaps) or '–'} |")
    L += ["", "## Sources in use", "", "| Source | Access | Cadence | Data through | Last pulled |", "|---|---|---|---|---|"]
    for s in cov["sources"]:
        if s.get("status") == "live":
            L.append(f"| [{s['name']}]({s.get('url', '')}) (`{s['id']}`) | {s.get('access', '')} | {s.get('cadence', '')} | {s.get('dataThrough', '–')} | {s.get('lastPulled', '–')} |")
    L += ["", "## Research queue (candidates)", "", "Ranked by value ÷ effort. Each one has a GitHub issue labelled `candidate`.", "",
          "| Candidate | Value | Effort | Fills |", "|---|---|---|---|"]
    for s in cov["queue"]:
        L.append(f"| `{s['id']}` {s['name']} | {s.get('value', '?')} | {s.get('effort', '?')} | {s.get('gap', '')} |")
    L += ["", "## Set aside", ""]
    L += [f"- `{s['id']}` {s['name']} ({s['status']}): {s.get('notes', '')}" for s in cov["sources"] if s.get("status") in ("rejected", "parked")]
    return "\n".join(L) + "\n"


def span(ys):
    ys = sorted(ys)
    parts, start, prev = [], ys[0], ys[0]
    for y in ys[1:] + [None]:
        if y != (prev + 1 if prev is not None else None):
            parts.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = y
        prev = y
    return ", ".join(parts)


def main():
    reg = yaml.safe_load((ROOT / "pipeline" / "sources.yml").read_text())["sources"]
    ids = [s["id"] for s in reg]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"sources.yml: duplicate ids {sorted(dup)}")
    meta = json.loads((DATA / "meta.json").read_text())
    manifest = load_manifest()
    srows = source_rows(reg, meta, manifest)
    cov = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "measures": measure_rows(meta),
        "sources": srows,
        "queue": sorted([s for s in srows if s.get("status") == "candidate"],
                        key=lambda s: -(s.get("value") or 0) / max(1, s.get("effort") or 3)),
        "unclaimed": unclaimed_files(reg),
    }
    (DATA / "coverage.json").write_text(json.dumps(cov, separators=(",", ":")))
    md = markdown(cov)
    (ROOT / "COVERAGE.md").write_text(md)
    due = [s for s in srows if s.get("due")]
    print(f"coverage: {len(cov['measures'])} measures, {sum(s.get('status') == 'live' for s in srows)} live sources, "
          f"{len(cov['queue'])} candidates, {len(due)} due, {len(cov['unclaimed'])} unregistered files")
    for s in due:
        print(f"  due  {s['id']}: {s['due']}")
    for f in cov["unclaimed"]:
        print(f"  !!   unregistered file data_manual/{f}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md.split("## County measures")[0])


if __name__ == "__main__":
    main()
