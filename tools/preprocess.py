"""data/raw -> data/cube: CF-normalize, harmonize, rechunk, record provenance.

No network access (that lives in fetch_sample.py). This is the boundary where
messy source NetCDF becomes the clean contract the API and renderer rely on:
canonical dims (time, depth, lat, lon), depth positive-down in metres, NaN for
missing, CF-valid units, and a provenance.json the agent can cite.

Usage:
    python tools/preprocess.py              # process whatever is in data/raw
    python tools/preprocess.py --fixtures   # build from data/sample, for CI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app import cap as cap_reader  # noqa: E402
from app.argo import parse_profiles, profile_summary  # noqa: E402
from app.cf import normalize_dataset  # noqa: E402
from app.provenance import write_provenance  # noqa: E402
from app.registry import load_registry_from  # noqa: E402

RAW = REPO / "data" / "raw"
CUBE = REPO / "data" / "cube"
#: 614 KB of REAL data, committed on purpose. See data/sample/README.md.
SAMPLE = REPO / "data" / "sample"
SOURCES = REPO / "data" / "sources.yaml"

#: Chunking follows Signell & Pothina (PRIOR-ART §E.1): the renderer asks for a
#: whole water column at one timestep, so keep depth and the horizontal plane
#: contiguous and chunk along time.
CHUNKS = {"time": 1, "depth": -1, "lat": -1, "lon": -1}


#: Where each gridded source lands in the cube. A source with no entry is not
#: a gridded field and is not processed by process_model.
STORE_NAME = {
    "incois_vam_argo": "incois_vam_bob.zarr",
    "glorys12_cur": "glorys12_cur_bob.zarr",
}


def process_model(spec, src: Path, store_name: str | None = None) -> Path:
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

    store = CUBE / (store_name or STORE_NAME.get(spec.id) or f"{spec.id}.zarr")
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
        # ERDDAP puts the dataset under /griddap; Copernicus addresses it by id
        # through its own client. Naming the right one matters: the provenance
        # is what a reader follows to check a number.
        source_url=(
            f"{spec.url}/griddap/{spec.dataset_id}"
            if spec.kind == "erddap_griddap"
            else f"{spec.url} (dataset {spec.dataset_id})"
        ),
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


def profiles_from_reader(spec, model_times) -> pd.DataFrame:
    """A plugin-read source -> the same profile frame every other source produces.

    THIS is what makes the source-reader half of the plugin interface a running
    example rather than a tested one (PS requirement F6). `plugins.open_source`
    existed, held a checked contract, and was called by nothing outside its own
    tests. It is called here, on a real moored buoy, and its output joins the
    same table the Argo floats land in.

    ONE PROFILE PER MODEL TIMESTEP, and the discard is deliberate and counted.
    A mooring reports DAILY from one fixed position, so a month of RAMA is
    about 36 profiles at a single point: on a globe that is 36 coincident marks
    and one arbitrary pick when a judge clicks. The model has three timesteps,
    so the mooring is subsampled to the day nearest each of them, which is the
    same shape a float gives (one profile per surfacing) and is the only one of
    those readings that can honestly be shown beside a given model field.
    Everything dropped is counted into the provenance.
    """
    from app import plugins as plugin_api

    ds = plugin_api.open_source(spec)

    # A reader that returns ragged CASTS takes the other path. A mooring's
    # profiles are all at one point, so they are subsampled to the model steps
    # to stop 36 marks stacking on one pixel; a glider's are metres apart and
    # tens of kilometres from each other, so the same rule would throw away the
    # track that makes it a glider.
    if str(ds.attrs.get("layout", "")) == "casts":
        return profiles_from_casts(ds, spec)

    accept = list(spec.qc.accept_flags)
    rows: list[pd.DataFrame] = []
    wanted = pd.to_datetime(list(model_times)) if model_times is not None else None
    n_available = 0
    n_kept = 0

    # `profile` is the axis open_source concatenates several stations along.
    n_stations = int(ds.sizes.get("profile", 1))
    for station_index in range(n_stations):
        one = ds.isel(profile=station_index) if "profile" in ds.dims else ds

        station = str(one.attrs.get("station", "") or f"station{station_index}")
        wmo = str(one.attrs.get("wmo_platform_code", "") or station)
        lat = float(one["lat"].values)
        lon = float(one["lon"].values)

        times = pd.to_datetime(one["time"].values)
        depths = np.asarray(one["depth"].values, dtype="float64")
        values = np.asarray(one["TEMP"].values, dtype="float64")
        flags = np.asarray(one["TEMP_QC"].values, dtype="float64")
        n_available += len(times)

        if wanted is not None and len(wanted) and len(times):
            # Nearest reported day to each model step, deduplicated: two model
            # steps can share a nearest day when the mooring has a gap.
            picks = sorted({int(np.argmin(np.abs(times - w))) for w in wanted})
        else:
            picks = list(range(len(times)))

        for i in picks:
            temp = values[i]
            flag = flags[i]
            keep = np.isfinite(temp) & np.isin(flag.astype("int16"), accept)
            if not keep.any():
                continue
            n_kept += 1
            stamp = pd.Timestamp(times[i])
            rows.append(
                pd.DataFrame(
                    {
                        "profile_id": f"{wmo}_{stamp.strftime('%Y%m%dT%H%M%S')}",
                        "wmo": wmo,
                        "time": stamp,
                        "lat": lat,
                        "lon": lon,
                        # A mooring measures at a KNOWN DEPTH on a fixed line,
                        # not at a pressure it has to convert. Left absent
                        # rather than back-computed: a pressure this instrument
                        # never measured would be an invented number.
                        "pres": np.nan,
                        "depth": depths[keep],
                        "temp": temp[keep],
                        "temp_qc": flag[keep].astype("int16"),
                    }
                )
            )

    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out.attrs["n_profiles_available"] = n_available
    out.attrs["n_profiles_kept"] = n_kept
    return out


def profiles_from_casts(ds, spec) -> pd.DataFrame:
    """A ragged (profile, level) cast Dataset -> the standard profile frame.

    EVERY CAST IS KEPT. The mooring branch above subsamples to the model's
    timesteps and says why: a mooring reports daily from one fixed position, so
    a month of it is 36 marks on one pixel and an arbitrary pick when a judge
    clicks. A glider is the opposite case. Its 109 in-box dives are at 109
    different positions strung out over ten weeks of flying, and the line they
    draw across the sea IS the thing a glider shows that no other instrument
    can. Subsampling it would be applying a rule to a case its reason does not
    reach.

    Salinity travels with the temperature here, because this format flags the
    two independently and a cast with a rejected salinity can still have a
    perfectly good temperature at the same level.
    """
    # The registry says what instrument this is; the reader worked it out from
    # the file's own `source` attribute. If they disagree, one of them is
    # wrong about what is in the water and the globe would draw the wrong mark
    # either way, so this fails the ingest rather than picking a winner.
    declared = getattr(spec, "instrument_class", None)
    detected = str(ds.attrs.get("platform_kind", "") or "")
    if declared and detected and declared != detected:
        raise ValueError(
            f"{spec.id}: sources.yaml declares instrument_class {declared!r} "
            f"but the file's own source attribute reads as {detected!r}. One "
            f"of the two is describing a different instrument"
        )

    accept = list(spec.qc.accept_flags)
    depth = np.asarray(ds["depth"].values, dtype="float64")
    pres = np.asarray(ds["pres"].values, dtype="float64")
    temp = np.asarray(ds["TEMP"].values, dtype="float64")
    temp_qc = np.asarray(ds["TEMP_QC"].values, dtype="float64")
    have_psal = "PSAL" in ds
    psal = np.asarray(ds["PSAL"].values, dtype="float64") if have_psal else None
    psal_qc = np.asarray(ds["PSAL_QC"].values, dtype="float64") if have_psal else None

    times = pd.to_datetime(ds["time"].values)
    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")
    wmo = str(ds.attrs.get("wmo_platform_code", "") or ds.attrs.get("station", ""))

    rows: list[pd.DataFrame] = []
    n_available = len(times)
    n_kept = 0
    for i in range(n_available):
        keep = (
            np.isfinite(depth[i])
            & np.isfinite(temp[i])
            & np.isin(temp_qc[i].astype("int16"), accept)
        )
        if not keep.any():
            continue
        n_kept += 1
        stamp = pd.Timestamp(times[i])
        frame = {
            "profile_id": f"{wmo}_{stamp.strftime('%Y%m%dT%H%M%S')}",
            "wmo": wmo,
            "time": stamp,
            "lat": float(lats[i]),
            "lon": float(lons[i]),
            # Unlike a mooring, this instrument DID measure a pressure, so the
            # column is carried rather than left absent.
            "pres": pres[i][keep],
            "depth": depth[i][keep],
            "temp": temp[i][keep],
            "temp_qc": temp_qc[i][keep].astype("int16"),
        }
        if have_psal:
            # A salinity that failed QC is dropped at its own level, leaving the
            # temperature there intact. Masking the whole level on either flag
            # would discard good temperature because salinity was bad.
            good_psal = np.isin(psal_qc[i].astype("int16"), accept)
            frame["psal"] = np.where(good_psal[keep], psal[i][keep], np.nan)
            frame["psal_qc"] = psal_qc[i][keep]
        rows.append(pd.DataFrame(frame))

    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out.attrs["n_profiles_available"] = n_available
    out.attrs["n_profiles_kept"] = n_kept
    return out


def _has_reader(spec) -> bool:
    """True when a plugin has registered a reader for this source's kind."""
    from app import plugins as plugin_api

    return plugin_api.load_plugins().source_reader(spec.kind) is not None


def model_timesteps(store: Path):
    """The cube's own time axis, so a daily instrument can be sampled to it."""
    try:
        ds = xr.open_zarr(store)
    except Exception:
        return None
    return pd.to_datetime(ds["time"].values)


def process_argo(
    jobs: list[tuple[object, list[Path]]],
    *,
    window: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    model_times=None,
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
        # A source whose KIND has a registered plugin reader is opened through
        # the plugin, not by a parser hardcoded here. That is the whole point of
        # the extension point: adding a moored buoy needed a plugin file and a
        # sources.yaml entry, and this branch, rather than a new parser in the
        # core for every instrument anyone might bring.
        if _has_reader(spec):
            print(f"{spec.id}: via the {spec.kind!r} plugin reader")
            df = profiles_from_reader(spec, model_times)
            available = df.attrs.get("n_profiles_available") if not df.empty else 0
            kept = df.attrs.get("n_profiles_kept") if not df.empty else 0
            print(
                f"  {kept} profile(s) kept of {available} reported, "
                f"{len(df)} accepted levels"
            )
            if not df.empty:
                df["source_id"] = spec.id
                frames.append(df)
            per_source[spec.id] = {
                "title": spec.title,
                "citation": spec.citation,
                "source_url": spec.url,
                "variables": [v.name for v in spec.variables],
                "qc_accept_flags": spec.qc.accept_flags,
                "prefer_adjusted": spec.qc.prefer_adjusted,
                "n_files": 0,
                "read_by_plugin": spec.kind,
                # The discard is disclosed: a mooring reports daily and only
                # the day nearest each model step is drawn.
                "n_profiles_reported": int(available or 0),
                "n_profiles_kept": int(kept or 0),
            }
            continue

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

        # A source declared `epoch: archive` is exempt, and the exemption is
        # narrow and deliberate. The rule above exists because an April 2025
        # float mark sitting unlabelled among July 2026 ones states a
        # co-location that does not exist -- SILENTLY, which is the part that
        # makes it a defect. An archive source is not silent: it carries an
        # epoch_note the registry refuses to let it omit, the client draws it
        # as a different thing, and the scorecard's five-day rule refuses to
        # pair it and counts the refusal.
        #
        # Without this exemption the PS's glider and CTD requirement (F2) is
        # unanswerable in this basin, because the Bay of Bengal has no
        # contemporaneous glider: on 2026-09-01 the entire near-real-time feed
        # held one Indian Ocean glider, in the Mozambique Channel. The choice
        # is between a real instrument with its date declared and no instrument
        # at all, and it is NOT between either of those and a pretend current
        # one.
        archive_ids = {
            s.id for s in load_registry_from(SOURCES).enabled()
            if getattr(s, "epoch", "contemporaneous") == "archive"
        }
        exempt = df["source_id"].isin(archive_ids)
        current = df["time"].between(start, end) | exempt
        dropped = before - df[current]["profile_id"].nunique()
        n_archive = int(df[exempt]["profile_id"].nunique())
        print(f"  time window {start.date()} .. {end.date()} "
              f"(the model cube's own span, widened half a step): "
              f"{dropped} profile(s) dropped as not contemporaneous")
        if n_archive:
            print(f"  {n_archive} archive profile(s) kept and marked as such "
                  f"from {sorted(archive_ids & set(df['source_id']))}")
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


def process_warnings(reg) -> Path | None:
    """Every `kind: cap` source into one warnings.json (HazardWatch, PRD F13).

    JSON rather than parquet or zarr, and that is a considered choice: a CAP
    alert is a nested document with a variable number of languages and areas,
    which is exactly what a columnar store is bad at, and the whole national
    feed comes to a few hundred kilobytes. The API reads this file and nothing
    else, so the offline path is the same code path as always.

    Two things happen here that the parser deliberately does not do, because
    both are pipeline decisions rather than readings of the format:

      * SACHET's geometry SIDECAR is attached to the alert it belongs to. The
        parser reads one document; joining two is ingest's job.
      * Oversized rings are SIMPLIFIED, with the reduction recorded on the
        alert. A single real Gujarat alert carried 93,478 points.
    """
    sources = [s for s in reg.enabled() if s.kind == "cap"]
    if not sources:
        return None

    print("warnings: CAP sources")
    records = []
    refused = []
    for spec in sources:
        root = REPO / spec.url if not Path(spec.url).is_absolute() else Path(spec.url)
        # A remote source keeps its endpoint in `url` and its local landing
        # directory in `path_template`; a local one puts the directory in `url`
        # and a glob in `path_template`. Both shapes resolve to a directory.
        if spec.url.startswith("http"):
            root = REPO / (spec.path_template or "")
            pattern = "*.cap.xml"
        else:
            pattern = spec.path_template or "*.cap.xml"

        if not root.is_dir():
            print(f"  {spec.id}: nothing at {root.relative_to(REPO)} (skipped)")
            continue

        found = sorted(root.glob(pattern))
        kept = 0
        for f in found:
            try:
                alert = cap_reader.parse_alert(f.read_bytes(), source=spec.id)
            except cap_reader.CapError as exc:
                # Counted and named. A CAP document we cannot read is a warning
                # we are not showing, and that has to be visible in the output
                # rather than inferred from a shorter list.
                refused.append({"file": f.name, "source": spec.id, "reason": str(exc)})
                continue

            sidecar = f.with_name(f.name.replace(".cap.", ".polygon."))
            if not alert.geometry() and sidecar.is_file() and sidecar.stat().st_size:
                try:
                    alert.attach_geometry(cap_reader.parse_polygon_sidecar(sidecar.read_bytes()))
                except cap_reader.CapError as exc:
                    alert.notes.append(f"polygon sidecar unreadable: {exc}")

            alert.simplify()
            records.append(alert.as_dict())
            kept += 1

        drawn = sum(1 for r in records[-kept:] if r["areas"]) if kept else 0
        print(f"  {spec.id}: {kept} alerts from {len(found)} files, {drawn} with geometry")

    if not records:
        print("  no CAP alerts on disk; HazardWatch will report an empty layer")

    vertices = sum(
        len(ring) for r in records for a in r["areas"] for ring in a["polygons"]
    )
    payload = {
        "generated_from": [s.id for s in sources],
        "citations": {s.id: s.citation for s in sources},
        "method": cap_reader.METHOD,
        "simplify_tolerance_deg": cap_reader.SIMPLIFY_TOLERANCE_DEG,
        "count": len(records),
        "vertices": vertices,
        "unreadable": refused,
        "alerts": records,
    }
    dest = CUBE / "warnings.json"
    dest.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {dest.relative_to(REPO)}  ({dest.stat().st_size / 1024:.0f} KB, "
          f"{vertices} vertices)")
    if refused:
        print(f"  !! {len(refused)} CAP documents were unreadable and are listed in the file")
    return dest


def build_fixtures() -> None:
    """Build the demo cube from the COMMITTED SAMPLE, with no network (CI).

    `data/sample/` holds 614 KB of real data: the INCOIS griddap subset exactly
    as tools/fetch_sample.py downloads it, and the processed in-situ profile
    table. See the README beside them for why they are in the repository when
    data/raw and data/cube are not.

    This used to synthesise a small invented field instead, and that was a
    quiet hole in the build. The browser suite in e2e/ asserts claims about the
    REAL Bay of Bengal by design (the surface is warmer than 2000 m, the
    cartouche cites incois_argo_10d_VAM, a BGC float really serves chlorophyll,
    the 26 degC surface varies in depth and splits in two on 10 July), and not
    one of those is reachable against an invented field. Four of six browser
    tests could not pass on CI however correct the application was, so the
    suite only really ran when somebody remembered to run it locally.

    The synthetic path survives below as a FALLBACK, for a checkout where the
    sample is missing. It builds something the API can serve so nothing hard
    crashes, and it says plainly that the demo-path claims cannot be tested
    against it.
    """
    CUBE.mkdir(parents=True, exist_ok=True)
    reg = load_registry_from(SOURCES)

    model = SAMPLE / "incois_vam_bob.nc"
    profiles = SAMPLE / "profiles.parquet"

    if not model.is_file():
        print(f"no committed sample at {SAMPLE.relative_to(REPO)}; "
              "falling back to a synthetic cube")
        _build_synthetic_cube()
    else:
        print(f"building from the committed sample ({SAMPLE.relative_to(REPO)}, no network)")
        process_model(reg.get("incois_vam_argo"), model)

        if profiles.is_file():
            dest = CUBE / "profiles.parquet"
            dest.write_bytes(profiles.read_bytes())
            prov = SAMPLE / "profiles.provenance.json"
            if prov.is_file():
                (CUBE / "profiles.provenance.json").write_bytes(prov.read_bytes())
            n = len(pd.read_parquet(dest)["profile_id"].unique())
            print(f"  -> {dest.relative_to(REPO)}  ({n} real profiles)")
        else:
            print("  no sample profile table; the instrument panels will be empty")

    # The warning layer either way: the rehearsal CAP bulletins are committed
    # under data/warnings/incois, which is exactly why they are committed. The
    # SACHET source finds nothing on a fresh checkout because its downloads
    # live under the gitignored data/raw, and that is printed rather than
    # passed over.
    process_warnings(reg)


def _build_synthetic_cube() -> None:
    """A tiny invented field, for a checkout with no committed sample.

    Enough for the API to serve and for the offline smoke check to pass. NOT
    enough for the demo-path browser suite, whose assertions are claims about
    the real ocean, and that limit is stated here rather than discovered as
    four red tests.
    """
    print("  SYNTHETIC field: the demo-path browser tests cannot be met by this")
    depth = np.array(
        [5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
         600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000],
        dtype="float64",
    )
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
        title="INCOIS VAM (synthetic fallback)",
        citation="SYNTHETIC FALLBACK -- not real data, do not cite",
        variables=["TEMP"],
        extra={"fixture": True},
    )
    print(f"  -> {store.relative_to(REPO)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fixtures",
        action="store_true",
        help="build the cube from data/sample, no network (this is what CI runs)",
    )
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

    # Depth-resolved currents (PS F1). Additive: absent is not an error, since
    # this source needs a Copernicus account and a checkout without one still
    # has a complete demo of everything INCOIS can answer.
    if reg.has("glorys12_cur") and reg.get("glorys12_cur").enabled:
        cur_src = RAW / "glorys" / "glorys12_cur_bob.nc"
        if cur_src.is_file():
            process_model(reg.get("glorys12_cur"), cur_src)
        else:
            print("no GLORYS currents in data/raw/glorys "
                  "(needs COPERNICUS_USERNAME and COPERNICUS_PASSWORD in .env)")

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

    # Any source whose kind has a plugin reader joins the same job list. The
    # core does not know what a mooring is; the plugin does.
    for spec in reg.enabled():
        if spec.id in {j[0].id for j in jobs}:
            continue
        if _has_reader(spec):
            jobs.append((spec, []))

    # Warnings are independent of the field pipeline: they need no cube, no
    # time window and no model grid, so a failure in either half cannot take
    # the other down.
    process_warnings(reg)

    window = model_time_window(CUBE / "incois_vam_bob.zarr")
    model_times = model_timesteps(CUBE / "incois_vam_bob.zarr")
    process_argo(jobs, window=window, model_times=model_times)

    print("cube ready. Start the API:  ./tasks.ps1 api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
