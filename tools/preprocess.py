"""data/raw -> data/cube: CF-normalize, harmonize, rechunk, record provenance.

No network access (that lives in fetch_sample.py). This is the boundary where
messy source NetCDF becomes the clean contract the API and renderer rely on:
canonical dims (time, depth, lat, lon), depth positive-down in metres, NaN for
missing, CF-valid units, and a provenance.json the agent can cite.

Usage:
    python tools/preprocess.py              # process whatever is in data/raw
    python tools/preprocess.py --fixtures   # tiny synthetic cube, for CI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app.argo import parse_profiles, profile_summary  # noqa: E402
from app.cf import normalize_dataset  # noqa: E402
from app.provenance import write_provenance  # noqa: E402
from app.registry import load_registry_from  # noqa: E402

RAW = REPO / "data" / "raw"
CUBE = REPO / "data" / "cube"
SOURCES = REPO / "data" / "sources.yaml"

#: Chunking follows Signell & Pothina (PRIOR-ART §E.1): the renderer asks for a
#: whole water column at one timestep, so keep depth and the horizontal plane
#: contiguous and chunk along time.
CHUNKS = {"time": 1, "depth": -1, "lat": -1, "lon": -1}


def process_model(spec, src: Path) -> Path:
    print(f"model: {src.name}")
    raw = xr.open_dataset(src, decode_times=True, mask_and_scale=True)
    print(f"  raw dims      : {dict(raw.sizes)}")
    print(f"  raw vars      : {list(raw.data_vars)}")
    print(f"  raw depth attr: {dict(raw[spec.dims.depth].attrs)}")

    ds = normalize_dataset(raw, spec)

    print(f"  normalized    : {dict(ds.sizes)}")
    print(f"  depth         : {ds['depth'].values[:4]} ... {ds['depth'].values[-2:]}"
          f"  ({ds['depth'].attrs['positive']}, {ds['depth'].attrs['units']})")
    for name in ds.data_vars:
        da = ds[name]
        finite = np.isfinite(da.values)
        print(f"  {name:5s} units={da.attrs.get('units','?'):5s} "
              f"valid={finite.mean() * 100:.1f}%  "
              f"range=[{np.nanmin(da.values):.2f}, {np.nanmax(da.values):.2f}]")

    chunks = {k: (ds.sizes[k] if v == -1 else v) for k, v in CHUNKS.items() if k in ds.sizes}
    ds = ds.chunk(chunks)
    for name in ds.data_vars:
        ds[name].encoding.clear()

    store = CUBE / "incois_vam_bob.zarr"
    if store.exists():
        import shutil

        shutil.rmtree(store)
    ds.to_zarr(store, mode="w")
    write_provenance(
        store,
        source_id=spec.id,
        title=spec.title,
        citation=spec.citation,
        variables=list(ds.data_vars),
        source_url=f"{spec.url}/griddap/{spec.dataset_id}",
        extra={
            "time_range": [str(pd.Timestamp(t)) for t in (ds.time.values[0], ds.time.values[-1])],
            "depth_levels": int(ds.sizes["depth"]),
            "bbox": [
                float(ds.lon.min()), float(ds.lat.min()),
                float(ds.lon.max()), float(ds.lat.max()),
            ],
            "cf_overrides_applied": spec.cf_overrides,
        },
    )
    size = sum(f.stat().st_size for f in store.rglob("*") if f.is_file())
    print(f"  -> {store.relative_to(REPO)}  ({size / 1024:.0f} KB)\n")
    return store


def model_time_window(store: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """The span a profile may fall in to be shown beside this model cube.

    The cube's own time axis, widened by half a timestep at each end. Without
    this, a BGC float's synthetic profile file drags in that float's ENTIRE
    deployment history: the three Bay of Bengal BGC floats carry 132 profiles
    from 2025-04-15 to 2026-08-30, against a model cube covering three dates in
    July 2026. Putting an April 2025 float mark inside a July 2026 field, on
    one globe, under one time scrubber, states a co-location that does not
    exist. Nine of those 132 profiles are genuinely contemporaneous, and those
    are the ones worth drawing.
    """
    try:
        ds = xr.open_zarr(store)
    except Exception:
        return None
    times = pd.to_datetime(ds["time"].values)
    if len(times) == 0:
        return None
    half = pd.Timedelta(days=5)
    if len(times) > 1:
        half = pd.Timedelta(np.median(np.diff(times.values))) / 2
    return times.min() - half, times.max() + half


def process_argo(
    jobs: list[tuple[object, list[Path]]],
    *,
    window: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> Path | None:
    """Parse every profile source into ONE table, tagged with where each row came from.

    Takes a list of (spec, files) rather than a single source because the
    profile table is the union of several instrument classes: core Argo floats,
    BGC floats, and later the text-ingested glider and CTD casts. They share a
    schema, a QC policy and a chart, so they belong in one table.

    Every row carries `source_id`. That column replaces a guess: provenance was
    routed by looking at the shape of the platform id, which works for a text
    cast (prefixed "CTD-...") but silently misfiles a BGC float, whose WMO is
    seven digits exactly like a core float's. A BGC measurement cited to the
    core daily files would be the same misattribution the routing exists to
    prevent, arriving by a different door.
    """
    frames = []
    per_source: dict[str, dict] = {}
    for spec, files in jobs:
        if not files:
            continue
        print(f"{spec.id}: {len(files)} file(s)")
        for f in sorted(files):
            df = parse_profiles(f, spec)
            n_prof = df["profile_id"].nunique() if not df.empty else 0
            print(f"  {f.name}: {n_prof} profiles, {len(df)} accepted levels")
            if df.empty:
                continue
            df["source_id"] = spec.id
            frames.append(df)
        per_source[spec.id] = {
            "title": spec.title,
            "citation": spec.citation,
            "source_url": spec.url,
            "variables": [v.name for v in spec.variables],
            "qc_accept_flags": spec.qc.accept_flags,
            "prefer_adjusted": spec.qc.prefer_adjusted,
            "n_files": len(files),
        }

    if not frames:
        return None
    # sort=False keeps column order stable; the BGC frame has more columns than
    # the core one, and the extra ones arrive as NaN for core rows, which is
    # correct: a core float did not measure chlorophyll.
    df = pd.concat(frames, ignore_index=True, sort=False)

    # Restrict to the demo box so the client is not handed the whole basin.
    reg_defaults = load_registry_from(SOURCES).defaults.get("demo_bbox", [80, 5, 95, 25])
    w, s, e, n = reg_defaults
    inside = df["lon"].between(w, e) & df["lat"].between(s, n)
    print(f"  {int(inside.sum())} of {len(df)} levels inside the demo box {reg_defaults}")
    df = df[inside].reset_index(drop=True)

    if window is not None and not df.empty:
        start, end = window
        before = df["profile_id"].nunique()
        current = df["time"].between(start, end)
        dropped = before - df[current]["profile_id"].nunique()
        print(f"  time window {start.date()} .. {end.date()} "
              f"(the model cube's own span, widened half a step): "
              f"{dropped} profile(s) dropped as not contemporaneous")
        df = df[current].reset_index(drop=True)

    if df.empty:
        print("  !! no profiles inside the demo box")
        return None

    out = CUBE / "profiles.parquet"
    df.to_parquet(out, index=False)
    summary = profile_summary(df)

    # Which parameters actually survived QC, per source. "Declared" and
    # "served" are different facts: a BGC float declares pH and may have every
    # pH level rejected, and a panel that offers an empty variable looks broken.
    measured = [c for c in df.columns if f"{c}_qc" in df.columns]
    for source_id, record in per_source.items():
        rows = df[df["source_id"] == source_id]
        record["n_profiles"] = int(rows["profile_id"].nunique())
        record["n_levels"] = int(len(rows))
        record["n_platforms"] = int(rows["wmo"].nunique())
        record["parameters_served"] = {
            col: int(rows[col].notna().sum())
            for col in measured
            if int(rows[col].notna().sum()) > 0
        }

    primary = next(iter(per_source)) if per_source else "argo_gdac_indian"
    write_provenance(
        out,
        source_id=primary,
        title="Profile observations (all instrument classes)",
        citation="; ".join(r["citation"] for r in per_source.values()),
        variables=sorted({v for r in per_source.values() for v in r["variables"]}),
        source_url=per_source.get(primary, {}).get("source_url"),
        extra={
            "n_profiles": int(len(summary)),
            "n_levels": int(len(df)),
            "n_platforms": int(df["wmo"].nunique()),
            "bbox": reg_defaults,
            "time_range": [str(df["time"].min()), str(df["time"].max())],
            # Per-source detail, so a citation can name the file family a given
            # profile came from rather than the union of everything ingested.
            "sources": per_source,
        },
    )
    print(f"  {len(summary)} profiles from {df['wmo'].nunique()} platforms "
          f"across {len(per_source)} source(s)")
    for source_id, record in per_source.items():
        served = ", ".join(f"{k} {v}" for k, v in record["parameters_served"].items())
        print(f"    {source_id}: {record['n_profiles']} profiles, {served}")
    print(f"  -> {out.relative_to(REPO)}  ({out.stat().st_size / 1024:.0f} KB)\n")
    return out


def build_fixtures() -> None:
    """A tiny synthetic cube so CI can exercise the offline path with no network."""
    print("building synthetic fixture cube (no network)")
    CUBE.mkdir(parents=True, exist_ok=True)
    depth = np.array([5, 10, 20, 50, 100, 200, 500, 1000], dtype="float64")
    lat = np.arange(5.5, 25.5, 1.0)
    lon = np.arange(80.5, 95.5, 1.0)
    time = pd.date_range("2026-07-10", periods=3, freq="10D")

    prof = 29.2 - 24.0 * (1.0 - np.exp(-depth / 350.0))
    field = np.broadcast_to(
        prof[None, :, None, None], (len(time), len(depth), len(lat), len(lon))
    ).astype("float32").copy()
    field[:, :, 0, 0] = np.nan  # a land cell

    ds = xr.Dataset(
        {"TEMP": (("time", "depth", "lat", "lon"), field)},
        coords={"time": time, "depth": depth, "lat": lat, "lon": lon},
    )
    ds.TEMP.attrs.update(units="degC", long_name="Temperature")
    ds.depth.attrs.update(units="m", positive="down", standard_name="depth")
    ds.attrs["source_id"] = "incois_vam_argo"

    store = CUBE / "incois_vam_bob.zarr"
    if store.exists():
        import shutil

        shutil.rmtree(store)
    ds.to_zarr(store, mode="w")
    write_provenance(
        store,
        source_id="incois_vam_argo",
        title="INCOIS VAM (synthetic CI fixture)",
        citation="SYNTHETIC FIXTURE -- not real data, do not cite",
        variables=["TEMP"],
        extra={"fixture": True},
    )
    print(f"  -> {store.relative_to(REPO)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixtures", action="store_true", help="build a synthetic cube for CI")
    args = ap.parse_args()

    CUBE.mkdir(parents=True, exist_ok=True)
    if args.fixtures:
        build_fixtures()
        return 0

    reg = load_registry_from(SOURCES)

    model_spec = reg.get("incois_vam_argo")
    model_src = RAW / f"{model_spec.dataset_id}_bob.nc"
    if not model_src.is_file():
        print(f"missing {model_src.relative_to(REPO)} -- run tools/fetch_sample.py first")
        return 1
    process_model(model_spec, model_src)

    argo_files = sorted((RAW / "argo").glob("*_prof.nc"))
    if not argo_files:
        print("no Argo files in data/raw/argo -- run tools/fetch_sample.py first")
        return 1

    jobs: list[tuple[object, list[Path]]] = [(reg.get("argo_gdac_indian"), argo_files)]

    # BGC is additive. Absent files are not an error: the fetch skips BGC when
    # no BGC float is in the demo box, and the demo works on core floats alone.
    bgc_spec = reg.get("argo_bgc_indian") if reg.has("argo_bgc_indian") else None
    bgc_files = sorted((RAW / "argo_bgc").glob("*_Sprof.nc"))
    if bgc_spec and bgc_spec.enabled and bgc_files:
        jobs.append((bgc_spec, bgc_files))
    elif bgc_spec and bgc_spec.enabled:
        print("no BGC files in data/raw/argo_bgc (none found in the demo box); "
              "core floats only")

    window = model_time_window(CUBE / 'incois_vam_bob.zarr')
    process_argo(jobs, window=window)

    print("cube ready. Start the API:  ./tasks.ps1 api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
