"""Local cube access and subsetting (TRD M2/M6).

This module is the reason OFFLINE=1 is the default rather than a mode: the API
reads zarr stores and a parquet table from disk and nothing else. There is no
network client anywhere in `services/api`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from .config import get_settings
from .provenance import read_provenance
from .registry import SourceSpec, load_registry


class SubsetError(ValueError):
    """A caller-fixable problem with a subset request -> HTTP 400.

    Distinct from "this dataset does not exist" (404) because the two need
    different reactions: one is a typo in a query, the other a missing store.
    """


@dataclass(frozen=True)
class StoreRef:
    source_id: str
    path: Path
    provenance: dict


def discover_stores() -> dict[str, StoreRef]:
    """Map source_id -> zarr store present in the cube directory.

    A source is only servable if it has actually been materialized locally,
    which is what keeps /catalog honest: it advertises what we can draw, not
    what we hope to download.
    """
    cube = get_settings().cube_dir
    found: dict[str, StoreRef] = {}
    if not cube.is_dir():
        return found

    for path in sorted(cube.glob("*.zarr")):
        prov = read_provenance(path)
        source_id = prov.get("source_id")
        if not source_id:
            # Fall back to the dataset attribute, so a hand-built store still
            # works -- but it will have no citation, and the API says so.
            try:
                source_id = xr.open_zarr(path).attrs.get("source_id")
            except Exception:
                source_id = None
        if source_id:
            found[source_id] = StoreRef(source_id=source_id, path=path, provenance=prov)
    return found


@lru_cache(maxsize=8)
def _open(path_str: str) -> xr.Dataset:
    return xr.open_zarr(path_str, decode_times=True)


def open_cube(source_id: str) -> tuple[xr.Dataset, StoreRef]:
    stores = discover_stores()
    if source_id not in stores:
        raise KeyError(source_id)
    ref = stores[source_id]
    return _open(str(ref.path)), ref


def clear_caches() -> None:
    _open.cache_clear()


# --- request parsing --------------------------------------------------------

def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse "west,south,east,north" with a message a caller can act on."""
    parts = [p.strip() for p in str(text).split(",")]
    if len(parts) != 4:
        raise SubsetError(
            f"bbox needs 4 comma-separated numbers (west,south,east,north), got {len(parts)}"
        )
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError:
        raise SubsetError(f"bbox values must be numbers, got {text!r}") from None

    if not (-180.0 <= w <= 180.0 and -180.0 <= e <= 180.0):
        raise SubsetError(f"bbox longitudes must lie in [-180, 180], got {w} and {e}")
    if not (-90.0 <= s <= 90.0 and -90.0 <= n <= 90.0):
        raise SubsetError(f"bbox latitudes must lie in [-90, 90], got {s} and {n}")
    if e <= w:
        raise SubsetError(f"bbox east ({e}) must be greater than west ({w})")
    if n <= s:
        raise SubsetError(f"bbox north ({n}) must be greater than south ({s})")
    return w, s, e, n


def nearest_time(ds: xr.Dataset, wanted: str) -> np.datetime64:
    """Snap to the nearest available timestep, or refuse if far outside.

    Refusing matters: an out-of-range time that silently returns the closest
    step would show a judge a field from a different month while the scrubber
    claims otherwise.
    """
    try:
        target = pd.Timestamp(wanted)
    except (ValueError, TypeError):
        raise SubsetError(f"time {wanted!r} is not a valid ISO-8601 timestamp") from None
    if target.tzinfo is not None:
        target = target.tz_convert("UTC").tz_localize(None)

    times = pd.to_datetime(ds["time"].values)
    if len(times) == 0:
        raise SubsetError("this dataset has no time axis")

    spacing = pd.Timedelta(days=10)
    if len(times) > 1:
        spacing = pd.Timedelta(np.median(np.diff(times.values)))
    tol = spacing  # one full step of slack either side

    if target < times.min() - tol or target > times.max() + tol:
        raise SubsetError(
            f"time {target.isoformat()} is outside the available range "
            f"{times.min().isoformat()} .. {times.max().isoformat()}"
        )
    return times[int(np.argmin(np.abs(times - target)))].to_datetime64()


def nearest_depth(ds: xr.Dataset, wanted: float) -> float:
    depths = np.asarray(ds["depth"].values, dtype="float64")
    if wanted < depths.min() - 1e-6 or wanted > depths.max() + 1e-6:
        raise SubsetError(
            f"depth {wanted} m is outside the available range "
            f"{depths.min()} .. {depths.max()} m"
        )
    return float(depths[int(np.argmin(np.abs(depths - wanted)))])


# --- the field subset -------------------------------------------------------

@dataclass
class FieldSlab:
    values: np.ndarray            # (lat, lon) or (depth, lat, lon)
    lats: list[float]
    lons: list[float]
    depths: list[float] | None
    depth: float | None
    time: str
    units: str


def select_field(
    ds: xr.Dataset,
    var: str,
    *,
    bbox: tuple[float, float, float, float],
    time: str,
    depth: float | None = None,
    all_depths: bool = False,
) -> FieldSlab:
    if var not in ds.data_vars:
        raise KeyError(var)

    w, s, e, n = bbox
    da = ds[var]

    # A descending coordinate needs a reversed slice; ERDDAP serves both.
    lat_ascending = bool(ds["lat"].values[0] <= ds["lat"].values[-1])
    lon_ascending = bool(ds["lon"].values[0] <= ds["lon"].values[-1])
    da = da.sel(
        lat=slice(s, n) if lat_ascending else slice(n, s),
        lon=slice(w, e) if lon_ascending else slice(e, w),
    )

    if da.sizes.get("lat", 0) == 0 or da.sizes.get("lon", 0) == 0:
        dl, dn = ds["lat"].values, ds["lon"].values
        raise SubsetError(
            f"bbox ({w}, {s}, {e}, {n}) selects no grid cells -- it is outside "
            f"this dataset's domain (lon {dn.min()}..{dn.max()}, "
            f"lat {dl.min()}..{dl.max()})"
        )

    t = nearest_time(ds, time)
    da = da.sel(time=t)

    served_depth: float | None = None
    depths: list[float] | None = None
    if all_depths:
        depths = [float(d) for d in np.asarray(ds["depth"].values, dtype="float64")]
    else:
        served_depth = nearest_depth(ds, 0.0 if depth is None else float(depth))
        da = da.sel(depth=served_depth)

    return FieldSlab(
        values=np.asarray(da.values, dtype="float64"),
        lats=[float(v) for v in np.asarray(da["lat"].values, dtype="float64")],
        lons=[float(v) for v in np.asarray(da["lon"].values, dtype="float64")],
        depths=depths,
        depth=served_depth,
        time=pd.Timestamp(t).isoformat() + "Z",
        units=str(da.attrs.get("units", ds[var].attrs.get("units", ""))),
    )


def cube_summary(source_id: str, spec: SourceSpec) -> dict:
    """The /catalog entry for one materialized source."""
    ds, ref = open_cube(source_id)
    times = [pd.Timestamp(t).isoformat() + "Z" for t in pd.to_datetime(ds["time"].values)]
    depths = [float(d) for d in np.asarray(ds["depth"].values, dtype="float64")]
    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")

    return {
        "id": source_id,
        "title": ref.provenance.get("title") or spec.title,
        "kind": spec.kind,
        "citation": ref.provenance.get("citation") or spec.citation,
        "variables": [
            {
                "name": v.name,
                "label": v.label or v.name,
                "units": str(ds[v.name].attrs.get("units", "")),
                "canonical": v.canonical,
            }
            for v in spec.variables
            if v.name in ds.data_vars
        ],
        "depths": depths,
        "times": times,
        "bbox": [float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max())],
        "retrieved_at": ref.provenance.get("retrieved_at"),
    }


def load_profiles() -> pd.DataFrame:
    """Argo profiles from the local parquet table, or an empty frame."""
    path = get_settings().profiles_parquet
    if not path.is_file():
        return pd.DataFrame(
            columns=["profile_id", "wmo", "time", "lat", "lon", "pres", "depth",
                     "temp", "temp_qc", "psal", "psal_qc"]
        )
    return pd.read_parquet(path)


def catalog_entries() -> list[dict]:
    reg = load_registry()
    stores = discover_stores()
    out = []
    for spec in reg.enabled():
        if spec.id in stores:
            out.append(cube_summary(spec.id, spec))
    return out
