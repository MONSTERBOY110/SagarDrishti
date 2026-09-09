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

    # GLORYS is the depth-resolved current source (PS F1), and it is now LIVE:
    # the Copernicus account arrived on 2026-09-09. What this pins is the thing
    # the account revealed, because it is the kind of error that would have
    # shipped quietly.
    #
    # The entry originally named the GLORYS12V1 multi-year REANALYSIS,
    # cmems_mod_glo_phy_my_0.083deg_P1D-m. Probed with real credentials, that
    # product ends 2026-06-23, and every one of this cube's three analysis
    # steps is in July 2026. It could not have produced a single
    # contemporaneous field. The analysis-and-forecast currents product covers
    # them, and that is what is configured.
    cur = reg.get("glorys12_cur")
    assert cur.enabled is True
    assert cur.kind == "copernicus"
    assert cur.dataset_id == "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"
    assert "_my_" not in cur.dataset_id, (
        "the multi-year reanalysis ends 2026-06-23, before every date in this cube"
    )
    assert {v.name for v in cur.variables} == {"uo", "vo"}
    # Temperature and salinity are deliberately NOT taken from Copernicus even
    # though the reanalysis carries them: INCOIS's own analysis is the
    # PS-preferred source and the one the scorecard verifies, and two answers
    # to one question with nothing to choose between them is worse than one.
    assert not {"thetao", "so"} & {v.name for v in cur.variables}
    assert "Copernicus Marine Service" in cur.citation
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


# --- three silent wrongs, each reproduced before it was fixed ---------------
#
# Found by sweeping the codebase for places that assume a source has a depth
# axis, ahead of registering a surface (satellite) source. All three were live
# in shipped code, none of them raised, and each produced a plausible-looking
# wrong picture rather than an error.


def _mixed_dataset():
    """A volumetric variable and a SURFACE variable in one dataset.

    This is the ordinary shape of an ocean-colour file merged beside a model
    field, and it is the shape that broke the canonical-order pass.
    """
    return xr.Dataset(
        {
            "TEMP": (
                ("time", "ZAX", "latitude", "longitude"),
                np.zeros((1, 2, 2, 2), dtype="float32"),
                {"units": "degC"},
            ),
            # Deliberately NOT in canonical order.
            "CHL": (
                ("latitude", "longitude", "time"),
                np.zeros((2, 2, 1), dtype="float32"),
                {"units": "mg/m3"},
            ),
        },
        coords={
            "time": ("time", np.array(["2026-07-30"], dtype="datetime64[ns]")),
            "ZAX": ("ZAX", np.array([5.0, 10.0]), {"positive": "down", "units": "m"}),
            "latitude": ("latitude", np.array([10.0, 11.0])),
            "longitude": ("longitude", np.array([85.0, 86.0])),
        },
    )


def _mixed_spec(**over):
    from app.registry import SourceSpec

    base = dict(
        id="mixed",
        title="mixed",
        kind="erddap_griddap",
        url="x",
        dims={"time": "time", "depth": "ZAX", "lat": "latitude", "lon": "longitude"},
        variables=[{"name": "TEMP"}, {"name": "CHL"}],
    )
    base.update(over)
    return SourceSpec(**base)


def test_a_surface_variable_beside_a_volumetric_one_is_still_put_in_canonical_order():
    """The canonical-order pass used to key on the WHOLE DATASET's dims.

    It built one target order from `ds.dims`, the union over every variable,
    then skipped any variable whose own dims did not match that union exactly.
    So the moment a surface variable shared a dataset with a volumetric one,
    the union contained `depth`, the surface variable never matched, and it was
    left in whatever order the file happened to use.

    Reproduced before the fix: TEMP came back as (time, depth, lat, lon) and
    CHL as (lat, lon, time). The renderer indexes by position, so it would have
    read CHL's TIME axis as latitude. Nothing raised. The comment above that
    code promises the renderer never has to guess an axis, which is exactly
    what it was forcing.
    """
    out = normalize_dataset(_mixed_dataset(), _mixed_spec())

    assert out["TEMP"].dims == ("time", "depth", "lat", "lon")
    assert out["CHL"].dims == ("time", "lat", "lon"), (
        "a surface variable must be ordered by its OWN dims, not by the "
        "dataset-wide union"
    )


def test_a_declared_variable_with_an_unindexable_axis_is_refused():
    """Silently leaving it alone is what allowed the bug above."""
    ds = _mixed_dataset()
    ds["ODD"] = (
        ("time", "latitude", "longitude", "nv"),
        np.zeros((1, 2, 2, 2)),
        {"units": "1"},
    )

    with pytest.raises(ValueError) as err:
        normalize_dataset(ds, _mixed_spec(variables=[{"name": "ODD"}]))

    message = str(err.value)
    assert "ODD" in message and "nv" in message
    assert "canonical" in message


def test_an_auxiliary_variable_with_an_odd_axis_is_left_alone():
    """CF bounds carry an `nv` dim and nothing reads them.

    The refusal above must apply to variables the registry DECLARES, not to
    everything in the file, or an ordinary CF file becomes unloadable.
    """
    ds = _mixed_dataset()
    ds["lat_bnds"] = (("latitude", "nv"), np.zeros((2, 2)), {})

    out = normalize_dataset(ds, _mixed_spec())

    # The canonical RENAME still applies to it, which is right: `latitude`
    # becomes `lat` everywhere in the dataset. What is skipped is the
    # TRANSPOSE, because there is no defined position for `nv`.
    assert out["lat_bnds"].dims == ("lat", "nv")
    assert out["CHL"].dims == ("time", "lat", "lon")


def test_a_cf_override_that_names_nothing_is_refused_at_startup():
    """One letter out, and the defect it was written for stays in the data.

    Reproduced before the fix: an override for `CHLA` on a source whose
    variable is `CHL` left the -1.0E34 fill unmasked, and the served minimum
    came back as -9.999999790214768e+33. Nothing raised. The only symptom would
    have been a colorbar spanning 1e34, with every real value rendered the same
    colour and a legend that looked entirely correct.
    """
    from app.registry import SourceSpec

    with pytest.raises(Exception) as err:
        SourceSpec(
            id="colour",
            title="colour",
            kind="erddap_griddap",
            url="x",
            dims={"time": "time", "lat": "latitude", "lon": "longitude"},
            variables=[{"name": "CHL"}],
            cf_overrides={"CHLA": {"_FillValue": -1.0e34}},
        )

    message = str(err.value)
    assert "CHLA" in message
    assert "CHL" in message, "the message must show what was available"


def test_an_override_for_a_declared_but_unfetched_variable_is_allowed():
    """The registry describes the SOURCE; a download is often a subset.

    `incois_vam_argo` declares corrections for TERR and SERR while the Bay of
    Bengal subset fetches only TEMP and SAL. Refusing that would refuse a
    correct config, so the check is against what the registry declares rather
    than against the variables a file happens to contain.
    """
    from app.registry import SourceSpec

    spec = SourceSpec(
        id="colour",
        title="colour",
        kind="erddap_griddap",
        url="x",
        dims={"time": "time", "lat": "latitude", "lon": "longitude"},
        variables=[{"name": "CHL"}, {"name": "KD490"}],
        cf_overrides={"KD490": {"units": "m-1"}},
    )
    assert "KD490" in spec.cf_overrides


def test_the_argo_pressure_block_is_not_checked_because_nothing_applies_it():
    """cf_overrides is consumed in exactly one place: cf.normalize_dataset.

    That runs only on gridded sources. An Argo file is parsed by app/argo.py,
    which reads the pressure axis itself and never looks at cf_overrides, so
    the `PRES` block on the gdac entries is documentation rather than an
    applied correction. Checking those keys against a variable list they were
    never meant to match would refuse a correct config for the wrong reason,
    and this test is what stops the validator being tightened into doing that.
    """
    from app.registry import SourceSpec

    spec = SourceSpec(
        id="argo_like",
        title="argo",
        kind="gdac_geo",
        url="x",
        variables=[{"name": "TEMP"}, {"name": "PSAL"}],
        cf_overrides={"PRES": {"units": "dbar"}},
    )
    assert spec.cf_overrides["PRES"]["units"] == "dbar"


def test_the_shipped_registry_still_loads():
    """The guards above must not have made the real config unloadable."""
    import pathlib

    from app.registry import load_registry_from

    root = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources.yaml"
    if not root.is_file():
        pytest.skip("no sources.yaml")

    reg = load_registry_from(root)
    assert len(reg.sources) >= 6
    assert reg.has("incois_vam_argo")
