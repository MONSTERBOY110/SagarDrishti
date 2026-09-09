"""Class-4-style model-versus-observation verification (TRD M5, PRD F9).

PRIOR-ART.md names this as one of the four things that make this project
defensible: "no operational viewer shows skill next to the field". Everything
else in the tool draws data. This is the part that says whether the model is
any good, in a number, with the observations behind it counted.

WHAT "CLASS 4" MEANS AND WHY THE LABEL SAYS "STYLE"
---------------------------------------------------
GODAE OceanView Class 4 (Ryan et al. 2015) verifies in OBSERVATION SPACE: the
model is interpolated to each observation's own position, depth and time, and
the residual is computed there. The alternative, interpolating observations
onto the model grid, smooths the observations and flatters the model.

This is Class-4 STYLE rather than Class 4, and the difference is stated rather
than glossed:

  * A real Class-4 comparison verifies a FORECAST against observations that
    were not assimilated into it. Ours compares an ANALYSIS, and INCOIS's VAM
    analysis assimilates the very Argo profiles we are comparing against. So
    the residual measures how well the analysis fits data it has already seen,
    which is a real and useful number (it bounds the analysis error) but is not
    forecast skill and must never be called that.
  * The analysis is a TEN-DAY field. An Argo profile is an instant. Comparing
    them carries a representativeness error that no amount of careful
    interpolation removes, and the size of the time offset is reported with
    every number so a reader can weigh it.

WHAT IT REFUSES
---------------
The same discipline as everywhere else in this project: no invented values.

  * A model column is interpolated from the FOUR surrounding grid cells. If any
    of them is missing at a level, that level is refused rather than filled
    from the ones that remain. Near a coast that is most of them, and a skill
    number computed from a silently reduced stencil would be quietly wrong
    exactly where the shelf matters.
  * No extrapolation in depth. An observation deeper than the model's deepest
    level, or shallower than its shallowest, has no counterpart.
  * Observation QC flags 1 and 2 only (Wong et al. 2020), the same filter the
    profiles themselves are served under.
  * Every refusal is COUNTED and served, so "1,300 matched pairs" is always
    accompanied by how many did not match and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xarray as xr

#: Depth bins, in metres. Chosen to follow ocean structure rather than to be
#: round: the mixed layer, the thermocline where a cyclone's heat lives, and
#: then the slower deep water. A uniform 200 m bin would put the whole
#: thermocline in one bucket and hide the depth where the model is worst.
DEPTH_BINS: tuple[tuple[float, float], ...] = (
    (0.0, 10.0),
    (10.0, 50.0),
    (50.0, 100.0),
    (100.0, 200.0),
    (200.0, 500.0),
    (500.0, 1000.0),
    (1000.0, 2000.0),
)

#: How far an observation may sit from the model step it is compared against.
#: The VAM analysis is a 10-day field, so half a step is the natural limit: any
#: further and a nearer analysis exists and should have been used.
MAX_TIME_OFFSET = pd.Timedelta(days=5)

METHOD = (
    "Class-4-style verification in observation space (Ryan et al. 2015): the "
    "model is interpolated to each observation's own position and depth, "
    "bilinearly in latitude and longitude from the four surrounding grid cells "
    "and linearly in depth between the two bracketing model levels, and the "
    "residual is formed there. A level is refused rather than filled if any of "
    "the four surrounding cells is missing, or if the observation lies outside "
    "the model's depth range. Observations are filtered to QC flags 1 and 2 "
    "(Wong et al. 2020). The model field is an ANALYSIS that assimilates these "
    "same profiles, so the residual bounds the analysis fit and is not forecast "
    "skill"
)


@dataclass
class Match:
    """One model-observation pair, kept so the numbers can be traced back."""

    profile_id: str
    platform: str
    source_id: str
    time: pd.Timestamp
    time_offset_hours: float
    lat: float
    lon: float
    depth: float
    observed: float
    modelled: float

    @property
    def residual(self) -> float:
        """Model minus observation. A positive bias means the model is warm."""
        return self.modelled - self.observed


@dataclass
class Refusals:
    """Why pairs did not form. Served, never swallowed."""

    no_model_time: int = 0
    outside_grid: int = 0
    missing_stencil: int = 0
    outside_depth_range: int = 0
    #: The instrument reported no value at this level. NOT a quality
    #: judgement, and kept apart from one for that reason: on this cube all
    #: 3,506 of these are BGC floats reporting oxygen at levels where their
    #: CTD did not report, and zero are QC rejections. Counting them as
    #: "rejected_qc" would tell a reader that three and a half thousand
    #: observations failed quality control, which is a statement about the
    #: data nobody could then trust.
    no_observation: int = 0
    rejected_qc: int = 0
    #: A value with no quality flag at all. Refused, because accept_flags is a
    #: whitelist and an unflagged value has not passed anything. Counted apart
    #: from rejected_qc for the same reason no_observation is: "failed QC" and
    #: "was never checked" are different statements about a dataset.
    no_qc_flag: int = 0
    notes: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return (
            self.no_model_time
            + self.outside_grid
            + self.missing_stencil
            + self.outside_depth_range
            + self.no_observation
            + self.rejected_qc
            + self.no_qc_flag
        )

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "no_model_time": self.no_model_time,
            "outside_grid": self.outside_grid,
            "missing_stencil": self.missing_stencil,
            "outside_depth_range": self.outside_depth_range,
            "no_observation": self.no_observation,
            "rejected_qc": self.rejected_qc,
            "no_qc_flag": self.no_qc_flag,
            **self.notes,
        }


def _bracket(axis: np.ndarray, value: float) -> tuple[int, int, float] | None:
    """Indices either side of `value` and the fractional position between them.

    None when the value lies outside the axis. Deliberately NOT clamped: a
    clamp would silently compare an observation against the edge of the domain
    and call it a match.
    """
    n = axis.size
    if n == 0 or not np.isfinite(value):
        return None
    if n == 1:
        return (0, 0, 0.0) if np.isclose(axis[0], value) else None
    if value < axis[0] or value > axis[-1]:
        return None
    upper = int(np.searchsorted(axis, value, side="left"))
    if upper == 0:
        return 0, 0, 0.0
    lower = upper - 1
    span = axis[upper] - axis[lower]
    frac = 0.0 if span == 0 else float((value - axis[lower]) / span)
    return lower, upper, frac


def model_column_at(
    values: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    lat: float,
    lon: float,
) -> np.ndarray | None:
    """The model's water column at an arbitrary position, bilinearly.

    `values` is (depth, lat, lon) for one timestep. Returns a (depth,) column,
    or None when the position is outside the grid.

    ALL FOUR surrounding cells must be finite at a level for that level to
    produce a value. Filling from whichever cells remain would be an invented
    number, and it would happen most often next to the coast, which is exactly
    where a forecaster is reading.
    """
    j = _bracket(lats, lat)
    i = _bracket(lons, lon)
    if j is None or i is None:
        return None
    j0, j1, fy = j
    i0, i1, fx = i

    corners = (
        (values[:, j0, i0], (1 - fy) * (1 - fx)),
        (values[:, j0, i1], (1 - fy) * fx),
        (values[:, j1, i0], fy * (1 - fx)),
        (values[:, j1, i1], fy * fx),
    )

    column = np.zeros(values.shape[0], dtype="float64")
    usable = np.ones(values.shape[0], dtype=bool)
    for corner, weight in corners:
        # A corner with zero weight is not part of the stencil: when the
        # position sits exactly on a grid line, only two cells are involved and
        # requiring the other two to be finite would refuse a valid match.
        if weight == 0.0:
            continue
        usable &= np.isfinite(corner)
        column += np.where(np.isfinite(corner), corner, 0.0) * weight

    return np.where(usable, column, np.nan)


def _interp_depth(column: np.ndarray, depths: np.ndarray, target: float) -> float:
    """The model value at an arbitrary depth, linearly between two levels.

    NaN when either bracketing level is missing, or when the target lies
    outside the model's depth range. No extrapolation: a value below the
    deepest model level is not a model value.
    """
    b = _bracket(depths, target)
    if b is None:
        return float("nan")
    k0, k1, fz = b
    lo, hi = column[k0], column[k1]
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return float("nan")
    return float(lo + fz * (hi - lo))


def colocate(
    ds: xr.Dataset,
    profiles: pd.DataFrame,
    *,
    variable: str = "TEMP",
    observed_column: str = "temp",
    qc_column: str = "temp_qc",
    accept_flags: tuple[int, ...] = (1, 2),
    max_time_offset: pd.Timedelta = MAX_TIME_OFFSET,
) -> tuple[list[Match], Refusals]:
    """Pair every accepted observation level with the model at its own position."""
    refusals = Refusals()
    matches: list[Match] = []

    if variable not in ds.data_vars or profiles.empty:
        return matches, refusals
    if observed_column not in profiles.columns:
        return matches, refusals

    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")
    depths = np.asarray(ds["depth"].values, dtype="float64")
    model_times = pd.to_datetime(ds["time"].values)

    # One column per (profile, timestep) rather than per level: a profile has
    # hundreds of levels at ONE position, so interpolating the column once and
    # then walking down it turns a per-level bilinear into a per-profile one.
    field_by_time: dict[int, np.ndarray] = {}

    for profile_id, rows in profiles.groupby("profile_id", sort=False):
        first = rows.iloc[0]
        lat = float(first["lat"])
        lon = float(first["lon"])
        obs_time = pd.Timestamp(first["time"])

        gaps = np.abs(model_times - obs_time)
        step = int(np.argmin(gaps))
        offset = pd.Timedelta(gaps[step])
        if offset > max_time_offset:
            refusals.no_model_time += len(rows)
            continue

        if step not in field_by_time:
            field_by_time[step] = np.asarray(
                ds[variable].isel(time=step).transpose("depth", "lat", "lon").values,
                dtype="float64",
            )
        column = model_column_at(field_by_time[step], lats, lons, lat, lon)
        if column is None:
            refusals.outside_grid += len(rows)
            continue

        qc = rows[qc_column].to_numpy() if qc_column in rows.columns else None
        for n, row in enumerate(rows.itertuples()):
            observed = float(getattr(row, observed_column))
            if not np.isfinite(observed):
                # No measurement at this level, which is not a quality
                # judgement. Checked FIRST, because a level with no value
                # usually carries flag 9 ("no QC performed") and would
                # otherwise be counted as a rejection.
                refusals.no_observation += 1
                continue
            if qc is not None:
                flag = qc[n]
                if not np.isfinite(flag):
                    refusals.no_qc_flag += 1
                    continue
                if int(flag) not in accept_flags:
                    refusals.rejected_qc += 1
                    continue

            depth = float(row.depth)
            if depth < depths[0] or depth > depths[-1]:
                refusals.outside_depth_range += 1
                continue

            modelled = _interp_depth(column, depths, depth)
            if not np.isfinite(modelled):
                refusals.missing_stencil += 1
                continue

            matches.append(
                Match(
                    profile_id=str(profile_id),
                    platform=str(first.get("wmo", "")),
                    source_id=str(first.get("source_id", "")),
                    time=obs_time,
                    time_offset_hours=round(offset.total_seconds() / 3600.0, 2),
                    lat=lat,
                    lon=lon,
                    depth=depth,
                    observed=observed,
                    modelled=modelled,
                )
            )

    return matches, refusals


def _stats(residuals: np.ndarray) -> dict:
    """Bias, RMSE and spread for one bin.

    Bias and RMSE are BOTH reported because they answer different questions and
    one without the other misleads. A model that is 2 degrees warm everywhere
    has a bias of +2 and an RMSE of 2. A model that is 2 degrees warm in half
    the ocean and 2 degrees cold in the other half has a bias of ZERO and an
    RMSE of 2. Reporting bias alone would call the second model perfect.
    """
    n = residuals.size
    if n == 0:
        return {"n": 0, "bias": None, "rmse": None, "mae": None, "std": None}
    return {
        "n": int(n),
        "bias": round(float(np.mean(residuals)), 4),
        "rmse": round(float(np.sqrt(np.mean(residuals**2))), 4),
        "mae": round(float(np.mean(np.abs(residuals))), 4),
        # Standard deviation of the residual, which is the part of the error
        # that a constant correction could not remove.
        "std": round(float(np.std(residuals)), 4),
    }


def score(
    matches: list[Match],
    refusals: Refusals,
    *,
    variable: str,
    units: str,
    bins: tuple[tuple[float, float], ...] = DEPTH_BINS,
) -> dict:
    """Per-depth-bin bias and RMSE, with everything needed to weigh them."""
    residuals = np.array([m.residual for m in matches], dtype="float64")
    depths = np.array([m.depth for m in matches], dtype="float64")
    offsets = np.array([m.time_offset_hours for m in matches], dtype="float64")

    by_depth = []
    for lo, hi in bins:
        # Half-open so a level exactly on a boundary lands in exactly one bin.
        inside = (depths >= lo) & (depths < hi)
        entry = {"depth_min": lo, "depth_max": hi}
        entry.update(_stats(residuals[inside]))
        by_depth.append(entry)

    platforms = sorted({m.platform for m in matches if m.platform})
    profiles = sorted({m.profile_id for m in matches})

    overall = _stats(residuals)
    return {
        "variable": variable,
        "units": units,
        "method": METHOD,
        "label": "Class-4-style verification",
        "overall": overall,
        "by_depth": by_depth,
        "n_profiles": len(profiles),
        "n_platforms": len(platforms),
        "platforms": platforms,
        # The time mismatch is part of the answer, not a footnote: the analysis
        # is a 10-day field and an Argo profile is an instant.
        "time_offset_hours": {
            "median": round(float(np.median(offsets)), 2) if offsets.size else None,
            "max": round(float(np.max(offsets)), 2) if offsets.size else None,
        },
        "refused": refusals.as_dict(),
        # The one caveat that must travel with every number this produces.
        "caveat": (
            "The INCOIS VAM analysis assimilates these same Argo profiles, so "
            "this residual measures how closely the analysis fits data it has "
            "already seen. It bounds the analysis error and is NOT forecast "
            "skill. The analysis is also a 10-day field compared against "
            "instantaneous profiles, which carries a representativeness error "
            "no interpolation removes."
        ),
    }
