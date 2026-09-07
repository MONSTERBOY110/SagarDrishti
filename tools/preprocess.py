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


def process_argo(spec, files: list[Path]) -> Path | None:
    print(f"argo: {len(files)} file(s)")
    frames = []
    for f in sorted(files):
        df = parse_profiles(f, spec)
        n_prof = df["profile_id"].nunique() if not df.empty else 0
        print(f"  {f.name}: {n_prof} profiles, {len(df)} accepted levels")
        frames.append(df)

    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)

    # Restrict to the demo box so the client is not handed the whole basin.
    reg_defaults = load_registry_from(SOURCES).defaults.get("demo_bbox", [80, 5, 95, 25])
    w, s, e, n = reg_defaults
    inside = df["lon"].between(w, e) & df["lat"].between(s, n)
    print(f"  {int(inside.sum())} of {len(df)} levels inside the demo box {reg_defaults}")
    df = df[inside].reset_index(drop=True)

    if df.empty:
        print("  !! no profiles inside the demo box")
        return None

    out = CUBE / "profiles.parquet"
    df.to_parquet(out, index=False)
    summary = profile_summary(df)
    write_provenance(
        out,
        source_id=spec.id,
        title=spec.title,
        citation=spec.citation,
        variables=["TEMP", "PSAL"],
        source_url=spec.url,
        extra={
            "n_profiles": int(len(summary)),
            "n_levels": int(len(df)),
            "n_floats": int(df["wmo"].nunique()),
            "qc_accept_flags": spec.qc.accept_flags,
            "bbox": reg_defaults,
            "time_range": [str(df["time"].min()), str(df["time"].max())],
        },
    )
    print(f"  {len(summary)} profiles from {df['wmo'].nunique()} floats")
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
    process_argo(reg.get("argo_gdac_indian"), argo_files)

    print("cube ready. Start the API:  ./tasks.ps1 api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
