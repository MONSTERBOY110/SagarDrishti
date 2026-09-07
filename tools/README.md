# tools/

| Script | Status | What it does |
|---|---|---|
| `fetch_sample.py` | Phase 1 | **The only network code in the repo.** Pulls one INCOIS griddap NetCDF subset + N daily Argo profile files into `data/raw/`. Run once; everything downstream reads local files. |
| `preprocess.py` | Phase 1 | `data/raw/` -> CF-normalized, unit-harmonized, rechunked `data/cube/*.zarr` + `profiles.parquet` + `provenance.json`. `--fixtures` builds a tiny synthetic cube for CI (no network). |
| `build_offline_cube.py` | Phase 4 | The full 2-4 GB demo cube (BoB + Arabian Sea, one month around a cyclone) per TRD §3. Wraps `preprocess.py` over a longer time range. |
| `validate_rmse.py` | Phase 4 | Reproduces a published GLORYS-vs-Argo comparison number within tolerance (TRD M5) so the scorecard's methodology is evidenced, not asserted. |
