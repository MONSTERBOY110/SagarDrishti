# Plugin interface (PS requirement F6, "Extensible Design")

The PS asks for "a documented plugin interface for future sensors (moorings,
HF-radar, ADCP) and ML-derived products". This is that interface.

Implementation: `services/api/app/plugins.py`. Plugin directory:
`services/api/plugins/`. Tests: `services/api/tests/test_plugins.py`. A worked
example that runs against the real cube: `services/api/plugins/d26_isotherm.py`.

---

## 1. What this is, and what it is not

There are exactly two extension points.

| Extension point | Registered by | Makes possible |
|---|---|---|
| **Source reader** | `registry.register_source_reader(kind=..., open=...)` | A new `kind:` in `data/sources.yaml`. `mooring`, `hf_radar`, `adcp`, `mqtt`, a lab CSV, a THREDDS mirror. |
| **Derived product** | `registry.register_derived_product(name=..., compute=...)` | A new selectable variable computed from fields already in the cube. A diagnostic (D26, mixed-layer depth) or an ML-derived product (a trained eddy or bloom index). |

What it is not:

- **Not networked.** A plugin runs inside `services/api`, which never imports a
  network client (`tests/test_offline.py` enforces this statically for `app/`,
  `tests/test_plugins.py` for `plugins/`). Fetching lives in
  `tools/fetch_sample.py` alone. A reader plugin reads a local file or a local
  broker, and nothing else.
- **Not an install step.** Discovery is a directory scan. Copy a `.py` file in,
  reload, done. No `pip install`, no restart, no editing this repo's core.
- **Not magic.** Nothing is picked up by decorator, subclass or naming
  convention. A plugin exposes `register(registry)` and *calls* a registration
  method. Registration is explicit so it is inspectable, and inspectable so
  "did my plugin load?" is one HTTP GET rather than a log hunt.
- **Not silent.** Every rule below has an id that appears in the error message.
  A plugin that fails quietly on stage is worse than one that refuses to load.

---

## 2. The two protocols

From `app/plugins.py`, exported for authors:

```python
class DerivedCompute(Protocol):
    def __call__(self, ds: xr.Dataset) -> xr.DataArray | np.ndarray: ...

class SourceOpen(Protocol):
    def __call__(self, spec: SourceSpec) -> xr.Dataset: ...
```

### DerivedCompute

`ds` is handed to you already subset and already validated:

- dims `(depth, lat, lon)`, in that order, for one timestep
- every variable named in your `requires`, under its own name
- a `depth` coordinate in metres, positive down, strictly increasing
- `NaN` for every missing value. Land, fill values and QC-rejected levels are
  already absent, and they must stay absent in your output
- `ds[var].attrs["units"]` set, and already checked against your declared units

Return an array of your declared output shape: `(lat, lon)` for
`output="surface"`, `(depth, lat, lon)` for `output="column"`. Use `NaN`
wherever the answer does not exist. Do not extrapolate.

### SourceOpen

`spec` is the validated `SourceSpec` for one entry in `data/sources.yaml`, so
`spec.url`, `spec.path_template`, `spec.dataset_id`, `spec.variables`,
`spec.dims`, `spec.qc` and `spec.cf_overrides` are all available to you.

Return an `xarray.Dataset` on the `app/cf.py` output contract (canonical dim
names, depth positive down and increasing, floating dtype, non-empty units).
If your source is raw, call `app.cf.normalize_dataset(ds, spec)` and let the
existing normalizer do it from the spec's own `dims:` and `cf_overrides:`
blocks. `open_source()` validates the result either way and refuses what does
not conform (rules D1-D5).

---

## 3. The config surface

| Surface | Where | Purpose |
|---|---|---|
| Plugin directory | `services/api/plugins/*.py` | Drop-in. Sorted load order. `__init__.py` skipped. A **leading underscore disables a file** (`_wip_adcp.py` does not load). |
| `SAGAR_PLUGINS` | environment variable | Points discovery at another directory. Read on every call, so a test or an operator can redirect it without a restart. |
| `sagardrishti.plugins` | Python entry-point group | Second channel, for a plugin shipped as an installed wheel. The target may be a module exposing `register`, or the `register` function itself. With nothing installed the lookup is empty and free, which is why it can sit in the default offline path. |
| `kind:` | `data/sources.yaml` | Selects the source reader for that entry. |

### DerivedProduct fields

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | URL path segment and selector key. `^[A-Za-z][A-Za-z0-9_]{0,31}$`. |
| `label` | yes | What a forecaster reads in the variable selector. |
| `units` | yes | The units of **your output**, not of the input. D26 is in `m`. Use `1` for a dimensionless index. |
| `requires` | yes | `{variable: expected_units}`. `None` as the units skips the check. Used for three things: gating the catalog listing, subsetting the inputs, and refusing to compute from the wrong unit. |
| `compute` | yes | A `DerivedCompute`. Exactly one positional argument. |
| `method` | yes | One sentence on how the number is produced. Echoed as provenance on every response, hence mandatory. |
| `output` | no (`"surface"`) | `"surface"` returns `(lat, lon)`, `"column"` returns `(depth, lat, lon)`. Declared, not inferred, so the framework can validate the shape it gets. |
| `params` | no (`{}`) | Thresholds and coefficients. Echoed as provenance. |
| `canonical` | no (`None`) | CF standard name, if one exists. |
| `applies_to` | no (`()`) | Restrict to named `source_id`s. Empty means "any dataset carrying the required variables", which is why D26 starts working on GLORYS12 the day those credentials land. |

---

## 4. Validation rules

### Registration (R1-R9), raised as `PluginError` at load time

| Rule | Refuses |
|---|---|
| R1 | A `name` that is not URL-safe. `product name 'D 26 !' is not usable. A name becomes a URL path segment, so it must match ^[A-Za-z][A-Za-z0-9_]{0,31}$` |
| R2 | An empty `label`. `The label is what a forecaster reads in the variable selector.` |
| R3 | Empty `units`. `A number without a unit is not shippable -- use '1' for a dimensionless index.` |
| R4 | An empty or non-mapping `requires`, or a non-string unit inside it. |
| R5 | A `compute` that is not callable, or does not take exactly one positional argument. `Bind extra arguments with functools.partial and register the partial.` |
| R6 | An `output` other than `surface` or `column`. |
| R7 | An empty `method`. `It is echoed as provenance on every response, so it cannot be optional.` |
| R8 | A duplicate product `name`. The message names **both** plugins: `product name 'D26' is already registered by plugin 'd26_isotherm'; plugin 'mine' tried to register it again.` |
| R9 | A reader `kind` that is not config-safe (`^[a-z][a-z0-9_]{0,31}$`), an `open` with the wrong arity, or a second reader for a kind that already has one. |

A file with no `register(registry)` hook is refused by name before any rule
runs. A plugin that raises at import (or inside `register`) is recorded as a
`PluginFailure` and **the other plugins in the directory still load**. Pass
`strict=True` (the CI and test posture) to raise instead.

### Compute output (C1-C5), raised when the product is drawn

| Rule | Refuses |
|---|---|
| C1 | A return value that is not a numpy array or an `xarray.DataArray`. |
| C2 | A non-floating dtype. `NaN is how absent data is expressed, and an integer array cannot hold it.` |
| C3 | A shape that does not match the declared `output`. |
| C4 | `+/-inf`. `Use NaN for a value that does not exist; infinity survives JSON encoding as a number and would be drawn as one.` |
| C5 | A finite value in a cell where **every level of every required input is missing**, i.e. land or below the seabed. This is the machine-checkable form of the project's missing-data rule: `Land, fill values and QC-rejected levels must stay absent -- return NaN there rather than a default.` |

### Reader output (D1-D5), raised when the source is opened

| Rule | Refuses |
|---|---|
| D1 | A return value that is not an `xarray.Dataset`. |
| D2 | No data variables, or a non-canonical dimension name. `the renderer must never guess which axis is depth` |
| D3 | A depth axis that is not strictly increasing, or that is negative. `That is a height axis; negate it and set positive='down'` |
| D4 | A non-floating data variable. |
| D5 | A data variable with no `units` attribute. |

Every one of these fails *silently* if unchecked, which is why they are checked
rather than trusted: a flipped depth axis puts the thermocline at the seabed
and still renders, a `-9999` fill value renders as a temperature.

---

## 5. Worked example: a derived product

Copy this file into `services/api/plugins/d20_isotherm.py` and it works. It is
the 20 degC isotherm, the conventional proxy for the top of the thermocline,
and it is verified against the real cube: basin median 122.0 m,
123.99 m at 12.5 N 86.5 E on 2026-07-30.

It repeats the small interpolation routine rather than importing it from
`d26_isotherm.py`, because plugins are loaded by path and are not importable
from each other. A plugin is a self-contained file on purpose.

```python
# plugin-example: d20_isotherm.py
"""D20: depth of the 20 degC isotherm, the conventional thermocline proxy."""

from __future__ import annotations

import numpy as np

THRESHOLD_DEGC = 20.0


def compute(ds):
    temp = np.asarray(ds["TEMP"].values, dtype="float64")
    depth = np.asarray(ds["depth"].values, dtype="float64")

    finite = np.isfinite(temp)
    upper, lower = temp[:-1], temp[1:]
    # Both levels must carry a measurement: a missing level between a warm and
    # a cold one straddles the threshold but never brackets it. NaN fails the
    # comparisons on its own; the finite test also excludes an infinity, which
    # would otherwise be accepted as a bracket.
    crossing = finite[:-1] & finite[1:] & (upper >= THRESHOLD_DEGC) & (lower < THRESHOLD_DEGC)

    out = np.full(temp.shape[1:], np.nan, dtype="float64")
    flat_out = out.reshape(-1)
    if crossing.any():
        flat_cross = crossing.reshape(crossing.shape[0], -1)
        flat_temp = temp.reshape(temp.shape[0], -1)
        cols = np.flatnonzero(flat_cross.any(axis=0))
        # argmax on booleans gives the first True: the shallowest crossing,
        # which is the one that matters when the column has an inversion.
        k = np.argmax(flat_cross, axis=0)[cols]
        t_up, t_lo = flat_temp[k, cols], flat_temp[k + 1, cols]
        z_up, z_lo = depth[k], depth[k + 1]
        frac = (t_up - THRESHOLD_DEGC) / (t_up - t_lo)
        flat_out[cols] = z_up + frac * (z_lo - z_up)
    return flat_out.reshape(temp.shape[1:])


def register(registry):
    registry.register_derived_product(
        name="D20",
        label="Depth of the 20 degC isotherm",
        units="m",
        requires={"TEMP": "degC"},
        compute=compute,
        output="surface",
        canonical="depth_of_isosurface_of_sea_water_potential_temperature",
        method=(
            "shallowest crossing of 20 degC, linear interpolation in depth "
            "between the two bracketing finite levels; no extrapolation, no "
            "interpolation across a missing level"
        ),
        params={"threshold": 20.0, "threshold_units": "degC"},
    )
```

### What the client then receives

`GET /field/incois_vam_argo/D20?bbox=80.5,5.5,95.5,25.5&time=2026-07-30&all_depths=true`

```json
{
  "source_id": "incois_vam_argo",
  "variable": "D20",
  "units": "m",
  "citation": "INCOIS Argo 10-day gridded analysis ...",
  "time": "2026-07-30T00:00:00Z",
  "depths": [0.0],
  "shape": [1, 21, 16],
  "derived": true,
  "derived_from": ["TEMP"],
  "method": "shallowest crossing of 20 degC ...",
  "params": {"threshold": 20.0, "threshold_units": "degC"},
  "plugin": "d20_isotherm",
  "output": "surface",
  "n_cells": 336,
  "n_valid": 204
}
```

Two things to be plain about:

- **A surface diagnostic is drawn at the surface.** It has no depth axis, so
  when the volumetric client asks for the whole column it gets one level at
  depth `0.0`. The existing renderer needs no change, and the result is a
  single sheet rather than a coloured column. The values themselves are depths
  in metres, which is what `units` says.
- **`n_valid` / `n_cells` is the honesty counter.** 204 of 336 columns have a
  20 degC crossing; the rest are land or have no crossing in the water. A
  reviewer sees the coverage instead of a picture that implies the whole box
  was computed.

---

## 6. Worked example: a source reader

The PS names moorings first. This reads a local mooring CSV as a new `kind`.
Copy it into `services/api/plugins/mooring_csv.py`.

```python
# plugin-example: mooring_csv.py
"""A source reader for kind `mooring`: a local time/depth/temperature CSV.

The shape the PS's "future sensors" all share is a single station with a time
axis and a depth axis, which is what RAMA/OMNI moorings, an ADCP bin set and an
HF-radar radial file all reduce to. Reading a CSV keeps the example honest:
there is no network client anywhere in services/api, so a reader's job is to
get local bytes into an xarray.Dataset on the cf.py contract.

Expected file, named by the source's `path_template`:

    time,depth,temp
    2026-07-30T00:00:00Z,5,29.31
    2026-07-30T00:00:00Z,20,28.98
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import xarray as xr

MISSING = {"", "nan", "NaN", "-9999", "-9999.0"}


def open_mooring(spec):
    path = Path(spec.path_template or "")
    if not path.is_file():
        # Refuse by name. A reader that returns an empty Dataset here would
        # show a judge an empty globe with no explanation.
        raise FileNotFoundError(
            f"source {spec.id!r} (kind {spec.kind!r}) expects a CSV at "
            f"path_template={spec.path_template!r}, which does not exist"
        )

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path.name} has a header but no rows")

    times = sorted({r["time"] for r in rows})
    depths = sorted({float(r["depth"]) for r in rows})
    grid = np.full((len(times), len(depths)), np.nan, dtype="float64")
    t_at = {t: i for i, t in enumerate(times)}
    z_at = {z: i for i, z in enumerate(depths)}
    for r in rows:
        raw = (r.get("temp") or "").strip()
        # A sentinel left as a number would be drawn as a temperature.
        if raw in MISSING:
            continue
        grid[t_at[r["time"]], z_at[float(r["depth"])]] = float(raw)

    ds = xr.Dataset(
        {"TEMP": (("time", "depth"), grid)},
        coords={
            "time": ("time", np.array(times, dtype="datetime64[ns]")),
            "depth": ("depth", np.array(depths, dtype="float64")),
        },
    )
    ds["TEMP"].attrs.update(units="degC", long_name="Sea water temperature")
    ds["depth"].attrs.update(units="m", positive="down", standard_name="depth")
    ds.attrs.update(source_id=spec.id, citation=spec.citation)
    return ds


def register(registry):
    registry.register_source_reader(
        kind="mooring",
        open=open_mooring,
        doc="Local mooring CSV with time, depth and temp columns",
    )
```

Then in `data/sources.yaml`:

```yaml
  - id: rama_bob_15n90e
    title: RAMA mooring 15N 90E (local export)
    kind: mooring
    url: file://data/raw/rama_15n90e.csv
    path_template: data/raw/rama_15n90e.csv
    citation: "RAMA/OMNI mooring, NOAA PMEL and NIOT/INCOIS"
    variables:
      - name: TEMP
        canonical: sea_water_temperature
        label: Temperature
```

**Known limitation, stated rather than implied.** The reader point is
registered, validated and tested at the `app/plugins.py` level, but it is not
yet reachable over HTTP: `/catalog` and `/field` read materialized zarr stores
through `app/store.py`, and `SourceKind` in `app/registry.py` is a closed
`Literal` that does not yet include `mooring`, `hf_radar` or `adcp`. Two small
changes land those (widen the `Literal`; have `store.discover_stores` consult
`plugins.open_source` for a kind with no zarr store). Until then, `kind:
mooring` in `sources.yaml` is refused by the registry validator, and the
reader is exercised by `open_source()` and its tests. The derived-product point
**is** wired end to end.

---

## 7. Failure triage

`GET /plugins` returns exactly `PluginRegistry.describe()`:

```json
{
  "plugins": [
    {"name": "d26_isotherm",
     "origin": "directory:D:\\Projects\\SagarDrishti\\services\\api\\plugins\\d26_isotherm.py",
     "derived_products": ["D26"], "source_readers": []}
  ],
  "derived_products": [{"name": "D26", "units": "m", "plugin": "d26_isotherm", "...": "..."}],
  "source_readers": [],
  "failures": []
}
```

| Symptom | Look at |
|---|---|
| The product is not in the selector | `GET /plugins` -> `failures`. Each entry carries `origin` (the exact file), `error` (the exception text) and `hint`. |
| `failures` is empty and the product is still missing | The file name starts with `_`, or the directory being scanned is not the one you edited. `GET /healthz` reports the resolved plugins directory. |
| Loaded, but absent from `/catalog` for one dataset | Its `requires` names a variable that cube does not carry, or `applies_to` excludes it. Both are deliberate: a selector must not offer an undrawable variable. |
| Loaded and listed, but `/field` returns 500 | A C-rule. The body names it. C5 is the common one: the compute filled land with a default. |
| The product name is also a real variable | `failures` reports `shadows a variable in dataset ...` and the product is not offered. Rename it. |

`POST /plugins/reload` re-scans the directory and returns the fresh
`describe()`. It never accepts uploaded code: it only re-reads files already on
that disk. It is still a mutating endpoint, so **gate it behind the operator
network in an INCOIS deployment**; it exists for the stage move below and for
development.

---

## 8. The 60-second live registration (PRD section 11 step 6)

The demo script promises a judge that a new product is registered live. This is
the exact sequence. It is covered by
`test_reload_picks_up_a_file_dropped_after_the_first_load` and
`test_the_worked_examples_in_docs_plugins_md_actually_run`, so the file in
section 5 cannot rot without the suite failing.

Before going on stage: have a second terminal open in the repo root, and
`docs/PLUGINS.md` section 5 already copied to
`storyboards/live/d20_isotherm.py`.

| t | Say | Do |
|---|---|---|
| 0:00 | "You asked for extensibility. Name a threshold." | Judge says 20 degC (or 28, or 24). |
| 0:05 | "Twenty. Here is the plugin: forty lines, one `register` call, no imports from our core." | Show `storyboards/live/d20_isotherm.py` on screen. Point at `register_derived_product`. |
| 0:20 | "It goes in the plugin directory." | `cp storyboards/live/d20_isotherm.py services/api/plugins/` |
| 0:25 | "No install, no restart. One reload." | `curl -X POST http://localhost:8000/plugins/reload` |
| 0:30 | "The API now says it loaded, and from which file." | The response names `D20` under `derived_products` and `d20_isotherm` under `plugins`, with the file path. |
| 0:40 | "Refresh the browser." | Reload the tab. **"Depth of the 20 degC isotherm"** is in the variable selector. |
| 0:50 | "Click it." | The D20 field draws over the Bay of Bengal. Median around 122 m. |
| 0:55 | "And it is cited, and it admits what it does not know." | Point at the panel: `method`, `params`, `plugin`, and `204 of 336 columns`. The 132 blank cells are land or have no 20 degC crossing. |

If the threshold the judge names is one you have not pre-copied, change the two
`THRESHOLD_DEGC` lines and the `name`/`label` in the editor before the `cp`.
That is a ten-second edit; budget for it rather than promising any threshold.

**The failure move.** If the reload reports a failure, read the `error` line
aloud. That is the demonstration too: the plugin refused to load and said which
file and why, instead of drawing a wrong ocean. Then fix and reload.
