"""The Copernicus in-situ TAC reader: gliders and CTD casts (PS requirement F2).

The PS names four instrument classes to co-display: "Argo float, Glider profile,
CTD and BGC data". Three of them were in the cube. This reader brings the other
two, from the archive INCOIS itself names in the problem statement's own Dataset
Link field.

The defects pinned here are not hypothetical. Every one was observed in the two
real files this reader was written against, and each is checked because getting
it wrong produces a number that looks fine:

  * 475 of 944 glider dives carry NON-MONOTONIC pressure. A glider samples
    continuously and the pressure reverses near the apex of a dive.
  * 943 of 944 carry gaps in pressure.
  * PRES_QC 4 appears alongside TEMP_QC 1: a good temperature at a depth the
    instrument could not determine.
  * The quality flags arrive as FLOATS, so a missing flag is NaN, not an int.
  * Both legs of each dive are present, tagged 'D' and 'A'.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from app import plugins as plugin_api
from plugins import insitu_tac


# ---------------------------------------------------------------------------
# A file shaped exactly like the real ones, built in memory.
# ---------------------------------------------------------------------------
def write_tac_file(
    path,
    *,
    times,
    lats,
    lons,
    pres,
    temp,
    psal,
    temp_qc=None,
    psal_qc=None,
    pres_qc=None,
    direction=None,
    platform_code="ru29",
    wmo="2801900",
    source="sub-surface gliders",
):
    """Write a Copernicus in-situ TAC profile file, defects and all."""
    n_prof, n_lev = np.shape(pres)
    ones = np.ones((n_prof, n_lev), dtype="float64")

    def qc(given, default):
        return ones * default if given is None else np.asarray(given, dtype="float64")

    ds = xr.Dataset(
        {
            "PRES": (("TIME", "DEPTH"), np.asarray(pres, dtype="float64"),
                     {"units": "dbar", "standard_name": "sea_water_pressure"}),
            "PRES_QC": (("TIME", "DEPTH"), qc(pres_qc, 1.0)),
            "TEMP": (("TIME", "DEPTH"), np.asarray(temp, dtype="float64"),
                     {"units": "degrees_C"}),
            "TEMP_QC": (("TIME", "DEPTH"), qc(temp_qc, 1.0)),
            "PSAL": (("TIME", "DEPTH"), np.asarray(psal, dtype="float64"),
                     {"units": "0.001"}),
            "PSAL_QC": (("TIME", "DEPTH"), qc(psal_qc, 1.0)),
            "DIRECTION": (("TIME",), np.asarray(
                direction if direction is not None else ["D"] * n_prof, dtype="S1")),
            "POSITION_QC": (("TIME",), np.ones(n_prof, dtype="float64")),
            "TIME_QC": (("TIME",), np.ones(n_prof, dtype="float64")),
        },
        coords={
            "TIME": ("TIME", np.asarray(times, dtype="datetime64[ns]")),
            "LATITUDE": ("TIME", np.asarray(lats, dtype="float64")),
            "LONGITUDE": ("TIME", np.asarray(lons, dtype="float64")),
        },
        attrs={
            "platform_code": platform_code,
            "platform_name": platform_code,
            "wmo_platform_code": wmo,
            "institution": "A real institution",
            "source": source,
            "id": f"GL_PR_GL_{platform_code}",
        },
    )
    ds.to_netcdf(path)
    return path


@pytest.fixture
def simple_glider(tmp_path):
    """Two clean descending dives, 4 levels each, at two positions."""
    return write_tac_file(
        tmp_path / "GL_PR_GL_test.nc",
        times=["2018-08-12T00:00:00", "2018-08-12T06:00:00"],
        lats=[5.0, 5.5],
        lons=[80.1, 80.4],
        pres=[[10.0, 100.0, 500.0, 1000.0], [10.0, 100.0, 500.0, 1000.0]],
        temp=[[28.5, 24.0, 10.0, 5.0], [28.4, 23.9, 9.9, 4.9]],
        psal=[[33.0, 34.5, 35.0, 34.8], [33.1, 34.6, 35.1, 34.9]],
    )


# ---------------------------------------------------------------------------
# Pressure is not depth
# ---------------------------------------------------------------------------
def test_pressure_becomes_depth_through_teos10_not_a_one_to_one_assumption(
    simple_glider,
):
    """1 dbar is not 1 m, and at 1000 dbar the difference is 7.9 metres.

    The file measures PRESSURE. Depth is a derived quantity that depends on
    latitude, because gravity does. Assuming a dbar is a metre puts a
    1000 dbar observation 7.9 m below where it was taken, and the scorecard
    then interpolates the model column at the wrong level and calls the
    difference model error.
    """
    ds = insitu_tac.read_casts(simple_glider)
    depth = ds["depth"].values

    # gsw.z_from_p(1000.0, 5.0) = -992.077608 m
    assert depth[0, 3] == pytest.approx(992.077608, abs=1e-5)
    assert depth[0, 2] == pytest.approx(496.0, abs=1.0)

    # The shallowest level moves least; the deepest most. The error is not a
    # constant offset, which is why a single fudge factor would not do either.
    assert abs(depth[0, 0] - 10.0) < 0.1
    assert depth[0, 3] < 1000.0 - 5.0

    # Latitude matters: the same pressure at a different latitude is a
    # different depth.
    assert depth[0, 3] != depth[1, 3] or ds["lat"].values[0] == ds["lat"].values[1]


def test_depth_is_positive_down_and_carries_its_units(simple_glider):
    ds = insitu_tac.read_casts(simple_glider)
    assert ds["depth"].attrs["units"] == "m"
    assert ds["depth"].attrs["positive"] == "down"
    assert float(ds["depth"].min()) > 0.0


# ---------------------------------------------------------------------------
# A moving platform
# ---------------------------------------------------------------------------
def test_a_glider_moves_so_position_is_per_profile_not_per_platform(simple_glider):
    """The mooring reader returns one position. A glider needs one per dive.

    A glider covers tens of kilometres between dives. Collapsing that to a
    single platform position would colocate every dive against the same model
    column, which is the error the scorecard exists to measure.
    """
    ds = insitu_tac.read_casts(simple_glider)
    assert ds["lat"].dims == ("profile",)
    assert ds["lon"].dims == ("profile",)
    assert float(ds["lat"].values[0]) != float(ds["lat"].values[1])
    assert ds["time"].dims == ("profile",)


def test_the_output_is_ragged_casts_not_a_shared_depth_axis(simple_glider):
    """Every dive has its own depths, so depth is a variable, not a coordinate.

    A mooring pivots onto shared sensor depths because its sensors are at fixed
    depths. A glider's levels are wherever it happened to sample, so a shared
    axis would either drop levels or invent them.
    """
    ds = insitu_tac.read_casts(simple_glider)
    assert ds["depth"].dims == ("profile", "level")
    assert "depth" not in ds.coords
    assert ds.attrs["layout"] == "casts"


# ---------------------------------------------------------------------------
# Quality control
# ---------------------------------------------------------------------------
def test_a_bad_pressure_flag_refuses_the_level_even_when_temperature_is_good():
    """A good temperature at an unknown depth is not a usable observation.

    Observed in the real glider: PRES_QC 4 alongside TEMP_QC 1. Filtering on
    the temperature flag alone accepts the reading and then places it at a
    depth the instrument itself flagged as wrong.
    """
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, 100.0, 500.0]],
            temp=[[28.5, 24.0, 10.0]],
            psal=[[33.0, 34.5, 35.0]],
            temp_qc=[[1.0, 1.0, 1.0]],
            pres_qc=[[1.0, 4.0, 1.0]],
        )
        ds = insitu_tac.read_casts(path)

    flags = ds["TEMP_QC"].values[0]
    depths = ds["depth"].values[0]
    # The level whose pressure was flagged bad is not offered as good.
    bad = np.isclose(depths, 99.4, atol=1.0)
    assert bad.any(), "the 100 dbar level should still be present, just not good"
    assert not np.isin(flags[bad], (1, 2)).any()
    assert int(ds.attrs["n_levels_refused_bad_pressure"]) == 1


def test_a_missing_quality_flag_is_missing_and_never_good():
    """The flags arrive as floats, so an absent flag is NaN.

    `np.asarray(nan).astype("int16")` is an undefined conversion that in
    practice yields a large negative number; comparing that against the
    accepted set is luck rather than a decision.
    """
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, 100.0]],
            temp=[[28.5, 24.0]],
            psal=[[33.0, 34.5]],
            temp_qc=[[1.0, np.nan]],
        )
        ds = insitu_tac.read_casts(path)

    assert int(ds["TEMP_QC"].values[0, 0]) == 1
    assert int(ds["TEMP_QC"].values[0, 1]) == insitu_tac.QC_MISSING


# ---------------------------------------------------------------------------
# Non-monotonic pressure
# ---------------------------------------------------------------------------
def test_pressure_that_reverses_within_a_dive_is_sorted_and_counted():
    """A glider's pressure reverses near the apex.

    The rest of the system reads a cast as a column from the surface down. An
    unsorted column makes a depth interpolation walk backwards, and the
    scorecard's bracketing search silently returns the wrong pair of levels.
    """
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, 300.0, 200.0, 500.0]],
            temp=[[28.5, 18.0, 22.0, 10.0]],
            psal=[[33.0, 34.9, 34.7, 35.0]],
        )
        ds = insitu_tac.read_casts(path)

    depth = ds["depth"].values[0]
    finite = depth[np.isfinite(depth)]
    assert np.all(np.diff(finite) > 0), "the column must read downwards"
    # The value travels with its own level, rather than the depths alone
    # being sorted underneath the measurements.
    temp = ds["TEMP"].values[0][np.isfinite(depth)]
    assert temp[1] == pytest.approx(22.0)
    assert temp[2] == pytest.approx(18.0)
    assert int(ds.attrs["n_profiles_resorted"]) == 1


def test_a_duplicated_depth_within_one_dive_is_dropped_and_counted():
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, 100.0, 100.0, 500.0]],
            temp=[[28.5, 24.0, 24.1, 10.0]],
            psal=[[33.0, 34.5, 34.5, 35.0]],
        )
        ds = insitu_tac.read_casts(path)

    depth = ds["depth"].values[0]
    finite = depth[np.isfinite(depth)]
    assert finite.size == 3
    assert np.all(np.diff(finite) > 0)
    assert int(ds.attrs["n_levels_duplicate_depth"]) == 1


def test_a_gap_in_pressure_removes_that_level_rather_than_guessing_it():
    """A gap inside the dive is counted; the padding after it is not.

    The file is a rectangle padded with NaN out to the longest dive in it.
    Counting that padding as missing pressure turns a glider with 121 real
    gaps into one reporting 20,667 of them, which is a number about the file's
    shape wearing the name of a number about the instrument.
    """
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, np.nan, 500.0]],
            temp=[[28.5, 24.0, 10.0]],
            psal=[[33.0, 34.5, 35.0]],
        )
        ds = insitu_tac.read_casts(path)

    depth = ds["depth"].values[0]
    assert np.isfinite(depth).sum() == 2
    assert int(ds.attrs["n_levels_no_pressure"]) == 1


def test_the_padding_that_squares_the_file_off_is_not_counted_as_a_gap():
    """A short dive in a file sized for a long one is padded, not incomplete."""
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00", "2018-08-12T06:00:00"],
            lats=[5.0, 5.5], lons=[80.1, 80.4],
            # The first dive sampled 4 levels, the second stopped after 2 and
            # the file pads it out to match.
            pres=[[10.0, 100.0, 300.0, 500.0], [10.0, 100.0, np.nan, np.nan]],
            temp=[[28.5, 24.0, 15.0, 10.0], [28.4, 23.9, np.nan, np.nan]],
            psal=[[33.0, 34.5, 34.9, 35.0], [33.1, 34.6, np.nan, np.nan]],
        )
        ds = insitu_tac.read_casts(path)

    assert int(ds.attrs["n_levels_no_pressure"]) == 0
    assert np.isfinite(ds["depth"].values[1]).sum() == 2


# ---------------------------------------------------------------------------
# One profile per dive
# ---------------------------------------------------------------------------
def test_only_one_leg_of_each_dive_is_kept_and_the_other_is_counted():
    """A glider profiles on the way down AND on the way up.

    The two legs are minutes apart in nearly the same water. Keeping both
    doubles the apparent number of independent observations, which is the same
    overcount as calling 25 casts 25 instruments.
    """
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00", "2018-08-12T00:20:00",
                   "2018-08-12T06:00:00"],
            lats=[5.0, 5.01, 5.5],
            lons=[80.1, 80.11, 80.4],
            pres=[[10.0, 100.0]] * 3,
            temp=[[28.5, 24.0]] * 3,
            psal=[[33.0, 34.5]] * 3,
            direction=["D", "A", "D"],
        )
        ds = insitu_tac.read_casts(path)

    assert ds.sizes["profile"] == 2
    assert int(ds.attrs["n_profiles_ascending_dropped"]) == 1
    assert ds.attrs["direction_kept"] == "D"


def test_a_ctd_cast_file_has_no_ascending_legs_and_loses_nothing():
    """A shipboard CTD only casts downwards, so the rule costs it nothing."""
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["1990-02-13T00:00:00"],
            lats=[10.0], lons=[88.0],
            pres=[[0.0, 50.0, 1100.0]],
            temp=[[28.0, 25.0, 4.0]],
            psal=[[33.5, 34.8, 34.9]],
            direction=["D"],
            platform_code="SHINYO MARU",
            wmo="JFCL",
            source="research vessel",
        )
        ds = insitu_tac.read_casts(path)

    assert ds.sizes["profile"] == 1
    assert int(ds.attrs["n_profiles_ascending_dropped"]) == 0
    assert ds.attrs["platform_kind"] == "ctd"


def test_the_instrument_class_is_read_from_the_file_not_the_filename(
    simple_glider,
):
    ds = insitu_tac.read_casts(simple_glider)
    assert ds.attrs["platform_kind"] == "glider"
    assert ds.attrs["wmo_platform_code"] == "2801900"


# ---------------------------------------------------------------------------
# The plugin contract
# ---------------------------------------------------------------------------
def test_the_reader_output_satisfies_the_plugin_contract(simple_glider, tmp_path):
    """D1-D5 in app/plugins.py, checked against the real output."""
    ds = insitu_tac.read_casts(simple_glider)

    assert isinstance(ds, xr.Dataset)                       # D1
    assert ds.data_vars                                     # D2
    assert set(map(str, ds.dims)) <= {"profile", "level"}   # D2
    for name, da in ds.data_vars.items():                   # D4, D5
        assert np.issubdtype(da.dtype, np.floating), name
        assert da.attrs.get("units"), name


def test_the_reader_registers_itself_for_the_insitu_tac_kind():
    registry = plugin_api.PluginRegistry()
    insitu_tac.register(registry)
    assert registry.source_reader("insitu_tac") is not None
    assert "insitu_tac" in {r.kind for r in registry.source_readers()}


def test_salinity_travels_with_its_own_flag_not_temperatures():
    """PSAL and TEMP are flagged independently in this format."""
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as d:
        path = write_tac_file(
            pathlib.Path(d) / "x.nc",
            times=["2018-08-12T00:00:00"],
            lats=[5.0], lons=[80.1],
            pres=[[10.0, 100.0]],
            temp=[[28.5, 24.0]],
            psal=[[33.0, 99.0]],
            temp_qc=[[1.0, 1.0]],
            psal_qc=[[1.0, 4.0]],
        )
        ds = insitu_tac.read_casts(path)

    assert int(ds["TEMP_QC"].values[0, 1]) == 1
    assert int(ds["PSAL_QC"].values[0, 1]) == 4


def test_the_method_string_says_how_depth_was_derived(simple_glider):
    """A number this project serves has to say where it came from."""
    ds = insitu_tac.read_casts(simple_glider)
    method = ds.attrs["reader_method"]
    assert "TEOS-10" in method
    assert "gsw.z_from_p" in method
