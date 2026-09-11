"""Potential density anomaly (sigma-0) as a derived product.

Density is the variable an oceanographer reaches for after temperature and
salinity, because it is what actually stratifies the ocean: it sets the mixed
layer, it identifies water masses, and it decides whether a column will
overturn. It is also never measured. There is no density sensor on an Argo
float; the quantity is computed from temperature, salinity and pressure
through an equation of state, and that computation is the thing these tests
pin.

THE STANDARD, AND WHY IT MATTERS WHICH ONE. We use TEOS-10 (IOC, SCOR and
IAPSO, 2010), the international standard since 2009, through the `gsw` Gibbs
SeaWater toolbox that this repository already depends on and already trusts
for the pressure-to-depth conversion in app/argo.py. The older EOS-80
(Fofonoff and Millard, 1983) is still in wide use and disagrees with TEOS-10
by order 0.01 kg/m3 in the open ocean. Saying which one produced a number is
part of the number.

WHAT IS SERVED IS SIGMA-0, NOT IN-SITU DENSITY. Sigma-0 is the potential
density anomaly referenced to the surface: the density a parcel would have if
it were moved adiabatically to 0 dbar, minus 1000 kg/m3. That reference is a
choice with consequences and it is stated on the served field, because
sigma-0 is the right variable for comparing water in the upper ocean and the
wrong one below roughly 1000 m, where the compressibility term makes it
misrank water masses and sigma-2 or sigma-4 is used instead.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

PLUGIN = (
    Path(__file__).resolve().parents[1] / "plugins" / "density_sigma0.py"
)


def _module():
    """The plugin loaded directly, so the maths can be tested without the
    registry in the way. The registration contract is tested separately, in
    test_plugins.py, against the real plugin directory."""
    spec = importlib.util.spec_from_file_location("density_sigma0", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ds(depths, temps, sals, *, lat=15.5, lon=88.5):
    """A one-cell (depth, lat, lon) dataset, the shape compute() is handed."""
    nz = len(depths)
    ds = xr.Dataset(
        {
            "TEMP": (("depth", "lat", "lon"), np.asarray(temps, dtype="float64").reshape(nz, 1, 1)),
            "SAL": (("depth", "lat", "lon"), np.asarray(sals, dtype="float64").reshape(nz, 1, 1)),
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
# These are the strongest assertion available: if our chain reproduces the
# numbers TEOS-10 publishes for its own function, the implementation is the
# standard rather than an approximation of it.


def test_sigma0_reproduces_the_published_teos10_check_values():
    """The gsw toolbox's own documented example for sigma0.

    Absolute Salinity and Conservative Temperature in, potential density
    anomaly out. Reproducing these to six decimals means our call is the
    reference implementation and not a lookalike.
    """
    gsw = pytest.importorskip("gsw")
    SA = np.array([34.7118, 34.8915, 35.0256, 34.8472, 34.7366, 34.7324])
    CT = np.array([28.8099, 28.4392, 22.7862, 10.2262, 6.8272, 4.3236])
    expected = np.array(
        [21.797901, 22.052215, 23.892985, 26.667609, 27.107380, 27.409749]
    )
    np.testing.assert_allclose(gsw.sigma0(SA, CT), expected, atol=1e-6)


def test_the_plugin_agrees_with_a_hand_run_teos10_chain():
    """One cell, computed here step by step, against the plugin's answer.

    This is the test that would fail if the plugin silently skipped the
    practical-to-Absolute salinity conversion or the in-situ-to-Conservative
    temperature conversion. Both are easy to omit, both change the answer in
    the second decimal, and neither omission looks wrong on a colour map.
    """
    gsw = pytest.importorskip("gsw")
    mod = _module()
    depth, t, sp, lat, lon = 100.0, 23.724, 34.757, 15.5, 88.5

    p = gsw.p_from_z(-depth, lat)
    SA = gsw.SA_from_SP(sp, p, lon, lat)
    CT = gsw.CT_from_t(SA, t, p)
    expected = float(gsw.sigma0(SA, CT))

    got = mod.sigma0_field(
        np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
        np.array([lat]), np.array([lon]),
    )
    assert float(got.ravel()[0]) == pytest.approx(expected, abs=1e-12)
    # And it is an ANOMALY, roughly 20 to 30, not an absolute density near
    # 1025. A reference mix-up would be invisible on a relative colour scale.
    assert 15.0 < float(got.ravel()[0]) < 35.0


# --- pressure is not depth ---------------------------------------------------


def test_pressure_comes_from_depth_and_latitude_not_from_depth_alone():
    """Treating metres as decibars is the classic error here.

    At 2000 m and 15 N the true pressure is about 2021 dbar, so using 2000
    would be 21 dbar light. It is a small relative error that produces a
    confident, wrong number, and nothing downstream can detect it.
    """
    gsw = pytest.importorskip("gsw")
    mod = _module()
    depth, t, sp, lat, lon = 2000.0, 2.649, 34.772, 15.5, 88.5

    got = float(
        mod.sigma0_field(
            np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
            np.array([lat]), np.array([lon]),
        ).ravel()[0]
    )

    # 2021.52 dbar at 15.5 N, not 2000. Pinned so that a change in the
    # toolbox's gravity model is caught here rather than showing up as a drift
    # in every deep density value.
    p_true = gsw.p_from_z(-depth, lat)
    assert p_true == pytest.approx(2021.5243, abs=1e-3), "the reference pressure moved"

    def chain(p):
        SA = gsw.SA_from_SP(sp, p, lon, lat)
        return float(gsw.sigma0(SA, gsw.CT_from_t(SA, t, p)))

    assert got == pytest.approx(chain(p_true), abs=1e-12)
    # The wrong-pressure answer is different, so this test can actually fail.
    assert abs(got - chain(depth)) > 1e-6


def test_latitude_enters_the_pressure_conversion():
    """p_from_z is latitude dependent through gravity. A plugin that passed a
    scalar latitude for the whole grid would be subtly wrong at the edges, and
    the demo box spans 5 N to 25 N."""
    mod = _module()
    t, sp, depth = 10.0, 35.0, 1000.0
    at5 = mod.sigma0_field(
        np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
        np.array([5.0]), np.array([88.5]),
    )
    at25 = mod.sigma0_field(
        np.array([[[t]]]), np.array([[[sp]]]), np.array([depth]),
        np.array([25.0]), np.array([88.5]),
    )
    assert float(at5.ravel()[0]) != float(at25.ravel()[0])


def test_latitude_is_broadcast_down_the_right_axis():
    """(depth, lat, lon) with lat varying: a transposed broadcast would put
    the northern latitude on the eastern column and nothing would look wrong."""
    mod = _module()
    depths = np.array([1000.0])
    lats = np.array([5.0, 25.0])
    lons = np.array([85.0, 90.0])
    temp = np.full((1, 2, 2), 10.0)
    sal = np.full((1, 2, 2), 35.0)

    got = mod.sigma0_field(temp, sal, depths, lats, lons)

    assert got.shape == (1, 2, 2)
    # Rows differ (latitude changes the pressure); the two columns of a row
    # differ only through longitude's small effect on Absolute Salinity.
    assert got[0, 0, 0] != got[0, 1, 0], "latitude did not vary down the lat axis"
    single = mod.sigma0_field(
        np.full((1, 1, 1), 10.0), np.full((1, 1, 1), 35.0),
        depths, np.array([5.0]), np.array([85.0]),
    )
    assert got[0, 0, 0] == pytest.approx(float(single.ravel()[0]), abs=1e-12)


# --- missing data ------------------------------------------------------------


def test_a_missing_temperature_or_salinity_gives_no_density():
    """Density needs BOTH. A cell with one of them is not a half answer, and
    filling the gap from a neighbour would invent a water mass."""
    mod = _module()
    out = mod.sigma0_field(
        np.array([[[28.0]], [[np.nan]], [[20.0]]]),
        np.array([[[33.0]], [[34.0]], [[np.nan]]]),
        np.array([5.0, 50.0, 100.0]),
        np.array([15.5]), np.array([88.5]),
    )
    assert np.isfinite(out[0, 0, 0])
    assert not np.isfinite(out[1, 0, 0]), "no temperature, so no density"
    assert not np.isfinite(out[2, 0, 0]), "no salinity, so no density"


def test_land_is_nan_everywhere_and_raises_nothing():
    mod = _module()
    nan3 = np.full((3, 1, 1), np.nan)
    with np.errstate(all="raise"):
        out = mod.sigma0_field(
            nan3, nan3, np.array([5.0, 50.0, 100.0]),
            np.array([15.5]), np.array([88.5]),
        )
    assert not np.isfinite(out).any()


def test_an_infinity_is_treated_as_no_measurement():
    """A NaN propagates on its own; an infinity would sail through the
    equation of state and come out as a finite-looking absurdity or a warning
    acted on by accident."""
    mod = _module()
    with np.errstate(all="raise"):
        out = mod.sigma0_field(
            np.array([[[np.inf]]]), np.array([[[35.0]]]),
            np.array([100.0]), np.array([15.5]), np.array([88.5]),
        )
    assert not np.isfinite(out.ravel()[0])


# --- the physics -------------------------------------------------------------


def test_cold_water_is_denser_than_warm_at_the_same_salinity():
    mod = _module()
    out = mod.sigma0_field(
        np.array([[[28.0]], [[4.0]]]), np.array([[[35.0]], [[35.0]]]),
        np.array([5.0, 10.0]), np.array([15.5]), np.array([88.5]),
    )
    assert out[1, 0, 0] > out[0, 0, 0]


def test_salty_water_is_denser_than_fresh_at_the_same_temperature():
    mod = _module()
    out = mod.sigma0_field(
        np.array([[[28.0]], [[28.0]]]), np.array([[[32.0]], [[35.0]]]),
        np.array([5.0, 10.0]), np.array([15.5]), np.array([88.5]),
    )
    assert out[1, 0, 0] > out[0, 0, 0]


def test_a_real_bay_of_bengal_column_stratifies_downward():
    """Real TEMP and SAL at 15.5 N, 88.5 E on 2026-07-30, from our own cube.

    Below the fresh surface layer the column is strongly stratified: sigma-0
    runs from about 21.2 at 50 m to about 27.8 at 2000 m. The top of this same
    column is NOT monotonic, and that has its own test below.
    """
    mod = _module()
    depths = np.array([50.0, 75.0, 100.0, 200.0, 500.0, 1000.0, 2000.0])
    temp = np.array([28.600, 26.402, 23.724, 14.427, 9.936, 6.746, 2.649])
    sal = np.array([33.675, 34.919, 34.757, 34.977, 35.021, 34.945, 34.772])

    out = mod.sigma0_field(
        temp.reshape(-1, 1, 1), sal.reshape(-1, 1, 1), depths,
        np.array([15.5]), np.array([88.5]),
    ).ravel()

    assert np.all(np.diff(out) > 0), "density must increase downward here"
    assert out[0] == pytest.approx(21.21, abs=0.05)
    assert out[-1] == pytest.approx(27.76, abs=0.05)


def test_the_freshwater_cap_inverts_the_density_in_the_top_of_a_real_column():
    """The same real column's top 20 m is statically UNSTABLE, and that is a
    fact about the analysis rather than a bug in this code.

    At 15.5 N, 88.5 E the analysis puts water at 10 m that is both warmer
    (29.232 against 28.739) and fresher (32.304 against 32.766) than the water
    at 5 m, so it is lighter, sitting under it. The Bay of Bengal is the
    freshest large bay in the world and a 10-day, 1-degree analysis is
    smoothed and not required to be statically stable.

    The point of this test is that the plugin must REPORT that, not repair it.
    Sorting the column, or clipping the inversion away, would turn a real
    property of INCOIS's product into a number we made up.
    """
    mod = _module()
    depths = np.array([5.0, 10.0, 20.0, 30.0, 50.0])
    temp = np.array([28.739, 29.232, 29.204, 28.879, 28.600])
    sal = np.array([32.766, 32.304, 32.205, 32.471, 33.675])

    out = mod.sigma0_field(
        temp.reshape(-1, 1, 1), sal.reshape(-1, 1, 1), depths,
        np.array([15.5]), np.array([88.5]),
    ).ravel()

    assert out[1] < out[0], "the 10 m water really is lighter than the 5 m water"
    assert out[2] < out[0]
    assert out[4] > out[0], "and below the cap it restratifies"


# --- the census that travels with the field ----------------------------------


def test_the_census_counts_unstable_columns_rather_than_hiding_them():
    mod = _module()
    depths = np.array([5.0, 10.0, 20.0])
    # column 0 stable, column 1 inverted at the top
    temp = np.array([[[28.0, 28.7]], [[26.0, 29.2]], [[24.0, 29.2]]])
    sal = np.array([[[34.0, 32.8]], [[34.5, 32.3]], [[35.0, 32.2]]])

    values = mod.sigma0_field(temp, sal, depths, np.array([15.5]), np.array([85.0, 88.5]))
    census = mod.stability_census(values)

    assert census["columns_wet"] == 2
    assert census["columns_unstable"] == 1
    assert census["max_inversion_kg_m3"] > 0.0


def test_the_census_separates_a_surface_inversion_from_a_deep_one():
    """The number that matters is not how many columns are unstable but where.

    In the real cube 213 of 225 wet columns are unstable and 208 of those are
    in the top 30 m, which is the river plume rather than a broken field.
    Reporting the total alone would make the correct answer look alarming.
    """
    mod = _module()
    depths = np.array([5.0, 10.0, 200.0, 300.0])
    # Column 0: inverted only at the surface pair. Column 1: inverted only
    # in the deep pair, which is the one worth a second look.
    temp = np.array(
        [[[28.0, 28.0]], [[29.5, 26.0]], [[14.0, 14.0]], [[13.0, 18.0]]]
    )
    sal = np.array(
        [[[33.0, 34.0]], [[32.0, 34.5]], [[35.0, 35.0]], [[35.0, 34.6]]]
    )
    values = mod.sigma0_field(temp, sal, depths, np.array([15.5]), np.array([85.0, 88.5]))
    census = mod.stability_census(values, depths)

    assert census["columns_unstable"] == 2
    assert census["columns_unstable_below_surface_layer"] == 1
    assert census["surface_layer_m"] == mod.SURFACE_LAYER_M
    lo, hi = census["inversion_depth_range_m"]
    assert lo == 5.0 and hi == 300.0


def test_the_census_reports_no_depth_range_when_nothing_is_inverted():
    mod = _module()
    depths = np.array([5.0, 50.0])
    values = mod.sigma0_field(
        np.array([[[28.0]], [[20.0]]]), np.array([[[33.0]], [[35.0]]]),
        depths, np.array([15.5]), np.array([88.5]),
    )
    census = mod.stability_census(values, depths)
    assert census["columns_unstable"] == 0
    assert census["inversion_depth_range_m"] is None


def test_the_census_ignores_land_columns():
    mod = _module()
    depths = np.array([5.0, 10.0])
    temp = np.array([[[28.0, np.nan]], [[26.0, np.nan]]])
    sal = np.array([[[34.0, np.nan]], [[34.5, np.nan]]])
    values = mod.sigma0_field(temp, sal, depths, np.array([15.5]), np.array([85.0, 88.5]))
    census = mod.stability_census(values)
    assert census["columns_total"] == 2
    assert census["columns_wet"] == 1
    assert census["columns_unstable"] == 0


def test_the_census_does_not_call_a_gap_an_inversion():
    """A missing level between two measured ones is not evidence of anything.
    Comparing across it would manufacture inversions on sparse columns."""
    mod = _module()
    depths = np.array([5.0, 10.0, 20.0])
    temp = np.array([[[28.0]], [[np.nan]], [[24.0]]])
    sal = np.array([[[34.0]], [[np.nan]], [[35.0]]])
    values = mod.sigma0_field(temp, sal, depths, np.array([15.5]), np.array([88.5]))
    census = mod.stability_census(values)
    assert census["columns_wet"] == 1
    assert census["columns_unstable"] == 0


# --- the shape and the compute() contract ------------------------------------


def test_compute_returns_a_column_shaped_field_and_notes():
    mod = _module()
    ds = _ds(
        [5.0, 50.0, 100.0],
        [28.739, 28.600, 23.724],
        [32.766, 33.675, 34.757],
    )
    values, notes = mod.compute(ds)
    assert np.asarray(values).shape == (3, 1, 1), "a column product is (depth, lat, lon)"
    assert notes["columns_wet"] == 1
    assert "reference" in notes and "0 dbar" in notes["reference"]
    assert "TEOS-10" in notes["standard"]


def test_compute_refuses_a_dataset_missing_salinity():
    """Density from temperature alone is not a degraded answer, it is a
    different quantity. Better to fail loudly than to serve one."""
    mod = _module()
    ds = _ds([5.0], [28.0], [34.0]).drop_vars("SAL")
    with pytest.raises(KeyError):
        mod.compute(ds)
