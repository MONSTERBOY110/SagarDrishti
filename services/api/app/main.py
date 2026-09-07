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

from . import store
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


def _nan_to_none(arr: np.ndarray) -> list:
    """NaN -> null in JSON.

    JSON has no NaN, and emitting a sentinel would let the client paint land as
    a temperature. null forces the renderer to leave the cell transparent.
    """
    flat = np.asarray(arr, dtype="float64").ravel()
    return [None if not np.isfinite(v) else round(float(v), 4) for v in flat]


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "offline": s.offline,
        "cube_dir": str(s.cube_dir),
        "cube_present": s.cube_dir.exists(),
        "stores": sorted(store.discover_stores()),
    }


@app.get("/catalog", tags=["data"])
def catalog() -> dict:
    """Datasets that are both enabled AND materialized locally.

    A source registered but not downloaded (or lacking credentials) must not
    appear here -- a variable selector that offers something undrawable is
    worse than one that offers less.
    """
    return {"datasets": store.catalog_entries()}


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

    if var not in ds.data_vars:
        raise HTTPException(
            404,
            f"unknown variable {var!r} in {source_id!r}; available: "
            f"{', '.join(sorted(ds.data_vars))}",
        )

    try:
        box = store.parse_bbox(bbox)
        slab = store.select_field(
            ds, var, bbox=box, time=time, depth=depth, all_depths=all_depths
        )
    except store.SubsetError as exc:
        raise HTTPException(400, str(exc)) from None

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
    return body


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
    spec = load_registry().get("argo_gdac_indian")
    return {
        "count": int(len(summary)),
        "citation": spec.citation,
        "profiles": [
            {
                "profile_id": r.profile_id,
                "wmo": r.wmo,
                "time": r.time.isoformat() + "Z",
                "lat": round(float(r.lat), 5),
                "lon": round(float(r.lon), 5),
                "n_levels": int(r.n_levels),
                "max_depth": round(float(r.max_depth), 1),
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
    spec = load_registry().get("argo_gdac_indian")
    first = sub.iloc[0]
    return {
        "profile_id": str(first["profile_id"]),
        "wmo": str(first["wmo"]),
        "time": first["time"].isoformat() + "Z",
        "lat": round(float(first["lat"]), 5),
        "lon": round(float(first["lon"]), 5),
        "citation": spec.citation,
        "qc_policy": f"QC flags {spec.qc.accept_flags} only (Wong et al. 2020)",
        "n_levels": int(len(sub)),
        "levels": {
            "depth": [round(float(v), 2) for v in sub["depth"]],
            "pres": [round(float(v), 2) for v in sub["pres"]],
            "temp": _nan_to_none(sub["temp"].to_numpy()),
            "psal": _nan_to_none(sub["psal"].to_numpy()),
        },
    }
