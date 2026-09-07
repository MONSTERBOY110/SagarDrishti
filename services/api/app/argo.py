"""Argo profile parsing (TRD M1, feeding M5).

Two things here are load-bearing for the scorecard and both fail quietly:

1. **QC filtering.** Argo ships every level it measured, including ones the
   delayed-mode QC marked bad. Keeping flags 1 and 2 only is the Argo
   community's own convention (Wong et al. 2020, PRIOR-ART.md §E.4). Using
   flag-4 data does not crash anything -- it just makes our RMSE wrong.

2. **Pressure is not depth.** PRES is decibars. Treating 1000 dbar as 1000 m
   is roughly a 1% error, which looks entirely plausible on a chart while
   biasing every depth-binned comparison.
"""

from __future__ import annotations

from pathlib import Path

import gsw
import numpy as np
import pandas as pd
import xarray as xr

from .registry import SourceSpec

#: Argo reference date for JULD. NOT the Unix epoch -- a 20-year error.
JULD_EPOCH = np.datetime64("1950-01-01T00:00:00", "ns")


def pressure_to_depth(pres, lat: float) -> np.ndarray:
    """Sea pressure (dbar) -> depth (m, positive down) at a given latitude.

    Uses TEOS-10 (`gsw.z_from_p`), which returns height as a negative number,
    so we negate it. Latitude matters because gravity varies with it: the same
    pressure is a slightly shallower depth near the poles.
    """
    p = np.asarray(pres, dtype="float64")
    z = gsw.z_from_p(p, lat)          # height, negative below the surface
    return np.asarray(-z, dtype="float64")


def _as_char(c) -> str:
    """One element of an Argo char array -> a single character.

    Depending on how the file was written and whether xarray decoded it, the
    same variable arrives as bytes, as a numpy str, or as the integer ASCII
    code. Getting this wrong is not a crash: `str(50)` yields "50" and a WMO id
    silently becomes "5057485055525432".
    """
    if isinstance(c, bytes):
        return c.decode("ascii", "ignore")
    if isinstance(c, (np.integer, int)):
        return chr(int(c)) if 0 < int(c) < 128 else ""
    return str(c)


def _decode_char_array(var: xr.DataArray) -> list[str]:
    """Argo stores identifiers as fixed-width char arrays, space padded.

    PLATFORM_NUMBER is (N_PROF, STRING8) of single characters -- joining and
    stripping is the only way to recover the WMO id, and the agent must cite
    that id with every number it speaks (CLAUDE.md).
    """
    return ["".join(_as_char(c) for c in row).strip() for row in var.values]


def _decode_qc(var: xr.DataArray) -> np.ndarray:
    """QC flags are single characters; blank means 'no QC performed' (-> 9)."""
    raw = np.asarray(var.values)
    flat = [
        int(s) if (s := _as_char(c).strip()).isdigit() else 9
        for c in raw.ravel()
    ]
    return np.asarray(flat, dtype="int16").reshape(raw.shape)


def parse_profiles(path: str | Path, spec: SourceSpec) -> pd.DataFrame:
    """Parse an Argo multi-profile file into a tidy level-per-row frame.

    Returns columns: profile_id, wmo, time, lat, lon, pres, depth, temp,
    temp_qc, psal, psal_qc -- one row per accepted level.
    """
    accept = set(spec.qc.accept_flags)
    prefer_adjusted = spec.qc.prefer_adjusted

    with xr.open_dataset(path, decode_times=False, mask_and_scale=True) as ds:
        wmos = _decode_char_array(ds["PLATFORM_NUMBER"])
        n_prof = len(wmos)

        juld = np.asarray(ds["JULD"].values, dtype="float64")
        times = JULD_EPOCH + (juld * 86_400_000_000_000.0).astype("timedelta64[ns]")
        lats = np.asarray(ds["LATITUDE"].values, dtype="float64")
        lons = np.asarray(ds["LONGITUDE"].values, dtype="float64")

        def pick(base: str) -> tuple[np.ndarray, np.ndarray]:
            """Adjusted values when QC allows, else raw -- Argo's own guidance."""
            adj = f"{base}_ADJUSTED"
            if prefer_adjusted and adj in ds.variables:
                vals = np.asarray(ds[adj].values, dtype="float64")
                qc_name = f"{adj}_QC"
                if not np.isnan(vals).all():
                    qc = _decode_qc(ds[qc_name]) if qc_name in ds.variables else np.full(vals.shape, 1)
                    return vals, qc
            vals = np.asarray(ds[base].values, dtype="float64")
            qc_name = f"{base}_QC"
            qc = _decode_qc(ds[qc_name]) if qc_name in ds.variables else np.full(vals.shape, 1)
            return vals, qc

        pres, pres_qc = pick("PRES")
        temp, temp_qc = pick("TEMP")
        if "PSAL" in ds.variables:
            psal, psal_qc = pick("PSAL")
        else:
            psal = np.full_like(temp, np.nan)
            psal_qc = np.full(temp.shape, 9, dtype="int16")

        rows = []
        for i in range(n_prof):
            # profile_id must distinguish two profiles from the SAME float on
            # the same day, so it carries the cycle position, not just the WMO.
            profile_id = f"{wmos[i]}_{pd.Timestamp(times[i]).strftime('%Y%m%dT%H%M%S')}"
            depth_i = pressure_to_depth(pres[i], float(lats[i]))

            keep = (
                np.isin(temp_qc[i], list(accept))
                & np.isin(pres_qc[i], list(accept))
                & ~np.isnan(temp[i])
                & ~np.isnan(pres[i])
            )
            if not keep.any():
                continue

            rows.append(
                pd.DataFrame(
                    {
                        "profile_id": profile_id,
                        "wmo": wmos[i],
                        "time": pd.Timestamp(times[i]),
                        "lat": lats[i],
                        "lon": lons[i],
                        "pres": pres[i][keep],
                        "depth": depth_i[keep],
                        "temp": temp[i][keep],
                        "temp_qc": temp_qc[i][keep].astype("int16"),
                        "psal": psal[i][keep],
                        "psal_qc": psal_qc[i][keep].astype("int16"),
                    }
                )
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "profile_id", "wmo", "time", "lat", "lon", "pres", "depth",
                "temp", "temp_qc", "psal", "psal_qc",
            ]
        )

    df = pd.concat(rows, ignore_index=True)
    return df.sort_values(["profile_id", "depth"]).reset_index(drop=True)


def profile_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per profile: position, time, level count, depth span.

    This is what the globe draws as clickable glyphs; the full levels are only
    fetched when a float is actually clicked.
    """
    if df.empty:
        return pd.DataFrame(columns=["profile_id", "wmo", "time", "lat", "lon", "n_levels", "max_depth"])
    g = df.groupby("profile_id", as_index=False).agg(
        wmo=("wmo", "first"),
        time=("time", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
        n_levels=("depth", "size"),
        max_depth=("depth", "max"),
    )
    return g
