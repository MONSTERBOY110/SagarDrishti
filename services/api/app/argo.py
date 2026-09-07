"""Argo profile parsing (TRD M1, feeding M5).

Three things here are load-bearing for the scorecard and all three fail quietly:

1. **QC filtering, PER PARAMETER.** Argo ships every level it measured,
   including ones the delayed-mode QC marked bad. Keeping flags 1 and 2 only is
   the Argo community's own convention (Wong et al. 2020, PRIOR-ART.md §E.4).
   Using flag-4 data does not crash anything, it just makes our RMSE wrong.

   Argo flags EACH PARAMETER separately, and so must we. An earlier version of
   this module built one boolean mask from TEMP_QC and PRES_QC and then indexed
   every parameter with it, so a salinity whose own flag said 3 or 4 was served
   as though it had been accepted. Measured against the ten real Indian Ocean
   daily files in `data/raw/argo`, that was 60,643 levels, carrying salinities
   including 0.00, 65.53 and 134.12 PSU where the ocean runs about 33 to 37.
   None of them happened to fall inside the Bay of Bengal demo box, which is
   precisely what made it dangerous: invisible until the box moved.

2. **Pressure is not depth.** PRES is decibars. Treating 1000 dbar as 1000 m
   is roughly a 1% error, which looks entirely plausible on a chart while
   biasing every depth-binned comparison.

3. **Pressure is not one parameter among several.** A level whose PRES is
   rejected has no depth, so its measurements cannot be placed in the water
   column or compared against a model level. That level is dropped outright,
   while a level that merely lost one of its measurements is kept with that
   measurement masked.
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


def frame_column(param: str) -> str:
    """Argo parameter name -> frame column. Lowercase is the whole rule.

    TEMP -> temp, PSAL -> psal, and a BGC float's CHLA -> chla, DOXY -> doxy,
    with the flag alongside as `<column>_qc`. Keeping the rule mechanical is
    what lets a new parameter be a `sources.yaml` entry rather than a patch
    here, which is the F3/F6 claim applied to this module itself.
    """
    return param.lower()


#: Parameters looked for when the registry entry names none. TEMP and PSAL are
#: the core-Argo pair; the rest are the BGC parameters an Sprof file carries.
#: A parameter absent from a file is simply not read.
KNOWN_PARAMETERS = (
    "TEMP", "PSAL", "DOXY", "CHLA", "NITRATE", "PH_IN_SITU_TOTAL", "BBP700", "CDOM",
)


class UnitsMismatch(ValueError):
    """A file declares a different unit than `sources.yaml` says it does."""


def _same_unit(declared: str, found: str) -> bool:
    """Compare two unit strings the way a reader would, not byte for byte.

    Argo files are not perfectly consistent about spelling: the same quantity
    appears as `degree_Celsius` and `degree_celsius`, and `micromole/kg` with
    or without spaces. Those are the same unit and must not be an error. A
    genuinely different unit still is one.
    """
    def key(u: str) -> str:
        return u.strip().lower().replace(" ", "").replace("_", "").replace("-", "")

    if key(declared) == key(found):
        return True
    # Practical salinity has several spellings in the wild and one meaning. The
    # CF-correct form is the dimensionless "1"; Argo writes "psu".
    salinity = {"psu", "1", "pss78", "practicalsalinityunits"}
    if key(declared) in salinity and key(found) in salinity:
        return True
    # Likewise pH, which is genuinely dimensionless and written both ways.
    dimensionless = {"dimensionless", "1", ""}
    return key(declared) in dimensionless and key(found) in dimensionless


def check_units(ds: xr.Dataset, spec: SourceSpec) -> dict[str, str]:
    """Verify each declared unit against the file, and return what was found.

    Why this is a refusal rather than a warning: the API labels a profile chart
    axis from the registry's `units`, so the DECLARATION is what a reader is
    shown. If a file quietly switched oxygen from micromole/kg to ml/l, every
    oxygen number on screen would be wrong by a factor of about 22 while the
    axis kept insisting otherwise. That is exactly the class of error this
    project refuses to make, and it costs one string comparison per variable to
    make impossible.
    """
    found: dict[str, str] = {}
    problems: list[str] = []
    for variable in spec.variables:
        if variable.name not in ds.variables:
            continue
        file_units = str(ds[variable.name].attrs.get("units", "")).strip()
        found[variable.name] = file_units
        if not variable.units or not file_units:
            # Nothing to compare against. An undeclared unit is a gap in the
            # config, not a contradiction, and cf.py owns that question.
            continue
        if not _same_unit(variable.units, file_units):
            problems.append(
                f"{variable.name}: sources.yaml declares {variable.units!r}, "
                f"the file declares {file_units!r}"
            )
    if problems:
        raise UnitsMismatch(
            f"source {spec.id!r}: " + "; ".join(problems) +
            ". Fix the declaration in data/sources.yaml, or convert the values. "
            "Do not relabel a unit whose numbers have not been converted."
        )
    return found


def parse_profiles(path: str | Path, spec: SourceSpec) -> pd.DataFrame:
    """Parse an Argo multi-profile file into a tidy level-per-row frame.

    Returns profile_id, wmo, time, lat, lon, pres, depth, then a value column
    and a `_qc` column for each parameter the file carries, one row per level
    that has a usable pressure and at least one accepted measurement.

    A measurement whose own QC flag is not accepted is NaN, and its flag is
    still reported: erasing the flag would hide WHY the value is missing, and
    "no sensor" and "sensor rejected" are different facts about a profile.
    """
    accept = list(spec.qc.accept_flags)
    prefer_adjusted = spec.qc.prefer_adjusted

    # Parameters the registry declares, so adding one is a config change. PRES
    # is deliberately not in this list: it is the level's coordinate, not a
    # measurement, and it is handled separately below.
    declared = [v.name for v in spec.variables if v.name != "PRES"]
    wanted = declared or list(KNOWN_PARAMETERS)

    with xr.open_dataset(path, decode_times=False, mask_and_scale=True) as ds:
        # Before any value is read: the file must agree with what the registry
        # says it contains. A unit that silently changed underneath us would
        # mislabel every number downstream.
        check_units(ds, spec)

        wmos = _decode_char_array(ds["PLATFORM_NUMBER"])
        n_prof = len(wmos)

        juld = np.asarray(ds["JULD"].values, dtype="float64")
        # Rounded to the second. JULD is a float count of DAYS, so the
        # nanosecond tail is float noise, not measurement precision: a real
        # surfacing came out as 14:13:48.001520640, which then appears verbatim
        # in a citation and reads as false precision. The profile_id has always
        # been second-resolution, so this also makes the two agree.
        times = JULD_EPOCH + np.round(juld * 86_400_000_000_000.0 / 1e9).astype(
            "timedelta64[s]"
        ).astype("timedelta64[ns]")
        lats = np.asarray(ds["LATITUDE"].values, dtype="float64")
        lons = np.asarray(ds["LONGITUDE"].values, dtype="float64")

        def pick(base: str) -> tuple[np.ndarray, np.ndarray]:
            """Adjusted values when QC allows, else raw: Argo's own guidance."""
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

        # Read each parameter and mask it against ITS OWN flag, here, once, so
        # no later step can index a value array with another parameter's mask.
        params: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for name in wanted:
            if name in ds.variables:
                values, flags = pick(name)
                values = np.where(np.isin(flags, accept), values, np.nan)
            else:
                # Declared by the registry, absent from this file. Emit the
                # column so the table's shape does not depend on which day's
                # file it came from, and flag 9 for "no QC performed".
                values = np.full(pres.shape, np.nan, dtype="float64")
                flags = np.full(pres.shape, 9, dtype="int16")
            params[name] = (values, flags)

        # A level needs a depth before it needs anything else.
        pres_ok = np.isin(pres_qc, accept) & ~np.isnan(pres)

        rows = []
        for i in range(n_prof):
            # profile_id must distinguish two profiles from the SAME float on
            # the same day, so it carries the cycle position, not just the WMO.
            profile_id = f"{wmos[i]}_{pd.Timestamp(times[i]).strftime('%Y%m%dT%H%M%S')}"
            depth_i = pressure_to_depth(pres[i], float(lats[i]))

            # Keep a level if it has a usable pressure AND at least one
            # surviving measurement. A level with a depth and nothing to put at
            # it is an empty row.
            has_value = np.zeros(pres.shape[1], dtype=bool)
            for values, _ in params.values():
                has_value |= ~np.isnan(values[i])
            keep = pres_ok[i] & has_value
            if not keep.any():
                continue

            columns: dict[str, object] = {
                "profile_id": profile_id,
                "wmo": wmos[i],
                "time": pd.Timestamp(times[i]),
                "lat": lats[i],
                "lon": lons[i],
                "pres": pres[i][keep],
                "depth": depth_i[keep],
            }
            for name, (values, flags) in params.items():
                col = frame_column(name)
                columns[col] = values[i][keep]
                columns[f"{col}_qc"] = flags[i][keep].astype("int16")
            rows.append(pd.DataFrame(columns))

    if not rows:
        base = ["profile_id", "wmo", "time", "lat", "lon", "pres", "depth"]
        for name in wanted:
            base += [frame_column(name), f"{frame_column(name)}_qc"]
        return pd.DataFrame(columns=base)

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
