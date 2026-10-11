-- MortalGIS master file: DuckDB schema.
-- One file holds (1) what the map shows today, (2) every value each source reported, kept as granular as the publisher gives it,
-- and (3) the ledger that decides which sources are allowed onto the map. The map's JSON files are derived from this file.
-- Nothing here is edited by hand except ledger.csv and sources_terms.csv (both live next to this file and are reloaded by master.py).

-- ------------------------------------------------------------------ build info
CREATE TABLE meta (key VARCHAR, value VARCHAR);

-- ------------------------------------------------------------------ reference
-- idx = the county's position in the site's arrays (m_*.json), kept so the export is byte-for-byte comparable.
CREATE TABLE counties (fips VARCHAR, name VARCHAR, state_name VARCHAR, state_fips VARCHAR, idx INTEGER);

-- One row per map measure (47 in the site today). meta_json is the site's own measure entry, kept whole.
CREATE TABLE measures (key VARCHAR, label VARCHAR, grp VARCHAR, place VARCHAR, unit VARCHAR, rate_type VARCHAR,
                       has_counts BOOLEAN, pair_key VARCHAR, default_period VARCHAR, filled_by VARCHAR, meta_json VARCHAR);

-- The source keys the map's own files use in `src` (nber, wonder, psx4 ...) and which publisher family they belong to.
CREATE TABLE site_sources (key VARCHAR, label VARCHAR, url VARCHAR, partial BOOLEAN, family VARCHAR);

-- ------------------------------------------------------------------ sources and terms
-- Registry (pipeline/sources.yml + staging/sources_proposed.yml) joined with sources_terms.csv.
--   family           publisher family. Two sources from the same family are one voice, not two (MI DHHS live + MI DHHS fatal injuries;
--                    CDC WONDER + CDC VSRR). Used to count how many publishers report a cell.
--   terms_status     stated | none_stated | restricted | unchecked.  none_stated = looked, nothing there.  unchecked = not looked yet.
--   terms_checked_on date a person or Claude read the terms_url; empty when taken from the registry without re-reading.
CREATE TABLE sources (id VARCHAR, name VARCHAR, publisher VARCHAR, family VARCHAR, url VARCHAR, license_text VARCHAR,
                      access VARCHAR, kind VARCHAR, geography VARCHAR, place VARCHAR, grain VARCHAR, years VARCHAR, cadence VARCHAR,
                      stated_suppression VARCHAR, registry_status VARCHAR, site_keys VARCHAR, notes VARCHAR,
                      terms_status VARCHAR, terms_url VARCHAR, terms_checked_on DATE, terms_note VARCHAR);

-- ------------------------------------------------------------------ ledger (loaded from ledger.csv)
-- One row per source x bundle x measure x place. status is the human decision; verdict is the automatic agreement gate.
-- A staged value reaches the map only when status is approved/released AND verdict = USE.
--   status   staged | approved | released | held | rejected | candidate | blocked
--   verdict  USE | SKIP | NO_CDC_MEASURE | n/a      (USE: >= 50 CDC-published county-years checked and >= 90% agree within max(2, 10%))
--   warnings semicolon-separated codes, never blocking: wonder_9_or_fewer, rate_under_20, terms_none_stated, low_agreement_years,
--            gate_sample_small, overlaps_other_bundle, review_before_use, x_cells_not_narrowable, band_only_1_4, state_total_off, spans_not_in_map,
--            exact_match_under_80, band_years_unreliable, terms_stated_review
--   anchor_n / anchor_off_n / anchor_off_years  the state-total check (table state_totals): years compared, years flagged, and the flagged years
CREATE TABLE ledger (source_id VARCHAR, bundle VARCHAR, measure VARCHAR, place VARCHAR, period_from VARCHAR, period_to VARCHAR,
                     status VARCHAR, verdict VARCHAR, checked_n INTEGER, agree_n INTEGER, agree_pct DOUBLE, exact_pct DOUBLE, low_years VARCHAR,
                     exact_fills INTEGER, band_cells INTEGER, discordant_n INTEGER, obs_n INTEGER,
                     anchor_n INTEGER, anchor_off_n INTEGER, anchor_off_years VARCHAR,
                     terms_status VARCHAR, warnings VARCHAR, approved_by VARCHAR, approved_on VARCHAR, note VARCHAR);

-- ------------------------------------------------------------------ what the map shows
-- count: -1 = hidden by CDC (1-9 deaths), NULL = no value. rate: -999 = CDC's own marker for no publishable rate (psx4 hidden cells); treat as NULL in analysis. src = site key for that measure-period (period_src).
-- filled = a state health department's exact count shown in place of CDC's hidden cell; fill_src = the source that filled it.
--   The site file only flags a filled cell, so fill_src comes from the build's report (meta.stateFills, per state and measure); when two sources of
--   one state fill the same measure the first one is named. A filled cell shows its count only: build_data.py leaves the rate empty (under 20 deaths).
-- period_src records which arrays the site file carries for each measure-period, so the export can rebuild the file exactly.
CREATE TABLE period_src (measure VARCHAR, period VARCHAR, src VARCHAR, has_count BOOLEAN, has_rate BOOLEAN, has_filled BOOLEAN, has_modeled BOOLEAN);
-- 1-4 bands the map shows in a tooltip (site file key `band`): a cell CDC hides (cells.count = -1) where a state's approved source says 1-4.
-- The count stays hidden and no rate is shown; the band is never added into any total.
CREATE TABLE band_cells (measure VARCHAR, period VARCHAR, fips VARCHAR, lo INTEGER, hi INTEGER, fill_src VARCHAR);
-- count_text: CDC's own complementary-suppression range, e.g. '10-50' (psx4, 2022 on). count is NULL for those cells.
-- count is DOUBLE because NOAA storm deaths are shared fractionally across counties (0.5, 0.2 ...); every other count is a whole number.
CREATE TABLE cells (measure VARCHAR, period VARCHAR, fips VARCHAR, count DOUBLE, count_text VARCHAR, rate DOUBLE, src VARCHAR,
                    filled BOOLEAN, modeled BOOLEAN, fill_src VARCHAR);
CREATE TABLE span_cells (measure VARCHAR, span VARCHAR, fips VARCHAR, count DOUBLE, rate DOUBLE);

-- ------------------------------------------------------------------ every value a staged source reported
--   kind    exact   the publisher's own count (0 included)
--           band    the publisher hides the cell but says how small: lo..hi (WISH 'X' = 1-4, MICA narrowed 'x' = 1-4)
--           masked  the publisher hides the cell and does not say why or how small (MICA 'x' that may be a complementary row)
--   measure the site measure the cause maps to (NULL when the map has no matching measure; cause_raw keeps the publisher's label)
--   released  eligible for the map: ledger status approved/released, verdict USE, and not a low-agreement year
CREATE TABLE observations (source_id VARCHAR, bundle VARCHAR, family VARCHAR, measure VARCHAR, cause_raw VARCHAR, period VARCHAR,
                           fips VARCHAR, kind VARCHAR, value INTEGER, lo INTEGER, hi INTEGER, low_agreement_year BOOLEAN, released BOOLEAN);

CREATE TABLE load_log (step VARCHAR, item VARCHAR, n INTEGER, detail VARCHAR);

-- ------------------------------------------------------------------ state totals: a second anchor besides CDC's county counts
-- The county-level gate asks "do this state's county counts match CDC's county counts where CDC publishes them (10+)?". It is blind to the
-- small counties it exists to fill. This asks a different question at the state level: do a bundle's county counts add up to the state total?
-- wonder_state_totals  CDC WONDER state x year totals, summed from the map's state_month files for years with all 12 months.
--                      lo..hi because WONDER hides months of 1-9 (lo counts them 0, hi counts them 9).
-- bundle_own_totals    the state total a bundle prints itself (IL state row, MO / WI / NC state totals); not every source prints one.
CREATE TABLE wonder_state_totals (measure VARCHAR, period VARCHAR, state_fips VARCHAR, lo INTEGER, hi INTEGER);
CREATE TABLE bundle_own_totals (source_id VARCHAR, bundle VARCHAR, cause_raw VARCHAR, period VARCHAR, own_total INTEGER);
-- state_totals: one row per source x bundle x cause x single year.
--   bundle_lo / bundle_hi  county sum: exact counts, plus 1..4 per band cell (WISH X, narrowed MICA x) and 1..9 per masked cell
--   n_absent               counties of the state the bundle says nothing about (not published, not even as hidden)
--   flag                   ok | off | no_reference.  Over: the county sum is above the reference (a definition wider than CDC's, or a parse error).
--                          Short: below the reference by more than 2%, judged only when n_absent <= 0, because missing counties explain a shortfall.
--                          Tolerance is max(2, 2%) against WONDER and max(2, 0.1%) above the bundle's own total. Warnings only; nothing is blocked.
CREATE TABLE state_totals (source_id VARCHAR, bundle VARCHAR, cause_raw VARCHAR, measure VARCHAR, period VARCHAR, state_fips VARCHAR,
                           n_state_counties INTEGER, n_exact INTEGER, n_band INTEGER, n_masked INTEGER, n_absent INTEGER,
                           bundle_lo INTEGER, bundle_hi INTEGER, wonder_lo INTEGER, wonder_hi INTEGER, own_total INTEGER,
                           vs_wonder_pct DOUBLE, vs_own_pct DOUBLE, wonder_flag VARCHAR, own_flag VARCHAR, flag VARCHAR, detail VARCHAR);

-- ------------------------------------------------------------------ evidence: how many publishers report each cell, and do they agree
-- all_obs puts the map's own values (CDC side, live state fills) next to the staged observations.
CREATE VIEW all_obs AS
    SELECT family, source_id, bundle, measure, period, fips, kind, value, lo, hi, released, FALSE AS from_site
      FROM observations
    UNION ALL
    SELECT s.family, 'site:' || c.src, 'site', c.measure, c.period, c.fips, 'exact', c.count, c.count, c.count, TRUE, TRUE
      FROM cells c JOIN site_sources s ON s.key = c.src
     WHERE c.count >= 0 AND NOT c.filled
    UNION ALL
    SELECT f.family, c.fill_src, 'live', c.measure, c.period, c.fips, 'exact', c.count, c.count, c.count, TRUE, TRUE
      FROM cells c JOIN sources f ON f.id = c.fill_src
     WHERE c.filled
    UNION ALL
    SELECT s.family, 'site:' || c.src, 'site', c.measure, c.period, c.fips, 'band', NULL, 1, 9, TRUE, TRUE
      FROM cells c JOIN site_sources s ON s.key = c.src
     WHERE c.count = -1 OR c.filled
    UNION ALL
    SELECT s.family, 'site:' || c.src, 'site', c.measure, c.period, c.fips, 'band', NULL,
           try_cast(split_part(c.count_text, '-', 1) AS INTEGER), try_cast(split_part(c.count_text, '-', 2) AS INTEGER), TRUE, TRUE
      FROM cells c JOIN site_sources s ON s.key = c.src
     WHERE c.count_text IS NOT NULL;

-- evidence: single = one publisher family, agree = 2+ families within max(2, 10% of the larger), conflict = 2+ families that do not.
-- band_lo/band_hi = the narrowest band any publisher states for a cell nobody reports exactly.
CREATE VIEW cell_evidence_all AS
    SELECT measure, period, fips,
           count(DISTINCT family) FILTER (WHERE kind = 'exact') AS n_publishers,
           min(value) FILTER (WHERE kind = 'exact') AS v_min,
           max(value) FILTER (WHERE kind = 'exact') AS v_max,
           max(lo) FILTER (WHERE kind = 'band') AS band_lo,
           min(hi) FILTER (WHERE kind = 'band') AS band_hi,
           CASE WHEN count(DISTINCT family) FILTER (WHERE kind = 'exact') = 0 THEN 'none'
                WHEN count(DISTINCT family) FILTER (WHERE kind = 'exact') = 1 THEN 'single'
                WHEN max(value) FILTER (WHERE kind = 'exact') - min(value) FILTER (WHERE kind = 'exact')
                     <= greatest(2, 0.1 * max(value) FILTER (WHERE kind = 'exact')) THEN 'agree'
                ELSE 'conflict' END AS evidence
      FROM all_obs GROUP BY measure, period, fips;

-- Same, counting only what is eligible for the map (the release view).
CREATE VIEW cell_evidence_released AS
    SELECT measure, period, fips,
           count(DISTINCT family) FILTER (WHERE kind = 'exact') AS n_publishers,
           min(value) FILTER (WHERE kind = 'exact') AS v_min,
           max(value) FILTER (WHERE kind = 'exact') AS v_max,
           max(lo) FILTER (WHERE kind = 'band') AS band_lo,
           min(hi) FILTER (WHERE kind = 'band') AS band_hi,
           CASE WHEN count(DISTINCT family) FILTER (WHERE kind = 'exact') = 0 THEN 'none'
                WHEN count(DISTINCT family) FILTER (WHERE kind = 'exact') = 1 THEN 'single'
                WHEN max(value) FILTER (WHERE kind = 'exact') - min(value) FILTER (WHERE kind = 'exact')
                     <= greatest(2, 0.1 * max(value) FILTER (WHERE kind = 'exact')) THEN 'agree'
                ELSE 'conflict' END AS evidence
      FROM all_obs WHERE released GROUP BY measure, period, fips;

-- Staged exact counts that would un-hide a cell CDC suppresses (count = -1, value 1-9) in a year that passed the gate.
-- Year periods join `cells`; 5-year spans join `span_cells`.
CREATE VIEW fill_candidates AS
    SELECT o.source_id, o.bundle, o.family, o.measure, o.period, o.fips, o.value, o.released
      FROM observations o JOIN cells c ON c.measure = o.measure AND c.period = o.period AND c.fips = o.fips
     WHERE o.kind = 'exact' AND c.count = -1 AND o.value BETWEEN 1 AND 9 AND NOT o.low_agreement_year
    UNION ALL
    SELECT o.source_id, o.bundle, o.family, o.measure, o.period, o.fips, o.value, o.released
      FROM observations o JOIN span_cells s ON s.measure = o.measure AND s.span = o.period AND s.fips = o.fips
     WHERE o.kind = 'exact' AND s.count = -1 AND o.value BETWEEN 1 AND 9 AND NOT o.low_agreement_year;
