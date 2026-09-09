"""A source reader for moored buoys, on real RAMA data (PS requirement F6).

The PS asks for "future integration of additional sensors (CTDs, moorings,
HF-radar, ADCP)". `app/plugins.py` has offered a source-reader extension point
from the start, with a checked output contract and its own error codes, but
nothing was registered against it: the half of the interface that reads a NEW
KIND of source was demonstrated by tests and by nothing else. This is the
running example.

WHY RAMA AND NOT A SYNTHETIC MOORING
------------------------------------
RAMA is the Research moored Array for African-Asian-Australian Monsoon
Analysis, the Indian Ocean arm of the global tropical moored buoy array, and
INCOIS is one of its partners. Three of its moorings sit inside our Bay of
Bengal demo box, on the 90 E line at 8 N, 12 N and 15 N, and they report
DAILY and CURRENTLY: mooring 15n90e (WMO 23009) returned 17 depth levels from
1 m to 500 m for 2026-07-30, which is the same day as the model timestep the
scene opens on.

So this is a real instrument class the PS names, contemporaneous with the model
field, at a fixed position, measuring a temperature profile. A synthetic
mooring would have demonstrated the plumbing and nothing else.

THREE THINGS THIS READER HAS TO GET RIGHT, AND WHY EACH IS A REAL DECISION
--------------------------------------------------------------------------
1. A DIFFERENT QC VOCABULARY. TAO/RAMA does not use Argo's flags. Its
   QT_5020 is 0 = no sensor, 1 = highest quality, 2 = default quality,
   3 = adjusted, 4 = lower quality, 5 = sensor failed. Argo's 2 means
   "probably good" and its 4 means "bad", so the two scales AGREE on 1 and 2
   by coincidence and DISAGREE on everything above. Relying on that
   coincidence would mean a RAMA flag 4 ("lower quality") being read against
   Argo's rules and a flag 5 (a FAILED SENSOR) sailing through a filter
   written for a scale where 5 does not appear. The mapping below is explicit
   for exactly that reason.

2. A FOURTH FILL CONVENTION. This source uses 1.0E35. The cube already handles
   -9999.0 (INCOIS VAM), -1.0E34 (INCOIS value-added and ocean colour) and
   99999.0 (Argo BGC). None of them is a rounding of another, and a sentinel
   read as a measurement is a 1e35 degree ocean.

3. A FLAT TABLE, NOT A GRID. ERDDAP tabledap serves this as one row per
   (time, depth) pair, 527 rows for one mooring over a month, with the
   position repeated on every row. The reader's job is to pivot that into the
   (time, depth) array the rest of the system expects, and to do it without
   assuming every timestep sampled the same depths, because a mooring loses
   and regains sensors mid-deployment.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

#: The sentinel RAMA writes for "no value". Distinct from every other fill
#: convention in this project, which is the point of naming it here.
FILL = 1.0e35

#: TAO/RAMA quality flag -> the Argo-style scale the rest of this project
#: filters on (1 good, 2 probably good, 3 dubious, 4 bad, 9 missing).
#:
#: Written out rather than assumed. The two scales happen to agree on 1 and 2
#: and disagree above that: RAMA 5 means the SENSOR FAILED, and there is no
#: flag 5 in the Argo scale at all, so an unmapped 5 would be compared against
#: `accept_flags` and silently kept or dropped depending on the reader's mood.
#: Mapping it to 4 ("bad") states what it means in the vocabulary the filter
#: actually speaks.
QC_MAP: dict[int, int] = {
    0: 9,   # no sensor at this depth        -> missing
    1: 1,   # highest quality                -> good
    2: 2,   # default quality                -> probably good
    3: 3,   # adjusted                       -> dubious
    4: 4,   # lower quality                  -> bad
    5: 4,   # SENSOR FAILED                  -> bad
}
#: Anything the array grows later. Mapped to "missing" rather than to a guess:
#: an unknown flag is not evidence of quality in either direction.
QC_UNKNOWN = 9

METHOD = (
    "ERDDAP tabledap flat table (one row per time and depth) pivoted onto a "
    "(time, depth) grid; the 1.0E35 sentinel is masked to NaN before anything "
    "reads it; TAO/RAMA quality flags are mapped explicitly onto the "
    "Argo-style scale the rest of the pipeline filters on, with a failed "
    "sensor (RAMA 5) mapped to bad rather than left to be compared against a "
    "scale it does not belong to"
)


def _column(ds: xr.Dataset, name: str) -> np.ndarray:
    if name not in ds.variables:
        raise ValueError(
            f"the mooring file has no {name!r} column; it carries "
            f"{sorted(map(str, ds.variables))}. This reader expects an ERDDAP "
            f"tabledap export of pmelTaoDyT."
        )
    return np.asarray(ds[name].values)


def read_mooring(path) -> xr.Dataset:
    """One downloaded RAMA mooring file -> a (time, depth) Dataset.

    Returns temperature and its mapped quality flag, with the mooring's fixed
    position as scalar coordinates and its WMO id in the attributes, because a
    number this project serves has to be citable to an instrument.
    """
    with xr.open_dataset(path) as raw:
        ds = raw.load()

    times = np.asarray(ds["time"].values, dtype="datetime64[ns]")
    depths = np.asarray(_column(ds, "depth"), dtype="float64")
    values = np.asarray(_column(ds, "T_20"), dtype="float64")
    flags_raw = np.asarray(_column(ds, "QT_5020"), dtype="float64")

    # Mask the sentinel BEFORE anything reads the numbers. np.isclose rather
    # than == because 1.0E35 does not round-trip exactly through float32, which
    # is how the file stores it.
    values = np.where(np.isclose(values, FILL, rtol=1e-6, atol=0.0), np.nan, values)
    depths = np.where(np.isclose(depths, FILL, rtol=1e-6, atol=0.0), np.nan, depths)

    # Map the flags. A NaN flag (the sentinel, or an absent column) is
    # "missing", never "good".
    flags = np.full(flags_raw.shape, QC_UNKNOWN, dtype="int16")
    finite = np.isfinite(flags_raw)
    for source_flag, mapped in QC_MAP.items():
        flags[finite & (flags_raw == source_flag)] = mapped
    unmapped = finite & ~np.isin(flags_raw, list(QC_MAP))
    flags[unmapped] = QC_UNKNOWN

    keep = np.isfinite(depths)
    times, depths, values, flags = times[keep], depths[keep], values[keep], flags[keep]
    if times.size == 0:
        raise ValueError("the mooring file carried no usable rows")

    # PIVOT. The axes are the SORTED UNIQUE values actually present, not a
    # range: a mooring loses and regains sensors mid-deployment, so the set of
    # depths is not the same on every day, and assuming a rectangular sampling
    # would either drop levels or invent them.
    time_axis = np.unique(times)
    depth_axis = np.unique(depths)
    ti = np.searchsorted(time_axis, times)
    di = np.searchsorted(depth_axis, depths)

    grid = np.full((time_axis.size, depth_axis.size), np.nan, dtype="float64")
    flag_grid = np.full((time_axis.size, depth_axis.size), QC_UNKNOWN, dtype="int16")
    grid[ti, di] = values
    flag_grid[ti, di] = flags

    lat = _finite_scalar(_column(ds, "latitude"), "latitude")
    lon = _finite_scalar(_column(ds, "longitude"), "longitude")
    station = _first_string(ds, "station")
    wmo = _first_string(ds, "wmo_platform_code")

    out = xr.Dataset(
        {
            "TEMP": (
                ("time", "depth"),
                grid,
                {
                    "units": "degC",
                    "standard_name": "sea_water_temperature",
                    "long_name": "Sea water temperature",
                },
            ),
            "TEMP_QC": (
                ("time", "depth"),
                flag_grid.astype("float64"),
                {
                    "units": "1",
                    "long_name": "Quality flag, mapped to the Argo scale",
                    "flag_values": "1 2 3 4 9",
                    "flag_meanings": "good probably_good dubious bad missing",
                    "comment": (
                        "Mapped from TAO/RAMA QT_5020 by plugins/rama_mooring.py. "
                        "RAMA 5 (sensor failed) maps to 4 (bad)."
                    ),
                },
            ),
        },
        coords={
            "time": ("time", time_axis),
            "depth": ("depth", depth_axis, {
                "units": "m", "positive": "down", "standard_name": "depth", "axis": "Z",
            }),
            "lat": lat,
            "lon": lon,
        },
        attrs={
            "station": station,
            "wmo_platform_code": wmo,
            "platform_kind": "mooring",
            "reader_method": METHOD,
        },
    )
    return out


def _finite_scalar(values: np.ndarray, what: str) -> float:
    """A mooring has ONE position, repeated on every row of the table."""
    arr = np.asarray(values, dtype="float64")
    arr = arr[np.isfinite(arr) & ~np.isclose(arr, FILL, rtol=1e-6, atol=0.0)]
    if arr.size == 0:
        raise ValueError(f"the mooring file has no usable {what}")
    unique = np.unique(np.round(arr, 4))
    if unique.size != 1:
        # Not fatal in principle, but a moored buoy that reports two positions
        # is either two moorings in one file or a drifting one, and both mean
        # the fixed-position assumption below is wrong.
        raise ValueError(
            f"the mooring file reports {unique.size} distinct {what} values "
            f"({unique[:4]}); this reader assumes one fixed position per file"
        )
    return float(unique[0])


def _first_string(ds: xr.Dataset, name: str) -> str:
    """The first usable value of an identifier column, as text.

    An identifier that arrives as a float is rendered as an INTEGER. ERDDAP
    types `wmo_platform_code` as a number, so `str()` on it gives "23009.0",
    and that string would go straight into the citation printed under the
    chart. A WMO id with a decimal point in it is not a WMO id.
    """
    if name not in ds.variables:
        return ""
    values = np.asarray(ds[name].values).ravel()
    for v in values:
        if isinstance(v, bytes):
            text = v.decode("ascii", "ignore").strip()
        elif isinstance(v, (np.floating, float)):
            if not np.isfinite(v):
                continue
            text = str(int(v)) if float(v).is_integer() else str(v)
        elif isinstance(v, (np.integer, int)):
            text = str(int(v))
        else:
            text = str(v).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def open_mooring(spec) -> xr.Dataset:
    """The registered entry point: open every file this source has on disk.

    One Dataset per call is the contract, so several moorings are concatenated
    along a `profile` axis. That is a canonical dimension the framework already
    knows (app/plugins.py `_CANONICAL_DIMS`), and it is the honest shape: three
    moorings at three positions are three profiles, not one grid.
    """
    from pathlib import Path

    root = Path(spec.url)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / spec.url
    files = sorted(root.glob(spec.path_template or "*.nc"))
    if not files:
        raise ValueError(
            f"no mooring files under {root} matching "
            f"{spec.path_template or '*.nc'}. Run tools/fetch_sample.py."
        )

    parts = [read_mooring(f) for f in files]
    if len(parts) == 1:
        return parts[0].expand_dims("profile")
    return xr.concat([p.expand_dims("profile") for p in parts], dim="profile")


def register(registry) -> None:
    registry.register_source_reader(
        kind="mooring",
        open=open_mooring,
        doc=(
            "Moored buoys from the tropical moored array (RAMA in the Indian "
            "Ocean), as ERDDAP tabledap NetCDF. Pivots the flat table onto a "
            "(time, depth) grid, masks the 1.0E35 sentinel, and maps TAO/RAMA "
            "quality flags onto the Argo-style scale this project filters on."
        ),
    )
