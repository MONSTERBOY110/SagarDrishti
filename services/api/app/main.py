"""SagarDrishti API (TRD M2).

Data plane only. This service never calls an LLM and never reaches the network;
the agent plane (services/agent) consumes these same public endpoints, which is
what keeps TRD's "kill the agent and every P0 still passes" property true.

Every response that carries numbers also carries `source_id` and `citation`,
because the agent is required to cite dataset + timestamp for anything it says
(CLAUDE.md) and it can only cite what the API gives it.
"""

from __future__ import annotations

import os

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from . import cf, ogc, plugins, store
from . import isosurface as isosurface_mod
from .config import get_settings
from .registry import load_registry

app = FastAPI(
    title="SagarDrishti API",
    description=(
        "Ocean model fields and in-situ profiles for the SagarDrishti 3D digital "
        "twin (SIH26067, MoES/INCOIS)."
    ),
    version="0.1.0",
)

# A hardcoded port is a deployment trap: it silently blocked the production
# build on :3001 while the dev server on :3000 worked, which reads as "no data"
# rather than as a CORS failure. Any loopback port is allowed by default, and a
# real deployment sets SAGAR_CORS_ORIGINS to its own exact origins.
_explicit = [o.strip() for o in os.environ.get("SAGAR_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit,
    allow_origin_regex=None if _explicit else r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# There was no compression at all against uvicorn, and the isosurface mesh is
# the first response big enough to care: about 8 KB of coordinates that gzip
# takes to roughly a third. Starlette ships this, so it is not a new
# dependency and the offline story is unchanged.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# OGC WMS 1.3.0 and WCS 1.0.0 (PS requirement F7, TRD M2). A router rather than
# two decorated functions because both endpoints parse their own query string:
# an OGC failure must return a ServiceExceptionReport, and a declared Query()
# would answer 422 JSON before the handler ever ran.
app.include_router(ogc.router)


def _nan_to_none(arr: np.ndarray) -> list:
    """NaN -> null in JSON.

    JSON has no NaN, and emitting a sentinel would let the client paint land as
    a temperature. null forces the renderer to leave the cell transparent.
    """
    flat = np.asarray(arr, dtype="float64").ravel()
    return [None if not np.isfinite(v) else round(float(v), 4) for v in flat]


def _profile_source(platform_id: str, recorded_source_id: str | None = None):
    """The registry source a profile row actually came from.

    Prefer the `source_id` the ingest RECORDED on the row. tools/preprocess.py
    writes it per row, so provenance is a fact carried with the measurement
    rather than a property inferred from how its platform id looks.

    The inference below remains as a fallback for a profiles table written
    before that column existed, and it is a genuine heuristic: app/text_profiles
    prefixes every text-ingested platform id (for example "CTD-BOB-07") so a
    cruise cast cannot be mistaken for a float. What it CANNOT distinguish is a
    BGC float from a core one, because both have a plain 7-digit WMO. Citing a
    BGC float's chlorophyll to the core daily files, which carry no chlorophyll
    at all, would be exactly the misattribution this function exists to
    prevent, which is why the recorded value wins.
    """
    reg = load_registry()
    if recorded_source_id and reg.has(str(recorded_source_id)):
        return reg.get(str(recorded_source_id))

    pid = str(platform_id)
    if not pid.isdigit():
        for spec in reg.sources:
            prefix = (spec.text or {}).get("platform_prefix")
            if prefix and pid.startswith(f"{prefix}-"):
                return spec
    return reg.get("argo_gdac_indian")


#: Depth and pressure are the level's coordinates, not measurements, so they
#: are never offered as a plottable variable.
_COORDINATE_COLUMNS = frozenset({"depth", "pres"})


def _measured_parameters(frame) -> list[str]:
    """Value columns in a profile frame, in the order the frame carries them.

    A column is a measurement if a `<name>_qc` column sits beside it. That is
    the same rule app/argo.py writes by, so the two cannot drift apart.
    """
    return [
        c for c in frame.columns
        if f"{c}_qc" in frame.columns and c not in _COORDINATE_COLUMNS
    ]


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "offline": s.offline,
        "cube_dir": str(s.cube_dir),
        "cube_present": s.cube_dir.exists(),
        "stores": sorted(store.discover_stores()),
        # An operator whose plugin did not appear checks here first: the usual
        # cause is discovery scanning a different directory than the one they
        # edited (docs/PLUGINS.md section 7).
        "plugins_dir": str(plugins.plugins_dir()),
        "plugins_loaded": [
            p["name"] for p in plugins.load_plugins().describe()["plugins"]
        ],
        "plugin_failures": len(plugins.load_plugins().failures),
    }


@app.get("/catalog", tags=["data"])
def catalog() -> dict:
    """Datasets that are both enabled AND materialized locally.

    A source registered but not downloaded (or lacking credentials) must not
    appear here -- a variable selector that offers something undrawable is
    worse than one that offers less.
    """
    datasets = store.catalog_entries()
    for entry in datasets:
        # A plugin-registered product is offered only where its inputs exist,
        # so this cannot add an undrawable variable to the selector (F6).
        entry["variables"].extend(plugins.derived_variables(entry["id"]))
    return {"datasets": datasets}


@app.get("/field/{source_id}/{var}", tags=["data"])
def field(
    source_id: str,
    var: str,
    bbox: str = Query(..., description="west,south,east,north in degrees"),
    time: str = Query(..., description="ISO-8601 timestamp; snapped to the nearest step"),
    depth: float | None = Query(None, description="metres, positive down"),
    all_depths: bool = Query(False, description="return the full water column in one call"),
) -> dict:
    """A horizontal slab, or the whole column when `all_depths` is set.

    The full-column form is the hot path for the volumetric renderer: one
    request per (variable, time) instead of one per depth level.
    """
    reg = load_registry()
    if not reg.has(source_id):
        raise HTTPException(404, f"unknown dataset {source_id!r}; see GET /catalog")
    spec = reg.get(source_id)
    if not spec.enabled:
        raise HTTPException(404, f"dataset {source_id!r} is disabled: {spec.disabled_reason}")

    try:
        ds, ref = store.open_cube(source_id)
    except KeyError:
        raise HTTPException(
            404,
            f"dataset {source_id!r} is registered but not materialized locally. "
            f"Run tools/fetch_sample.py and tools/preprocess.py.",
        ) from None

    derived_prov: dict | None = None
    stored = var in ds.data_vars
    if not stored and plugins.load_plugins().derived(var) is None:
        offered = sorted(ds.data_vars) + [
            p["name"] for p in plugins.derived_variables(source_id)
        ]
        raise HTTPException(
            404,
            f"unknown variable {var!r} in {source_id!r}; available: "
            f"{', '.join(offered)}",
        )

    try:
        box = store.parse_bbox(bbox)
        if stored:
            slab = store.select_field(
                ds, var, bbox=box, time=time, depth=depth, all_depths=all_depths
            )
        else:
            # A plugin-derived product (F6). It returns the same FieldSlab a
            # stored variable does, so the body built below and the renderer
            # need no special case at all.
            slab, derived_prov = plugins.compute_derived(
                source_id,
                var,
                ds,
                bbox=box,
                time=time,
                depth=depth,
                all_depths=all_depths,
            )
    except store.SubsetError as exc:
        raise HTTPException(400, str(exc)) from None
    except plugins.PluginError as exc:
        # 500 rather than 400: the request was well formed and the plugin is at
        # fault. The rule id is in the message (docs/PLUGINS.md).
        raise HTTPException(500, str(exc)) from None

    body = {
        "source_id": source_id,
        "variable": var,
        "units": slab.units,
        "citation": ref.provenance.get("citation") or spec.citation,
        "time": slab.time,
        "lats": slab.lats,
        "lons": slab.lons,
        "shape": list(slab.values.shape),
        "values": _nan_to_none(slab.values),
    }
    if slab.depths is not None:
        body["depths"] = slab.depths
    else:
        body["depth"] = slab.depth
    if derived_prov is not None:
        # Method, params, plugin and the valid-cell count. A computed number has
        # to carry how it was computed and how much of the box it covers, or it
        # is a number without provenance (CLAUDE.md).
        body.update(derived_prov)
    return body


@app.get("/plugins", tags=["ops"])
def plugin_report() -> dict:
    """What loaded, from which file, and what refused to load (F6).

    A plugin that fails silently on stage is worse than one that refuses, so
    the failure list is a first-class part of this response.
    """
    return plugins.load_plugins().describe()


@app.post("/plugins/reload", tags=["ops"])
def plugin_reload() -> dict:
    """Re-scan the plugin directory. This is the live move in PRD 11 step 6.

    It re-reads files already on this disk and never accepts uploaded code, but
    it is still mutating: gate it behind the operator network in an INCOIS
    deployment (docs/PLUGINS.md section 7).
    """
    return plugins.reload_plugins().describe()


@app.get("/profiles", tags=["data"])
def profiles(
    bbox: str | None = Query(None, description="west,south,east,north in degrees"),
    time: str | None = Query(None, description="ISO-8601 date; matches the whole day"),
) -> dict:
    """One entry per in-situ profile -- the clickable glyphs on the globe.

    Levels are deliberately NOT included: a day of Indian-Ocean Argo is tens of
    thousands of levels, and the client only needs them for the float actually
    clicked.
    """
    df = store.load_profiles()
    if df.empty:
        return {"profiles": [], "count": 0, "citation": ""}

    if bbox:
        try:
            w, s, e, n = store.parse_bbox(bbox)
        except store.SubsetError as exc:
            raise HTTPException(400, str(exc)) from None
        df = df[df["lon"].between(w, e) & df["lat"].between(s, n)]

    if time:
        try:
            import pandas as pd

            day = pd.Timestamp(time).normalize()
        except (ValueError, TypeError):
            raise HTTPException(400, f"time {time!r} is not a valid ISO-8601 timestamp") from None
        df = df[df["time"].dt.normalize() == day]

    from .argo import profile_summary

    summary = profile_summary(df)
    reg = load_registry()

    # Which parameters each profile actually SERVES, not which its source
    # declares. A BGC float that had every pH level rejected must not be
    # advertised as carrying pH, or the panel offers a variable that draws
    # nothing and reads as a broken chart.
    measured = _measured_parameters(df)
    served: dict[str, list[str]] = {}
    recorded: dict[str, str] = {}
    for profile_id, rows in df.groupby("profile_id", sort=False):
        served[profile_id] = [c for c in measured if bool(rows[c].notna().any())]
        if "source_id" in rows.columns:
            recorded[profile_id] = str(rows["source_id"].iloc[0])

    def source_of(row):
        return _profile_source(row.wmo, recorded.get(row.profile_id))

    present = sorted({source_of(r).id for r in summary.itertuples()})
    # One response can span several sources, so cite each one present rather
    # than asserting a single provenance for all.
    citation = "; ".join(reg.get(s).citation for s in present)
    return {
        "count": int(len(summary)),
        "citation": citation,
        "source_ids": present,
        "profiles": [
            {
                "profile_id": r.profile_id,
                "wmo": r.wmo,
                "time": r.time.isoformat() + "Z",
                "lat": round(float(r.lat), 5),
                "lon": round(float(r.lon), 5),
                "n_levels": int(r.n_levels),
                "max_depth": round(float(r.max_depth), 1),
                "source_id": source_of(r).id,
                # The instrument class, so the globe can draw a BGC float, a
                # core float and a ship cast as different marks instead of
                # 22 identical squares.
                "platform_kind": source_of(r).kind,
                "parameters": served.get(r.profile_id, []),
            }
            for r in summary.itertuples()
        ],
    }


@app.get("/profiles/{profile_id}", tags=["data"])
def profile_detail(profile_id: str) -> dict:
    """Every accepted level of one profile -- the ECharts depth-vs-variable plot.

    The WMO id and the profile timestamp are returned alongside the values so
    the chart can print its own citation, which is where the agent's citation
    discipline starts.
    """
    df = store.load_profiles()
    sub = df[df["profile_id"] == profile_id]
    if sub.empty:
        # Allow lookup by bare WMO id too: judges will click a float, but the
        # agent will more naturally say "float 2902746".
        sub = df[df["wmo"] == profile_id]
    if sub.empty:
        raise HTTPException(404, f"no profile {profile_id!r}; see GET /profiles")

    sub = sub.sort_values("depth")
    first = sub.iloc[0]
    # The recorded source wins over inference: see _profile_source.
    recorded = str(first["source_id"]) if "source_id" in sub.columns else None
    spec = _profile_source(str(first["wmo"]), recorded)

    # Serve every parameter this profile actually measured, and nothing else.
    # Which columns exist depends on the instrument class: a core float has
    # temperature and salinity, a BGC float adds oxygen, chlorophyll, nitrate
    # and pH. Enumerating them rather than naming two keeps a new parameter a
    # `sources.yaml` change, which is the F3 claim applied to this endpoint.
    declared = {v.name.lower(): v for v in spec.variables}
    parameters = []
    levels: dict[str, list] = {
        "depth": [round(float(v), 2) for v in sub["depth"]],
        "pres": [round(float(v), 2) for v in sub["pres"]],
    }
    for column in _measured_parameters(sub):
        values = sub[column].to_numpy()
        if not bool(sub[column].notna().any()):
            # Measured by this instrument class in general, but every level of
            # THIS profile was rejected or absent. Omitted rather than served
            # as a column of nulls.
            continue
        spec_var = declared.get(column)
        levels[column] = _nan_to_none(values)
        parameters.append({
            "name": column,
            "label": spec_var.label if spec_var and spec_var.label else column.upper(),
            # Verified against the source file at parse time by
            # app/argo.py:check_units, so labelling an axis from it cannot
            # disagree with the numbers on it.
            "units": (spec_var.units if spec_var else None) or "",
            "canonical": (spec_var.canonical if spec_var else None) or "",
            "n_values": int(sub[column].notna().sum()),
        })

    return {
        "profile_id": str(first["profile_id"]),
        "wmo": str(first["wmo"]),
        "time": first["time"].isoformat() + "Z",
        "lat": round(float(first["lat"]), 5),
        "lon": round(float(first["lon"]), 5),
        "source_id": spec.id,
        "platform_kind": spec.kind,
        "citation": spec.citation,
        "qc_policy": (
            f"QC flags {spec.qc.accept_flags} only (Wong et al. 2020)"
            if spec.kind in ("gdac_geo", "gdac_bgc")
            else f"QC flags {spec.qc.accept_flags} only"
        ),
        # Stated because it changes which numbers appear. On these BGC floats
        # the raw chlorophyll and oxygen flags are 3 on every level and only
        # the adjusted product reaches an accepted flag, so without this the
        # profile would carry no chlorophyll at all.
        "adjusted_preferred": bool(spec.qc.prefer_adjusted),
        "n_levels": int(len(sub)),
        "parameters": parameters,
        "levels": levels,
    }


@app.get("/isosurface/{source_id}/{var}", tags=["data"])
def isosurface(
    source_id: str,
    var: str,
    value: float = Query(..., description="the isovalue, in the variable's own units"),
    value_units: str = Query(
        ...,
        description=(
            "units of `value`, checked against the served variable. Required, "
            "not defaulted: 26 degC and 26 K are different surfaces"
        ),
    ),
    bbox: str = Query(..., description="west,south,east,north in degrees"),
    time: str = Query(..., description="ISO-8601 timestamp; snapped to the nearest step"),
) -> dict:
    """The surface where a field takes a given value, as a triangle mesh (F1).

    The PS names isosurface extraction alongside depth slices and time-step
    animation as the three required 3D techniques. Depth slices and animation
    are served by `/field`; this is the third.

    Computed per request rather than precomputed. Extraction is a few
    milliseconds on the demo cube, so there is no cache to go stale and a judge
    can type an arbitrary value and watch the surface move.

    THE MESH IS A PICTURE OF A LEVEL SET, NOT A DIFFERENTIABLE OBJECT. Slope,
    curvature, heat content, volume and any other quantity that would be
    computed FROM the geometry must be answered from the field instead. The
    vertices are a rendering of where the field crosses a value; treating them
    as the field itself is how a plausible number with no measurement behind it
    gets spoken, which CLAUDE.md forbids outright.
    """
    reg = load_registry()
    if not reg.has(source_id):
        raise HTTPException(404, f"unknown dataset {source_id!r}; see GET /catalog")
    spec = reg.get(source_id)
    if not spec.enabled:
        raise HTTPException(404, f"dataset {source_id!r} is disabled: {spec.disabled_reason}")

    try:
        ds, ref = store.open_cube(source_id)
    except KeyError:
        raise HTTPException(
            404,
            f"dataset {source_id!r} is registered but not materialized locally. "
            f"Run tools/fetch_sample.py and tools/preprocess.py.",
        ) from None

    if var not in ds.data_vars:
        # Deliberately NOT falling back to a derived product. A plugin's
        # surface product is already a surface; asking for the isosurface of a
        # depth field is a different question that nothing here answers.
        raise HTTPException(
            404,
            f"unknown variable {var!r} in {source_id!r}; available: "
            f"{', '.join(sorted(ds.data_vars))}. A plugin-derived product cannot "
            "be used here: this route meshes a volumetric field, and a derived "
            "surface product has no volume to mesh.",
        )

    try:
        box = store.parse_bbox(bbox)
        slab = store.select_field(ds, var, bbox=box, time=time, all_depths=True)
    except store.SubsetError as exc:
        raise HTTPException(400, str(exc)) from None

    # The isovalue must be in the same units as the field, and this is checked
    # rather than assumed. 26 degC and 26 K are different surfaces and both
    # numbers look equally reasonable in a URL.
    served_units = cf.canonical_unit(slab.units) or slab.units or ""
    wanted_units = cf.canonical_unit(value_units) or value_units
    if served_units and wanted_units and served_units != wanted_units:
        raise HTTPException(
            400,
            f"value_units {value_units!r} does not match {var!r}, which is served "
            f"in {slab.units!r}. Convert the value first: relabelling a number "
            "whose units were not converted is how a wrong surface gets drawn "
            "with a confident label.",
        )

    depths = np.asarray(slab.depths if slab.depths is not None else [], dtype="float64")
    try:
        mesh = isosurface_mod.extract(
            slab.values,
            depths=depths,
            lats=np.asarray(slab.lats, dtype="float64"),
            lons=np.asarray(slab.lons, dtype="float64"),
            isovalue=float(value),
        )
    except isosurface_mod.ExtractorError as exc:
        # The request was well formed and the DATA violates a contract the
        # extractor depends on, so this is ours, not the caller's.
        raise HTTPException(500, str(exc)) from None

    citation = ref.provenance.get("citation") or spec.citation
    return {
        "source_id": source_id,
        "variable": var,
        "units": slab.units,
        "value": float(value),
        "value_units": slab.units,
        # The SNAPPED time, not what was asked for. A mesh labelled with the
        # request rather than the step it came from is a number without
        # provenance.
        "time": slab.time,
        "citation": citation,
        "retrieved_at": ref.provenance.get("retrieved_at"),
        "extractor": isosurface_mod.EXTRACTOR,
        "extractor_version": isosurface_mod.EXTRACTOR_VERSION,
        "method": isosurface_mod.METHOD,
        # The grid the mesh was extracted on, so a vertex can be traced back to
        # cube cells rather than floating free.
        "bbox": [box[0], box[1], box[2], box[3]],
        "lats": [round(float(v), 6) for v in slab.lats],
        "lons": [round(float(v), 6) for v in slab.lons],
        "depths": [round(float(v), 4) for v in depths],
        # Geometry. Flat triples, because a nested list costs about 30 per cent
        # more bytes for the same numbers.
        "positions": [round(float(v), 5) for v in mesh.positions.reshape(-1)],
        "indices": [int(v) for v in mesh.triangles.reshape(-1)],
        "dz_bracket": [round(float(v), 4) for v in mesh.dz_bracket],
        "on_edge": [bool(v) for v in mesh.on_edge],
        **mesh.counts,
    }
