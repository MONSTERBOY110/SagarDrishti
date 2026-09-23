# tools/

| Script | Status | What it does |
|---|---|---|
| `fetch_sample.py` | Phase 1 | **The only network code in the repo.** Pulls one INCOIS griddap NetCDF subset + N daily Argo profile files into `data/raw/`. Run once; everything downstream reads local files. |
| `preprocess.py` | Phase 1 | `data/raw/` -> CF-normalized, unit-harmonized, rechunked `data/cube/*.zarr` + `profiles.parquet` + `provenance.json`. `--fixtures` builds a tiny synthetic cube for CI (no network). |
| `build_offline_cube.py` | Phase 4 | The full 2-4 GB demo cube (BoB + Arabian Sea, one month around a cyclone) per TRD §3. Wraps `preprocess.py` over a longer time range. |
| `validate_rmse.py` | Phase 4 | Reproduces a published GLORYS-vs-Argo comparison number within tolerance (TRD M5) so the scorecard's methodology is evidenced, not asserted. |
| `check_dashes.py` | house style | The lead's rule is zero em and en dashes. Reads the tracked file list from git, so it covers the docs and the deck sources too. A CI job. |
| `check_contrast.py` | house style | Every colour token in `globals.css` states a measured contrast ratio in its own comment; this re-measures each one against the ground it is actually used on and fails on a stated figure that is no longer true, or on one under its floor. Written after a palette inversion left the caveat ink at 1.4:1 in a draft. A CI job. |
| `make_plate_tile.py` | house style | Generates the station sheet's form stock as a seamless raster whose mean RGB **is** `--plate`. The tile is opaque, so it silently overrides the token: the script reads `--plate` out of `globals.css` and refuses to run if the two disagree, and CI re-runs it and fails on any diff. |
| `capture_deck_assets.mjs` | evidence | The four screenshots the idea deck uses, taken from the running build at 3x and clipped to what each slot shows. Checked in for the same reason as the one below: the deck claims its pictures are of the real system, and for one day they were of a build that had been replaced. Feeds `.ppt-build/refresh_23sep.py`. |
| `capture_evidence.mjs` | evidence | Drives the running build through the same controls a judge would click and writes a dated screenshot set under `docs/evidence/`, with a README it fills in from the numbers it read off the page. Node, not Python: it needs Playwright. |
