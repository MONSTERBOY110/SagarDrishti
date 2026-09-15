"""A source reader for gliders and CTD casts (PS requirements F2 and F6).

WHY THIS EXISTS
---------------
The problem statement names four instrument classes to co-display: "Argo float,
Glider profile, CTD and BGC data". Argo core, Argo BGC and a moored buoy were in
the cube. Gliders and CTDs were not, and an earlier search closed them as
unobtainable after GTSPP returned one moored buoy inside the demo box and the
Copernicus near-real-time feed carried exactly one Indian Ocean glider, in the
Mozambique Channel, 4,000 km away.

That search was looking in the wrong place. The problem statement's own Dataset
Link field names the archive, and the archive has both: the Copernicus in-situ
Thematic Assembly Centre publishes a HISTORY part alongside the rolling
thirty-day LATEST part that had been searched. The history index carries 89,115
files, of which 5 gliders and 24 CTD collections intersect the Bay of Bengal
box.

WHAT IT READS, AND THE ONE THING THAT CANNOT BE FIXED
-----------------------------------------------------
Two real deployments:

  * ru29, a Rutgers Slocum glider (WMO 2801900), 222 dives inside the box
    between 12 August and 24 October 2018, off southern Sri Lanka, to 962 dbar.
  * SHINYO MARU (JFCL), 15 shipboard CTD casts in the Bay of Bengal in 1990 and
    1991, to 1100 dbar.

Both predate the model field by years, and nothing in this reader hides that.
The scorecard's existing time test refuses a pairing beyond five days and counts
it under `no_model_time`, so these casts are DISPLAYED against the model and
never SCORED against it, and the refusal is served rather than inferred. That is
the honest position: the basin has no contemporaneous glider to offer, the PS
asks for gliders to be co-displayed rather than verified, and a residual formed
across eight years would be a number about the ocean's variability wearing the
costume of model error.

FIVE DEFECTS, EACH OBSERVED IN THE REAL FILES
---------------------------------------------
1. PRESSURE IS NOT DEPTH. The files measure pressure in decibars. Depth depends
   on latitude because gravity does, and the conversion is TEOS-10's
   `gsw.z_from_p`. At 1000 dbar at 5 N the difference from assuming one metre
   per decibar is 7.9 m, which is larger than the spacing between the model's
   deep levels: an observation placed 7.9 m too deep is interpolated against the
   wrong part of the column and the difference is then reported as model error.

2. PRESSURE THAT REVERSES. 475 of ru29's 944 half-dives carry non-monotonic
   pressure. Most of that is the ascending legs, whose pressure decreases by
   definition and which the direction rule below removes; 3 DESCENDING dives
   still reverse, because a glider samples continuously and can wobble. Both
   are handled by sorting, and the counter reports the 3 rather than the 475,
   because the 475 would be counting the ascending legs twice: once as dropped
   and once as disordered. Every consumer downstream reads a cast as a column
   from the surface down, and a bracketing search over an unsorted axis returns
   a confident wrong answer rather than an error.

3. GAPS IN PRESSURE. 943 of 944 half-dives contain at least one NaN pressure,
   and a measurement whose depth is unknown is dropped rather than placed at
   zero. The counter reports only gaps INSIDE a dive's sampled span, and on
   these two files that number is 0: the file is a rectangle padded out to its
   longest dive, so all 20,667 NaNs are padding and none is a hole in a
   profile. The distinction is the whole point of counting. A counter that
   summed raw NaNs would have reported 20,667 missing levels and been believed.

4. A GOOD MEASUREMENT AT A BAD DEPTH. PRES_QC 4 occurs alongside TEMP_QC 1.
   Filtering on the temperature flag alone accepts a reading the instrument
   itself could not locate. The pressure flag is therefore folded into every
   parameter's flag, because a temperature at an unknown depth is not an
   observation of anything.

5. FLOATING-POINT QUALITY FLAGS. The flags arrive as floats and a missing flag
   is NaN. Casting NaN to an integer is undefined; in practice it produces a
   large negative number that no accepted-flag test matches by accident rather
   than by decision. Missing is mapped explicitly to 9.

ONE PROFILE PER DIVE
--------------------
A glider profiles on the way down and again on the way up, and both legs are in
the file, tagged 'D' and 'A'. They are minutes apart in nearly the same water.
Keeping both would double the apparent number of independent observations, which
is the same overcount as calling 25 casts 25 instruments. The descending leg is
kept, the ascending leg is counted and disclosed.
"""

from __future__ import annotations

from pathlib import Path

import gsw
import numpy as np
import xarray as xr

#: The flag this reader writes when the source offers none. 9 is "missing" on
#: the Argo scale the rest of the project filters against (Wong et al. 2020).
QC_MISSING = 9

#: The flag written over a level whose PRESSURE was rejected. The measurement
#: may be perfect; it is not locatable, so it cannot be used.
QC_BAD = 4

#: Which leg of a dive becomes the profile. See the module docstring.
DIRECTION_KEPT = "D"

METHOD = (
    "Copernicus in-situ TAC profile file read by plugins/insitu_tac.py. "
    "Pressure is converted to depth with TEOS-10 gsw.z_from_p(p, lat), which "
    "accounts for the latitude dependence of gravity, rather than assuming one "
    "metre per decibar. Levels with no pressure, or with a pressure quality "
    "flag outside 1 and 2, are refused rather than placed. Each dive is sorted "
    "into a downward-reading column and duplicate depths are dropped. Only the "
    "descending leg of a dive is kept, because the ascending leg samples "
    "nearly the same water minutes later. Quality flags are carried through on "
    "the Argo scale (Wong et al. 2020) with a missing flag mapped to 9."
)

#: What the file's own `source` attribute calls each instrument class. Read
#: from the file rather than guessed from the filename, because the same
#: directory carries both and a filename is not evidence.
_KIND_BY_SOURCE = {
    "sub-surface gliders": "glider",
    "research vessel": "ctd",
    "ctd": "ctd",
}

_PARAMETERS = ("TEMP", "PSAL")


def _kind_from(ds: xr.Dataset) -> str:
    source = str(ds.attrs.get("source", "") or "").strip().lower()
    if source in _KIND_BY_SOURCE:
        return _KIND_BY_SOURCE[source]
    # An unrecognised source is reported as such rather than guessed into one
    # of the two classes, because the glyph on the globe is a claim about what
    # kind of instrument took the measurement.
    return "unknown"


def _flags(ds: xr.Dataset, name: str, shape) -> np.ndarray:
    """A quality flag array on the Argo scale, with missing meaning missing."""
    if name not in ds:
        return np.full(shape, QC_MISSING, dtype="float64")
    raw = np.asarray(ds[name].values, dtype="float64")
    out = np.where(np.isfinite(raw), raw, float(QC_MISSING))
    return out.reshape(shape)


def read_casts(path) -> xr.Dataset:
    """One in-situ TAC profile file -> a ragged (profile, level) Dataset.

    Depth is a DATA VARIABLE rather than a coordinate, because every cast has
    its own levels. A mooring can pivot onto shared sensor depths; a glider
    samples wherever it happened to be, so a shared axis would either drop
    levels or invent them.
    """
    with xr.open_dataset(path, decode_timedelta=False) as raw:
        ds = raw.load()

    times = np.asarray(ds["TIME"].values, dtype="datetime64[ns]").ravel()
    lats = np.asarray(ds["LATITUDE"].values, dtype="float64").ravel()
    lons = np.asarray(ds["LONGITUDE"].values, dtype="float64").ravel()
    pres = np.asarray(ds["PRES"].values, dtype="float64")
    n_prof, n_lev = pres.shape

    values = {p: np.asarray(ds[p].values, dtype="float64") if p in ds
              else np.full((n_prof, n_lev), np.nan) for p in _PARAMETERS}
    flags = {p: _flags(ds, f"{p}_QC", (n_prof, n_lev)) for p in _PARAMETERS}
    pres_flags = _flags(ds, "PRES_QC", (n_prof, n_lev))

    # --- one profile per dive ------------------------------------------------
    if "DIRECTION" in ds:
        direction = np.asarray(ds["DIRECTION"].values).ravel()
        direction = np.array([
            d.decode("ascii", "replace") if isinstance(d, bytes) else str(d)
            for d in direction
        ])
        keep_profile = direction == DIRECTION_KEPT
        # A file that tags nothing 'D' is not one where every dive is ascending;
        # it is one that does not use the convention, so the rule is not applied.
        if not keep_profile.any():
            keep_profile = np.ones(n_prof, dtype=bool)
            n_dropped = 0
        else:
            n_dropped = int((~keep_profile).sum())
    else:
        keep_profile = np.ones(n_prof, dtype=bool)
        n_dropped = 0

    idx = np.flatnonzero(keep_profile)
    times, lats, lons = times[idx], lats[idx], lons[idx]
    pres, pres_flags = pres[idx], pres_flags[idx]
    values = {p: v[idx] for p, v in values.items()}
    flags = {p: f[idx] for p, f in flags.items()}
    n_prof = idx.size
    if n_prof == 0:
        raise ValueError(f"{Path(path).name} carried no usable profiles")

    # --- pressure -> depth, per level, at the cast's own latitude ------------
    # z_from_p returns HEIGHT, negative downwards. Depth is its negation, which
    # is what `positive: down` means and what every consumer here expects.
    lat_grid = np.repeat(lats[:, None], pres.shape[1], axis=1)
    with np.errstate(invalid="ignore"):
        depth = -gsw.z_from_p(pres, lat_grid)

    # A pressure flagged bad leaves the measurement unplaceable. Count it
    # before it is masked, so the number served is the number observed.
    bad_pressure = np.isfinite(pres) & ~np.isin(pres_flags, (1.0, 2.0))
    n_bad_pressure = int(bad_pressure.sum())
    for p in _PARAMETERS:
        flags[p] = np.where(bad_pressure, float(QC_BAD), flags[p])

    # A gap INSIDE the sampled span, not the NaN padding that squares the file
    # off to the longest dive. Counting the padding would report a glider with
    # 121 real gaps as having 20,667 of them.
    n_no_pressure = 0
    for row in pres:
        have = np.flatnonzero(np.isfinite(row))
        if have.size:
            n_no_pressure += int((have[-1] - have[0] + 1) - have.size)
    depth = np.where(np.isfinite(pres), depth, np.nan)

    # --- sort each dive into a downward-reading column ----------------------
    n_resorted = 0
    n_duplicate = 0
    out_depth = np.full((n_prof, n_lev), np.nan)
    out_pres = np.full((n_prof, n_lev), np.nan)
    out_values = {p: np.full((n_prof, n_lev), np.nan) for p in _PARAMETERS}
    out_flags = {p: np.full((n_prof, n_lev), float(QC_MISSING)) for p in _PARAMETERS}

    for i in range(n_prof):
        have = np.isfinite(depth[i])
        d = depth[i][have]
        if d.size == 0:
            continue
        order = np.argsort(d, kind="stable")
        if not np.all(np.diff(d) > 0):
            n_resorted += 1
        d_sorted = d[order]
        # Keep the FIRST of any repeated depth. Averaging two readings at one
        # depth would produce a number neither instrument reported.
        unique = np.ones(d_sorted.size, dtype=bool)
        unique[1:] = np.diff(d_sorted) > 0
        n_duplicate += int((~unique).sum())
        take = np.flatnonzero(have)[order][unique]
        k = take.size
        out_depth[i, :k] = depth[i][take]
        out_pres[i, :k] = pres[i][take]
        for p in _PARAMETERS:
            out_values[p][i, :k] = values[p][i][take]
            out_flags[p][i, :k] = flags[p][i][take]

    data = {
        "depth": (("profile", "level"), out_depth, {
            "units": "m", "positive": "down", "standard_name": "depth",
            "comment": "Derived from PRES with TEOS-10 gsw.z_from_p at each "
                       "cast's own latitude.",
        }),
        "pres": (("profile", "level"), out_pres, {
            "units": "dbar", "standard_name": "sea_water_pressure",
            "comment": "As measured. Kept so the depth can be re-derived.",
        }),
    }
    units = {"TEMP": "degC", "PSAL": "1e-3"}
    long_names = {
        "TEMP": "Sea water temperature",
        "PSAL": "Practical salinity",
    }
    for p in _PARAMETERS:
        data[p] = (("profile", "level"), out_values[p], {
            "units": units[p], "long_name": long_names[p],
        })
        data[f"{p}_QC"] = (("profile", "level"), out_flags[p], {
            "units": "1",
            "long_name": "Quality flag on the Argo scale",
            "flag_values": "1 2 3 4 9",
            "flag_meanings": "good probably_good dubious bad missing",
            "comment": "A level whose PRESSURE was rejected is flagged 4 here "
                       "regardless of the source's own flag for this "
                       "parameter: a measurement at an unknown depth cannot be "
                       "used.",
        })

    platform = str(ds.attrs.get("platform_code", "") or "").strip()
    wmo = str(ds.attrs.get("wmo_platform_code", "") or "").strip() or platform

    return xr.Dataset(
        data,
        coords={
            "time": ("profile", times),
            "lat": ("profile", lats),
            "lon": ("profile", lons),
        },
        attrs={
            "layout": "casts",
            "station": platform,
            "platform_name": str(ds.attrs.get("platform_name", "") or platform),
            "wmo_platform_code": wmo,
            "platform_kind": _kind_from(ds),
            "institution": str(ds.attrs.get("institution", "") or ""),
            "reader_method": METHOD,
            "direction_kept": DIRECTION_KEPT,
            "n_profiles_ascending_dropped": n_dropped,
            "n_profiles_resorted": n_resorted,
            "n_levels_duplicate_depth": n_duplicate,
            "n_levels_no_pressure": n_no_pressure,
            "n_levels_refused_bad_pressure": n_bad_pressure,
        },
    )


def open_insitu_tac(spec) -> xr.Dataset:
    """Every file this source points at, concatenated along `profile`."""
    root = Path(spec.url)
    pattern = getattr(spec, "path_template", None) or "*.nc"
    files = sorted(root.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"no in-situ TAC files matching {pattern!r} under {root}. "
            f"Run tools/fetch_sample.py to download them."
        )

    parts = [read_casts(f) for f in files]
    if len(parts) == 1:
        return parts[0]

    merged = xr.concat(parts, dim="profile", combine_attrs="drop_conflicts")
    # Sum the disclosure counters rather than letting concat drop them: the
    # number served has to cover every file that was read.
    for key in ("n_profiles_ascending_dropped", "n_profiles_resorted",
                "n_levels_duplicate_depth", "n_levels_no_pressure",
                "n_levels_refused_bad_pressure"):
        merged.attrs[key] = int(sum(int(p.attrs.get(key, 0)) for p in parts))
    merged.attrs["layout"] = "casts"
    merged.attrs["reader_method"] = METHOD
    return merged


def register(registry) -> None:
    registry.register_source_reader(
        kind="insitu_tac",
        open=open_insitu_tac,
        doc=(
            "Gliders and CTD casts from the Copernicus in-situ Thematic "
            "Assembly Centre, the archive the problem statement's own Dataset "
            "Link field names. Converts pressure to depth through TEOS-10 at "
            "each cast's own latitude, sorts each dive into a downward-reading "
            "column, keeps one leg per dive, and refuses a level whose "
            "pressure was flagged even when its measurement was not."
        ),
    )
