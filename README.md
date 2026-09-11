# SagarDrishti (सागर दृष्टि) - Digital Twin of the Indian Ocean

Browser-native 3D visualization of INCOIS ocean model fields fused with live
in-situ observations, built for **Smart India Hackathon 2026, PS SIH26067**
(Ministry of Earth Sciences / INCOIS · theme: Disaster Management).

> INCOIS generates 3D ocean model output and in-situ observations daily, but
> forecasters must "toggle between disparate software packages" to see them
> together - which "impedes timely hazard assessment, search-and-rescue support,
> fishery advisories, climate monitoring." SagarDrishti puts model fields and
> instrument profiles in one interactive 3D scene, in a browser, with no client
> install.

**New to this repository? Read [`docs/START-HERE.md`](docs/START-HERE.md)** for a
plain-English account of what the tool is, how to run it, and what is still
outstanding.

**Where the P0 requirements stand, with today's measurements:**
[`docs/P0-STATUS.md`](docs/P0-STATUS.md).

**Docs, in reading order:** [`docs/HANDOFF.md`](docs/HANDOFF.md) →
[`docs/PRD.md`](docs/PRD.md) → [`docs/TRD.md`](docs/TRD.md) →
[`docs/PRIOR-ART.md`](docs/PRIOR-ART.md) → [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
[`docs/TEAM-ROLES.md`](docs/TEAM-ROLES.md) ·
[`docs/SAGARNODE-BOM.md`](docs/SAGARNODE-BOM.md) ·
[decisions](docs/adr/)

**Presenting it:** [`docs/MENTOR-BRIEF-14-SEP.md`](docs/MENTOR-BRIEF-14-SEP.md)
is the full current-state briefing: every parameter, every dataset with its
size, the research paper behind each method, and the numbers to quote with the
caveat that must follow each.
[`docs/PITCH-INTERNAL.md`](docs/PITCH-INTERNAL.md) is the three-minute
internal-round script, timed.
[`docs/IDEA-PDF-DRAFT.md`](docs/IDEA-PDF-DRAFT.md) is the six-slide idea
submission, written out, every claim marked built or planned.

## Repo layout (TRD §8)

```
apps/web/            Next.js 15 + Cesium 1.145 client (deck.gl installed, unused)
services/api/        FastAPI data plane: REST + OGC WMS/WCS + plugin registry
services/agent/      Samudra Sahayak agent plane (Phase 2) - detachable by design
packages/scene/      SceneState schema shared by UI, deep links and the agent
data/sources.yaml    dataset registry - THE extensibility surface (PS F3/F6)
firmware/sagarnode/  ESP32 live-sensor station - sketch written, never flashed
tools/               fetch_sample · preprocess · build_offline_cube · validate_rmse
storyboards/         JSON guided tours (Phase 4)
```

## Two planes

The **data plane** (NetCDF/ASCII → xarray → chunked zarr → FastAPI → WebGL) is
deterministic and satisfies every P0 requirement on its own. The **agent plane**
calls the same public API the browser calls and can only mutate the scene
through a validated `SceneState` patch. Kill the agent and the product still
stands - that isolation is deliberate pivot insurance (TRD §6.5).

## Offline-first is the default, not a mode

`OFFLINE` defaults to `1`. The API reads only from the local zarr/parquet cube,
Cesium's assets are vendored into `apps/web/public/cesium` (no ion token, no
network), and the entire demo runs with WiFi off. Network access exists in
exactly one file: `tools/fetch_sample.py`.

## Getting started

Prerequisites: Python 3.11 (see [ADR-0002](docs/adr/0002-python-311.md)),
Node 22+, pnpm 10.

```bash
# Python data plane
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r services/api/requirements-dev.txt

# Web client (postinstall vendors Cesium's assets into public/cesium)
pnpm install

# One-time: pull real sample data (the only network step)
./.venv/Scripts/python.exe tools/fetch_sample.py
./.venv/Scripts/python.exe tools/preprocess.py

# Run (two terminals)
cd services/api && ../../.venv/Scripts/python.exe -m uvicorn app.main:app --reload
pnpm web:dev
```

Windows shortcut: `./tasks.ps1 <setup|fetch|api|web|test|offline|build|serve|demo|e2e>`.
Use `demo` rather than `build` then `serve` by hand: `next start` reads the
build manifest once at boot, so a server left running across a rebuild serves
stale HTML that 400s on its own assets and looks exactly like a data outage.
The `api` and `offline` tasks free port 8000 first for the same reason: a
uvicorn started without `--reload` imports the app once, so a new route added
while it runs answers 404 until it is restarted.

## API surface

All thirteen routes are served by `services/api`, and OpenAPI is at `/docs`.

| Route | What it is for |
|---|---|
| `GET /healthz` | Liveness, offline flag, which stores and plugins loaded |
| `GET /catalog` | Datasets actually materialized locally, with their variables, depths, times and citation |
| `GET /field/{source}/{var}` | One slab: `bbox`, `time`, `depth` or `all_depths`. Serves plugin-derived products too |
| `GET /profiles` | Station glyphs for the globe: position, time, instrument class, parameters served |
| `GET /profiles/{id}` | Every accepted level of one profile, with its QC policy and citation |
| `GET /isosurface/{source}/{var}` | **Isosurface extraction (F1).** The surface where a field takes a given value, as a triangle mesh with its extraction method and refusal counts. Marching cubes on the native grid, no resampling |
| `GET /scorecard/{source}/{var}` | **Class-4-style verification (F9).** Per-depth-bin bias and RMSE of the model against the in-situ profiles, interpolated to each cast's own position and depth, with every unpaired level counted and the reason it was refused. Carries the caveat that the analysis assimilates these same profiles, so this is analysis fit and not forecast skill |
| `GET /warnings` | **HazardWatch (F13).** Active CAP v1.2 warnings at an instant, as polygons and circles, from India's national CAP backbone (NDMA SACHET) plus ocean-hazard rehearsal bulletins. Refuses to serve a cancelled, superseded, expired or not-yet-effective alert, and refuses a drill unless asked; every refusal is counted |
| `GET /currents/{source}` | **Current vectors at depth (F1).** A block-averaged, drawable velocity field: 43,621 native cells become a few hundred arrows. Says the stride it used, the cells behind each arrow, the depth it actually served, and the coastal blocks it refused for being more land than water |
| `GET /storyboards` | **Guided tours (F12).** JSON-scripted tours: a scene patch, a line of narration and the evidence it rests on, per step. Every numeral in a narration line must be backed by the patch or the evidence, and the loader refuses a tour where it is not |
| `GET /wms` | **OGC WMS 1.3.0.** GetCapabilities and GetMap, for stored variables AND plugin-derived products. `CRS:84` and `EPSG:4326`, time and elevation dimensions, six palettes, TRANSPARENT and BGCOLOR per spec |
| `GET /wcs` | **OGC WCS 1.0.0.** GetCapabilities, DescribeCoverage and GetCoverage, serving CF-1.8 NetCDF. Refuses to resample rather than inventing cells |
| `GET /plugins` | The registered plugins, their derived products and any load failures |
| `POST /plugins/reload` | Re-scan the plugin directory without a restart |

### The agent plane, on :8010

Samudra Sahayak is a **separate service** (`services/agent`, `./tasks.ps1
agent`), and that is the architecture rather than a packaging choice: TRD
section 6.5 states the property as "kill the agent and every P0 still passes".
Stop that process and the globe, the scorecard, HazardWatch and the tours carry
on; the web client probes the port and omits the ask box entirely.

| Route | What it is for |
|---|---|
| `GET /healthz` | Liveness, whether the data plane under it is reachable, and **whether a language model is loaded** (none is; see below) |
| `GET /tools` | The tool schemas, in the shape a model would be handed, plus the no-fabrication rule |
| `POST /ask` | A question, answered from tool results only, with the full tool trace and citations |

Two properties are enforced mechanically rather than promised:

- **Numbers enter answers only through tools.** `app/guard.py` checks every
  numeral in a finished answer against the tool results behind it and
  **withholds** an answer that fails, rather than correcting it silently. It is
  written and tested now, while the planner is deterministic, precisely so that
  the day a model is plugged in behind the same interface the guard has already
  been the last step for weeks.
- **The agent cannot draw.** Its only channel to the view is a validated scene
  patch, applied through the same store a person's clicks go through, checked
  against the same key list the guided tours use.

**There is no language model in the loop, and every response says so.** The
planner is a deterministic router over the tools; `planner: "rules"` is in each
answer and printed in the UI. PRD section 10 already answers a judge on this
("offline mode uses a local model or disables narration gracefully"), and an
audience that assumed otherwise would have been misled.

Open our own WMS layer in QGIS:

```
http://127.0.0.1:8000/wms?service=WMS&version=1.3.0&request=GetCapabilities
```

The plugin interface is documented in [`docs/PLUGINS.md`](docs/PLUGINS.md).

## Tests

```bash
./tasks.ps1 test     # 414 data-plane tests
./tasks.ps1 agent    # then: python -m pytest services/agent/tests  (68 tests)
./tasks.ps1 e2e      # 9 browser tests against a production build
```

Both run with no network. `data/raw/` and `data/cube/` are gitignored, so CI
builds its cube from **`data/sample/`**, 614 KB of real INCOIS field and Argo
profiles committed for that purpose (`python tools/preprocess.py --fixtures`).
The browser suite asserts claims about the real Bay of Bengal, so testing it
against an invented field would assert nothing; the reasoning and the
attribution are in `data/sample/README.md`.

The data plane is developed test-first (CLAUDE.md). The suite pins the CF
edge cases that real government NetCDF actually exhibits: three different
`_FillValue` conventions (-9999.0, -1.0E34 and 99999.0, all observed in live
files), `scale_factor`/`add_offset` applied exactly once, a vertical coordinate
with no `positive` attribute, non-CF unit strings, and a declared unit that
disagrees with the file it describes. Plus Argo QC-flag filtering per parameter
(flags 1 and 2 only, per Wong et al. 2020), the adjusted-product preference
that is the only reason BGC chlorophyll exists at all, and colorbar mapping.

The browser tests run against a **production build** because a bundler failure
that only appears in production once left the globe as an empty black frame
while every panel worked. They also fail on any off-origin request, which is
how the air-gapped promise (PRD F11) is enforced mechanically, and on any em or
en dash reaching the screen.

`python tools/check_dashes.py` enforces the typography rule across every
tracked file; CI runs it as its own job.

## Data sources

Registered in [`data/sources.yaml`](data/sources.yaml), which is the
extensibility surface PS requirements F3 and F6 are graded on: seven sources
across six kinds, and adding a delimited-text layout or a BGC parameter is a
config entry rather than a code change.

| Source | Kind | State |
|---|---|---|
| `incois_vam_argo` | erddap_griddap | live, the primary field ([ADR-0003](docs/adr/0003-incois-vam-primary-field.md)) |
| `argo_gdac_indian` | gdac_geo | live, 13 core floats in the demo box |
| `argo_bgc_indian` | gdac_bgc | live, 3 BGC floats: oxygen, chlorophyll, nitrate, pH |
| `rama_mooring_bob` | mooring | live, read by a PLUGIN source reader. RAMA moored buoy 15n90e (WMO 23009) |
| `incois_oceansat2_chl` | erddap_griddap | registered and disabled: the series ends 2020, so it cannot share a 2026 scrubber |
| `ctd_text_ascii` | file | reader live and tested; awaiting a real cast file |
| `odv_spreadsheet` | file | reader live and tested; awaiting a real export |
| `local_cube` | zarr | the `OFFLINE=1` target |
| `glorys12` | copernicus | disabled pending credentials (the only depth-resolved currents) |

## Licence & attribution

Built entirely on open-source components (₹0 licence cost). Data remains the
property of its providers and every derived product carries a `provenance.json`;
the agent cites dataset, timestamp and float WMO id for every number it speaks.


