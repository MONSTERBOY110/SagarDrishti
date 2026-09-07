"""CF-convention normalization (TRD M1, TRD §9).

These are the four edge cases CLAUDE.md names by hand, because they are the
ones that silently corrupt a field instead of raising: a fill value painted as
a real temperature, a double-applied scale factor, an inverted depth axis, and
a unit string nobody converted.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from app.cf import normalize_dataset
from app.registry import load_registry


@pytest.fixture
def vam_spec():
    """The real spec from data/sources.yaml -- not a test-local invention."""
    return load_registry().get("incois_vam_argo")


# --- Test 1: fill values ----------------------------------------------------

def test_fill_value_becomes_nan(vam_like_nc, vam_spec):
    """-9999.0 must become NaN, not a -9999 C ocean cell."""
    raw = xr.open_dataset(vam_like_nc, mask_and_scale=False, decode_times=False)
    assert float(raw["TEMP"].isel(time=0, ZAX=0, latitude=0, longitude=0)) == -9999.0

    ds = normalize_dataset(xr.open_dataset(vam_like_nc, decode_times=False), vam_spec)

    land = ds["TEMP"].isel(time=0, depth=0, lat=0, lon=0)
    assert np.isnan(float(land)), "fill value survived normalization"
    assert not (ds["TEMP"] < -100).any(), "a fill value is still being read as data"
    # and the real data is untouched
    assert 28.0 < float(ds["TEMP"].isel(time=0, depth=0, lat=1, lon=1)) < 30.0


def test_alternate_fill_convention(vam_like_nc, vam_spec):
    """The value-added datasets use -1.0E34. An override must handle either."""
    spec = vam_spec.model_copy(deep=True)
    spec.cf_overrides["TEMP"]["_FillValue"] = -1.0e34

    ds = xr.open_dataset(vam_like_nc, decode_times=False, mask_and_scale=False)
    ds["TEMP"].values[0, 0, 1, 1] = -1.0e34
    out = normalize_dataset(ds, spec)

    assert np.isnan(float(out["TEMP"].isel(time=0, depth=0, lat=1, lon=1)))


# --- Test 2: packed integers ------------------------------------------------

def test_scale_factor_applied_exactly_once(packed_nc):
    """scale_factor/add_offset must be applied once, and never to the fill.

    Both directions matter. When xarray has already unpacked (attributes move
    to .encoding) applying again would corrupt every value; when it has not
    (mask_and_scale=False, attributes still in .attrs) we must do the unpacking
    ourselves. The same function has to handle both, or the source registry
    cannot accept files from both kinds of reader.
    """
    from app.cf import apply_packing

    path, expected = packed_nc
    good = ~np.isnan(expected)

    # (a) already unpacked by xarray -> must be a no-op
    unpacked = xr.open_dataset(path)["sst"]
    assert "scale_factor" not in unpacked.attrs
    np.testing.assert_allclose(unpacked.values[good], expected[good], atol=1e-6)
    got = apply_packing(unpacked).values
    np.testing.assert_allclose(got[good], expected[good], atol=1e-6)
    assert np.isnan(got[1, 2]), "the integer _FillValue became a real value"

    # (b) still raw -> must unpack exactly once and mask the sentinel
    raw = xr.open_dataset(path, mask_and_scale=False)["sst"]
    assert raw.attrs["scale_factor"] == 0.01
    assert raw.values[0, 0] == 0 and raw.values[1, 2] == -32768
    got_raw = apply_packing(raw).values
    np.testing.assert_allclose(got_raw[good], expected[good], atol=1e-6)
    assert np.isnan(got_raw[1, 2]), "the integer _FillValue was unpacked as data"


# --- Test 3: the depth axis -------------------------------------------------

def test_depth_axis_is_canonical_and_positive_down(vam_like_nc, vam_spec):
    """ZAX carries no `positive` attribute in the real source (verified
    2026-09-07). The override must supply it, or every depth in the UI is a
    coin flip."""
    raw = xr.open_dataset(vam_like_nc, decode_times=False)
    assert "positive" not in raw["ZAX"].attrs, "fixture drifted from the real source"

    ds = normalize_dataset(raw, vam_spec)

    assert "depth" in ds.dims and "ZAX" not in ds.dims
    depth = ds["depth"]
    assert depth.attrs["positive"] == "down"
    assert depth.attrs["units"] == "m"
    assert (depth.values > 0).all(), "depth must be positive-down metres"
    assert np.all(np.diff(depth.values) > 0), "depth must increase downward"
    assert float(depth[0]) == 5.0 and float(depth[-1]) == 1000.0
    # canonical dim order, so the renderer can index without guessing
    assert ds["TEMP"].dims == ("time", "depth", "lat", "lon")


def test_negative_up_axis_is_flipped(vam_like_nc, vam_spec):
    """A source that stores height (positive up) must be flipped, not renamed.

    GLORYS-family products and several ERDDAP mirrors do this.
    """
    ds = xr.open_dataset(vam_like_nc, decode_times=False)
    # A dimension coordinate is immutable in place; rebuild it as height.
    ds = ds.assign_coords(ZAX=("ZAX", -np.asarray(ds["ZAX"].values)))
    ds["ZAX"].attrs.update(units="METERS", long_name="ZAX")
    spec = vam_spec.model_copy(deep=True)
    spec.cf_overrides["ZAX"]["positive"] = "up"

    out = normalize_dataset(ds, spec)

    assert (out["depth"].values > 0).all()
    assert np.all(np.diff(out["depth"].values) > 0)
    assert float(out["depth"][0]) == 5.0
    # the surface value must still be the surface value after the flip
    assert 28.0 < float(out["TEMP"].isel(time=0, depth=0, lat=1, lon=1)) < 30.0


# --- Test 4: units ----------------------------------------------------------

def test_unit_relabel_does_not_change_magnitudes(vam_like_nc, vam_spec):
    """"degs" is degrees Celsius spelled wrongly -- relabel, never rescale."""
    raw = xr.open_dataset(vam_like_nc, decode_times=False)
    before = float(raw["TEMP"].isel(time=0, ZAX=0, latitude=1, longitude=1))

    ds = normalize_dataset(raw, vam_spec)

    assert ds["TEMP"].attrs["units"] == "degC"
    assert float(ds["TEMP"].isel(time=0, depth=0, lat=1, lon=1)) == pytest.approx(before)


def test_unit_conversion_does_change_magnitudes(vam_like_nc, vam_spec):
    """cm/sec -> m/s is a real conversion (the value-added currents use it).

    Relabelling and converting are different operations and must not be
    conflated: one is a typo fix, the other is arithmetic.
    """
    spec = vam_spec.model_copy(deep=True)
    spec.cf_overrides["TEMP"] = {"units": "cm s-1", "_FillValue": -9999.0}
    spec.variables[0].convert_to = "m s-1"

    raw = xr.open_dataset(vam_like_nc, decode_times=False)
    before = float(raw["TEMP"].isel(time=0, ZAX=0, latitude=1, longitude=1))

    ds = normalize_dataset(raw, spec)

    assert ds["TEMP"].attrs["units"] == "m s-1"
    assert float(ds["TEMP"].isel(time=0, depth=0, lat=1, lon=1)) == pytest.approx(before * 0.01)


def test_unknown_unit_conversion_raises(vam_like_nc, vam_spec):
    """Refuse to guess. A silent no-op conversion is worse than a crash."""
    spec = vam_spec.model_copy(deep=True)
    spec.variables[0].convert_to = "furlongs per fortnight"

    with pytest.raises(ValueError, match="no conversion"):
        normalize_dataset(xr.open_dataset(vam_like_nc, decode_times=False), spec)


# --- registry ---------------------------------------------------------------

def test_registry_matches_the_live_source_shape():
    """sources.yaml is the extensibility surface (PS F3/F6); it must parse and
    must still describe the source we actually verified."""
    reg = load_registry()
    spec = reg.get("incois_vam_argo")

    assert spec.enabled is True
    assert spec.kind == "erddap_griddap"
    assert spec.dataset_id == "incois_argo_10d_VAM"
    assert spec.dims.depth == "ZAX"
    assert spec.cf_overrides["ZAX"]["positive"] == "down"
    assert {v.name for v in spec.variables} >= {"TEMP", "SAL"}

    # GLORYS12 is registered but disabled pending credentials (ADR-0003).
    glorys = reg.get("glorys12")
    assert glorys.enabled is False and glorys.disabled_reason

    # Only enabled sources are offered to the client.
    assert "glorys12" not in [s.id for s in reg.enabled()]
    assert "incois_vam_argo" in [s.id for s in reg.enabled()]


# --- the depth axis must be STRICTLY increasing -----------------------------
#
# The module docstring has promised "depth positive down, metres, strictly
# increasing" from the start, and the tests above assert it, but nothing
# enforced it at runtime: `sortby("depth")` gives non-DECREASING, so a source
# with a duplicated level sailed through and produced a zero-thickness cell.
#
# That matters because every consumer divides by that thickness. The D26 plugin
# interpolates a crossing as (threshold - upper) / (lower - upper), and an
# isosurface extractor does the same per cell edge. A duplicate level makes
# both divide by zero, and numpy answers inf or nan rather than raising, so the
# result would be a hole in a surface with no error anywhere to explain it.

def _cube_with_depths(depths, spec_id="local_cube"):
    """A minimal normalized-shape dataset with a chosen depth axis."""
    import numpy as np
    import xarray as xr

    from app.registry import load_registry

    n = len(depths)
    data = np.arange(float(n * 2 * 2)).reshape(1, n, 2, 2)
    ds = xr.Dataset(
        {"TEMP": (("time", "depth", "lat", "lon"), data, {"units": "degC"})},
        coords={
            "time": ("time", np.array(["2026-07-30"], dtype="datetime64[ns]")),
            "depth": ("depth", np.asarray(depths, dtype="float64"),
                      {"units": "m", "positive": "down"}),
            "lat": ("lat", np.array([10.0, 11.0])),
            "lon": ("lon", np.array([85.0, 86.0])),
        },
    )
    return ds, load_registry().get(spec_id)


def test_a_duplicated_depth_level_is_refused(tmp_path):
    """Two levels at the same depth make a cell with no interior."""
    ds, spec = _cube_with_depths([5.0, 10.0, 10.0, 20.0])

    with pytest.raises(ValueError) as err:
        normalize_dataset(ds, spec)

    message = str(err.value)
    assert "strictly increasing" in message
    assert "10.0" in message, "the message must name the level that repeats"
    assert "zero-thickness" in message or "thickness" in message
    # It must say what to do, not just that something is wrong.
    assert "source file" in message


def test_a_non_finite_depth_level_is_refused():
    """A NaN depth cannot be sorted, interpolated across, or drawn.

    Left alone it also defeats the duplicate check itself, because every
    comparison against NaN is False and `np.diff` propagates it, so the
    strictly-increasing test would pass a NaN through while rejecting a
    duplicate. Checking finiteness explicitly closes that.
    """
    ds, spec = _cube_with_depths([5.0, float("nan"), 20.0])

    with pytest.raises(ValueError) as err:
        normalize_dataset(ds, spec)

    assert "non-finite" in str(err.value)


def test_an_unsorted_but_distinct_depth_axis_is_accepted_and_sorted():
    """Out of order is a fixable presentation problem, not a broken file.

    ERDDAP serves both orders and the sort is what the normalizer is for. Only
    a duplicate is unfixable without inventing a rule for which level wins.
    """
    ds, spec = _cube_with_depths([20.0, 5.0, 10.0])

    out = normalize_dataset(ds, spec)

    assert list(out["depth"].values) == [5.0, 10.0, 20.0]
    assert np.all(np.diff(out["depth"].values) > 0)


def test_the_shipped_cube_has_a_strictly_increasing_depth_axis():
    """The guard would be worthless if the real cube could not pass it."""
    import pathlib

    import xarray as xr

    store = (
        pathlib.Path(__file__).resolve().parents[3] / "data" / "cube" / "incois_vam_bob.zarr"
    )
    if not store.is_dir():
        pytest.skip("no local cube; run tools/fetch_sample.py then tools/preprocess.py")

    with xr.open_zarr(store) as ds:
        depths = np.asarray(ds["depth"].values, dtype="float64")

    assert depths.size == 24
    assert np.all(np.isfinite(depths))
    assert np.all(np.diff(depths) > 0), "the shipped cube violates its own contract"
    assert depths[0] == 5.0 and depths[-1] == 2000.0
