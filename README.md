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

**Docs, in reading order:** [`docs/HANDOFF.md`](docs/HANDOFF.md) →
[`docs/PRD.md`](docs/PRD.md) → [`docs/TRD.md`](docs/TRD.md) →
[`docs/PRIOR-ART.md`](docs/PRIOR-ART.md) → [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
[`docs/TEAM-ROLES.md`](docs/TEAM-ROLES.md) ·
[`docs/SAGARNODE-BOM.md`](docs/SAGARNODE-BOM.md) ·
[decisions](docs/adr/)

## Repo layout (TRD §8)

```
apps/web/            Next.js 15 + Cesium 1.145 + deck.gl 9 client
services/api/        FastAPI data plane: REST + (Phase 4) OGC WMS/WCS + WebSocket
services/agent/      Samudra Sahayak agent plane (Phase 2) - detachable by design
packages/scene/      SceneState schema shared by UI, deep links and the agent
data/sources.yaml    dataset registry - THE extensibility surface (PS F3/F6)
firmware/sagarnode/  ESP32 live-sensor station (Phase 2; parts list in docs/)
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

Windows shortcut: `./tasks.ps1 <setup|fetch|api|web|test>`.

## Tests

```bash
cd services/api && ../../.venv/Scripts/python.exe -m pytest -q
```

The data plane is developed test-first (CLAUDE.md). The suite pins the CF
edge cases that real government NetCDF actually exhibits - two different
`_FillValue` conventions, `scale_factor`/`add_offset`, a vertical coordinate
with no `positive` attribute, non-CF unit strings - plus Argo QC-flag filtering
(flags 1 and 2 only, per Wong et al. 2020) and colorbar mapping.

## Data sources

Registered in [`data/sources.yaml`](data/sources.yaml). Phase 1 primary is
INCOIS's own open ERDDAP griddap analysis (`incois_argo_10d_VAM`) plus Argo GDAC
profiles; Copernicus GLORYS12 is registered but disabled pending credentials.
See [ADR-0003](docs/adr/0003-incois-vam-primary-field.md).

## Licence & attribution

Built entirely on open-source components (₹0 licence cost). Data remains the
property of its providers and every derived product carries a `provenance.json`;
the agent cites dataset, timestamp and float WMO id for every number it speaks.
