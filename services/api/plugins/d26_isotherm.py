"""D26: depth of the 26 degC isotherm, as a derived-product plugin.

Why this and not a toy: D26 is the operational tropical-cyclone
intensification variable. The 26 degC isotherm is the conventional base of the
layer that can fuel a cyclone, so its depth (with the heat content above it) is
what a forecaster reads when deciding whether a system over the Bay of Bengal
will deepen. INCOIS publishes it. It is computed, never measured, which makes
it the honest demonstration of the derived-product extension point: the field
is new, the store on disk is not.

Two decisions are load-bearing, and both are about refusing to answer:

  * No extrapolation. Where the whole column is warmer than 26 degC the
    isotherm is below the deepest valid level, and where it is colder the
    isotherm is above the shallowest -- in neither case does a depth exist.
    Our own Bay of Bengal cube has 16 shelf columns on 2026-07-30 that are
    warmer than 26 degC all the way to the seabed (for example 21.5 N, 87.5 E,
    valid only at 5 m). Extrapolating there would print a confident depth for
    an isotherm that is not in the water.
  * No interpolation across a gap. A crossing is only real between two
    adjacent levels that BOTH carry a measurement. 28.0 / missing / 25.0
    straddles 26 degC but never brackets it.

The level spacing in the real cube is 5, 10, 20, 30, 50, 75, 100, 125, 150,
200 ... metres, so the interpolation uses the actual bracketing pair and never
an assumed dz.
"""

from __future__ import annotations

import numpy as np

THRESHOLD_DEGC = 26.0

METHOD = (
    "shallowest crossing of 26 degC, linear interpolation in depth between the "
    "two bracketing finite levels; no extrapolation above the shallowest or "
    "below the deepest valid level; no interpolation across a missing level"
)


def isotherm_depth(temp, depth, threshold: float = THRESHOLD_DEGC) -> np.ndarray:
    """Depth of the shallowest `threshold` crossing per column.

    `temp` is (depth, ...) with NaN for missing; `depth` is metres positive
    down and strictly increasing. Returns an array shaped like temp's trailing
    dimensions, NaN wherever no crossing exists.
    """
    temp = np.asarray(temp, dtype="float64")
    depth = np.asarray(depth, dtype="float64")
    if temp.ndim < 1 or temp.shape[0] != depth.shape[0]:
        raise ValueError(
            f"temp's first axis must be depth: got temp {temp.shape} against "
            f"{depth.shape[0]} levels"
        )

    finite = np.isfinite(temp)
    upper, lower = temp[:-1], temp[1:]
    # Both levels measured, warm above, cold below. A NaN fails both
    # comparisons on its own, so the explicit finite test is there for the case
    # NaN does not cover: an infinity would satisfy `>= threshold`, be accepted
    # as a bracket, and then divide to NaN with a RuntimeWarning instead of
    # being excluded cleanly.
    crossing = finite[:-1] & finite[1:] & (upper >= threshold) & (lower < threshold)

    out = np.full(temp.shape[1:], np.nan, dtype="float64")
    flat_out = out.reshape(-1)
    if not crossing.any():
        return flat_out.reshape(temp.shape[1:])

    flat_cross = crossing.reshape(crossing.shape[0], -1)
    flat_temp = temp.reshape(temp.shape[0], -1)
    has = flat_cross.any(axis=0)
    cols = np.flatnonzero(has)
    # argmax on a boolean array gives the FIRST True, i.e. the shallowest
    # crossing -- which is the one that matters when a column has an inversion.
    k = np.argmax(flat_cross, axis=0)[cols]

    t_up, t_lo = flat_temp[k, cols], flat_temp[k + 1, cols]
    z_up, z_lo = depth[k], depth[k + 1]
    # t_up >= threshold > t_lo on every selected cell, so the denominator is
    # strictly positive: dividing only on the selection avoids a 0/0 warning.
    frac = (t_up - threshold) / (t_up - t_lo)
    flat_out[cols] = z_up + frac * (z_lo - z_up)
    return flat_out.reshape(temp.shape[1:])


def crossing_census(temp, depth, threshold: float = THRESHOLD_DEGC) -> dict:
    """How many columns cross the threshold, and how many cross it more than once.

    The second number is the interesting one and it is not a curiosity. On
    2026-07-10 seven columns of our own Bay of Bengal cube cross 26 degC twice:
    the temperature falls below 26 by 75 m, returns above 26 at 100 m, and
    falls again by 125 m. That is a real subsurface temperature inversion, the
    signature of the barrier layer the Bay of Bengal is known for, where
    monsoon and river freshwater cap a warmer layer beneath.

    In those columns `isotherm_depth` reports the SHALLOWEST crossing, about 65
    to 71 m, while a deepest-crossing convention would report about 100 to 110
    m. Both are defensible; they answer different questions, and the difference
    of roughly 40 m matters to anyone reading D26 as cyclone heat potential.
    Serving one number and saying nothing would hide that a choice was made,
    so the count travels with the field.
    """
    temp = np.asarray(temp, dtype="float64")
    depth = np.asarray(depth, dtype="float64")
    finite = np.isfinite(temp)
    crossing = finite[:-1] & finite[1:] & (temp[:-1] >= threshold) & (temp[1:] < threshold)
    per_column = crossing.reshape(crossing.shape[0], -1).sum(axis=0)
    wet = finite.reshape(finite.shape[0], -1).any(axis=0)
    return {
        "columns_total": int(per_column.size),
        "columns_wet": int(wet.sum()),
        "columns_with_crossing": int((per_column >= 1).sum()),
        "columns_with_multiple_crossings": int((per_column > 1).sum()),
    }


def compute(ds):
    temp = ds["TEMP"].values
    depth = ds["depth"].values
    values = isotherm_depth(temp, depth, THRESHOLD_DEGC)
    census = crossing_census(temp, depth, THRESHOLD_DEGC)

    notes = dict(census)
    multiple = census["columns_with_multiple_crossings"]
    if multiple:
        notes["multiple_crossings_note"] = (
            f"{multiple} column(s) cross {THRESHOLD_DEGC:g} degC more than once, a "
            "subsurface temperature inversion. The value served is the SHALLOWEST "
            "crossing; a deepest-crossing convention would report a greater depth "
            "in those columns."
        )
    return values, notes


def register(registry) -> None:
    registry.register_derived_product(
        name="D26",
        label="Depth of the 26 degC isotherm",
        units="m",
        requires={"TEMP": "degC"},
        compute=compute,
        output="surface",
        canonical="depth_of_isosurface_of_sea_water_potential_temperature",
        method=METHOD,
        params={"threshold": THRESHOLD_DEGC, "threshold_units": "degC"},
    )
