#!/usr/bin/env python3
"""MortalGIS master file: build, reload the ledger, check, export, summarise.

  python3 -I master.py build   --site <site/data> --registry <pipeline/sources.yml> --proposed <sources_proposed.yml> --staging <bundles dir> --db mortalgis_master.duckdb
  python3 -I master.py ledger  --db mortalgis_master.duckdb          # reload ledger.csv (after you edit status / approved_by) and refresh `released`
  python3 -I master.py check   --site <site/data> --db mortalgis_master.duckdb [--fill-union <fill_union.py>]
  python3 -I master.py export-json --db mortalgis_master.duckdb --out <dir>   # rebuilds the site's m_*.json from the master (used by `check` for parity)
  python3 -I master.py stats   --db mortalgis_master.duckdb

Nothing here touches the site or any remote. `build` writes the DuckDB file to --db and rewrites ledger.csv next to this script
(ledger.csv keeps whatever you typed in status / approved_by / approved_on / note). The weekly build (pipeline/build_data.py) reads ledger.csv
through pipeline/statefill.py; `check` confirms that file and this one describe the same bundles.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------------------------- constants
# Staged cause key -> site measure key (the same map stage_check.py uses). Other causes (accidents, mvc ...) are kept raw.
KEYMAP = {"falls": "falls", "homicide": "homicide", "suicide": "suicide", "cancer": "cancer", "heart": "heart", "stroke": "stroke",
          "alzheimers": "alzheimers", "diabetes": "diabetes", "liver": "liver", "clrd": "clrd", "flu": "flu_pneumonia", "flu_pneumonia": "flu_pneumonia",
          "kidney": "kidney", "covid": "covid", "all": "all_deaths", "firearm": "firearm", "overdose": "overdose", "alcohol": "alcohol"}
STATE_ABBR = {"01": "AL", "12": "FL", "13": "GA", "17": "IL", "18": "IN", "24": "MD", "26": "MI", "28": "MS", "29": "MO", "37": "NC", "45": "SC", "47": "TN", "55": "WI", "08": "CO", "40": "OK", "34": "NJ", "27": "MN", "54": "WV", "51": "VA", "50": "VT", "25": "MA", "31": "NE", "20": "KS"}
# State sources the live build already uses to fill CDC-hidden cells (site/app.html FILLSRC) -> registry id
LIVE_FILL = {"26": "mi_mdhhs", "36": "ny_vitals", "35": "nm_ibis", "42": "pa_eddie"}
LIVE_FILL_ABBR = {"MI": "mi_mdhhs", "NY": "ny_vitals", "NM": "nm_ibis", "PA": "pa_eddie"}
# The map's own `src` keys -> publisher family. CDC WONDER, VSRR, the NCHS files and the Atlas are one voice (NCHS death certificates).
SITE_FAMILY = {"nber": "cdc_nchs", "nber_partial": "cdc_nchs", "psx4": "cdc_nchs", "cdc2020": "cdc_nchs", "wonder": "cdc_nchs",
               "atlas": "cdc_nchs", "rpvx": "cdc_nchs", "census": "census", "chr": "chr", "fars": "nhtsa", "noaa": "noaa"}
SOURCE_FAMILY = {"mi_mdhhs": "MI", "mi_fatal_injuries": "MI", "ny_vitals": "NY", "nm_ibis": "NM", "pa_eddie": "PA", "nc_schs_lcd": "NC",
                 "il_idph_causes": "IL", "il_idph_injury": "IL", "il_idph_overdose": "IL", "in_isdh_mortality": "IN",
                 "tn_health_county": "TN", "wi_wish": "WI", "mo_mica": "MO",
                 "al_dph": "AL", "fl_charts": "FL", "ga_oasis": "GA", "md_vsa": "MD", "ms_mstahrs": "MS", "sc_scan": "SC", "ok_ok2share": "OK", "co_cdphe": "CO", "nj_shad": "NJ", "mn_mdh_county": "MN", "wv_hsc_vital": "WV", "va_vdh_profiles": "VA", "va_ocme_annual": "VA", "vt_vdh_annual": "VT", "ma_deaths_report": "MA", "ne_dhhs_vital_report": "NE", "ks_kdhe_d25": "KS", "ks_kdhe_annual": "KS"}
# staged bundle files -> (registry source id, bundle name). Two files with the same bundle are merged before the agreement gate.
STAGED = [(["mi_injury_county_2000-2024.json"], "mi_fatal_injuries", "mi_injury"),
          (["nc_vital_stats_county_2019-2023.json"], "nc_schs_lcd", "nc_lcd"),
          (["il_causes_county_2008-2023.json"], "il_idph_causes", "il_causes"),
          (["il_injury_county_2010-2023.json"], "il_idph_injury", "il_injury"),
          (["il_overdose_county_2020-2023.json"], "il_idph_overdose", "il_overdose"),
          (["in_mortality_county_2000-2002.json", "in_mortality_county_2000-2017.json"], "in_isdh_mortality", "in_table5"),
          (["in_injury_county_2000-2002.json", "in_injury_county_2000-2017.json"], "in_isdh_mortality", "in_table9"),
          (["tn_county_2009-2022.json"], "tn_health_county", "tn_county"),
          (["wi_wish_county_1999-2024.json"], "wi_wish", "wi_wish"),
          (["mo_mica_county_1999-2024.json"], "mo_mica", "mo_mica"),
          (["al_113causes_county_2015-2024.json"], "al_dph", "al_113causes"),
          (["fl_charts_county_1970-2024.json"], "fl_charts", "fl_charts"),
          (["ga_oasis_county_1999-2024.json"], "ga_oasis", "ga_oasis"),
          (["md_vsa_county_1999-2024.json"], "md_vsa", "md_vsa"),
          (["ms_mstahrs_county_1999-2024.json"], "ms_mstahrs", "ms_mstahrs"),
          (["sc_scan_county_1999-2024.json"], "sc_scan", "sc_scan"),
          (["ok_ok2share_county_2010-2024.json"], "ok_ok2share", "ok_ok2share"),
          (["co_cdphe_county_2025.json"], "co_cdphe", "co_cdphe"),
          (["nj_shad_county_2000-2024.json"], "nj_shad", "nj_shad"),
          (["mn_mdh_county_2021-2024.json"], "mn_mdh_county", "mn_mdh_county"),
          (["wv_hsc_vital_1999-2006.json"], "wv_hsc_vital", "wv_hsc_vital"),
          (["va_vdh_profiles_1997-2013.json"], "va_vdh_profiles", "va_vdh_profiles"),
          (["va_ocme_annual_county_2014-2023.json"], "va_ocme_annual", "va_ocme_annual"),
          (["wv_hsc_vital_2016-2020.json"], "wv_hsc_vital", "wv_hsc_recent"),
          (["vt_vdh_annual_2009-2024.json"], "vt_vdh_annual", "vt_vdh_annual"),
          (["vt_vdh_early_county_2000-2005.json"], "vt_vdh_annual", "vt_vdh_early"),
          (["ma_deaths_report_county_2020-2022.json"], "ma_deaths_report", "ma_deaths_report"),
          (["ne_dhhs_vital_report_county_2008-2016.json"], "ne_dhhs_vital_report", "ne_dhhs_vital_report"),
          (["ne_dhhs_vital_early_county_2005-2007.json"], "ne_dhhs_vital_report", "ne_dhhs_vital_early"),
          (["ks_kdhe_d25_county_2016.json"], "ks_kdhe_d25", "ks_kdhe_d25"),
          (["ks_kdhe_annual_county_2001-2024.json"], "ks_kdhe_annual", "ks_kdhe_annual")]
BUNDLE_SOURCE = {bundle: sid for _files, sid, bundle in STAGED}
FIPS_OF = {**{ab: fips for fips, ab in STATE_ABBR.items()}, "NY": "36", "NM": "35", "PA": "42"}
# a state with several staged sources: the one named first here is used when the build's report does not say which filled a cell
STATE_DEFAULT_FILL = {}
for _f, _sid, _b in STAGED:
    STATE_DEFAULT_FILL.setdefault(FIPS_OF[SOURCE_FAMILY[_sid]], _sid)
STATE_DEFAULT_FILL.update(LIVE_FILL)  # Michigan keeps its live source
HELD = {("il_idph_overdose", "il_overdose", "overdose")}  # held for audit at the user's request
LEDGER_COLS = ["source_id", "bundle", "measure", "place", "period_from", "period_to", "status", "verdict", "checked_n", "agree_n", "agree_pct", "exact_pct",
               "low_years", "exact_fills", "band_cells", "discordant_n", "obs_n", "anchor_n", "anchor_off_n", "anchor_off_years",
               "terms_status", "warnings", "approved_by", "approved_on", "note"]
MANUAL_COLS = ["status", "approved_by", "approved_on", "note"]  # a person edits these; build never overwrites them
INT_COLS = ["checked_n", "agree_n", "exact_fills", "band_cells", "discordant_n", "obs_n", "anchor_n", "anchor_off_n"]
STATUSES = {"staged", "approved", "released", "held", "rejected", "candidate", "blocked", "parked"}
VERDICTS = {"USE", "SKIP", "NO_CDC_MEASURE", "n/a"}
TERMS = {"stated", "stated_review", "none_stated", "restricted", "unchecked"}
GATE_MIN_CHECKED, GATE_MIN_SHARE, YEAR_MIN_CHECKED, YEAR_MIN_SHARE = 50, 0.90, 5, 0.80  # same rule as pipeline/build_data.py


def norm(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower().replace(".", "").strip()
    return n.replace("saint ", "st ")


def jdump(o) -> str:
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def family_of(s: dict) -> str:
    if s["id"] in SOURCE_FAMILY:
        return SOURCE_FAMILY[s["id"]]
    pub = str(s.get("publisher") or "")
    if re.search(r"CDC|NCHS|NBER", pub):
        return "cdc_nchs"
    return re.sub(r"[^a-z0-9]+", "_", pub.lower()).strip("_")[:24] or s["id"]


def derive_terms(s: dict) -> str:
    lic = str(s.get("license") or "")
    if not lic or lic == "None":
        return "unchecked"
    if re.search(r"forbid|proprietary|not redistribut|no redistribution", lic, re.I):
        return "restricted"
    if re.search(r"no license stated|not stated", lic, re.I):
        return "none_stated"
    return "stated"


# ----------------------------------------------------------------------------------------------- build
def load_registry(registry: Path, proposed: Path) -> dict:
    reg = {s["id"]: s for s in yaml.safe_load(registry.read_text())["sources"]}
    if proposed and proposed.exists():
        for s in yaml.safe_load(proposed.read_text())["sources"]:
            reg[s["id"]] = {**reg.get(s["id"], {}), **s}  # the newer proposed entry wins
    return reg


def build_sources(con, reg: dict):
    terms = {}
    tp = HERE / "sources_terms.csv"
    if tp.exists():
        for r in csv.DictReader(tp.open(newline="")):
            terms[r["source_id"]] = r
    rows = []
    for sid, s in reg.items():
        t = terms.get(sid)
        status = t["terms_status"] if t else derive_terms(s)
        rows.append((sid, s.get("name"), s.get("publisher"), family_of(s), s.get("url"), str(s.get("license")) if s.get("license") else None,
                     s.get("access"), s.get("kind"), s.get("geography"), ",".join(map(str, s.get("place") or [])) or None, s.get("grain"),
                     str(s.get("years")) if s.get("years") is not None else None, s.get("cadence"), s.get("hidden"), s.get("status"),
                     ",".join(s.get("src") or []) or None, s.get("notes"), status,
                     (t or {}).get("terms_url") or None, (t or {}).get("terms_checked_on") or None,
                     (t or {}).get("terms_note") or ("taken from the registry licence text; not re-read" if status != "unchecked" else None)))
    con.executemany("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CAST(? AS DATE),?)", rows)
    return len(rows)


def fill_sources(meta: dict) -> dict:
    """(state FIPS, measure) -> the source that filled hidden cells there, read from the build's own report (meta.stateFills).
    Keys look like 'MI:cancer' (a source the build reads itself) or 'IL/il_causes:heart' (a staged bundle approved in the ledger).
    The site file only flags a filled cell, it does not name the source, so a state whose two sources fill the same measure gets the first one."""
    out = {}
    for k, v in sorted((meta.get("stateFills") or {}).items()):
        if not v.get("used") or not v.get("filled"):
            continue
        head, cause = k.split(":")
        ab, _, bundle = head.partition("/")
        sid = BUNDLE_SOURCE[bundle] if bundle else LIVE_FILL_ABBR[ab]
        out.setdefault((FIPS_OF[ab], KEYMAP.get(cause, cause)), sid)
    return out


def build_cells(con, site: Path, counties: list):
    fips = [c[0] for c in counties]
    N = len(fips)
    fips_arr = pd.Series(fips, dtype="object")
    n_cells = n_spans = 0
    meta = json.loads((site / "meta.json").read_text())
    measures = meta["measures"]
    fsrc = fill_sources(meta)
    for m in measures:
        key = m["key"]
        d = json.loads((site / f"m_{key}.json").read_text())
        con.execute("INSERT INTO measures VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [key, m.get("label"), m.get("group"), m.get("place"), m.get("unit"), m.get("rateType"), bool(m.get("hasCounts")),
                     m.get("pair"), m.get("defaultPeriod"), d.get("filledBy"), jdump(m)])
        counts, rates, srcs = d.get("count") or {}, d.get("rate") or {}, d.get("src") or {}
        filled, modeled = d.get("filled") or {}, d.get("modeled") or {}
        periods = sorted(set(counts) | set(rates) | set(srcs) | set(filled) | set(modeled))
        con.executemany("INSERT INTO period_src VALUES (?,?,?,?,?,?,?)",
                        [(key, p, srcs.get(p), p in counts, p in rates, p in filled, p in modeled) for p in periods])
        bd = [(key, p, fips[i], 1, 4, fsrc.get((fips[i][:2], key)) or STATE_DEFAULT_FILL.get(fips[i][:2]))
              for p, ix in sorted((d.get("band") or {}).items()) for i in ix]
        if bd:
            con.executemany("INSERT INTO band_cells VALUES (?,?,?,?,?,?)", bd)
        frames = []
        for p in periods:
            c, r = counts.get(p), rates.get(p)
            if c is None and r is None:
                continue
            c = c if c is not None else [None] * N
            r = r if r is not None else [None] * N
            f = filled.get(p) or [0] * N
            mo = modeled.get(p) or [0] * N
            txt = pd.array([v if isinstance(v, str) else None for v in c], dtype="string")
            cs = pd.array([None if isinstance(v, str) else v for v in c], dtype="Float64")
            rs = pd.array(r, dtype="Float64")
            keep = ~cs.isna() | ~txt.isna() | ~pd.isna(rs)  # at least one of count / range / rate present
            fr = pd.DataFrame({"measure": key, "period": p, "fips": fips_arr, "count": cs, "count_text": txt, "rate": rs, "src": srcs.get(p),
                               "filled": [bool(x) for x in f], "modeled": [bool(x) for x in mo],
                               "fill_src": [("nber_small" if f[i] == 2 else (fsrc.get((fips[i][:2], key)) or STATE_DEFAULT_FILL.get(fips[i][:2]))) if f[i] else None for i in range(N)]})
            frames.append(fr[keep])
        if frames:
            df = pd.concat(frames, ignore_index=True)
            con.register("df_cells", df)
            con.execute("INSERT INTO cells SELECT measure, period, fips, count, count_text, rate, src, filled, modeled, fill_src FROM df_cells")
            con.unregister("df_cells")
            n_cells += len(df)
        sp_frames = []
        for span, sp in (d.get("spans") or {}).items():
            c, r = sp.get("count"), sp.get("rate")
            if c is None and r is None:
                continue
            c = c if c is not None else [None] * N
            r = r if r is not None else [None] * N
            cs, rs = pd.array(c, dtype="Float64"), pd.array(r, dtype="Float64")
            keep = ~cs.isna() | ~pd.isna(rs)
            fr = pd.DataFrame({"measure": key, "span": span, "fips": fips_arr, "count": cs, "rate": rs})
            sp_frames.append(fr[keep])
        if sp_frames:
            df = pd.concat(sp_frames, ignore_index=True)
            con.register("df_spans", df)
            con.execute("INSERT INTO span_cells SELECT * FROM df_spans")
            con.unregister("df_spans")
            n_spans += len(df)
    return n_cells, n_spans


def build_observations(con, staging: Path, counties: list):
    """Every value each staged bundle reports. Names are matched to FIPS within the bundle's state (plus the bundle's own fips_alias)."""
    by_state = {}
    for fips, name, _st in counties:
        by_state.setdefault(fips[:2], {})[norm(name)] = fips
    rows, log, own = [], [], []
    for files, sid, bundle in STAGED:
        for fn in files:
            b = json.loads((staging / fn).read_text())
            st = b["state"]
            # the state total the bundle prints itself: IL state_row {year: {cause: n}}; MO / WI / NC state_totals {cause: {year: n}}
            for y, cs in (b.get("state_row") or {}).items():
                own += [(sid, bundle, c, str(y), int(n)) for c, n in cs.items() if n is not None]
            for c, ys in (b.get("state_totals") or {}).items():
                if not c.endswith("_span"):
                    own += [(sid, bundle, c, str(y), int(n)) for y, n in ys.items() if str(y).isdigit() and n is not None]
            n2f = dict(by_state[st])
            for k, v in (b.get("fips_alias") or {}).items():
                n2f[norm(k)] = v
            fam = STATE_ABBR[st]
            unmatched, seen = {}, 0

            def add(cause, period, name, kind, value=None, lo=None, hi=None, bundle_name=bundle):
                nonlocal seen
                f = n2f.get(norm(name))
                if not f:
                    unmatched[name] = unmatched.get(name, 0) + 1
                    return
                rows.append((sid, bundle_name, fam, KEYMAP.get(cause), cause, str(period), f, kind, value, lo, hi))
                seen += 1

            for cause, years in (b.get("data") or {}).items():
                for y, cells in years.items():
                    for name, n in cells.items():
                        if n is not None:
                            add(cause, y, name, "exact", int(n), int(n), int(n))
            for cause, spans in (b.get("spans") or {}).items():
                for sp, cells in spans.items():
                    for name, n in cells.items():
                        if n is not None:
                            add(cause, sp, name, "exact", int(n), int(n), int(n), bundle_name=bundle + "_5yr")
            narrow = {(c, y): set(map(str, names)) for c, ys in (b.get("narrow_1_4") or {}).items() for y, names in ys.items()}
            for cause, years in (b.get("masked") or {}).items():  # WISH: X = under 5 and more than zero
                for y, names in years.items():
                    for name in names:
                        add(cause, y, name, "band", None, 1, 4)
            for (cause, y), names in narrow.items():  # MICA: tables whose every x is a trigger cell
                for name in sorted(names):
                    add(cause, y, name, "band", None, 1, 4)
            for cause, years in (b.get("x_cells") or {}).items():  # MICA: x that may be a complementary row
                for y, names in years.items():
                    for name in names:
                        if str(name) not in narrow.get((cause, y), set()):
                            add(cause, y, name, "masked")
            log.append(("bundle", f"{bundle}:{fn}", seen, ("unmatched names: " + json.dumps(dict(sorted(unmatched.items(), key=lambda kv: -kv[1])[:6]))) if unmatched else "all names matched"))
    df = pd.DataFrame(rows, columns=["source_id", "bundle", "family", "measure", "cause_raw", "period", "fips", "kind", "value", "lo", "hi"])
    before = len(df)
    df = df.drop_duplicates(subset=["source_id", "bundle", "cause_raw", "period", "fips", "kind"], keep="last")
    log.append(("bundle", "duplicates removed", before - len(df), "same bundle, cause, period, county and kind reported twice"))
    for c in ("value", "lo", "hi"):
        df[c] = pd.array(df[c], dtype="Int32")
    df["low_agreement_year"] = False
    df["released"] = False
    df = df.sort_values(["source_id", "bundle", "cause_raw", "period", "fips"]).reset_index(drop=True)
    con.register("df_obs", df)
    con.execute("INSERT INTO observations SELECT source_id, bundle, family, measure, cause_raw, period, fips, kind, value, lo, hi, low_agreement_year, released FROM df_obs")
    con.unregister("df_obs")
    con.executemany("INSERT INTO bundle_own_totals VALUES (?,?,?,?,?)", [(a, b, c, d, n) for (a, b, c, d), n in {(a, b, c, d): n for a, b, c, d, n in own}.items()])
    return len(df), log


def build_state_totals(con, site: Path):
    """State-level anchor. Loads CDC WONDER state x year totals (summed from the map's state_month files) and compares each staged
    bundle's county sums with them and with the state total the bundle prints itself. Warnings only; see schema.sql for the rules."""
    rows = []
    for p in sorted((site / "state_month").glob("*.json")):
        d = json.loads(p.read_text())
        measure = "all_deaths" if p.stem == "all" else p.stem
        for st, arr in d["series"].items():
            by = {}
            for m, v in zip(d["months"], arr):
                by.setdefault(m[:4], []).append(v)
            for y, vs in by.items():
                if len(vs) < 12 or any(v is None for v in vs):
                    continue  # a partial year
                known = sum(v for v in vs if v >= 0)
                rows.append((measure, y, st, known, known + 9 * sum(1 for v in vs if v == -1)))
    con.executemany("INSERT INTO wonder_state_totals VALUES (?,?,?,?,?)", rows)
    con.execute("""
        INSERT INTO state_totals
        WITH sc AS (SELECT state_fips, count(*) AS n FROM counties GROUP BY 1),
        b AS (SELECT o.source_id, o.bundle, o.cause_raw, o.measure, o.period, substr(o.fips, 1, 2) AS state_fips,
                     coalesce(sum(o.value) FILTER (WHERE o.kind = 'exact'), 0) AS exact_sum,
                     count(*) FILTER (WHERE o.kind = 'exact') AS n_exact,
                     count(*) FILTER (WHERE o.kind = 'band') AS n_band,
                     count(*) FILTER (WHERE o.kind = 'masked') AS n_masked
                FROM observations o WHERE o.period NOT LIKE '%-%' AND o.period <> 'TTM' GROUP BY ALL),
        j AS (SELECT b.*, sc.n AS n_state_counties, sc.n - b.n_exact - b.n_band - b.n_masked AS n_absent,
                     b.exact_sum + b.n_band + b.n_masked AS bundle_lo, b.exact_sum + 4 * b.n_band + 9 * b.n_masked AS bundle_hi,
                     w.lo AS wonder_lo, w.hi AS wonder_hi, t.own_total
                FROM b JOIN sc ON sc.state_fips = b.state_fips
                LEFT JOIN wonder_state_totals w ON w.measure = b.measure AND w.period = b.period AND w.state_fips = b.state_fips
                LEFT JOIN bundle_own_totals t ON t.source_id = b.source_id AND t.bundle = b.bundle AND t.cause_raw = b.cause_raw AND t.period = b.period),
        f AS (SELECT j.*,
                     CASE WHEN wonder_lo IS NULL THEN NULL
                          WHEN bundle_lo > wonder_hi + greatest(2, 0.02 * wonder_lo) THEN 'over'
                          WHEN n_absent <= 0 AND bundle_hi < wonder_lo - greatest(2, 0.02 * wonder_lo) THEN 'short' ELSE 'ok' END AS wonder_flag,
                     CASE WHEN own_total IS NULL THEN NULL
                          WHEN bundle_lo > own_total + greatest(2, 0.001 * own_total) THEN 'over'
                          WHEN n_absent <= 0 AND bundle_hi < own_total - greatest(2, 0.02 * own_total) THEN 'short' ELSE 'ok' END AS own_flag
                FROM j)
        SELECT source_id, bundle, cause_raw, measure, period, state_fips, n_state_counties, n_exact, n_band, n_masked, n_absent,
               bundle_lo, bundle_hi, wonder_lo, wonder_hi, own_total,
               round((bundle_lo - wonder_lo) / nullif(wonder_lo, 0), 4), round((bundle_lo - own_total) / nullif(own_total, 0), 4),
               wonder_flag, own_flag,
               CASE WHEN wonder_flag IS NULL AND own_flag IS NULL THEN 'no_reference'
                    WHEN coalesce(wonder_flag, 'ok') = 'ok' AND coalesce(own_flag, 'ok') = 'ok' THEN 'ok' ELSE 'off' END,
               nullif(concat_ws('+', CASE WHEN wonder_flag IN ('over', 'short') THEN 'wonder_' || wonder_flag END,
                                     CASE WHEN own_flag IN ('over', 'short') THEN 'own_' || own_flag END), '')
          FROM f ORDER BY source_id, bundle, cause_raw, period""")
    return len(rows)


def gate(con):
    """Agreement with CDC, per source x bundle x measure, by the build's own rule. Returns (groups, periods) DataFrames and marks low-agreement years."""
    per = con.execute("""
        SELECT o.source_id, o.bundle, o.measure, o.period,
               count(*) FILTER (WHERE c.count >= 10) AS checked,
               count(*) FILTER (WHERE c.count >= 10 AND abs(c.count - o.value) <= greatest(2, 0.1 * c.count)) AS agree,
               count(*) FILTER (WHERE c.count BETWEEN 10 AND 19) AS n1019,
               count(*) FILTER (WHERE c.count BETWEEN 10 AND 19 AND o.value = c.count) AS ex1019
          FROM observations o JOIN cells c ON c.measure = o.measure AND c.period = o.period AND c.fips = o.fips
         WHERE o.kind = 'exact' AND o.measure IS NOT NULL GROUP BY ALL
        UNION ALL
        SELECT o.source_id, o.bundle, o.measure, o.period,
               count(*) FILTER (WHERE c.count >= 10) AS checked,
               count(*) FILTER (WHERE c.count >= 10 AND abs(c.count - o.value) <= greatest(2, 0.1 * c.count)) AS agree,
               count(*) FILTER (WHERE c.count BETWEEN 10 AND 19) AS n1019,
               count(*) FILTER (WHERE c.count BETWEEN 10 AND 19 AND o.value = c.count) AS ex1019
          FROM observations o JOIN span_cells c ON c.measure = o.measure AND c.span = o.period AND c.fips = o.fips
         WHERE o.kind = 'exact' AND o.measure IS NOT NULL GROUP BY ALL""").df()
    per["low"] = (per.checked >= YEAR_MIN_CHECKED) & (per.agree / per.checked.where(per.checked > 0, 1) < YEAR_MIN_SHARE)
    g = per.groupby(["source_id", "bundle", "measure"]).agg(checked_n=("checked", "sum"), agree_n=("agree", "sum"),
                                                          n1019=("n1019", "sum"), ex1019=("ex1019", "sum")).reset_index()
    g["agree_pct"] = g.agree_n / g.checked_n.where(g.checked_n > 0)
    g["exact_pct"] = g.ex1019 / g.n1019.where(g.n1019 > 0)  # share of CDC-published counts of 10-19 that the state reproduces exactly
    g["verdict"] = ["USE" if (c >= GATE_MIN_CHECKED and a / c >= GATE_MIN_SHARE) else "SKIP" for c, a in zip(g.checked_n, g.agree_n)]
    low = per[per.low].groupby(["source_id", "bundle", "measure"]).period.apply(lambda s: ";".join(sorted(s))).rename("low_years").reset_index()
    g = g.merge(low, how="left", on=["source_id", "bundle", "measure"])
    lowp = per[per.low][["source_id", "bundle", "measure", "period"]]
    con.register("low_p", lowp)
    con.execute("""UPDATE observations o SET low_agreement_year = TRUE FROM low_p l
                    WHERE o.source_id = l.source_id AND o.bundle = l.bundle AND o.measure = l.measure AND o.period = l.period""")
    con.unregister("low_p")
    return g, per


NBER_SMALL_FILE = Path(os.environ.get("MORTALGIS_NBER_SMALL") or HERE.parent / "data_manual" / "nber_exact_small_1968-2004.json")
NBER_PLACE = {"res": "residence", "occ": "occurrence"}


def nber_small_rows(con, terms: dict):
    """Ledger rows (source nber_small) for the exact 1-9 counts the NCHS files carry for cells the map hides in its 1968-2004 history.
    One row per measure and place. exact_fills = the cells the map shows once the row is approved: staged cells that are hidden (count -1) in a
    year the map takes from those files (src nber / nber_partial), or already filled by this source. Cells in years the map takes from CDC
    stay hidden and are not counted. No CDC agreement gate applies (the cells come from the files the series itself is built from), so the
    verdict is n/a and the observations table does not hold them."""
    if not NBER_SMALL_FILE.exists():
        return []
    data = json.loads(NBER_SMALL_FILE.read_text()).get("data") or {}
    recs = [(cause, pl, "all_deaths" if cause == "all" else cause, y, f) for cause, places in data.items() for pl, ys in places.items()
            for y, cells in ys.items() for f in cells]
    df = pd.DataFrame(recs, columns=["cause", "pl", "measure", "period", "fips"])
    df["mkey"] = [m + ("_died" if pl == "occ" else "") for m, pl in zip(df.measure, df.pl)]
    con.register("nb_small", df)
    q = con.execute("""SELECT t.cause, t.pl, t.measure, count(*) AS staged_n,
                              count(*) FILTER (WHERE c.src IN ('nber','nber_partial') AND (c.count = -1 OR (c.filled AND c.fill_src = 'nber_small'))) AS fill_n,
                              min(t.period) FILTER (WHERE c.src IN ('nber','nber_partial') AND (c.count = -1 OR (c.filled AND c.fill_src = 'nber_small'))) AS p0,
                              max(t.period) FILTER (WHERE c.src IN ('nber','nber_partial') AND (c.count = -1 OR (c.filled AND c.fill_src = 'nber_small'))) AS p1
                         FROM nb_small t LEFT JOIN cells c ON c.measure = t.mkey AND c.period = t.period AND c.fips = t.fips
                        GROUP BY t.cause, t.pl, t.measure ORDER BY t.measure, t.pl""").fetchall()
    con.unregister("nb_small")
    out = []
    for cause, pl, measure, staged_n, fill_n, p0, p1 in q:
        w = ["wonder_9_or_fewer", "rate_under_20"]
        if terms.get("nber_small") in ("none_stated", "unchecked", "stated_review"):
            w.append("terms_" + terms["nber_small"])
        if fill_n < staged_n:
            w.append("cdc_years_stay_hidden")
        out.append(dict(source_id="nber_small", bundle="nber_small", measure=measure, place=NBER_PLACE[pl], period_from=p0 or "", period_to=p1 or "",
                        status="staged", verdict="n/a", checked_n=None, agree_n=None, agree_pct=None, exact_pct=None, low_years="", exact_fills=int(fill_n),
                        band_cells=0, discordant_n=None, obs_n=0, anchor_n=None, anchor_off_n=None, anchor_off_years="",
                        terms_status=terms.get("nber_small", "unchecked"), warnings=";".join(w), approved_by="", approved_on="",
                        note=f"{staged_n:,} exact 1-9 cells in the file; {staged_n - int(fill_n):,} are not shown (years the map takes from CDC, or cells a state source already fills)"))
    return out


def _hist_series():
    """pipeline/hist_series.py (plain data shared with pipeline/hist_state.py), loaded by path so this file needs no package setup."""
    import importlib.util
    p = Path(__file__).resolve().parents[1] / "pipeline" / "hist_series.py"
    spec = importlib.util.spec_from_file_location("hist_series_for_master", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hist_state_rows(terms: dict):
    """Ledger rows for the state-level historical mode (1900-1945): one per series, source miller_vsh_1900_1936 or nber_infant_1920_1945, bundle
    hist_state, place 'state'. No CDC overlap exists before 1959, so there is no agreement gate (verdict n/a); the build (pipeline/hist_state.py)
    reads only approved or released rows and runs its own internal checks. These rows stay out of the county STAGED lists."""
    p = Path(__file__).resolve().parents[1] / "pipeline" / "hist_series.py"
    if not p.exists():
        return []
    HS = _hist_series()
    out = []
    for s in HS.SERIES:
        src = HS.SOURCES[s["source"]]
        y0, y1 = (1900, 1936) if s["source"] == "miller" else (1920, 1945)
        w = ["no_cdc_overlap", "classification_breaks", "registration_area_only" if s["source"] == "miller" else "imputed_values_flagged"]
        if s["grade"] in ("C", "H"):
            w.append("no_modern_equivalent")
        t = terms.get(src["id"], "unchecked")
        if t in ("none_stated", "unchecked", "stated_review"):
            w.append("terms_" + t)
        what = ", ".join(s["cols"]) if s["cols"] else "infant deaths and births"
        out.append(dict(source_id=src["id"], bundle=HS.BUNDLE, measure=s["key"], place="state", period_from=str(y0), period_to=str(y1), status="staged",
                        verdict="n/a", checked_n=None, agree_n=None, agree_pct=None, exact_pct=None, low_years="", exact_fills=0, band_cells=0,
                        discordant_n=None, obs_n=0, anchor_n=None, anchor_off_n=None, anchor_off_years="", terms_status=t, warnings=";".join(w),
                        approved_by="", approved_on="",
                        note=f"state series, grade {s['grade']}: {s['label']} (printed column(s): {what}); state-level historical mode, not read by the county build"))
    return out


def ledger_rows(con, reg: dict, site: Path):
    g, _per = gate(con)
    meta = json.loads((site / "meta.json").read_text())
    sf = meta.get("stateFills") or {}  # the build's own report of what it filled, per state source and cause
    obs = con.execute("""SELECT o.source_id, o.bundle, coalesce(o.measure, o.cause_raw) AS measure, any_value(o.measure IS NULL) AS no_measure,
                                min(o.period) AS period_from, max(o.period) AS period_to,
                                count(*) FILTER (WHERE o.kind = 'exact') AS obs_n,
                                count(*) FILTER (WHERE o.kind = 'masked') AS masked_n,
                                count(*) FILTER (WHERE o.kind = 'band') AS band_obs_n
                           FROM observations o GROUP BY o.source_id, o.bundle, coalesce(o.measure, o.cause_raw)""").df()
    fills = con.execute("SELECT source_id, bundle, measure, count(DISTINCT period || '|' || fips) AS n FROM fill_candidates GROUP BY ALL").df()
    bands = con.execute("""SELECT source_id, bundle, measure, count(DISTINCT period || '|' || fips) AS n FROM (
                              SELECT o.source_id, o.bundle, o.measure, o.period, o.fips FROM observations o JOIN cells c
                                ON c.measure = o.measure AND c.period = o.period AND c.fips = o.fips
                               WHERE o.kind = 'band' AND c.count = -1 AND NOT o.low_agreement_year
                              UNION ALL
                              SELECT o.source_id, o.bundle, o.measure, o.period, o.fips FROM observations o JOIN span_cells c
                                ON c.measure = o.measure AND c.span = o.period AND c.fips = o.fips
                               WHERE o.kind = 'band' AND c.count = -1 AND NOT o.low_agreement_year) GROUP BY ALL""").df()
    anc = con.execute("""SELECT source_id, bundle, coalesce(measure, cause_raw) AS measure,
                                count(*) FILTER (WHERE flag <> 'no_reference') AS n, count(*) FILTER (WHERE flag = 'off') AS off,
                                string_agg(period || ' ' || detail, ';' ORDER BY period) FILTER (WHERE flag = 'off') AS yrs,
                                count(*) FILTER (WHERE flag = 'off' AND n_band + n_masked > 0 AND wonder_lo > 0 AND bundle_hi < 0.9 * wonder_lo) AS band_off
                           FROM state_totals GROUP BY ALL""").df()
    terms = dict(con.execute("SELECT id, terms_status FROM sources").fetchall())
    fam = dict(con.execute("SELECT id, family FROM sources").fetchall())
    out = []
    for _, r in obs.iterrows():
        gg = g[(g.source_id == r.source_id) & (g.bundle == r.bundle) & (g.measure == r.measure)]
        have = len(gg) > 0
        verdict = ("USE" if gg.iloc[0].verdict == "USE" else "SKIP") if have else "NO_CDC_MEASURE"
        chk = int(gg.iloc[0].checked_n) if have else None
        agr = int(gg.iloc[0].agree_n) if have else None
        pct = round(agr / chk, 4) if have and chk else None
        epct = round(float(gg.iloc[0].exact_pct), 4) if have and pd.notna(gg.iloc[0].exact_pct) else None
        en = int(gg.iloc[0].n1019) if have else 0
        low = gg.iloc[0].low_years if have and isinstance(gg.iloc[0].low_years, str) else ""
        f = fills[(fills.source_id == r.source_id) & (fills.bundle == r.bundle) & (fills.measure == r.measure)]
        b = bands[(bands.source_id == r.source_id) & (bands.bundle == r.bundle) & (bands.measure == r.measure)]
        ex = int(f.n.sum()) if verdict == "USE" else 0
        # once a bundle is approved and built into the map its cells are no longer hidden, so count what the build filled too
        rep = sf.get(f"{SOURCE_FAMILY.get(r.source_id)}/{r.bundle}:{'all' if r.measure == 'all_deaths' else r.measure}")
        if rep and rep.get("used"):
            ex += int(rep.get("filled") or 0)
        bd = int(b.n.sum()) if verdict == "USE" else 0
        w = []
        if ex:
            w += ["wonder_9_or_fewer", "rate_under_20"]
        if bd:
            w.append("band_only_1_4")
        if r.masked_n:
            w.append("x_cells_not_narrowable")
        if terms.get(r.source_id) in ("none_stated", "unchecked", "stated_review"):
            w.append("terms_" + terms[r.source_id])
        if low:
            w.append("low_agreement_years")
        if have and chk and chk < 100 and verdict == "USE":
            w.append("gate_sample_small")
        if have and pct is not None and pct < 0.95 and verdict == "USE":
            w.append("agreement_under_95")
        if have and epct is not None and en >= 100 and epct < 0.80 and verdict == "USE":
            w.append("exact_match_under_80")  # the state's count often differs from CDC's by 1-2 where both are published
        a = anc[(anc.source_id == r.source_id) & (anc.bundle == r.bundle) & (anc.measure == r.measure)]
        a_n = int(a.n.iloc[0]) if len(a) else None
        a_off = int(a.off.iloc[0]) if len(a) else None
        a_yrs = a.yrs.iloc[0] if len(a) and isinstance(a.yrs.iloc[0], str) else ""
        if a_off:
            w.append("state_total_off")
        if len(a) and int(a.band_off.iloc[0]) and (bd or r.masked_n):
            w.append("band_years_unreliable")  # a masked column whose upper bound is far below the state total is not a 1-4 band
        if r.bundle.endswith("_5yr"):
            w.append("spans_not_in_map")  # 5-year totals are loaded and checked, but the map does not use them yet
        status = "held" if (r.source_id, r.bundle, r.measure) in HELD else "staged"
        if status == "held":
            w.append("review_before_use")
        place = "residence"
        out.append(dict(source_id=r.source_id, bundle=r.bundle, measure=r.measure, place=place, period_from=r.period_from, period_to=r.period_to,
                        status=status, verdict=verdict, checked_n=chk, agree_n=agr, agree_pct=pct, exact_pct=epct, low_years=low, exact_fills=ex, band_cells=bd,
                        discordant_n=(chk - agr) if have else None, obs_n=int(r.obs_n) + int(r.band_obs_n) + int(r.masked_n),
                        anchor_n=a_n, anchor_off_n=a_off, anchor_off_years=a_yrs,
                        terms_status=terms.get(r.source_id, "unchecked"), warnings=";".join(w), approved_by="", approved_on="", note=""))
    # overlap: same publisher family, same measure, more than one bundle
    df = pd.DataFrame(out)
    fam_measure = {}
    for r in out:
        fam_measure.setdefault((fam.get(r["source_id"]), r["measure"]), set()).add(r["bundle"].replace("_5yr", ""))
    for r in out:
        if len(fam_measure[(fam.get(r["source_id"]), r["measure"])]) > 1 and r["verdict"] == "USE":
            r["warnings"] = ";".join([x for x in r["warnings"].split(";") if x] + ["overlaps_other_bundle"])

    # the build's own live state fills: per-state, per-cause report written by build_data.py
    mkeys = {m["key"] for m in meta["measures"]}
    for k, v in sorted(sf.items()):
        ab, cause = k.split(":")
        if "/" in ab:  # a staged bundle the build used; its ledger row is made below, from the bundle itself
            continue
        sid = LIVE_FILL_ABBR[ab]
        measure = KEYMAP.get(cause, cause)
        used = bool(v.get("used"))
        w = ["wonder_9_or_fewer", "rate_under_20"] if v.get("filled") else []
        if terms.get(sid) in ("none_stated", "unchecked"):
            w.append("terms_" + terms[sid])
        if v.get("skippedYears"):
            w.append("low_agreement_years")
        pf = con.execute("SELECT min(period), max(period) FROM cells WHERE filled AND fill_src = ? AND measure = ?", [sid, measure]).fetchone()
        chk = int(v.get("checked") or 0)
        out.append(dict(source_id=sid, bundle="live", measure=measure, place="residence", period_from=pf[0] or "", period_to=pf[1] or "",
                        status="released" if used else "staged", verdict="USE" if used else "SKIP", checked_n=chk,
                        agree_n=round(float(v.get("agree") or 0) * chk), agree_pct=v.get("agree"), low_years=";".join(v.get("skippedYears") or []),
                        exact_fills=int(v.get("filled") or 0), band_cells=0, discordant_n=chk - round(float(v.get("agree") or 0) * chk),
                        obs_n=int(v.get("filled") or 0), terms_status=terms.get(sid, "unchecked"), warnings=";".join(w),
                        approved_by="", approved_on="", note="from meta.stateFills (build_data.py); used=%s" % used))
    out += nber_small_rows(con, terms)
    out += hist_state_rows(terms)
    # every other registry entry: one row so the ledger answers "what have we got, what is missing"
    have = {r["source_id"] for r in out}
    for sid, s in reg.items():
        if sid in have:
            continue
        rs = s.get("status")
        status = {"live": "released", "proposed-live": "staged", "hold-for-audit": "held"}.get(rs, rs if rs in STATUSES else "candidate")
        w = ["terms_" + terms[sid]] if terms.get(sid) in ("none_stated", "unchecked") else []
        out.append(dict(source_id=sid, bundle="live" if rs == "live" else "registry", measure="*", place="", period_from="", period_to="",
                        status=status, verdict="n/a", checked_n=None, agree_n=None, agree_pct=None, low_years="", exact_fills=0, band_cells=0,
                        discordant_n=None, obs_n=0, terms_status=terms.get(sid, "unchecked"), warnings=";".join(w), approved_by="", approved_on="",
                        note=f"registry status: {rs}"))
    return out


def write_ledger_csv(rows: list, path: Path):
    old = {}
    if path.exists():
        for r in csv.DictReader(path.open(newline="")):
            old[(r["source_id"], r["bundle"], r["measure"], r["place"])] = r
    for r in rows:
        k = (r["source_id"], r["bundle"], r["measure"], r["place"])
        if k in old:
            for c in MANUAL_COLS:
                if old[k].get(c):
                    r[c] = old[k][c]
    rows.sort(key=lambda r: (r["status"] not in ("released",), r["source_id"], r["bundle"], r["measure"]))
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None or (isinstance(r.get(c), float) and pd.isna(r.get(c))) else r.get(c)) for c in LEDGER_COLS})


def load_ledger(con, path: Path):
    rows = list(csv.DictReader(path.open(newline="")))
    con.execute("DELETE FROM ledger")
    data = []
    for r in rows:
        rec = []
        for c in LEDGER_COLS:
            v = (r.get(c) or "").strip()
            if c in INT_COLS:
                rec.append(int(float(v)) if v else None)
            elif c in ("agree_pct", "exact_pct"):
                rec.append(float(v) if v else None)
            else:
                rec.append(v)
        data.append(rec)
    con.executemany("INSERT INTO ledger VALUES (" + ",".join("?" * len(LEDGER_COLS)) + ")", data)
    refresh_released(con)
    return len(data)


def refresh_released(con):
    """An observation is eligible for the map only when its ledger row is approved/released, the gate says USE, and its year passed."""
    con.execute("UPDATE observations SET released = FALSE")
    con.execute("""UPDATE observations o SET released = TRUE FROM ledger l
                    WHERE l.source_id = o.source_id AND l.bundle = o.bundle AND l.measure = o.measure AND l.place = 'residence'
                      AND l.status IN ('approved', 'released') AND l.verdict = 'USE' AND NOT o.low_agreement_year""")


def build(a):
    site, staging, db = Path(a.site), Path(a.staging), Path(a.db)
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    con.execute(Path(a.schema).read_text())
    meta = json.loads((site / "meta.json").read_text())
    counties = meta["counties"]
    con.executemany("INSERT INTO counties VALUES (?,?,?,?,?)", [(c[0], c[1], c[2], c[0][:2], i) for i, c in enumerate(counties)])
    con.executemany("INSERT INTO site_sources VALUES (?,?,?,?,?)",
                    [(k, v.get("label"), v.get("url"), bool(v.get("partial")), SITE_FAMILY.get(k, k)) for k, v in meta["sources"].items()])
    reg = load_registry(Path(a.registry), Path(a.proposed) if a.proposed else None)
    n_src = build_sources(con, reg)
    n_cells, n_spans = build_cells(con, site, counties)
    n_obs, log = build_observations(con, staging, counties)
    n_wonder = build_state_totals(con, site)
    rows = ledger_rows(con, reg, site)
    lp = Path(a.ledger)
    write_ledger_csv(rows, lp)
    n_led = load_ledger(con, lp)
    con.executemany("INSERT INTO load_log VALUES (?,?,?,?)", log)
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    con.executemany("INSERT INTO meta VALUES (?,?)", [("built_at", built), ("site_generated", str(meta.get("generated"))),
                                                      ("cells", str(n_cells)), ("span_cells", str(n_spans)), ("observations", str(n_obs)),
                                                      ("sources", str(n_src)), ("ledger_rows", str(n_led)), ("wonder_state_years", str(n_wonder)),
                                                      ("note", "Built from the site's m_*.json plus staged bundles. See schema.sql.")])
    con.execute("CHECKPOINT")
    con.close()
    tmp = db.with_suffix(".compact")  # a fresh copy drops the slack left by many inserts (38 MB -> 33 MB)
    if tmp.exists():
        tmp.unlink()
    c2 = duckdb.connect()
    c2.execute(f"ATTACH '{db}' AS old (READ_ONLY)")
    c2.execute(f"ATTACH '{tmp}' AS new")
    c2.execute("COPY FROM DATABASE old TO new")
    c2.execute("CHECKPOINT new")
    c2.close()
    tmp.replace(db)
    print(f"built {db}  cells {n_cells:,}  span cells {n_spans:,}  observations {n_obs:,}  sources {n_src}  ledger rows {n_led}  ({db.stat().st_size/1e6:.1f} MB)")
    for l in log:
        print("  ", *l)


# ----------------------------------------------------------------------------------------------- export + check
def _whole(c):
    return int(c) if c is not None and float(c).is_integer() else c


def export_measure(con, key: str, N: int, idx: dict):
    ps = con.execute("SELECT period, src, has_count, has_rate, has_filled, has_modeled FROM period_src WHERE measure = ?", [key]).fetchall()
    cells = con.execute("SELECT period, fips, coalesce(count_text, CAST(count AS VARCHAR)) AS cnt, count, count_text, rate, CASE WHEN fill_src = 'nber_small' THEN 2 WHEN filled THEN 1 ELSE 0 END, modeled FROM cells WHERE measure = ?", [key]).fetchall()
    out = {"rate": {}, "src": {}}
    count, filled, modeled = {}, {}, {}
    for p, src, hc, hr, hf, hm in ps:
        out["src"][p] = src
        if hr:
            out["rate"][p] = [None] * N
        if hc:
            count[p] = [None] * N
        if hf:
            filled[p] = [0] * N
        if hm:
            modeled[p] = [0] * N
    for p, f, _cnt, c, ctext, r, fl, mo in cells:
        i = idx[f]
        if p in count:
            count[p][i] = ctext if ctext is not None else _whole(c)
        if p in out["rate"]:
            out["rate"][p][i] = r
        if fl and p in filled:
            filled[p][i] = fl  # 1 = a state's count, 2 = the exact small count from the NCHS files (source nber_small)
        if mo and p in modeled:
            modeled[p][i] = 1
    if count:
        out["count"] = count
    if modeled:
        out["modeled"] = modeled
    if filled:
        out["filled"] = filled
    band = {}
    for p, f in con.execute("SELECT period, fips FROM band_cells WHERE measure = ? ORDER BY period, fips", [key]).fetchall():
        band.setdefault(p, []).append(idx[f])
    if band:
        out["band"] = {p: sorted(v) for p, v in band.items()}
    fb = con.execute("SELECT filled_by FROM measures WHERE key = ?", [key]).fetchone()[0]
    if fb:
        out["filledBy"] = fb
    spans = {}
    for span, f, c, r in con.execute("SELECT span, fips, count, rate FROM span_cells WHERE measure = ?", [key]).fetchall():
        s = spans.setdefault(span, {"count": [None] * N, "rate": [None] * N})
        s["count"][idx[f]] = _whole(c)
        s["rate"][idx[f]] = r
    if spans:
        out["spans"] = spans
    return out


def export_json(a):
    con = duckdb.connect(a.db, read_only=True)
    counties = con.execute("SELECT fips FROM counties ORDER BY idx").fetchall()
    idx = {f[0]: i for i, f in enumerate(counties)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    keys = [r[0] for r in con.execute("SELECT key FROM measures ORDER BY key").fetchall()]
    for k in keys:
        (out / f"m_{k}.json").write_text(jdump(export_measure(con, k, len(counties), idx)))
    print(f"wrote {len(keys)} measure files to {out}")


def check(a):
    site = Path(a.site)
    con = duckdb.connect(a.db, read_only=True)
    results = []

    def ok(name, cond, detail=""):
        results.append((bool(cond), name, detail))

    counties = con.execute("SELECT fips FROM counties ORDER BY idx").fetchall()
    N = len(counties)
    idx = {f[0]: i for i, f in enumerate(counties)}
    # 1. parity: rebuild every site measure file from the master and compare with the file the site actually serves
    bad = []
    for k in [r[0] for r in con.execute("SELECT key FROM measures ORDER BY key").fetchall()]:
        orig = json.loads((site / f"m_{k}.json").read_text())
        new = export_measure(con, k, N, idx)
        for part in sorted(set(orig) | set(new)):
            if orig.get(part) != new.get(part):
                bad.append(f"{k}.{part}")
    nfiles = len(list(site.glob("m_*.json")))
    ok("parity: master rebuilds every site m_*.json exactly", not bad and nfiles == con.execute("SELECT count(*) FROM measures").fetchone()[0],
       f"{nfiles} files; differences: {bad[:6]}")
    # 2. keys unique and values in range
    ok("cells unique on (measure, period, fips)", con.execute("SELECT count(*) FROM (SELECT 1 FROM cells GROUP BY measure, period, fips HAVING count(*) > 1)").fetchone()[0] == 0)
    ok("span_cells unique on (measure, span, fips)", con.execute("SELECT count(*) FROM (SELECT 1 FROM span_cells GROUP BY measure, span, fips HAVING count(*) > 1)").fetchone()[0] == 0)
    ok("observations unique", con.execute("SELECT count(*) FROM (SELECT 1 FROM observations GROUP BY source_id, bundle, cause_raw, period, fips, kind HAVING count(*) > 1)").fetchone()[0] == 0)
    ok("counts are -1 (hidden) or >= 0", con.execute("SELECT count(*) FROM cells WHERE count < -1").fetchone()[0] == 0)
    odd = con.execute("SELECT measure, period, fips, count FROM cells WHERE rate = -999 AND NOT (src = 'psx4' AND count = -1)").fetchall()
    ok("rates are >= 0, except -999 on CDC psx4 cells (CDC's own marker for no publishable rate)",
       con.execute("SELECT count(*) FROM cells WHERE rate < 0 AND (rate <> -999 OR src <> 'psx4')").fetchone()[0] == 0,
       f"{con.execute('SELECT count(*) FROM cells WHERE rate = -999').fetchone()[0]:,} cells carry -999; not on a hidden count: {odd}")
    ok("rate and count never both missing", con.execute("SELECT count(*) FROM cells WHERE count IS NULL AND count_text IS NULL AND rate IS NULL").fetchone()[0] == 0)
    ok("filled cells carry a state source and a 1-9 count", con.execute("SELECT count(*) FROM cells WHERE filled AND (fill_src IS NULL OR count NOT BETWEEN 1 AND 9)").fetchone()[0] == 0)
    ok("1-4 bands on the map sit on cells CDC hides, rest on a released band observation, and the count stays hidden",
       con.execute("""SELECT count(*) FROM band_cells b LEFT JOIN cells c ON c.measure = b.measure AND c.period = b.period AND c.fips = b.fips
                       WHERE c.count IS DISTINCT FROM -1 OR c.filled OR NOT EXISTS (SELECT 1 FROM observations o WHERE o.measure = b.measure AND o.period = b.period
                             AND o.fips = b.fips AND o.kind = 'band' AND o.released)""").fetchone()[0] == 0,
       f"{con.execute('SELECT count(*) FROM band_cells').fetchone()[0]:,} band cells")
    ok("every released 1-4 band that CDC hides is on the map (none dropped, none added)",
       con.execute("""SELECT (SELECT count(*) FROM (SELECT DISTINCT o.measure, o.period, o.fips FROM observations o JOIN cells c ON c.measure = o.measure AND c.period = o.period AND c.fips = o.fips
                                                      WHERE o.kind = 'band' AND o.released AND c.count = -1 AND NOT c.filled) x)
                           - (SELECT count(*) FROM band_cells)""").fetchone()[0] == 0,
       "released band observations on still-hidden cells equal band_cells")
    ok("every county code is known", con.execute("""SELECT (SELECT count(*) FROM cells WHERE fips NOT IN (SELECT fips FROM counties))
                                                    + (SELECT count(*) FROM span_cells WHERE fips NOT IN (SELECT fips FROM counties))
                                                    + (SELECT count(*) FROM observations WHERE fips NOT IN (SELECT fips FROM counties))""").fetchone()[0] == 0)
    ok("every src key is a known site source", con.execute("SELECT count(*) FROM period_src WHERE src IS NOT NULL AND src NOT IN (SELECT key FROM site_sources)").fetchone()[0] == 0)
    ok("exact observations have a non-negative value; bands have lo <= hi", con.execute(
        "SELECT count(*) FROM observations WHERE (kind='exact' AND (value IS NULL OR value < 0)) OR (kind='band' AND (lo IS NULL OR hi IS NULL OR lo > hi))").fetchone()[0] == 0)
    case = " ".join(f"WHEN '{fam}' THEN '{fips}'" for fips, fam in STATE_ABBR.items())
    ok("every staged observation sits in the state its publisher covers", con.execute(
        f"SELECT count(*) FROM observations o JOIN counties c ON c.fips = o.fips WHERE c.state_fips <> CASE o.family {case} END").fetchone()[0] == 0)
    # 3. ledger integrity
    L = con.execute("SELECT * FROM ledger").df()
    ok("ledger keys unique", not L.duplicated(["source_id", "bundle", "measure", "place"]).any())
    ok("ledger status / verdict / terms vocabularies", set(L.status) <= STATUSES and set(L.verdict) <= VERDICTS and set(L.terms_status) <= TERMS,
       f"{sorted(set(L.status) - STATUSES)} {sorted(set(L.verdict) - VERDICTS)} {sorted(set(L.terms_status) - TERMS)}")
    srcs = {r[0] for r in con.execute("SELECT id FROM sources").fetchall()}
    ok("every ledger row names a known source", set(L.source_id) <= srcs, str(sorted(set(L.source_id) - srcs)))
    ok("terms gate: nothing approved or released has unchecked terms", not ((L.status.isin(["approved", "released"])) & (L.terms_status == "unchecked")).any(),
       str(L[(L.status.isin(["approved", "released"])) & (L.terms_status == "unchecked")].source_id.unique().tolist()))
    obs_n = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    ok("ledger obs_n adds up to the observations table", int(L[L.bundle != "live"].obs_n.fillna(0).sum()) == obs_n, f"ledger {int(L[L.bundle != 'live'].obs_n.fillna(0).sum()):,} vs table {obs_n:,}")
    rel = con.execute("SELECT count(*) FROM observations WHERE released").fetchone()[0]
    rel_expected = con.execute("""SELECT count(*) FROM observations o JOIN ledger l ON l.source_id=o.source_id AND l.bundle=o.bundle AND l.measure=o.measure
                                   WHERE l.status IN ('approved','released') AND l.verdict='USE' AND NOT o.low_agreement_year""").fetchone()[0]
    ok("released flags match the ledger", rel == rel_expected, f"{rel:,} released observations")
    # 3b. the site data and the ledger agree: every state fill the build made rests on an approved or released ledger row
    meta = json.loads((site / "meta.json").read_text())
    unapproved = []
    for k, v in sorted((meta.get("stateFills") or {}).items()):
        if not (v.get("used") and v.get("filled")):
            continue
        head, cause = k.split(":")
        ab, _, bundle = head.partition("/")
        sid, bnd = (BUNDLE_SOURCE[bundle], bundle) if bundle else (LIVE_FILL_ABBR[ab], "live")
        row = L[(L.source_id == sid) & (L.bundle == bnd) & (L.measure == KEYMAP.get(cause, cause)) & (L.place == "residence")]
        if row.empty or row.iloc[0].status not in ("approved", "released"):
            unapproved.append(f"{k} ({'no row' if row.empty else row.iloc[0].status})")
    ok("every state fill in the site data rests on an approved or released ledger row", not unapproved, "; ".join(unapproved) or f"{sum(1 for v in (meta.get('stateFills') or {}).values() if v.get('used') and v.get('filled'))} fills checked")
    # 3c. the NCHS-file small counts: every fill the build made rests on an approved or released row, and the master holds the same number
    bad_n = []
    for k, v in sorted((meta.get("nberSmall") or {}).items()):
        if not (v.get("used") and v.get("filled")):
            continue
        cause, pl = k.split(":")
        row = L[(L.source_id == "nber_small") & (L.bundle == "nber_small") & (L.measure == KEYMAP.get(cause, cause)) & (L.place == NBER_PLACE[pl])]
        if row.empty or row.iloc[0].status not in ("approved", "released"):
            bad_n.append(f"{k} ({'no row' if row.empty else row.iloc[0].status})")
    n_rep = sum(int(v.get("filled") or 0) for v in (meta.get("nberSmall") or {}).values())
    n_db = con.execute("SELECT count(*) FROM cells WHERE fill_src = 'nber_small'").fetchone()[0]
    ok("every NCHS-file small count in the site data rests on an approved or released ledger row", not bad_n, "; ".join(bad_n) or f"{n_rep:,} cells reported")
    ok("NCHS-file small counts in the master equal the build's report", n_rep == n_db, f"report {n_rep:,} vs master {n_db:,}")
    # 4. every staged value is accounted for: bundle file totals vs rows loaded (+ matched names)
    log = {(s, i): (n, d) for s, i, n, d in con.execute("SELECT * FROM load_log").fetchall()}
    stray = []
    for (s, i), (n, d) in log.items():
        if s == "bundle" and d.startswith("unmatched names: "):
            stray += [f"{i}: {k}" for k in json.loads(d[len("unmatched names: "):]) if k.upper() != "UNKNOWN"]
    ok("every county name in every bundle matched a county (the unassigned-county rows of WISH and SCAN aside)", not stray, "; ".join(stray) or "only the unassigned-county rows (WISH UNKNOWN, SCAN Unknown) are left over")
    # 5. cross-check against the staging tools: fill_union.py is the original count of exact fills / bands
    if a.fill_union and Path(a.fill_union).exists():
        files = sorted(Path(a.staging).glob("*.json")) if a.staging else []
        try:
            res = subprocess.run([sys.executable, "-I", a.fill_union, "--site", str(site)] + [str(f) for f in files], capture_output=True, text=True, timeout=600)
            txt = res.stdout
            m_ex = re.search(r"unique exact fills.*?all\s+([\d,]+)", txt, re.S)
            m_bd = re.search(r"narrower band.*?all\s+([\d,]+)", txt, re.S)
            ref_ex = int(m_ex.group(1).replace(",", "")) if m_ex else None
            ref_bd = int(m_bd.group(1).replace(",", "")) if m_bd else None
            mine_ex = con.execute("""SELECT count(*) FROM (SELECT DISTINCT f.measure, f.period, f.fips FROM fill_candidates f JOIN ledger l
                                       ON l.source_id=f.source_id AND l.bundle=f.bundle AND l.measure=f.measure
                                      WHERE l.verdict='USE' AND f.period NOT LIKE '%-%')""").fetchone()[0]
            mine_bd = con.execute("""SELECT count(*) FROM (SELECT DISTINCT o.measure, o.period, o.fips FROM observations o JOIN cells c
                                        ON c.measure=o.measure AND c.period=o.period AND c.fips=o.fips JOIN ledger l
                                        ON l.source_id=o.source_id AND l.bundle=o.bundle AND l.measure=o.measure
                                      WHERE o.kind='band' AND c.count=-1 AND NOT o.low_agreement_year AND l.verdict='USE'
                                        AND NOT EXISTS (SELECT 1 FROM fill_candidates f JOIN ledger l2 ON l2.source_id=f.source_id AND l2.bundle=f.bundle AND l2.measure=f.measure
                                                         WHERE l2.verdict='USE' AND f.measure=o.measure AND f.period=o.period AND f.fips=o.fips))""").fetchone()[0]
            ok("exact fills match fill_union.py", ref_ex == mine_ex, f"fill_union {ref_ex:,} vs master {mine_ex:,}" if ref_ex else txt[-300:])
            ok("1-4 band cells match fill_union.py", ref_bd == mine_bd, f"fill_union {ref_bd:,} vs master {mine_bd:,}" if ref_bd else txt[-300:])
        except Exception as e:  # noqa: BLE001
            ok("fill_union cross-check ran", False, str(e))
    # 6. state totals: a second anchor besides CDC's county counts
    exp = con.execute("""SELECT count(*) FROM (SELECT 1 FROM observations WHERE period NOT LIKE '%-%' AND period <> 'TTM'
                          GROUP BY source_id, bundle, cause_raw, period, substr(fips, 1, 2))""").fetchone()[0]
    got = con.execute("SELECT count(*) FROM state_totals").fetchone()[0]
    ok("state-total comparison covers every staged cause and single year", exp == got and got > 0, f"{got:,} state-years")
    ok("state_totals unique on source, bundle, cause, year", con.execute(
        "SELECT count(*) FROM (SELECT 1 FROM state_totals GROUP BY source_id, bundle, cause_raw, period HAVING count(*) > 1)").fetchone()[0] == 0)
    off = con.execute("SELECT count(*) FROM state_totals WHERE flag = 'off'").fetchone()[0]
    ok("ledger state-total columns agree with the state_totals table", int(L.anchor_off_n.fillna(0).sum()) == off, f"{off:,} state-years flagged for review (warnings only)")
    # CDC's own cells only (filled cells are a state's number, not WONDER's); a fill that lifts the county sum above the state total is reported, not failed
    w_bad = con.execute("""SELECT count(*) FROM (SELECT c.period, substr(c.fips, 1, 2) AS st, sum(c.count) AS s FROM cells c
                             WHERE c.measure = 'all_deaths' AND c.count >= 0 AND c.src = 'wonder' AND NOT c.filled GROUP BY ALL) x
                           JOIN wonder_state_totals w ON w.measure = 'all_deaths' AND w.period = x.period AND w.state_fips = x.st
                          WHERE x.s > w.hi OR x.s < 0.95 * w.lo""").fetchone()[0]
    w_fill = con.execute("""SELECT count(*) FROM (SELECT c.period, substr(c.fips, 1, 2) AS st, sum(c.count) AS s FROM cells c
                             WHERE c.measure = 'all_deaths' AND c.count >= 0 AND c.src = 'wonder' GROUP BY ALL) x
                           JOIN wonder_state_totals w ON w.measure = 'all_deaths' AND w.period = x.period AND w.state_fips = x.st
                          WHERE x.s > w.hi""").fetchone()[0]
    w_all = con.execute("SELECT count(*) FROM wonder_state_totals").fetchone()[0]
    ok("WONDER state totals reproduce from the map's own county counts (all deaths, CDC cells only: county sum never above the state total, within 5% below)", w_bad == 0,
       f"{w_all:,} state-years loaded; outside the band: {w_bad}" + (f"; note: with state fills added, {w_fill} state-year(s) sum above WONDER's total" if w_fill else ""))
    # 7. the build's loader (pipeline/statefill.py) and this file describe the same staged bundles
    repo = site.absolute().parents[1]
    sf_path = repo / "pipeline" / "statefill.py"
    if sf_path.exists():
        import importlib.util
        sys.path.insert(0, str(sf_path.parent))
        try:
            spec = importlib.util.spec_from_file_location("statefill_for_check", sf_path)
            sf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sf)
            mine = [(tuple(files), sid, bundle) for files, sid, bundle in STAGED]
            theirs = [(tuple(files), sid, bundle) for files, sid, bundle, _st, _ab in sf.STAGED]
            states_ok = all(STATE_ABBR.get(st) == ab for _f, _s, _b, st, ab in sf.STAGED)
            ok("pipeline/statefill.py lists the same staged bundles, cause map and live sources as master.py",
               mine == theirs and states_ok and sf.MEASURE == KEYMAP and sf.LIVE_SOURCE == LIVE_FILL_ABBR,
               f"bundles equal: {mine == theirs}; states: {states_ok}; causes: {sf.MEASURE == KEYMAP}; live: {sf.LIVE_SOURCE == LIVE_FILL_ABBR}")
        except Exception as e:  # noqa: BLE001
            ok("pipeline/statefill.py could be compared with master.py", False, str(e))
        finally:
            sys.path.pop(0)
    # 8. the state-level historical mode: its ledger rows are exactly the series pipeline/hist_series.py defines, none of them rides on a county bundle,
    #    and every series the site data lists rests on an approved or released row
    hs_path = repo / "pipeline" / "hist_series.py"
    if hs_path.exists():
        HS = _hist_series()
        want = {(HS.SOURCES[s["source"]]["id"], HS.BUNDLE, s["key"], "state") for s in HS.SERIES}
        have = {(r.source_id, r.bundle, r.measure, r.place) for r in L.itertuples() if r.bundle == HS.BUNDLE}
        ok("historical state series: ledger rows equal the series defined in pipeline/hist_series.py", want == have,
           f"{len(have)} rows; missing {sorted(want - have)[:3]}; extra {sorted(have - want)[:3]}")
        county_bundles = {b for _f, _s, b in STAGED}
        ok("historical state series stay out of the county STAGED lists", HS.BUNDLE not in county_bundles)
        idx_p = site / "hist_state" / "index.json"
        if idx_p.exists():
            listed = [s["key"] for s in json.loads(idx_p.read_text()).get("series", [])]
            bad_h = []
            for k in listed:
                sid = HS.SOURCES[HS.SERIES_BY_KEY[k]["source"]]["id"]
                row = L[(L.source_id == sid) & (L.bundle == HS.BUNDLE) & (L.measure == k) & (L.place == "state")]
                if row.empty or row.iloc[0].status not in ("approved", "released"):
                    bad_h.append(f"{k} ({'no row' if row.empty else row.iloc[0].status})")
            ok("every series in site/data/hist_state rests on an approved or released ledger row", not bad_h, "; ".join(bad_h) or f"{len(listed)} series listed")
    bad = [r for r in results if not r[0]]
    for good, name, detail in results:
        print(("PASS  " if good else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    print(f"\n{len(results) - len(bad)} of {len(results)} checks passed")
    return 1 if bad else 0


def stats(a):
    con = duckdb.connect(a.db, read_only=True)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731
    print("file", Path(a.db).name, f"{Path(a.db).stat().st_size/1e6:.1f} MB")
    for k, v in q("SELECT key, value FROM meta"):
        print(f"  {k}: {v}")
    print("\nledger by status / verdict")
    for r in q("SELECT status, verdict, count(*) FROM ledger GROUP BY ALL ORDER BY 1, 2"):
        print("  ", *r)
    print("\nstaged exact fills by state family, counting each cell once (verdict USE, whatever the status)")
    for r in q("""SELECT f.family, count(*) FROM (SELECT DISTINCT f.family, f.measure, f.period, f.fips FROM fill_candidates f JOIN ledger l
                    ON l.source_id=f.source_id AND l.bundle=f.bundle AND l.measure=f.measure WHERE l.verdict='USE' AND f.period NOT LIKE '%-%') f GROUP BY 1 ORDER BY 1"""):
        print("  ", *r)
    print("\nevidence over every cell with at least one exact value (all sources, staged included)")
    for r in q("SELECT evidence, count(*) FROM cell_evidence_all GROUP BY 1 ORDER BY 2 DESC"):
        print("  ", *r)
    print("\nstate totals: bundle county sums against WONDER's state total and the state's own printed total (warnings only)")
    for r in q("SELECT flag, count(*) FROM state_totals GROUP BY 1 ORDER BY 2 DESC"):
        print("  ", *r)
    for r in q("""SELECT source_id || '/' || bundle, count(*) FILTER (WHERE flag = 'off'), count(*) FILTER (WHERE flag <> 'no_reference')
                    FROM state_totals GROUP BY 1 HAVING count(*) FILTER (WHERE flag = 'off') > 0 ORDER BY 2 DESC"""):
        print(f"   {r[0]}: {r[1]} of {r[2]} compared state-years flagged")
    print("\nconflicts: cells where two publisher families disagree beyond max(2, 10%)")
    for r in q("SELECT measure, count(*) FROM cell_evidence_all WHERE evidence='conflict' GROUP BY 1 ORDER BY 2 DESC LIMIT 12"):
        print("  ", *r)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--site", required=True)
    b.add_argument("--registry", required=True)
    b.add_argument("--proposed", default="")
    b.add_argument("--staging", required=True)
    b.add_argument("--db", default=str(HERE / "mortalgis_master.duckdb"))
    b.add_argument("--schema", default=str(HERE / "schema.sql"))
    b.add_argument("--ledger", default=str(HERE / "ledger.csv"))
    l = sub.add_parser("ledger")
    l.add_argument("--db", default=str(HERE / "mortalgis_master.duckdb"))
    l.add_argument("--ledger", default=str(HERE / "ledger.csv"))
    c = sub.add_parser("check")
    c.add_argument("--site", required=True)
    c.add_argument("--db", default=str(HERE / "mortalgis_master.duckdb"))
    c.add_argument("--staging", default="")
    c.add_argument("--fill-union", dest="fill_union", default="")
    e = sub.add_parser("export-json")
    e.add_argument("--db", default=str(HERE / "mortalgis_master.duckdb"))
    e.add_argument("--out", required=True)
    s = sub.add_parser("stats")
    s.add_argument("--db", default=str(HERE / "mortalgis_master.duckdb"))
    a = p.parse_args()
    if a.cmd == "build":
        build(a)
    elif a.cmd == "ledger":
        con = duckdb.connect(a.db)
        n = load_ledger(con, Path(a.ledger))
        con.execute("CHECKPOINT")
        print(f"reloaded {n} ledger rows; released observations: {con.execute('SELECT count(*) FROM observations WHERE released').fetchone()[0]:,}")
    elif a.cmd == "check":
        sys.exit(check(a))
    elif a.cmd == "export-json":
        export_json(a)
    elif a.cmd == "stats":
        stats(a)


if __name__ == "__main__":
    main()
