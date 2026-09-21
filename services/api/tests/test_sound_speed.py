"""Speed of sound in seawater as a derived product.

WHY THIS VARIABLE. Sound is how the ocean is measured and how things in it are
found. Every echo sounder, every ADCP, every sonar and every acoustic float
positioning fix converts a travel time into a distance by assuming a sound
speed, and INCOIS's own mandates include search and rescue support, where the
Navy and Coast Guard care about exactly this field. It is also the variable
that creates the SOFAR channel: because sound speed falls with temperature and
rises with pressure, a tropical column has a MINIMUM at depth, and sound
launched there is refracted back towards the axis instead of escaping, so it
travels for thousands of kilometres. Finding that axis is a real operational
question and this plugin answers it from the model field.

It is never measured directly by any instrument in our holdings. Like density,
it is computed from temperature, salinity and pressure, which makes it the
third demonstration of the derived-product extension point (PS F6) and the
third field served through WMS and WCS without a byte changing on disk (F7).

THE STANDARD. TEOS-10 (IOC, SCOR and IAPSO, 2010) through the `gsw` Gibbs
SeaWater toolbox, the same library and the same chain the density plugin uses,
so the two derived fields cannot disagree about what a decibar or an Absolute
Salinity is.

    depth, latitude        -> pressure            gsw.p_from_z
    practical salinity, p  -> Absolute Salinity   gsw.SA_from_SP
    in-situ temperature    -> Conservative Temp   gsw.CT_from_t
    SA, CT, p              -> sound speed         gsw.sound_speed

Feeding practical salinity and in-situ temperature straight in is the usual
shortcut. It produces a plausible number that is wrong, and no colour map
would show it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "sound_speed.py"


def _module():
    """The plugin loaded directly, so the maths can be tested without the
    registry in the way. Registration is covered in test_plugins.py against
    the real plugin directory."""
    spec = importlib.util.spec_from_file_location("sound_speed", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ds(depths, temps, sals, *, lat=15.5, lon=88.5):
    """A one-cell (depth, lat, lon) dataset, the shape compute() is handed."""
    nz = len(depths)
    ds = xr.Dataset(
        {
            "TEMP": (("depth", "lat", "lon"),
                     np.asarray(temps, dtype="float64").reshape(nz, 1, 1)),
            "SAL": (("depth", "lat", "lon"),
                    np.asarray(sals, dtype="float64").reshape(nz, 1, 1)),
        },
        coords={
            "depth": ("depth", np.asarray(depths, dtype="float64")),
            "lat": ("lat", np.array([float(lat)])),
            "lon": ("lon", np.array([float(lon)])),
        },
    )
    ds["TEMP"].attrs["units"] = "degC"
    ds["SAL"].attrs["units"] = "1"
    return ds


# --- the published check values ---------------------------------------------


def test_sound_speed_reproduces_the_published_teos10_check_values():
    """The gsw toolbox's own documented example for sound_speed.

    Reproducing the reference implementation to six decimals means our call IS
    the standard rather than something that resembles it.
    """
    gsw = pytest.importorskip("gsw")
    SA = np.array([34.7118, 34.8915, 35.0256, 34.8472, 34.7366, 34.7324])
    CT = np.array([28.8099, 28.4392, 22.7862, 10.2262, 6.8272, 4.3236])
    p = np.array([10.0, 50.0, 125.0, 250.0, 600.0, 1000.0])
    expected = np.array(
        [1542.478379, 1542.572504, 1530.740258, 1494.430078, 1487.391369, 1483.937418]
    )
    np.testing.assert_allclose(gsw.sound_speed(SA, CT, p), expected, atol=1e-6)


def test_the_plugin_agrees_with_a_hand_run_teos10_chain():
    """One cell, computed here step by step, against the plugin.

    This is the test that fails if the plugin skips the practical-to-Absolute
    salinity conversion or the in-situ-to-Conservative temperature conversion.
    Both are easy to omit and neither omission looks wrong on a colour map.
    """
    gsw = pytest.importorskip("gsw")
    mod = _module()
    depth, t, sp, lat, lon = 100.0, 23.724, 34.757, 15.5, 88.5

    p = gsw.p_from_z(-depth, lat)
    SA = gsw.SA_from_SP(sp, p, lon, lat)
    CT = gsw.CT_from_t(SA, t, p)
    expected = float(gsw.sound_speed(SA, CT, p))

    got = mod.sound_speed_field(
        np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
        np.array([lat]), np.array([lon]),
    )
    assert float(got.ravel()[0]) == pytest.approx(expected, abs=1e-12)
    # Seawater, not air (343) and not fresh water at 4 degrees (1421).
    assert 1400.0 < float(got.ravel()[0]) < 1600.0


# --- pressure is not depth ---------------------------------------------------


def test_pressure_comes_from_depth_and_latitude_not_from_depth_alone():
    """Treating metres as decibars is the classic error in this chain.

    Sound speed rises about 1.7 m/s per 100 dbar, so at 2000 m the roughly
    21 dbar difference between metres and decibars is about 0.35 m/s. Small,
    confident, and undetectable downstream, which is exactly why it is pinned.
    """
    gsw = pytest.importorskip("gsw")
    mod = _module()
    depth, t, sp, lat, lon = 2000.0, 2.649, 34.772, 15.5, 88.5

    got = float(mod.sound_speed_field(
        np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
        np.array([lat]), np.array([lon]),
    ).ravel()[0])

    p_proper = gsw.p_from_z(-depth, lat)
    naive = gsw.sound_speed(
        gsw.SA_from_SP(sp, depth, lon, lat),
        gsw.CT_from_t(gsw.SA_from_SP(sp, depth, lon, lat), t, depth),
        depth,
    )
    assert p_proper != pytest.approx(depth, abs=1.0), "the fixture must exercise the gap"
    assert got != pytest.approx(float(naive), abs=1e-6), (
        "metres were used as decibars: the latitude-aware conversion is missing"
    )


def test_latitude_and_longitude_are_broadcast_down_the_right_axes():
    """Latitude varies down axis 1 and longitude along axis 2.

    A SQUARE grid, because that is the only shape on which the mistake is
    silent: reshaping a 2-element latitude to (1, 1, 2) against 3 longitudes
    raises, so a rectangular grid would catch a transposition by accident
    rather than on purpose.

    Both coordinates genuinely enter the answer. Latitude does through
    gravity, so pressure. Longitude does too, more faintly, because
    gsw.SA_from_SP applies a regional composition anomaly that is a function
    of position; at 1000 m here that is about 0.0002 m/s against latitude's
    0.004. So the test cannot say "constant along a row" and instead pins one
    cell against the chain run by hand for THAT cell's own coordinates, which
    a transposition would fail.
    """
    gsw = pytest.importorskip("gsw")
    mod = _module()
    depths = np.array([1000.0])
    t, s = 6.746, 34.945
    lat = np.array([5.0, 25.0])
    lon = np.array([80.0, 95.0])
    out = mod.sound_speed_field(
        np.full((1, 2, 2), t), np.full((1, 2, 2), s), depths, lat, lon
    )
    assert out.shape == (1, 2, 2)

    def by_hand(la, lo):
        p = gsw.p_from_z(-depths[0], la)
        SA = gsw.SA_from_SP(s, p, lo, la)
        return float(gsw.sound_speed(SA, gsw.CT_from_t(SA, t, p), p))

    # Row 1, column 0 is latitude 25 N at longitude 80 E. Under a transposed
    # broadcast it would hold latitude 5 N at longitude 95 E instead.
    assert out[0, 1, 0] == pytest.approx(by_hand(25.0, 80.0), abs=1e-9)
    assert out[0, 1, 0] != pytest.approx(by_hand(5.0, 95.0), abs=1e-6)

    # And latitude is the stronger of the two, which is the physics: gravity
    # moves the pressure, the composition anomaly only moves the salinity.
    d_lat = abs(out[0, 0, 0] - out[0, 1, 0])
    d_lon = abs(out[0, 0, 0] - out[0, 0, 1])
    assert d_lat > 10 * d_lon > 0.0


# --- what is not a measurement ----------------------------------------------


def test_a_missing_temperature_or_salinity_gives_no_sound_speed():
    """Sound speed from one of the two is not a partial answer."""
    mod = _module()
    out = mod.sound_speed_field(
        np.array([[[28.6]], [[np.nan]], [[14.4]]]),
        np.array([[[33.7]], [[34.9]], [[np.nan]]]),
        np.array([50.0, 75.0, 200.0]), np.array([15.5]), np.array([88.5]),
    ).ravel()
    assert np.isfinite(out[0])
    assert np.isnan(out[1]) and np.isnan(out[2])


def test_an_infinity_is_treated_as_no_measurement():
    """An infinity would travel through the polynomial and come out looking
    like a finite number rather than propagating as NaN."""
    mod = _module()
    out = mod.sound_speed_field(
        np.array([[[np.inf]], [[28.6]]]), np.array([[[33.7]], [[33.7]]]),
        np.array([5.0, 50.0]), np.array([15.5]), np.array([88.5]),
    ).ravel()
    assert np.isnan(out[0]) and np.isfinite(out[1])


def test_land_is_nan_everywhere_and_raises_nothing():
    mod = _module()
    out = mod.sound_speed_field(
        np.full((3, 1, 1), np.nan), np.full((3, 1, 1), np.nan),
        np.array([5.0, 50.0, 200.0]), np.array([15.5]), np.array([88.5]),
    )
    assert out.shape == (3, 1, 1) and np.isnan(out).all()


# --- the physics, in the three directions it moves --------------------------


def test_warm_water_carries_sound_faster_than_cold():
    mod = _module()
    warm, cold = (mod.sound_speed_field(
        np.array([[[t]]]), np.array([[[35.0]]]), np.array([5.0]),
        np.array([15.0]), np.array([88.0])).ravel()[0] for t in (30.0, 5.0))
    assert warm > cold + 50.0


def test_salty_water_carries_sound_faster_than_fresh():
    mod = _module()
    salty, fresh = (mod.sound_speed_field(
        np.array([[[15.0]]]), np.array([[[s]]]), np.array([5.0]),
        np.array([15.0]), np.array([88.0])).ravel()[0] for s in (37.0, 33.0))
    assert salty > fresh


def test_pressure_speeds_sound_up_at_the_same_temperature_and_salinity():
    """The term that makes the SOFAR channel exist: below the thermocline
    temperature stops falling and pressure takes over, so the profile turns."""
    mod = _module()
    deep, shallow = (mod.sound_speed_field(
        np.array([[[5.0]]]), np.array([[[35.0]]]), np.array([z]),
        np.array([15.0]), np.array([88.0])).ravel()[0] for z in (2000.0, 5.0))
    assert deep > shallow + 25.0


# --- a real column, and the channel in it -----------------------------------


def test_a_real_bay_of_bengal_column_has_a_sound_channel():
    """Real TEMP and SAL at 15.5 N, 88.5 E on 2026-07-30, from our own cube.

    A textbook SOFAR profile: about 1540 m/s in the warm surface layer,
    falling through the thermocline to a minimum near 1492 m/s, then turning
    back up as pressure takes over. The minimum is INTERIOR, which is what
    makes it a channel rather than just the coldest water.
    """
    mod = _module()
    depths = np.array([5.0, 100.0, 500.0, 1000.0, 1600.0, 2000.0])
    temp = np.array([28.739, 23.724, 9.936, 6.746, 3.775, 2.649])
    sal = np.array([32.766, 34.757, 35.021, 34.945, 34.838, 34.772])

    out = mod.sound_speed_field(
        temp.reshape(-1, 1, 1), sal.reshape(-1, 1, 1), depths,
        np.array([15.5]), np.array([88.5]),
    ).ravel()

    assert out[0] == pytest.approx(1540.43, abs=0.05)
    assert out[-1] == pytest.approx(1493.69, abs=0.05)
    k = int(np.nanargmin(out))
    assert 0 < k < len(out) - 1, "the minimum must be interior, not the bottom cell"
    assert depths[k] == 1600.0
    assert out[k] == pytest.approx(1491.82, abs=0.05)


def test_the_channel_census_finds_the_axis_and_its_depth():
    mod = _module()
    depths = np.array([5.0, 100.0, 500.0, 1000.0, 1600.0, 2000.0])
    temp = np.array([28.739, 23.724, 9.936, 6.746, 3.775, 2.649]).reshape(-1, 1, 1)
    sal = np.array([32.766, 34.757, 35.021, 34.945, 34.838, 34.772]).reshape(-1, 1, 1)
    field = mod.sound_speed_field(temp, sal, depths, np.array([15.5]), np.array([88.5]))

    census = mod.channel_census(field, depths)
    assert census["columns_wet"] == 1
    assert census["columns_with_channel"] == 1
    assert census["axis_depth_median_m"] == 1600.0
    assert census["axis_speed_min_m_s"] == pytest.approx(1491.82, abs=0.05)


def test_a_column_whose_minimum_is_the_bottom_cell_is_not_a_channel():
    """Sound trapped by the sea floor is not a waveguide. A monotonically
    falling profile has its minimum at the last level and must be reported as
    having no axis, or the census would claim a channel everywhere."""
    mod = _module()
    depths = np.array([5.0, 100.0, 500.0])
    # Falling all the way down: cold at the bottom, no pressure turn yet.
    field = np.array([1540.0, 1520.0, 1500.0]).reshape(-1, 1, 1)
    census = mod.channel_census(field, depths)
    assert census["columns_wet"] == 1
    assert census["columns_with_channel"] == 0
    assert census["axis_depth_median_m"] is None


def test_the_census_ignores_land_columns():
    mod = _module()
    depths = np.array([5.0, 100.0, 500.0])
    field = np.full((3, 1, 2), np.nan)
    field[:, 0, 0] = [1540.0, 1500.0, 1510.0]
    census = mod.channel_census(field, depths)
    assert census["columns_total"] == 2
    assert census["columns_wet"] == 1
    assert census["columns_with_channel"] == 1


# --- the derived-product entry point ----------------------------------------


def test_compute_returns_a_column_shaped_field_and_notes():
    mod = _module()
    ds = _ds([5.0, 100.0, 500.0, 1000.0, 1600.0, 2000.0],
             [28.739, 23.724, 9.936, 6.746, 3.775, 2.649],
             [32.766, 34.757, 35.021, 34.945, 34.838, 34.772])
    values, notes = mod.compute(ds)
    assert values.shape == (6, 1, 1)
    assert np.isfinite(values).all()
    assert "TEOS-10" in notes["standard"]
    assert notes["columns_with_channel"] == 1
    assert notes["axis_depth_median_m"] == 1600.0
    assert "channel_note" in notes and "SOFAR" in notes["channel_note"]


def test_compute_refuses_a_dataset_missing_salinity():
    mod = _module()
    ds = _ds([5.0, 50.0], [28.7, 28.6], [32.8, 33.7]).drop_vars("SAL")
    with pytest.raises(KeyError):
        mod.compute(ds)
