"""The F6 extension points (PS "Extensible Design", PRD F6, PRD section 11 step 6).

PRD section 11 step 6 promises a judge that we register a new product LIVE on
stage and it appears in the variable selector. That promise is the reason this
file exists and is this long: "register a plugin in 60 seconds" is a stage move
with an audience, so every step of it (drop a file, reload, see it listed,
compute a real number from it) is a test rather than a hope.

The other half of the file is about refusing. A plugin that fails silently on
stage is worse than one that refuses to load, and a derived product that
invents a value on land breaks binding rule 7 far more convincingly than raw
data ever could -- the number looks computed, so it looks trustworthy.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from app import plugins as P
from app.plugins import PluginError

#: The shipped plugin directory. Loaded by path, so the tests exercise exactly
#: what a deployment loads, not a copy of it.
PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugins"
DOCS = Path(__file__).resolve().parents[3] / "docs" / "PLUGINS.md"

#: The kind the end-to-end reader tests use. PluginRegistry is kind-agnostic,
#: but registry.SourceKind (a closed Literal, and not this file's to widen) is
#: what decides which kinds data/sources.yaml may NAME -- so the reader path is
#: proved end to end with a kind already in that Literal, and gains
#: mooring/hf_radar/adcp when the widening lands. See the test below.
READER_KIND = "mqtt"

#: Marks a fenced block in docs/PLUGINS.md as a copy-paste plugin example.
#: Extracting on an explicit marker (rather than "every python fence") is what
#: lets test 34 fail loudly when the docs are edited instead of skipping.
EXAMPLE_MARKER = re.compile(r"#\s*plugin-example:\s*(\S+)\s*\n")

GOOD_PLUGIN = '''
"""A minimal derived product, for tests."""
import numpy as np


def compute(ds):
    return np.asarray(ds["TEMP"].values, dtype="float64")[0] * 0.0 + np.where(
        np.isfinite(np.asarray(ds["TEMP"].values, dtype="float64")).any(axis=0), 1.0, np.nan
    )


def register(registry):
    registry.register_derived_product(
        name="ONES",
        label="One where there is water",
        units="1",
        requires={"TEMP": "degC"},
        compute=compute,
        method="1.0 wherever the column has any finite temperature level",
    )
'''


@pytest.fixture(autouse=True)
def _isolate_plugin_state():
    """Plugin discovery is cached, and several tests re-scan the same directory.

    Clearing before AND after keeps this file independent of the order pytest
    runs it in, and of the other test modules.
    """
    P.clear_plugin_cache()
    yield
    P.clear_plugin_cache()


def _write(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _column_ds(depths, temps, *, units="degC", var="TEMP"):
    """A one-cell (depth, lat, lon) dataset, the shape compute() is handed."""
    arr = np.asarray(temps, dtype="float64").reshape((len(depths), 1, 1))
    ds = xr.Dataset(
        {var: (("depth", "lat", "lon"), arr)},
        coords={
            "depth": ("depth", np.asarray(depths, dtype="float64")),
            "lat": ("lat", np.array([12.5])),
            "lon": ("lon", np.array([86.5])),
        },
    )
    ds[var].attrs["units"] = units
    return ds


def _cube_ds(depths, field, *, units="degC"):
    """A (time, depth, lat, lon) cube, the shape store.select_field is handed."""
    field = np.asarray(field, dtype="float64")
    nt, nz, ny, nx = field.shape
    ds = xr.Dataset(
        {"TEMP": (("time", "depth", "lat", "lon"), field)},
        coords={
            "time": ("time", np.array(["2026-07-30"] * nt, dtype="datetime64[ns]")),
            "depth": ("depth", np.asarray(depths, dtype="float64")),
            "lat": ("lat", np.arange(ny, dtype="float64") + 10.5),
            "lon": ("lon", np.arange(nx, dtype="float64") + 85.5),
        },
    )
    ds["TEMP"].attrs["units"] = units
    ds["depth"].attrs.update(units="m", positive="down")
    return ds


# --- discovery --------------------------------------------------------------

def test_a_plugin_in_the_directory_registers_and_is_discoverable(tmp_path):
    path = _write(tmp_path, "ones.py", GOOD_PLUGIN)

    reg = P.load_plugins(directory=tmp_path, strict=True)

    assert [p.name for p in reg.derived_products()] == ["ONES"]
    assert reg.derived("ONES").plugin == "ones"
    described = reg.describe()
    origins = [p["origin"] for p in described["plugins"]]
    assert any(str(path) in o for o in origins), f"describe() hid the source file: {origins}"
    assert described["derived_products"][0]["units"] == "1"


def test_a_plugin_directory_that_does_not_exist_is_not_an_error(tmp_path):
    """A deployment with no plugins is normal, not broken."""
    reg = P.load_plugins(directory=tmp_path / "nope", strict=True)
    assert reg.derived_products() == []
    assert reg.failures == ()


def test_a_module_without_a_register_hook_is_rejected_by_name(tmp_path):
    path = _write(tmp_path, "no_hook.py", "X = 1\n")

    reg = P.load_plugins(directory=tmp_path)

    assert reg.derived_products() == []
    assert len(reg.failures) == 1
    msg = reg.failures[0].error
    assert "no_hook.py" in msg and "register(registry)" in msg


def test_a_plugin_that_raises_at_import_does_not_crash_startup_and_its_neighbour_still_loads(
    tmp_path,
):
    """One broken file must not take the working ones with it."""
    _write(tmp_path, "ones.py", GOOD_PLUGIN)
    _write(tmp_path, "broken.py", "raise RuntimeError('deliberate import failure')\n")

    reg = P.load_plugins(directory=tmp_path)

    assert [p.name for p in reg.derived_products()] == ["ONES"]
    assert len(reg.failures) == 1
    assert "deliberate import failure" in reg.failures[0].error
    assert "broken.py" in reg.failures[0].origin


def test_strict_mode_raises_instead_of_recording_a_failure(tmp_path):
    _write(tmp_path, "broken.py", "raise RuntimeError('deliberate import failure')\n")

    with pytest.raises(PluginError, match="deliberate import failure"):
        P.load_plugins(directory=tmp_path, strict=True)


def test_reload_picks_up_a_file_dropped_after_the_first_load(tmp_path):
    """This is the stage move in PRD section 11 step 6, so it is a test."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    first = P.load_plugins(directory=tmp_path, strict=True)
    assert first.derived_products() == []

    _write(tmp_path, "ones.py", GOOD_PLUGIN)
    # Without the reload the cached registry is returned, which is the whole
    # reason POST /plugins/reload exists.
    assert P.load_plugins(directory=tmp_path, strict=True).derived_products() == []

    after = P.reload_plugins(directory=tmp_path, strict=True)
    assert [p.name for p in after.derived_products()] == ["ONES"]


def test_a_file_with_a_leading_underscore_is_disabled(tmp_path):
    """The stage needs a way to switch a plugin off without deleting it."""
    _write(tmp_path, "_ones.py", GOOD_PLUGIN)
    reg = P.load_plugins(directory=tmp_path, strict=True)
    assert reg.derived_products() == []
    assert reg.failures == ()


# --- registration validation (R1 - R9) --------------------------------------

def _register_one(**kwargs):
    reg = P.PluginRegistry()
    defaults = dict(
        name="D26",
        label="Depth of the 26 degC isotherm",
        units="m",
        requires={"TEMP": "degC"},
        compute=lambda ds: np.zeros(()),
        method="a stated method",
    )
    defaults.update(kwargs)
    reg.register_derived_product(**defaults)
    return reg


def test_a_product_with_no_units_is_refused_with_a_message_about_provenance():
    with pytest.raises(PluginError, match="R3") as exc:
        _register_one(units="  ")
    assert "unit" in str(exc.value)


def test_a_product_with_no_method_is_refused():
    """The method string is echoed as provenance, so it cannot be optional."""
    with pytest.raises(PluginError, match="R7"):
        _register_one(method="")


def test_a_product_name_that_is_not_url_safe_is_refused():
    with pytest.raises(PluginError, match="R1"):
        _register_one(name="D 26 !")


def test_a_product_with_an_empty_label_is_refused():
    with pytest.raises(PluginError, match="R2"):
        _register_one(label="")


def test_a_product_with_no_required_variables_is_refused():
    with pytest.raises(PluginError, match="R4"):
        _register_one(requires={})


def test_a_compute_with_the_wrong_arity_is_refused_at_registration():
    with pytest.raises(PluginError, match="R5"):
        _register_one(compute=lambda ds, threshold: None)


def test_an_unknown_output_shape_is_refused():
    with pytest.raises(PluginError, match="R6"):
        _register_one(output="volume")


def test_two_plugins_claiming_the_same_product_name_collide_loudly_naming_both(tmp_path):
    _write(tmp_path, "first.py", GOOD_PLUGIN)
    _write(tmp_path, "second.py", GOOD_PLUGIN)

    reg = P.load_plugins(directory=tmp_path)

    assert len(reg.derived_products()) == 1, "a collision must not silently overwrite"
    assert len(reg.failures) == 1
    msg = reg.failures[0].error
    assert "R8" in msg and "first" in msg and "second" in msg


# --- the source-reader extension point --------------------------------------

def _spec(kind: str, **kw):
    from app.registry import SourceSpec

    payload = dict(id="test_source", title="Test source", kind=kind, url="file:///dev/null")
    payload.update(kw)
    return SourceSpec.model_validate(payload)


def test_a_source_reader_registers_a_new_kind_and_is_returned_for_it():
    reg = P.PluginRegistry()
    reg.register_source_reader(kind="mooring", open=lambda spec: None, doc="RAMA moorings")

    assert reg.source_reader("mooring").doc == "RAMA moorings"
    assert reg.source_reader("hf_radar") is None


def test_a_reader_kind_that_is_not_config_safe_is_refused():
    reg = P.PluginRegistry()
    with pytest.raises(PluginError, match="R9"):
        reg.register_source_reader(kind="HF Radar", open=lambda spec: None)


def test_two_readers_claiming_the_same_kind_collide_loudly():
    reg = P.PluginRegistry()
    reg.register_source_reader(kind="mooring", open=lambda spec: None)
    with pytest.raises(PluginError, match="R9"):
        reg.register_source_reader(kind="mooring", open=lambda spec: None)


def test_a_kind_with_no_registered_reader_is_reported_not_guessed():
    reg = P.PluginRegistry()
    with pytest.raises(PluginError) as exc:
        P.open_source(_spec("mqtt"), registry=reg)
    msg = str(exc.value)
    assert "mqtt" in msg and "docs/PLUGINS.md" in msg


def _reader_registry(dataset):
    reg = P.PluginRegistry()
    reg.register_source_reader(kind=READER_KIND, open=lambda spec: dataset)
    return reg


def test_a_reader_that_returns_a_non_cf_dataset_is_refused():
    """A reader is a data-plane component, so it is held to the cf.py contract."""
    upside_down = _column_ds([100.0, 50.0, 5.0], [22.0, 26.0, 29.0])
    with pytest.raises(PluginError, match="D3"):
        P.open_source(_spec(READER_KIND), registry=_reader_registry(upside_down))

    integer_temps = _column_ds([5.0, 50.0, 100.0], [29, 26, 22])
    integer_temps["TEMP"] = integer_temps["TEMP"].astype("int16")
    with pytest.raises(PluginError, match="D4"):
        P.open_source(_spec(READER_KIND), registry=_reader_registry(integer_temps))

    no_units = _column_ds([5.0, 50.0, 100.0], [29.0, 26.0, 22.0], units="")
    with pytest.raises(PluginError, match="D5"):
        P.open_source(_spec(READER_KIND), registry=_reader_registry(no_units))

    weird_dims = xr.Dataset(
        {"TEMP": (("ZAX", "N_PROF"), np.zeros((2, 2)))},
    )
    weird_dims["TEMP"].attrs["units"] = "degC"
    with pytest.raises(PluginError, match="D2"):
        P.open_source(_spec(READER_KIND), registry=_reader_registry(weird_dims))

    with pytest.raises(PluginError, match="D1"):
        P.open_source(_spec(READER_KIND), registry=_reader_registry("a dataset, honest"))


def test_a_reader_that_returns_a_conforming_dataset_is_accepted():
    good = _column_ds([5.0, 50.0, 100.0], [29.0, 26.0, 22.0])

    out = P.open_source(_spec(READER_KIND), registry=_reader_registry(good))

    assert list(out.data_vars) == ["TEMP"]


def test_a_reader_registers_for_a_sensor_kind_the_registry_cannot_yet_name():
    """The one remaining gap for the PS's literal moorings/HF-radar/ADCP ask.

    PluginRegistry is kind-agnostic, so those readers register and are returned
    today. What is still closed is registry.SourceKind, the Literal deciding
    which kinds data/sources.yaml may NAME. Widening it is one line in a file
    this agent does not own, so it ships as an integration snippet -- and this
    test passes before and after, rather than letting the stage find out.
    """
    import typing

    from app.registry import SourceKind

    reg = P.PluginRegistry()
    for kind in ("mooring", "hf_radar", "adcp"):
        reg.register_source_reader(kind=kind, open=lambda spec: None, doc=f"{kind} reader")
        assert reg.source_reader(kind) is not None

    allowed = set(typing.get_args(SourceKind))
    assert READER_KIND in allowed, (
        "the end-to-end reader tests need a kind data/sources.yaml can already "
        f"name; SourceKind allows {sorted(allowed)}"
    )


# --- the D26 example, hand-checked ------------------------------------------

def _d26():
    """The shipped example plugin, loaded exactly as a deployment loads it."""
    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)
    prod = reg.derived("D26")
    assert prod is not None, f"D26 not registered by {PLUGIN_DIR}"
    return prod


def _d26_values(ds):
    """The D26 field alone, with the run notes discarded.

    `compute` returns `(values, notes)` since the contract gained an optional
    per-run notes dict: `method` describes what a product ALWAYS does and
    `n_valid` is counted generically, so neither could say that seven columns
    of this particular field crossed 26 degC twice. Tests that only care about
    the numbers go through here; the ones that care about the notes unpack the
    tuple themselves and say so.
    """
    return np.asarray(P.compute_values(_d26(), ds))


def test_the_shipped_example_plugin_loads_from_the_real_plugin_directory():
    prod = _d26()
    assert prod.units == "m"
    assert prod.requires == {"TEMP": "degC"}
    assert prod.output == "surface"
    assert "26" in prod.method and "no extrapolation" in prod.method


def test_d26_matches_a_hand_checked_synthetic_column():
    # T(50 m) = 28.546, T(75 m) = 25.211, so the 26 degC crossing sits between
    # them:  f = (28.546 - 26) / (28.546 - 25.211) = 0.7634182...
    #        z = 50 + f * (75 - 50)                = 69.0854...
    # These are the real values at 12.5 N, 86.5 E on 2026-07-30.
    ds = _column_ds(
        [5.0, 10.0, 20.0, 50.0, 75.0, 100.0],
        [29.305, 29.168, 28.980, 28.546, 25.211, 22.860],
    )
    expected = 50.0 + (28.546 - 26.0) / (28.546 - 25.211) * (75.0 - 50.0)

    got = float(_d26_values(ds).ravel()[0])

    assert got == pytest.approx(expected, abs=1e-9)
    assert round(got, 4) == 69.0855


def test_d26_hits_a_level_exactly_when_the_temperature_is_exactly_26():
    ds = _column_ds([10.0, 20.0, 30.0], [28.0, 26.0, 24.0])
    got = float(_d26_values(ds).ravel()[0])
    assert got == pytest.approx(20.0), "an exact level must be reported, not interpolated past"


def test_d26_is_nan_for_an_all_warm_column_and_does_not_extrapolate_below():
    """16 real shelf columns in our own cube look exactly like this."""
    ds = _column_ds([5.0, 25.0, 75.0], [28.9, 28.1, 26.9])
    assert not np.isfinite(_d26_values(ds).ravel()[0])


def test_d26_is_nan_for_an_all_cold_column_and_does_not_extrapolate_above():
    ds = _column_ds([5.0, 25.0, 75.0], [24.0, 20.0, 14.0])
    assert not np.isfinite(_d26_values(ds).ravel()[0])


def test_d26_is_nan_on_land_where_every_level_is_missing():
    ds = _column_ds([5.0, 25.0, 75.0], [np.nan, np.nan, np.nan])
    assert not np.isfinite(_d26_values(ds).ravel()[0])


def test_d26_refuses_to_interpolate_across_a_missing_level():
    """28.0, NaN, 25.0 straddles 26 degC but there is no measured bracket."""
    ds = _column_ds([10.0, 20.0, 30.0], [28.0, np.nan, 25.0])
    assert not np.isfinite(_d26_values(ds).ravel()[0])


def test_d26_treats_a_non_finite_level_as_no_measurement():
    """A NaN fails the warm/cold comparisons by itself; an infinity does not.

    Without the explicit finite test an inf level is accepted as a bracket and
    divides to NaN with a RuntimeWarning, which is the same answer arrived at
    by accident rather than by rule.
    """
    ds = _column_ds([10.0, 20.0, 30.0], [np.inf, 25.0, 24.0])
    with np.errstate(all="raise"):
        out = _d26_values(ds)
    assert not np.isfinite(out.ravel()[0])


def test_d26_takes_the_shallowest_crossing_when_the_column_has_an_inversion():
    ds = _column_ds([5.0, 10.0, 20.0, 30.0, 50.0], [28.0, 25.0, 27.0, 24.0, 20.0])
    expected = 5.0 + (28.0 - 26.0) / (28.0 - 25.0) * (10.0 - 5.0)
    got = float(_d26_values(ds).ravel()[0])
    assert got == pytest.approx(expected)
    assert got < 10.0, "a deeper crossing was reported over a shallower one"


def test_d26_uses_the_real_level_spacing_and_not_an_assumed_dz():
    """The real cube's levels run 5, 10, 20, 30, 50, 75 ... -- never uniform."""
    ds = _column_ds([5.0, 150.0], [27.0, 24.0])
    expected = 5.0 + (27.0 - 26.0) / (27.0 - 24.0) * (150.0 - 5.0)
    got = float(_d26_values(ds).ravel()[0])
    assert got == pytest.approx(expected)
    assert got == pytest.approx(53.3333, abs=1e-4)


def test_d26_is_computed_per_column_across_a_grid():
    depths = [5.0, 50.0, 100.0]
    field = np.array(
        [
            [[29.0, 29.0], [29.0, np.nan]],       # 5 m, one land cell
            [[28.0, 27.0], [24.0, np.nan]],       # 50 m
            [[22.0, 25.0], [20.0, np.nan]],       # 100 m
        ]
    )
    ds = xr.Dataset(
        {"TEMP": (("depth", "lat", "lon"), field)},
        coords={
            "depth": ("depth", np.asarray(depths)),
            "lat": ("lat", np.array([10.5, 11.5])),
            "lon": ("lon", np.array([85.5, 86.5])),
        },
    )
    ds["TEMP"].attrs["units"] = "degC"

    out = _d26_values(ds)

    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(50.0 + (28.0 - 26.0) / (28.0 - 22.0) * 50.0)
    assert out[0, 1] == pytest.approx(50.0 + (27.0 - 26.0) / (27.0 - 25.0) * 50.0)
    assert out[1, 0] == pytest.approx(5.0 + (29.0 - 26.0) / (29.0 - 24.0) * 45.0)
    assert not np.isfinite(out[1, 1])


# --- compute-output validation (C1 - C5) ------------------------------------

def _compute_with(fn, *, output="surface", units="m", cube=None, **kw):
    reg = P.PluginRegistry()
    reg.register_derived_product(
        name="PROBE",
        label="Probe",
        units=units,
        requires={"TEMP": "degC"},
        compute=fn,
        method="a stated method",
        output=output,
    )
    ds = cube if cube is not None else _cube_ds(
        [5.0, 50.0, 100.0],
        np.array([[[[29.0, np.nan]], [[26.5, np.nan]], [[22.0, np.nan]]]]),
    )
    return P.compute_derived(
        "test_source", "PROBE", ds,
        bbox=(80.0, 5.0, 95.0, 25.0), time="2026-07-30", registry=reg, **kw
    )


def test_a_product_that_invents_a_value_on_land_is_rejected():
    """C5 is the machine-checkable form of binding rule 7."""
    with pytest.raises(PluginError, match="C5") as exc:
        _compute_with(lambda ds: np.zeros(ds["TEMP"].shape[1:], dtype="float64"))
    assert "land" in str(exc.value) or "missing" in str(exc.value)


def test_a_product_returning_an_integer_array_is_rejected():
    """C2: an int array cannot hold NaN, so it cannot admit missing data."""
    with pytest.raises(PluginError, match="C2"):
        _compute_with(lambda ds: np.zeros(ds["TEMP"].shape[1:], dtype="int32"))


def test_a_product_returning_the_wrong_shape_is_rejected():
    with pytest.raises(PluginError, match="C3"):
        _compute_with(lambda ds: np.full((7, 7), np.nan))


def test_a_product_returning_inf_is_rejected():
    def compute(ds):
        out = np.full(ds["TEMP"].shape[1:], np.nan)
        out[0, 0] = np.inf
        return out
    with pytest.raises(PluginError, match="C4"):
        _compute_with(compute)


def test_a_product_returning_something_that_is_not_an_array_is_rejected():
    with pytest.raises(PluginError, match="C1"):
        _compute_with(lambda ds: "69 metres")


def test_a_compute_that_raises_is_reported_with_the_plugin_named():
    with pytest.raises(PluginError, match="PROBE") as exc:
        _compute_with(lambda ds: 1 / 0)
    assert "ZeroDivisionError" in str(exc.value)


def test_a_dataarray_result_is_accepted_as_well_as_an_ndarray():
    def compute(ds):
        arr = np.asarray(ds["TEMP"].values, dtype="float64")
        good = np.isfinite(arr).any(axis=0)
        return xr.DataArray(
            np.where(good, 1.0, np.nan), dims=("lat", "lon"), coords={"lat": ds["lat"], "lon": ds["lon"]}
        )
    slab, _prov = _compute_with(compute, units="1")
    assert slab.values.shape == (1, 2)


# --- the catalog surface ----------------------------------------------------

@pytest.fixture
def fixture_cube(cube_dir, monkeypatch):
    """Point settings at conftest's synthetic cube (source_id incois_vam_argo)."""
    from app.config import get_settings
    from app.store import clear_caches

    monkeypatch.setenv("SAGAR_CUBE", str(cube_dir))
    get_settings.cache_clear()
    clear_caches()
    yield cube_dir
    get_settings.cache_clear()
    clear_caches()


def test_the_derived_product_appears_in_a_catalog_style_listing(fixture_cube):
    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)

    entries = P.derived_variables("incois_vam_argo", registry=reg)

    d26 = next(e for e in entries if e["name"] == "D26")
    assert d26["units"] == "m"
    assert d26["label"]
    assert d26["derived"] is True
    assert d26["plugin"] == "d26_isotherm"
    assert d26["derived_from"] == ["TEMP"]
    assert d26["method"]
    assert d26["params"]["threshold"] == 26.0


def test_a_product_whose_required_variable_is_absent_is_not_listed(fixture_cube):
    reg = P.PluginRegistry()
    reg.register_derived_product(
        name="CHLINT", label="Integrated chlorophyll", units="mg m-2",
        requires={"CHL": None}, compute=lambda ds: None, method="stated",
    )
    # conftest's cube carries TEMP only. Offering an undrawable variable is the
    # exact failure /catalog already refuses for un-materialized sources.
    assert P.derived_variables("incois_vam_argo", registry=reg) == []


def test_a_product_restricted_by_applies_to_is_only_listed_for_that_source(fixture_cube):
    reg = P.PluginRegistry()
    reg.register_derived_product(
        name="ONLYGLO", label="GLORYS only", units="m", requires={"TEMP": "degC"},
        compute=lambda ds: None, method="stated", applies_to=("cmems_glorys12",),
    )
    assert P.derived_variables("incois_vam_argo", registry=reg) == []


def test_a_product_that_shadows_a_real_cube_variable_is_not_offered_and_is_reported(fixture_cube):
    reg = P.PluginRegistry()
    reg.register_derived_product(
        name="TEMP", label="Shadow", units="degC", requires={"TEMP": "degC"},
        compute=lambda ds: None, method="stated",
    )

    assert P.derived_variables("incois_vam_argo", registry=reg) == []

    assert len(reg.failures) == 1
    assert "shadows" in reg.failures[0].error and "incois_vam_argo" in reg.failures[0].error


def test_an_unlisted_derived_product_name_is_a_key_error_not_a_wrong_number(fixture_cube):
    from app import store

    ds, _ref = store.open_cube("incois_vam_argo")
    with pytest.raises(KeyError):
        P.compute_derived(
            "incois_vam_argo", "NOSUCH", ds,
            bbox=(85.0, 10.0, 88.0, 14.0), time="2026-07-30", registry=P.PluginRegistry(),
        )


# --- the served slab and its provenance -------------------------------------

def test_the_derived_field_carries_dataset_timestamp_method_and_coverage_provenance(fixture_cube):
    from app import store

    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)
    ds, ref = store.open_cube("incois_vam_argo")

    slab, prov = P.compute_derived(
        "incois_vam_argo", "D26", ds,
        bbox=(85.0, 10.0, 88.0, 14.0), time="2026-07-30T00:00:00Z",
        all_depths=True, registry=reg,
    )

    assert prov["source_id"] == "incois_vam_argo"
    assert prov["time"] == slab.time == "2026-07-30T00:00:00Z"
    assert prov["citation"] == ref.provenance["citation"]
    assert prov["derived"] is True
    assert prov["derived_from"] == ["TEMP"]
    assert "26" in prov["method"]
    assert prov["params"]["threshold"] == 26.0
    assert prov["plugin"] == "d26_isotherm"
    assert prov["units"] == "m"
    # The honesty counter: a judge sees the coverage, not a picture that
    # implies the whole box was computed.
    assert prov["n_cells"] == 12
    assert prov["n_valid"] == 11  # conftest's land cell at lat[0], lon[0]


def test_a_surface_product_is_served_as_a_single_level_at_the_surface(fixture_cube):
    from app import store

    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)
    ds, _ref = store.open_cube("incois_vam_argo")

    slab, _prov = P.compute_derived(
        "incois_vam_argo", "D26", ds,
        bbox=(85.0, 10.0, 88.0, 14.0), time="2026-07-30", all_depths=True, registry=reg,
    )

    # The existing volumetric client asks for the whole column in one call, so
    # a 2-D diagnostic is served as one level. That single 0.0 is a TRANSPORT
    # PLACEHOLDER, not a level the field sits at, and the response says so.
    assert slab.depths == [0.0]
    assert slab.values.shape == (1, len(slab.lats), len(slab.lons))
    assert slab.units == "m"
    assert _prov["surface_level_is_a_placeholder"] is True

    single, p2 = P.compute_derived(
        "incois_vam_argo", "D26", ds,
        bbox=(85.0, 10.0, 88.0, 14.0), time="2026-07-30", registry=reg,
    )
    assert single.values.shape == (len(single.lats), len(single.lons))
    # NO FABRICATED DEPTH. This used to be 0.0, and /field answered
    # `"depth": 0.0` for a field whose own values run from 41 to 96 metres: a
    # reader was told the slab came from the surface level while the field
    # describes the whole water column and its values ARE depths. There is no
    # depth to report for a surface product, so none is reported.
    assert single.depths is None
    assert single.depth is None, (
        "a surface product must not claim to have come from a depth"
    )
    # And the placeholder flag is absent here, because there is no placeholder:
    # a flag that appeared on every response would stop meaning anything.
    assert "surface_level_is_a_placeholder" not in p2


def test_a_column_product_is_served_level_by_level_like_a_stored_variable():
    depths = [5.0, 50.0, 100.0]
    cube = _cube_ds(depths, np.array([[[[29.0, np.nan]], [[26.5, np.nan]], [[22.0, np.nan]]]]))

    def anomaly(ds):
        arr = np.asarray(ds["TEMP"].values, dtype="float64")
        return arr - 28.0

    full, _p = _compute_with(anomaly, output="column", units="degC", cube=cube, all_depths=True)
    assert full.depths == depths
    assert full.values.shape == (3, 1, 2)

    one, _p2 = _compute_with(anomaly, output="column", units="degC", cube=cube, depth=60.0)
    assert one.depth == 50.0
    assert one.values.shape == (1, 2)
    assert one.values[0, 0] == pytest.approx(-1.5)


def test_a_product_whose_required_units_do_not_match_the_cube_is_refused(fixture_cube):
    """Computing D26 from Kelvin gives a plausible-looking wrong answer."""
    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)
    cube = _cube_ds(
        [5.0, 50.0, 100.0],
        np.array([[[[302.0, np.nan]], [[299.5, np.nan]], [[295.0, np.nan]]]]),
        units="degK",
    )

    with pytest.raises(PluginError) as exc:
        P.compute_derived(
            "test_source", "D26", cube,
            bbox=(80.0, 5.0, 95.0, 25.0), time="2026-07-30", registry=reg,
        )
    msg = str(exc.value)
    assert "degC" in msg and "degK" in msg


def test_a_bad_bbox_or_time_on_a_derived_request_still_raises_subset_error(fixture_cube):
    """The derived path reuses store's validated refusals, it does not reinvent them."""
    from app import store

    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)
    ds, _ref = store.open_cube("incois_vam_argo")

    with pytest.raises(store.SubsetError, match="outside this dataset"):
        P.compute_derived(
            "incois_vam_argo", "D26", ds,
            bbox=(10.0, -40.0, 20.0, -30.0), time="2026-07-30", registry=reg,
        )

    with pytest.raises(store.SubsetError, match="outside the available range"):
        P.compute_derived(
            "incois_vam_argo", "D26", ds,
            bbox=(85.0, 10.0, 88.0, 14.0), time="1998-01-01", registry=reg,
        )


# --- the docs, and the offline guard ----------------------------------------

def _examples_from_docs() -> dict[str, str]:
    text = DOCS.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", text, flags=re.S):
        m = EXAMPLE_MARKER.match(block)
        if m:
            found[m.group(1)] = block
    return found


def test_the_worked_examples_in_docs_plugins_md_actually_run(tmp_path):
    """The copy-paste in the docs is a stage artifact, so it must not rot."""
    examples = _examples_from_docs()
    assert set(examples) >= {"d20_isotherm.py", "mooring_csv.py"}, (
        "docs/PLUGINS.md lost a block marked `# plugin-example: <filename>`; "
        f"found {sorted(examples)}. Re-mark the fence rather than deleting this test."
    )

    for filename, body in examples.items():
        _write(tmp_path, filename, body)

    reg = P.load_plugins(directory=tmp_path, strict=True)

    assert "D20" in [p.name for p in reg.derived_products()]
    assert reg.source_reader("mooring") is not None

    # And the documented D20 actually computes: the same column as D26's
    # hand check crosses 20 degC between 100 m and 125 m.
    ds = _column_ds(
        [5.0, 50.0, 75.0, 100.0, 125.0],
        [29.305, 28.546, 25.211, 22.860, 19.880],
    )
    got = float(np.asarray(reg.derived("D20").compute(ds)).ravel()[0])
    expected = 100.0 + (22.860 - 20.0) / (22.860 - 19.880) * 25.0
    assert got == pytest.approx(expected)


def test_the_plugins_directory_imports_no_network_client():
    """tests/test_offline.py scans app/ only, and a plugin is the obvious hiding place."""
    banned = {"requests", "httpx", "aiohttp", "urllib3", "urllib.request", "ftplib", "paramiko"}
    offenders: dict[str, set[str]] = {}

    for path in sorted(PLUGIN_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = {b for b in banned if f"import {b}" in text or f"from {b}" in text}
        if hits:
            offenders[path.name] = hits

    assert not offenders, (
        f"network clients imported inside services/api/plugins: {offenders}. "
        "Network access belongs in tools/fetch_sample.py only."
    )


def test_entry_point_discovery_needs_no_install_and_no_network(tmp_path):
    """The second discovery channel must cost nothing when nothing is installed."""
    reg = P.load_plugins(directory=tmp_path, strict=True)
    assert reg.derived_products() == []
    assert reg.failures == ()


# --- the real cube ----------------------------------------------------------

REAL_CUBE = Path(__file__).resolve().parents[3] / "data" / "cube" / "incois_vam_bob.zarr"


@pytest.mark.skipif(not REAL_CUBE.is_dir(), reason="data/cube is gitignored; CI has no real cube")
def test_d26_on_the_real_cube_is_plausible_for_the_bay_of_bengal():
    ds = xr.open_zarr(REAL_CUBE)
    if ds.sizes.get("depth") != 24:
        pytest.skip("real cube has been re-fetched with a different level set")

    temp = np.asarray(ds["TEMP"].sel(time="2026-07-30").values, dtype="float64")
    out = _d26_values(_slab_ds(ds, temp))

    has_data = np.isfinite(temp).any(axis=0)
    assert not np.isfinite(out[~has_data]).any(), "a value was invented over land"

    # Warm all the way to the seabed on the shelf: no crossing exists, so the
    # only honest answer is absence. 16 such columns on 2026-07-30.
    warm_to_seabed = has_data & ~np.isfinite(out)
    assert warm_to_seabed.sum() > 0
    deepest = np.take_along_axis(
        np.where(np.isfinite(temp), temp, np.nan),
        (np.isfinite(temp).cumsum(axis=0).argmax(axis=0))[None, :, :],
        axis=0,
    )[0]
    assert (deepest[warm_to_seabed] > 26.0).all(), "a real crossing was missed"

    median = float(np.nanmedian(out))
    assert 30.0 < median < 150.0, f"basin median D26 of {median} m is not oceanographic"


def _slab_ds(ds, temp):
    out = xr.Dataset(
        {"TEMP": (("depth", "lat", "lon"), temp)},
        coords={"depth": ds["depth"], "lat": ds["lat"], "lon": ds["lon"]},
    )
    out["TEMP"].attrs["units"] = "degC"
    return out


# --- a product may report on the run, not just describe the recipe ----------
#
# `method` and `params` describe what a product ALWAYS does, and n_cells and
# n_valid are counted generically for every product. None of them can say
# anything about the field in hand. D26 is the case that showed the gap: on
# 2026-07-10 seven Bay of Bengal columns cross 26 degC TWICE, a real subsurface
# temperature inversion, and D26 serves the shallowest crossing at about 65 to
# 71 m where a deepest-crossing convention would say about 100 to 110 m. Both
# answer defensible questions and they differ by roughly 40 m, which matters to
# anyone reading D26 as cyclone heat potential. Serving one number and saying
# nothing hides that a choice was made.

def _d26_module():
    """The shipped plugin module itself, loaded by path as the loader loads it.

    `plugins/` is a data directory rather than a package on sys.path, so this
    is the honest way to reach a helper that is not part of the registered
    product surface.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "d26_isotherm_under_test", PLUGIN_DIR / "d26_isotherm.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_compute_may_return_values_alone(monkeypatch):
    """The old contract still works, or every existing plugin breaks."""
    registry = P.PluginRegistry()
    registry.register_derived_product(
        name="PLAIN",
        label="Plain",
        units="1",
        requires={"TEMP": None},
        compute=lambda ds: np.zeros(
            (ds.sizes["lat"], ds.sizes["lon"]), dtype="float64"
        ),
        output="surface",
        method="a constant",
    )
    product = registry.derived("PLAIN")

    values, notes = P._split_compute_result(product, np.zeros((2, 2)))
    assert notes == {}
    assert values.shape == (2, 2)


def test_a_compute_may_return_values_and_notes():
    registry = P.PluginRegistry()
    registry.register_derived_product(
        name="NOTED", label="Noted", units="1", requires={"TEMP": None},
        compute=lambda ds: (np.zeros((2, 2)), {"anything": 1}),
        output="surface", method="a constant",
    )
    product = registry.derived("NOTED")

    values, notes = P._split_compute_result(product, (np.zeros((2, 2)), {"anything": 1}))
    assert notes == {"anything": 1}
    assert values.shape == (2, 2)


def test_a_malformed_notes_return_is_refused():
    """A 3-tuple, or a second element that is not a dict, is a plugin bug.

    Accepting it would put whatever the plugin returned into the response
    provenance, which is the one place that has to be trustworthy.
    """
    registry = P.PluginRegistry()
    registry.register_derived_product(
        name="BROKEN", label="Broken", units="1", requires={"TEMP": None},
        compute=lambda ds: np.zeros((2, 2)), output="surface", method="x",
    )
    product = registry.derived("BROKEN")

    with pytest.raises(P.PluginError, match="C1"):
        P._split_compute_result(product, (np.zeros((2, 2)), "not a dict"))
    with pytest.raises(P.PluginError, match="C1"):
        P._split_compute_result(product, (np.zeros((2, 2)), {}, "extra"))
    with pytest.raises(P.PluginError, match="notes keys must be strings"):
        P._split_compute_result(product, (np.zeros((2, 2)), {1: "numeric key"}))


def test_d26_counts_the_columns_that_cross_twice():
    """A column with an inversion is counted, not silently resolved.

    Two crossings, at the 50/75 m pair and again at the 100/125 m pair, which
    is the exact shape of the seven real columns on 2026-07-10.
    """
    crossing_census = _d26_module().crossing_census

    depth = np.array([5.0, 30.0, 50.0, 75.0, 100.0, 125.0, 150.0])
    inverted = np.array([29.0, 29.0, 28.0, 25.6, 26.1, 19.0, 14.7])
    simple = np.array([29.0, 29.0, 28.0, 25.6, 24.0, 19.0, 14.7])
    land = np.full(7, np.nan)

    column = np.stack([inverted, simple, land], axis=1)[:, :, None]
    census = crossing_census(column, depth)

    assert census["columns_total"] == 3
    assert census["columns_wet"] == 2
    assert census["columns_with_crossing"] == 2
    assert census["columns_with_multiple_crossings"] == 1


def test_d26_puts_the_inversion_count_in_the_provenance():
    compute = _d26_module().compute

    depth = np.array([5.0, 30.0, 50.0, 75.0, 100.0, 125.0, 150.0])
    inverted = np.array([29.0, 29.0, 28.0, 25.6, 26.1, 19.0, 14.7])
    ds = xr.Dataset(
        {"TEMP": (("depth", "lat", "lon"), inverted[:, None, None])},
        coords={"depth": depth, "lat": [12.5], "lon": [85.5]},
    )

    values, notes = compute(ds)

    assert notes["columns_with_multiple_crossings"] == 1
    assert "SHALLOWEST" in notes["multiple_crossings_note"]
    assert "inversion" in notes["multiple_crossings_note"]
    # And the served value IS the shallow one, so the note describes what
    # actually happened rather than a hypothetical.
    shallow = np.asarray(values).ravel()[0]
    assert 60.0 < shallow < 80.0, shallow


def test_a_field_with_no_inversion_carries_no_inversion_note():
    """The note must appear only when it is true.

    A note present on every response is noise, and noise is how a real warning
    gets ignored.
    """
    compute = _d26_module().compute

    depth = np.array([5.0, 30.0, 50.0, 75.0, 100.0])
    simple = np.array([29.0, 29.0, 28.0, 25.6, 24.0])
    ds = xr.Dataset(
        {"TEMP": (("depth", "lat", "lon"), simple[:, None, None])},
        coords={"depth": depth, "lat": [12.5], "lon": [85.5]},
    )

    _values, notes = compute(ds)

    assert notes["columns_with_multiple_crossings"] == 0
    assert "multiple_crossings_note" not in notes


# --- the source-reader half of the plugin interface, on a real mooring ------
#
# PS requirement F6 names moorings. The framework has offered a source-reader
# extension point from the start, with a checked contract and its own error
# codes, and until now nothing was registered against it: that half was
# demonstrated by tests of the FRAMEWORK and by no actual reader.
#
# services/api/plugins/rama_mooring.py is the running example, on RAMA, the
# Indian Ocean arm of the tropical moored array that INCOIS partners on. These
# tests cover the three things it has to get right, each of which is a real
# property of the real data rather than an invented edge case.

def _rama_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rama_mooring_under_test", PLUGIN_DIR / "rama_mooring.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mooring_file(tmp_path, *, times, depths, values, flags, lat=15.0, lon=90.0,
                  station="15n90e", wmo=23009.0):
    """An ERDDAP tabledap export: a FLAT TABLE, one row per (time, depth).

    Deliberately flat and deliberately unsorted, because that is what the
    service actually returns and the pivot is the reader's job.
    """
    import itertools

    rows = list(itertools.product(range(len(times)), range(len(depths))))
    n = len(rows)
    ds = xr.Dataset(
        {
            "station": ("row", np.array([station] * n, dtype=object)),
            "wmo_platform_code": ("row", np.full(n, wmo, dtype="float32")),
            "longitude": ("row", np.full(n, lon, dtype="float32")),
            "latitude": ("row", np.full(n, lat, dtype="float32")),
            "time": ("row", np.array([times[i] for i, _ in rows], dtype="datetime64[ns]")),
            "depth": ("row", np.array([depths[j] for _, j in rows], dtype="float32")),
            "T_20": ("row", np.array([values[i][j] for i, j in rows], dtype="float32"),
                     {"units": "degree_C"}),
            "QT_5020": ("row", np.array([flags[i][j] for i, j in rows], dtype="float32")),
        }
    )
    path = tmp_path / "rama_test.nc"
    ds.to_netcdf(path)
    return path


def test_the_mooring_reader_is_registered_against_its_kind():
    """The gap this closes: a contract with nothing registered against it."""
    reg = P.load_plugins(directory=PLUGIN_DIR, strict=True)

    reader = reg.source_reader("mooring")
    assert reader is not None, "kind 'mooring' has no reader"
    assert reader.plugin == "rama_mooring"
    assert reader.doc, "a reader must say what it reads"
    # Both halves of the interface now have a running example, which is the
    # whole point of this file.
    assert reg.derived("D26") is not None


def test_a_flat_table_is_pivoted_onto_a_time_by_depth_grid(tmp_path):
    """ERDDAP serves one row per (time, depth), 527 rows for one real mooring.

    The pivot uses the depths ACTUALLY PRESENT rather than an assumed set: a
    mooring loses and regains sensors mid-deployment, so assuming a rectangular
    sampling would either drop levels or invent them.
    """
    rama = _rama_module()
    times = ["2026-07-29", "2026-07-30"]
    depths = [1.0, 20.0, 100.0]
    values = [[29.4, 29.1, 22.8], [29.5, 29.2, 22.9]]
    flags = [[2, 2, 2], [2, 2, 2]]

    ds = rama.read_mooring(_mooring_file(tmp_path, times=times, depths=depths,
                                         values=values, flags=flags))

    assert ds["TEMP"].dims == ("time", "depth")
    assert ds.sizes == {"time": 2, "depth": 3}
    assert list(ds.depth.values) == [1.0, 20.0, 100.0]
    assert ds["TEMP"].values[1][2] == pytest.approx(22.9)
    # One position, as scalar coordinates: a mooring does not move.
    assert float(ds.lat) == 15.0 and float(ds.lon) == 90.0


def test_the_fourth_fill_convention_is_masked(tmp_path):
    """1.0E35, which is none of the three the cube already handles.

    -9999.0 (INCOIS VAM), -1.0E34 (value-added and ocean colour) and 99999.0
    (Argo BGC) are all live in this project, and none is a rounding of another.
    A sentinel read as a measurement is a 1e35 degree ocean.
    """
    rama = _rama_module()
    ds = rama.read_mooring(_mooring_file(
        tmp_path,
        times=["2026-07-30"],
        depths=[1.0, 20.0],
        values=[[29.4, 1.0e35]],
        flags=[[2, 2]],
    ))

    temps = ds["TEMP"].values.ravel()
    assert temps[0] == pytest.approx(29.4)
    assert np.isnan(temps[1]), "the 1.0E35 sentinel reached the output as a value"
    assert not (np.nan_to_num(temps, nan=0.0) > 1e30).any()


def test_a_failed_sensor_is_mapped_to_bad_rather_than_compared_to_the_wrong_scale(tmp_path):
    """The decisive one, and the reason the mapping is written out.

    TAO/RAMA flags are 0 no sensor, 1 highest, 2 default, 3 adjusted, 4 lower,
    5 SENSOR FAILED. Argo's scale means something different above 2 and has no
    5 at all, so the two agree on 1 and 2 by coincidence and diverge beyond.
    Filtering RAMA flags with Argo's rules would compare a failed sensor
    against a scale it does not belong to.
    """
    rama = _rama_module()

    assert rama.QC_MAP[5] == 4, "a failed sensor must map to bad"
    assert rama.QC_MAP[0] == 9, "no sensor is missing, not good"
    assert rama.QC_MAP[1] == 1 and rama.QC_MAP[2] == 2

    ds = rama.read_mooring(_mooring_file(
        tmp_path,
        times=["2026-07-30"],
        depths=[1.0, 20.0, 100.0, 200.0],
        values=[[29.4, 28.0, 22.8, 15.0]],
        flags=[[2, 5, 0, 1]],          # good, FAILED, no sensor, highest
    ))

    mapped = ds["TEMP_QC"].values.ravel().astype(int).tolist()
    assert mapped == [2, 4, 9, 1]
    # The flag meanings travel with the data, so a reader of the file does not
    # have to know RAMA's vocabulary to interpret it.
    assert "flag_meanings" in ds["TEMP_QC"].attrs
    assert "sensor failed" in ds["TEMP_QC"].attrs["comment"].lower()


def test_an_unknown_flag_becomes_missing_rather_than_a_guess(tmp_path):
    """An array can grow a flag value. An unknown one is not evidence of
    quality in either direction, so it must not be assumed good."""
    rama = _rama_module()
    ds = rama.read_mooring(_mooring_file(
        tmp_path,
        times=["2026-07-30"],
        depths=[1.0, 20.0],
        values=[[29.4, 28.0]],
        flags=[[2, 7]],
    ))

    assert ds["TEMP_QC"].values.ravel().astype(int).tolist() == [2, rama.QC_UNKNOWN]


def test_a_wmo_id_is_not_rendered_with_a_decimal_point(tmp_path):
    """ERDDAP types wmo_platform_code as a NUMBER, so str() gives '23009.0'.

    That string would go straight into the citation printed under the chart,
    and a WMO id with a decimal point in it is not a WMO id.
    """
    rama = _rama_module()
    ds = rama.read_mooring(_mooring_file(
        tmp_path, times=["2026-07-30"], depths=[1.0],
        values=[[29.4]], flags=[[2]], wmo=23009.0,
    ))

    assert ds.attrs["wmo_platform_code"] == "23009"


def test_a_file_reporting_two_positions_is_refused(tmp_path):
    """A moored buoy has ONE position. Two means either two moorings in one
    file or a drifting one, and both make the fixed-position assumption wrong."""
    rama = _rama_module()
    path = _mooring_file(tmp_path, times=["2026-07-30"], depths=[1.0, 20.0],
                         values=[[29.4, 28.0]], flags=[[2, 2]])
    with xr.open_dataset(path) as ds:
        moved = ds.load()
    moved["latitude"].values[1] = 12.0
    path2 = tmp_path / "moved.nc"
    moved.to_netcdf(path2)

    with pytest.raises(ValueError, match="one fixed position"):
        rama.read_mooring(path2)


def test_the_reader_output_passes_the_frameworks_own_contract(tmp_path, monkeypatch):
    """D1 to D5 are what stop a reader shipping something unusable.

    Going through open_source rather than calling the reader directly is the
    point: this is the path the pipeline uses, and it is where a flipped depth
    axis or a missing unit would be caught.
    """
    rama = _rama_module()
    _mooring_file(tmp_path, times=["2026-07-29", "2026-07-30"], depths=[1.0, 20.0],
                  values=[[29.4, 28.0], [29.5, 28.1]], flags=[[2, 2], [2, 2]])
    (tmp_path / "rama_test.nc").rename(tmp_path / "rama_x.nc")

    reg = P.PluginRegistry()
    reg._begin("rama_mooring", "test")
    rama.register(reg)
    reg._end()

    from app.registry import SourceSpec

    spec = SourceSpec(
        id="m", title="m", kind="mooring", url=str(tmp_path),
        path_template="rama_*.nc",
        variables=[{"name": "TEMP", "units": "degC"}],
        dims={"time": "time", "depth": "depth"},
    )

    ds = P.open_source(spec, registry=reg)

    assert "TEMP" in ds.data_vars
    assert ds["TEMP"].attrs["units"] == "degC"
    assert np.all(np.diff(ds["depth"].values) > 0)
    assert (np.asarray(ds["depth"].values) >= 0).all()


def test_the_real_mooring_reaches_the_profile_table():
    """End to end on the shipped cube: the plugin's output is in the parquet.

    A registered reader that nothing calls is the gap this closes, so the
    assertion that matters is that a mooring row exists in the same table the
    Argo floats land in, carrying its own source id.
    """
    import pathlib

    import pandas as pd

    parquet = (
        pathlib.Path(__file__).resolve().parents[3] / "data" / "cube" / "profiles.parquet"
    )
    if not parquet.is_file():
        pytest.skip("no local cube; run tools/fetch_sample.py then tools/preprocess.py")

    df = pd.read_parquet(parquet)
    if "source_id" not in df.columns:
        pytest.skip("profiles.parquet predates the source_id column")
    moorings = df[df["source_id"] == "rama_mooring_bob"]
    if moorings.empty:
        pytest.skip("no mooring in the local cube; the RAMA line may be out of the water")

    assert moorings["wmo"].nunique() == 1, "one mooring, one platform id"
    # A fixed station: every row at the same position.
    assert moorings["lat"].nunique() == 1 and moorings["lon"].nunique() == 1
    # Physically sensible Bay of Bengal temperatures.
    assert moorings["temp"].between(5.0, 32.0).all()
    # Only accepted flags reached the table.
    assert moorings["temp_qc"].isin([1, 2]).all()
    # A mooring measures at a known depth and reports no pressure, and that
    # absence is honest rather than back-computed.
    assert moorings["pres"].isna().all()
