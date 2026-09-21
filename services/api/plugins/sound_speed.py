"""SVEL: the speed of sound in seawater, as a derived product.

Sound is how the ocean is measured and how things in it are found. Every echo
sounder, ADCP, sonar and acoustic float fix turns a travel time into a
distance by assuming a sound speed, so an error in this field is an error in a
position. Two of INCOIS's stated mandates run through it directly: search and
rescue support, where the Coast Guard and Navy are working acoustically, and
the ocean state forecasts that back them.

It is NEVER MEASURED by anything in our holdings. Like density it is computed
from temperature, salinity and pressure, which makes it the third honest
demonstration of the derived-product extension point beside D26 and SIG0
(PS F6), and the third field served through WMS and WCS without a byte
changing on disk (F7).

THE SOFAR CHANNEL, WHICH IS WHY THE PROFILE IS INTERESTING
-----------------------------------------------------------
Sound speed rises with temperature, with salinity and with pressure. In the
tropics the first two fall rapidly through the thermocline while the third
climbs steadily, so a column has a MINIMUM at depth. Sound launched near that
minimum is refracted back towards it from both above and below, so instead of
escaping it is trapped and can travel for thousands of kilometres. That is the
SOFAR channel, and the depth of the minimum is its axis.

Finding the axis is an operational question, not an ornament, so this plugin
reports it the way density_sigma0 reports its stability census: as notes that
travel with the field. In our own 2026-07-30 cube 212 of 215 wet columns have
an interior minimum, and at 15.5 N, 88.5 E the profile runs 1540.4 m/s at the
surface, down to 1491.8 m/s at 1600 m, and back up to 1493.7 m/s at 2000 m.

A minimum sitting on the LAST level is not a channel. It means the profile was
still falling when the cube ran out, and sound there is bounded by the sea
floor rather than by refraction. The census counts those separately instead of
claiming a waveguide everywhere.

WHICH STANDARD, BECAUSE IT MATTERS
-----------------------------------
TEOS-10 (IOC, SCOR and IAPSO, 2010) through the `gsw` Gibbs SeaWater toolbox:
the same library, and deliberately the same chain, that density_sigma0 uses
and that app/argo.py uses for pressure to depth. One definition of a decibar
across the whole service, so two derived fields cannot disagree about where
they are.

    depth, latitude        -> pressure            gsw.p_from_z
    practical salinity, p  -> Absolute Salinity   gsw.SA_from_SP
    in-situ temperature    -> Conservative Temp   gsw.CT_from_t
    SA, CT, p              -> sound speed         gsw.sound_speed

Feeding practical salinity and in-situ temperature straight into the last call
is the usual shortcut. It returns a plausible number that is wrong, and no
colour map would reveal it.
"""

from __future__ import annotations

import numpy as np

STANDARD = "TEOS-10 (IOC, SCOR and IAPSO, 2010) via the gsw Gibbs SeaWater toolbox"

METHOD = (
    "speed of sound in seawater, TEOS-10: pressure from depth and latitude "
    "(gsw.p_from_z), practical to Absolute Salinity (gsw.SA_from_SP), in-situ "
    "to Conservative Temperature (gsw.CT_from_t), then gsw.sound_speed; a cell "
    "needs BOTH temperature and salinity"
)

CHANNEL_NOTE = (
    "The depth of the sound-speed minimum is the SOFAR channel axis, where "
    "sound is refracted back from above and below instead of escaping. A "
    "minimum lying on the deepest level is not an axis: the profile was still "
    "falling where the cube ends, so it is counted separately."
)


def sound_speed_field(temp, sal, depth, lat, lon) -> np.ndarray:
    """Sound speed on a (depth, lat, lon) grid, NaN where it is not defined.

    `temp` is in-situ temperature in degC and `sal` is PRACTICAL salinity,
    both shaped (depth, lat, lon) with NaN for missing. `depth` is metres
    positive down; `lat` and `lon` are the grid's own coordinate vectors, in
    degrees. The result is metres per second.

    A cell needs both temperature and salinity. Sound speed from one of them
    is not a partial answer, it is a different quantity.
    """
    import gsw

    temp = np.asarray(temp, dtype="float64")
    sal = np.asarray(sal, dtype="float64")
    depth = np.asarray(depth, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")

    if temp.shape != sal.shape:
        raise ValueError(f"TEMP {temp.shape} and SAL {sal.shape} must be the same grid")
    if temp.ndim != 3:
        raise ValueError(f"expected (depth, lat, lon); got {temp.shape}")
    nz, ny, nx = temp.shape
    if (depth.size, lat.size, lon.size) != (nz, ny, nx):
        raise ValueError(
            f"coordinates {depth.size, lat.size, lon.size} do not match the "
            f"field {temp.shape}"
        )

    # Latitude down axis 1, longitude along axis 2. Transposing this broadcast
    # puts the northern latitude on the eastern column and leaves every value
    # physically plausible, which is why it has its own test.
    depth3 = depth.reshape(nz, 1, 1)
    lat3 = lat.reshape(1, ny, 1)
    lon3 = lon.reshape(1, 1, nx)

    # Pressure from depth AND latitude: gravity varies across the demo box's
    # 5 N to 25 N, and at 2000 m metres and decibars differ by about 21 dbar,
    # which is about 0.35 m/s here.
    pressure = np.broadcast_to(
        gsw.p_from_z(-depth3, np.broadcast_to(lat3, (nz, ny, 1))), (nz, ny, nx)
    )

    # Only finite cells enter the equation of state. An infinity is not
    # excluded by NaN propagation: it travels through the polynomial and
    # emerges as a finite-looking absurdity.
    usable = np.isfinite(temp) & np.isfinite(sal)
    out = np.full(temp.shape, np.nan, dtype="float64")
    if not usable.any():
        return out

    t_ok = temp[usable]
    s_ok = sal[usable]
    p_ok = pressure[usable]
    lat_ok = np.broadcast_to(lat3, temp.shape)[usable]
    lon_ok = np.broadcast_to(lon3, temp.shape)[usable]

    absolute_salinity = gsw.SA_from_SP(s_ok, p_ok, lon_ok, lat_ok)
    conservative_temperature = gsw.CT_from_t(absolute_salinity, t_ok, p_ok)
    out[usable] = gsw.sound_speed(absolute_salinity, conservative_temperature, p_ok)
    return out


#: A column needs at least this many finite levels before its minimum means
#: anything. Two levels always have a minimum and it is never a channel.
MIN_LEVELS = 3


def channel_census(speed, depth) -> dict:
    """Where the SOFAR axis is, and in how many columns there is one at all.

    A column counts as having a channel when its sound-speed minimum is
    INTERIOR: neither the first finite level nor the last. A minimum at the
    bottom means the profile was still falling where the data stops, and a
    minimum at the top means there is no surface duct to speak of. Reporting
    those as channels would claim a waveguide the field does not show.
    """
    speed = np.asarray(speed, dtype="float64")
    depth = np.asarray(depth, dtype="float64")
    nz = speed.shape[0]
    flat = speed.reshape(nz, -1)

    finite = np.isfinite(flat)
    wet = finite.sum(axis=0) >= MIN_LEVELS

    out = {
        "columns_total": int(flat.shape[1]),
        "columns_wet": int(wet.sum()),
        "columns_with_channel": 0,
        "axis_depth_median_m": None,
        "axis_depth_range_m": None,
        "axis_speed_min_m_s": None,
        "speed_min_m_s": None,
        "speed_max_m_s": None,
    }
    if not wet.any():
        return out

    out["speed_min_m_s"] = round(float(np.nanmin(flat)), 3)
    out["speed_max_m_s"] = round(float(np.nanmax(flat)), 3)

    # argmin over a column that has gaps: fill the gaps with +inf so a missing
    # level can never win, and keep the index in the ORIGINAL level numbering.
    filled = np.where(finite, flat, np.inf)
    k = np.argmin(filled, axis=0)

    first = np.argmax(finite, axis=0)                      # first finite level
    last = nz - 1 - np.argmax(finite[::-1], axis=0)        # last finite level
    interior = wet & (k > first) & (k < last)

    out["columns_with_channel"] = int(interior.sum())
    if interior.any():
        axes = depth[k[interior]]
        out["axis_depth_median_m"] = round(float(np.median(axes)), 3)
        out["axis_depth_range_m"] = [float(axes.min()), float(axes.max())]
        out["axis_speed_min_m_s"] = round(
            float(np.min(filled[k[interior], np.flatnonzero(interior)])), 3
        )
    return out


def compute(ds):
    """The derived-product entry point: (values, notes)."""
    temp = ds["TEMP"].values
    sal = ds["SAL"].values
    values = sound_speed_field(
        temp, sal, ds["depth"].values, ds["lat"].values, ds["lon"].values
    )

    notes = dict(channel_census(values, ds["depth"].values))
    notes["standard"] = STANDARD
    notes["channel_note"] = CHANNEL_NOTE
    if notes["columns_with_channel"]:
        lo, hi = notes["axis_depth_range_m"]
        notes["channel_note"] = (
            f"{notes['columns_with_channel']} of {notes['columns_wet']} wet "
            f"columns have an interior sound-speed minimum, the SOFAR channel "
            f"axis, with a median depth of {notes['axis_depth_median_m']:g} m "
            f"and a range of {lo:g} to {hi:g} m. {CHANNEL_NOTE}"
        )
    return values, notes


def register(registry) -> None:
    registry.register_derived_product(
        name="SVEL",
        label="Speed of sound in seawater",
        units="m s-1",
        requires={"TEMP": "degC", "SAL": "1"},
        compute=compute,
        output="column",
        canonical="speed_of_sound_in_sea_water",
        method=METHOD,
        params={"standard": "TEOS-10"},
    )
