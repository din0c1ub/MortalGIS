# Transcribing VSUS 1937 and 1938, Table 19 (run by hand, once)

These scripts turned the CDC/NCHS scans of *Vital Statistics of the United States 1937* and *1938*, Part I, into
`data_manual/hist_state/hist_vsus_1937_1938_state.json`. The weekly build does not run them.

1. `extract_t19.py <pdf> <page> <dir>`: renders a page at 300 dpi, levels it if it was scanned at an angle, finds the column rules and reads each column strip with tesseract (digits only).
2. `assemble_t19.py <dir> <out>`: pairs the left and right pages and cuts them into state blocks of 24 rows (White, Other, by sex, by population group). Rows lost at a page break are left empty, not shifted. `us_block_t19.py` adds the United States block.
3. `reocr2_t19.py` reads single cells again (tags `b` and `c`) for the cells that do not settle. `carry_reads.py` keeps those readings when a page is re-assembled.
4. `resolve3_t19.py` settles a state total when two of its four derivations agree: the printed total, male + female, the three population groups, and the groups by sex. `resolve4_t19.py` also uses the row sum (total deaths = the sum of the 37 cause columns), plus any values read by eye.
5. `grid_t19.py`, `colsheet_t19.py` and `zoom_t19.py` make contact sheets of the printed cells with the current value under each one. They were checked by eye. `add_manual.py` records what was read into `t19_<year>_manual.json`. Both files are kept here.
6. `final_t19.py` takes the final values and checks every column against the printed United States line. White and Other were checked separately, for each of the 26 columns used, in both years.
7. `build_vsus3738.py` maps the Table 19 columns to Miller's causes and adds the Table 18 lines. It refuses to write if any column fails the national check.

`grid_extra.py` has the scratch folder of the 2026-10-15 session written into it. Change the path before running it again.
