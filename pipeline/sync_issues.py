"""Keep GitHub Issues in step with site/data/coverage.json (run by the weekly workflow after coverage.py).

  [candidate] <id>: <name>    one per sources.yml entry with status: candidate   (label: candidate)
  [refresh] <id>: <name>      a live source that is due or failed to refresh      (label: refresh-due)
  [registry] Unregistered data files                                              (label: registry)

Issues are matched by their title prefix, so renaming a source keeps its issue. A candidate whose status
changes (live, rejected, parked) gets a closing comment. A refresh issue closes itself once the source is
fresh again. Discussion and decisions happen in the issues; the facts live in sources.yml.
Needs the gh CLI and GH_TOKEN with issues: write (the Actions GITHUB_TOKEN is enough).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"candidate": ("1f5f7a", "Possible new data source (from pipeline/sources.yml)"),
          "refresh-due": ("b8621b", "A source in use needs a new pull or is failing"),
          "registry": ("6a4c93", "pipeline/sources.yml needs an update")}
DRY = "--dry-run" in sys.argv


def gh(*args, input=None):
    if DRY and args[0] in ("issue", "label") and args[1] in ("create", "close", "comment", "edit"):
        print("DRY gh", " ".join(a if len(a) < 80 else a[:77] + "..." for a in args))
        return ""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, input=input).stdout


def body_candidate(s):
    rows = [("Fills", s.get("gap")), ("Value (1-5)", s.get("value")), ("Effort (1-5)", s.get("effort")),
            ("Access", s.get("access")), ("Kind", s.get("kind")), ("Link", s.get("url")), ("Notes", s.get("notes"))]
    t = "\n".join(f"- **{k}:** {v}" for k, v in rows if v not in (None, ""))
    return (f"{t}\n\n### To do\n- [ ] Check access, years, fields and license\n- [ ] Pull a sample and check it against the coverage gap\n"
            f"- [ ] Decide: set `status: live` (and wire it into the pipeline) or `status: rejected` with the reason in `notes`\n\n"
            f"_Opened automatically from `pipeline/sources.yml` (id `{s['id']}`). Edit the registry, not this text._")


def main():
    cov = json.loads((ROOT / "site" / "data" / "coverage.json").read_text())
    existing = {l["name"] for l in json.loads(gh("label", "list", "--limit", "200", "--json", "name"))}
    for name, (color, desc) in LABELS.items():
        if name not in existing:
            gh("label", "create", name, "--color", color, "--description", desc)
    issues = json.loads(gh("issue", "list", "--state", "all", "--limit", "1000", "--json", "number,title,state"))

    def find(prefix):
        hits = [i for i in issues if i["title"].startswith(prefix)]
        return next((i for i in hits if i["state"] == "OPEN"), hits[0] if hits else None)

    opened = closed = 0
    for s in cov["sources"]:
        sid = s["id"]
        # candidates
        cand = find(f"[candidate] {sid}:")
        if s.get("status") == "candidate":
            if not cand:
                gh("issue", "create", "--title", f"[candidate] {sid}: {s['name']}", "--label", "candidate", "--body", body_candidate(s))
                opened += 1
        elif cand and cand["state"] == "OPEN":
            gh("issue", "close", str(cand["number"]), "--comment", f"Registry status is now `{s.get('status')}`. {s.get('notes', '')}".strip())
            closed += 1
        # refresh due
        ref = find(f"[refresh] {sid}:")
        if s.get("due"):
            if not ref or ref["state"] != "OPEN":
                gh("issue", "create", "--title", f"[refresh] {sid}: {s['name']}", "--label", "refresh-due",
                   "--body", f"{s['due']}.\n\n- Access: {s.get('access')}\n- Data through: {s.get('dataThrough', '?')}\n"
                             f"- Last pulled: {s.get('lastPulled', 'n/a')}\n- Link: {s.get('url', '')}\n\n_Opened by the weekly build; closes itself when the source is fresh._")
                opened += 1
        elif ref and ref["state"] == "OPEN":
            gh("issue", "close", str(ref["number"]), "--comment", f"Fresh again (data through {s.get('dataThrough', '?')}).")
            closed += 1
    reg = find("[registry] Unregistered data files")
    if cov.get("unclaimed"):
        if not reg or reg["state"] != "OPEN":
            gh("issue", "create", "--title", "[registry] Unregistered data files", "--label", "registry",
               "--body", "These files load into the site but no `pipeline/sources.yml` entry lists them under `files:`:\n\n"
                         + "\n".join(f"- `data_manual/{f}`" for f in cov["unclaimed"]))
            opened += 1
    elif reg and reg["state"] == "OPEN":
        gh("issue", "close", str(reg["number"]), "--comment", "All files are registered.")
        closed += 1
    print(f"issues: {opened} opened, {closed} closed")


if __name__ == "__main__":
    main()
