"""Argo profile parsing: QC filtering and pressure-to-depth (TRD M1/M5).

Both of these feed the Class-4-style scorecard (PRIOR-ART.md §E.4). A bad QC
flag or a dbar-treated-as-metres bug does not crash anything -- it just makes
every RMSE number we show a judge wrong, which is worse.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.argo import parse_profiles, pressure_to_depth
from app.registry import load_registry


@pytest.fixture
def argo_spec():
    return load_registry().get("argo_gdac_indian")


# --- Test 6: QC flags and WMO identity --------------------------------------

def test_only_qc_flags_1_and_2_survive(argo_like_nc, argo_spec):
    """Wong et al. 2020 / PRIOR-ART §E.4: good (1) and probably-good (2) only.

    The fixture flags one level 4 (bad) and one level 3 (dubious) in profile 1.

    This test used to assert `set(df["temp_qc"]) <= {1, 2}`, and that assertion
    was deliberately changed rather than fixed. It described a property of the
    FLAG column, not of the served data, and it only held because the parser
    dropped whole levels on temperature's flag. Dropping the level also threw
    away that level's salinity, which the fixture flags good. The invariant
    worth defending is narrower and stronger: a rejected VALUE is never served,
    while its flag is still reported so a reader can tell "rejected" from
    "never measured".
    """
    df = parse_profiles(argo_like_nc, argo_spec)

    # The rejected temperatures themselves are gone, which is the point.
    assert 28.40 not in df["temp"].values   # the level flagged 4
    assert 21.90 not in df["temp"].values   # the level flagged 3

    # Every temperature actually served answers to an accepted flag.
    served = df[df["temp"].notna()]
    assert set(served["temp_qc"].unique()) <= {1, 2}

    # 3 profiles x 6 levels = 18 rows. All 18 survive, because this fixture's
    # PRES_QC and PSAL_QC are good everywhere, so the two temperature-rejected
    # levels still carry a usable salinity. Their temperature is NaN.
    assert len(df) == 18
    assert df["temp"].isna().sum() == 2
    assert df["psal"].notna().all(), "a good salinity was discarded with a bad temperature"


def test_wmo_id_extracted_from_char_array(argo_like_nc, argo_spec):
    """PLATFORM_NUMBER is fixed-width char padding, not a string. Every number
    the agent speaks must carry a WMO id (CLAUDE.md), so this cannot be fuzzy."""
    df = parse_profiles(argo_like_nc, argo_spec)

    wmos = sorted(df["wmo"].unique())
    assert wmos == ["2902746", "5906521"]
    assert all(isinstance(w, str) and w.isdigit() and len(w) == 7 for w in wmos)
    # two profiles from the same float must remain distinguishable
    same_float = df[df["wmo"] == "2902746"]
    assert same_float["profile_id"].nunique() == 2


def test_profile_carries_position_and_time(argo_like_nc, argo_spec):
    """A profile without lat/lon/time cannot be co-located with a model field,
    which is the whole point of the scorecard."""
    df = parse_profiles(argo_like_nc, argo_spec)

    assert df["time"].notna().all()
    assert df["lat"].between(-90, 90).all()
    assert df["lon"].between(-180, 180).all()
    # JULD is days since 1950-01-01, NOT 1970. 27969 d -> 2026-07-30; reading it
    # against the Unix epoch would land in 2046 and silently break time matching.
    assert df["time"].dt.year.unique().tolist() == [2026]
    assert df["time"].min().strftime("%Y-%m-%d") == "2026-07-30"


# --- Test 7: pressure to depth ----------------------------------------------

def test_pressure_to_depth_is_not_the_identity():
    """The failure mode we are guarding against is dbar used as metres.

    Physically, 1000 dbar is about 990 m, not 1000 m -- roughly a 1% error that
    looks plausible on a chart and quietly biases every depth-binned RMSE.
    """
    pres = np.array([0.0, 100.0, 500.0, 1000.0, 2000.0])
    depth = pressure_to_depth(pres, lat=12.5)

    assert depth[0] == pytest.approx(0.0, abs=1e-6)
    assert (depth[1:] > 0).all(), "depth must be positive-down"
    assert np.all(np.diff(depth) > 0), "depth must increase with pressure"

    # ~0.99 x pressure across the range, and definitely NOT equal to pressure
    ratio = depth[1:] / pres[1:]
    assert np.all((ratio > 0.975) & (ratio < 1.0)), f"implausible ratios: {ratio}"
    assert abs(depth[3] - 1000.0) > 5.0, "dbar is being treated as metres"


def test_pressure_to_depth_depends_on_latitude():
    """Gravity varies with latitude, so the same pressure is a shallower depth
    at high latitude. If our function ignores lat, this test fails."""
    p = np.array([1000.0])
    equator = pressure_to_depth(p, lat=0.0)[0]
    high_lat = pressure_to_depth(p, lat=60.0)[0]

    assert equator > high_lat
    assert 1.0 < (equator - high_lat) < 10.0, "latitude effect has the wrong magnitude"


def test_parsed_profile_depths_are_positive_down(argo_like_nc, argo_spec):
    df = parse_profiles(argo_like_nc, argo_spec)

    assert (df["depth"] > 0).all()
    for _, g in df.groupby("profile_id"):
        assert np.all(np.diff(g["depth"].values) > 0), "levels not ordered downward"
    # depth must differ from pressure -- proof the conversion ran end to end
    assert not np.allclose(df["depth"].values, df["pres"].values)


# --- per-parameter QC: each value answers to its OWN flag -------------------
#
# Found by checking the parser against the 10 real Indian Ocean daily files
# rather than against its own fixture. `parse_profiles` built one boolean
# `keep` mask from TEMP_QC and PRES_QC and then indexed EVERY parameter with
# it, so a salinity whose own flag said 3 or 4 was emitted as though accepted.
# In those files that is 60,643 levels, carrying values including 0.00, 65.53
# and 134.12 PSU against an ocean range of roughly 33 to 37.
#
# The served Bay of Bengal subset happens to contain none of them, which is
# what makes this worth a test rather than a note: the bug is invisible today
# and appears the moment the demo box, the dates or the float set changes.

def test_a_rejected_salinity_is_not_served_beside_a_good_temperature(
    argo_mixed_qc_nc, argo_spec
):
    """Level 1: TEMP flag 1, PSAL flag 4, PSAL value 134.12.

    The temperature is good and must survive. The salinity must not appear as a
    number, and its flag must still be reported, because erasing the flag would
    hide why the value is missing.
    """
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)

    assert 134.12 not in df["psal"].round(2).values, "a QC-rejected salinity was served"
    assert 65.53 not in df["psal"].round(2).values, "a QC-rejected salinity was served"

    level = df[df["pres"].round(1) == 10.0]
    assert len(level) == 1, "a level with a good temperature must survive"
    assert level["temp"].iloc[0] == pytest.approx(29.05, abs=1e-3)
    assert np.isnan(level["psal"].iloc[0]), "rejected salinity must be NaN, not a value"
    assert level["psal_qc"].iloc[0] == 4, "the flag must still say why it is missing"


def test_a_good_salinity_survives_a_rejected_temperature(argo_mixed_qc_nc, argo_spec):
    """Level 2: TEMP flag 4, PSAL flag 1.

    The old code dropped the whole level because temperature gated it, throwing
    away a perfectly good salinity measurement. Argo flags each parameter
    separately and so must we.
    """
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)

    level = df[df["pres"].round(1) == 20.0]
    assert len(level) == 1, "a level with a good salinity must not be dropped"
    assert np.isnan(level["temp"].iloc[0]), "rejected temperature must be NaN"
    assert level["temp_qc"].iloc[0] == 4
    assert level["psal"].iloc[0] == pytest.approx(35.10, abs=1e-3)


def test_a_level_with_no_usable_pressure_is_dropped_entirely(argo_mixed_qc_nc, argo_spec):
    """Level 4: PRES flag 4, both measurements good.

    Pressure is not one parameter among several. Without it the level has no
    depth, so its values cannot be placed in the water column or compared with
    a model level, and there is nothing honest to do but drop it.
    """
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)

    assert 100.0 not in df["pres"].round(1).values
    assert 22.40 not in df["temp"].round(2).values, (
        "a measurement was served at a depth we cannot compute"
    )


def test_a_level_whose_every_measurement_is_rejected_is_dropped(argo_mixed_qc_nc, argo_spec):
    """Level 3: TEMP flag 3, PSAL flag 3. Nothing left to carry."""
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)

    assert 50.0 not in df["pres"].round(1).values, (
        "a level with no accepted measurement is an empty row"
    )


def test_probably_good_flag_2_is_accepted(argo_mixed_qc_nc, argo_spec):
    """Level 5: both flags 2. Wong et al. 2020 accepts 1 and 2."""
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)

    level = df[df["pres"].round(1) == 200.0]
    assert len(level) == 1
    assert level["temp"].iloc[0] == pytest.approx(15.20, abs=1e-3)
    assert level["psal"].iloc[0] == pytest.approx(34.80, abs=1e-3)


def test_no_served_value_disagrees_with_its_own_flag(argo_mixed_qc_nc, argo_spec):
    """The invariant, stated once for every parameter at once.

    This is the assertion that should have existed from the start: not "the
    temperature flags are all good" but "no number is served whose own flag
    rejects it". The first is a property of one column; the second is the
    promise the API prints in every profile response.
    """
    df = parse_profiles(argo_mixed_qc_nc, argo_spec)
    accepted = set(argo_spec.qc.accept_flags)

    for value_col, qc_col in (("temp", "temp_qc"), ("psal", "psal_qc")):
        served = df[df[value_col].notna()]
        offenders = served[~served[qc_col].isin(accepted)]
        assert offenders.empty, (
            f"{len(offenders)} served {value_col} value(s) carry a rejected flag: "
            f"{offenders[[value_col, qc_col]].to_dict('records')}"
        )


# --- BGC synthetic profiles: the PS's "BGC" instrument class ----------------

@pytest.fixture
def bgc_spec():
    return load_registry().get("argo_bgc_indian")


def test_bgc_parameters_are_read_from_the_registry_not_hardcoded(argo_bgc_like_nc, bgc_spec):
    """PRD F2 names BGC as an instrument class, and F3 says a new variable is a
    config entry rather than a rewrite. Both claims land on this test: the
    parser is told which parameters exist by `sources.yaml`, so the frame gains
    a column per declared parameter with its flag beside it."""
    df = parse_profiles(argo_bgc_like_nc, bgc_spec)

    for column in ("temp", "psal", "doxy", "chla", "ph_in_situ_total"):
        assert column in df.columns, f"{column} missing: the registry declares it"
        assert f"{column}_qc" in df.columns, f"{column} has no flag column"


def test_the_adjusted_product_is_what_makes_bgc_data_exist(argo_bgc_like_nc, bgc_spec):
    """The single most important behaviour in the BGC path.

    Every RAW chlorophyll, oxygen and pH level in the fixture is flagged 3,
    matching the real floats, where raw CHLA_QC is flag 3 on all 13,934
    measured levels. Our policy accepts 1 and 2 only. So if the parser read the
    raw product, the correct answer under our own policy would be "no
    chlorophyll", and the panel would be empty for a reason no one could see.
    Preferring the adjusted product is what turns three empty columns into
    data, and it is a config flag, so this test is what stops it being flipped
    off by accident.
    """
    df = parse_profiles(argo_bgc_like_nc, bgc_spec)

    assert df["chla"].notna().sum() == 2, "no chlorophyll survived: adjusted product ignored?"
    assert df["doxy"].notna().sum() == 2
    assert df["ph_in_situ_total"].notna().sum() == 2

    # The values served are the ADJUSTED ones, not the raw ones.
    chla = sorted(df["chla"].dropna().round(3).tolist())
    assert chla == [0.081, 0.412], f"raw chlorophyll leaked through: {chla}"


def test_raw_bgc_values_that_are_physically_impossible_never_appear(argo_bgc_like_nc, bgc_spec):
    """Negative chlorophyll and a pH of -381 are in the real raw arrays.

    They are flagged, and the adjusted product replaces them, so neither the QC
    filter nor the adjusted preference may be the only thing standing between
    those numbers and a chart.
    """
    df = parse_profiles(argo_bgc_like_nc, bgc_spec)

    assert (df["chla"].dropna() >= 0).all(), "negative chlorophyll served"
    ph = df["ph_in_situ_total"].dropna()
    assert ph.between(7.0, 8.5).all(), f"pH outside any ocean value: {ph.tolist()}"
    assert -381.62 not in df["ph_in_situ_total"].values
    assert -0.993 not in df["chla"].values


def test_parameters_keep_their_own_sampling_levels(argo_bgc_like_nc, bgc_spec):
    """A BGC sensor samples more sparsely than the CTD beside it.

    Chlorophyll exists on levels 0 and 2, oxygen on 1 and 2. A level must
    therefore be allowed to carry some parameters and not others, and the gaps
    must stay gaps: filling them would invent measurements, and dropping the
    level would throw away the temperature that IS there.
    """
    df = parse_profiles(argo_bgc_like_nc, bgc_spec).sort_values("depth").reset_index(drop=True)

    assert len(df) == 4, "levels were dropped for having a sparse BGC sensor"
    assert df["temp"].notna().all(), "the CTD measured every level"
    # Level 0 (about 5 dbar): chlorophyll yes, oxygen no.
    assert not np.isnan(df.loc[0, "chla"])
    assert np.isnan(df.loc[0, "doxy"])
    # Level 1 (about 50 dbar): the reverse.
    assert np.isnan(df.loc[1, "chla"])
    assert not np.isnan(df.loc[1, "doxy"])


def test_the_oxygen_minimum_survives_the_pipeline(argo_bgc_like_nc, bgc_spec):
    """The Bay of Bengal oxygen minimum zone is the feature these floats exist
    to measure, and the real float reaches 1.71 micromole/kg at 141 m under a
    28.5 degC surface. A pipeline that clamped, interpolated or dropped
    near-zero values would erase the most scientifically interesting thing in
    the dataset while looking perfectly healthy."""
    df = parse_profiles(argo_bgc_like_nc, bgc_spec)

    doxy = df[["depth", "doxy"]].dropna().sort_values("doxy")
    assert doxy.iloc[0]["doxy"] == pytest.approx(1.71, abs=1e-3)
    assert 100 < doxy.iloc[0]["depth"] < 200, "the minimum moved in depth"


def test_a_juld_timestamp_is_rounded_to_the_second(argo_bgc_like_nc, bgc_spec):
    """JULD is a float count of DAYS, so its nanosecond tail is float noise.

    Left alone it produced 14:13:48.001520640 on a real float, which then
    appears verbatim in the citation printed under the chart and reads as false
    precision about when the float surfaced.
    """
    df = parse_profiles(argo_bgc_like_nc, bgc_spec)
    stamp = df["time"].iloc[0]

    assert stamp.nanosecond == 0 and stamp.microsecond == 0, (
        f"sub-second float noise survived: {stamp.isoformat()}"
    )
    # And the id, which has always been second-resolution, agrees with it.
    assert df["profile_id"].iloc[0] == f"2903831_{stamp.strftime('%Y%m%dT%H%M%S')}"


def test_a_units_mismatch_between_file_and_registry_is_refused(
    argo_bgc_like_nc, bgc_spec, tmp_path
):
    """The registry's `units` is what labels the chart axis, so it may not lie.

    Oxygen is the case that makes this matter: micromole/kg and ml/l differ by
    a factor of about 22, both are used in the literature, and both look
    entirely plausible on an axis. Relabelling without converting would put a
    wrong number under a confident label, which is the one thing this project
    treats as unacceptable.
    """
    from app.argo import UnitsMismatch, check_units
    import xarray as xr

    lying = bgc_spec.model_copy(deep=True)
    for v in lying.variables:
        if v.name == "DOXY":
            v.units = "ml/l"       # the file says micromole/kg

    with xr.open_dataset(argo_bgc_like_nc, decode_times=False) as ds:
        with pytest.raises(UnitsMismatch) as err:
            check_units(ds, lying)

    message = str(err.value)
    assert "DOXY" in message
    assert "ml/l" in message and "micromole/kg" in message
    assert "sources.yaml" in message, "the message must say where to fix it"


def test_equivalent_unit_spellings_are_not_a_mismatch(argo_bgc_like_nc, bgc_spec):
    """Argo is inconsistent about spelling and that is not an error.

    `degree_Celsius` and `degree_celsius` are the same unit; so are `psu` and
    the CF-correct dimensionless `1` for practical salinity. Refusing on case
    or on a synonym would make the check a nuisance that someone eventually
    switches off, which is worse than not having it.
    """
    from app.argo import check_units
    import xarray as xr

    tolerant = bgc_spec.model_copy(deep=True)
    for v in tolerant.variables:
        if v.name == "TEMP":
            v.units = "degree_celsius"     # file: degree_Celsius
        if v.name == "PSAL":
            v.units = "1"                  # file: psu
        if v.name == "PH_IN_SITU_TOTAL":
            v.units = "1"                  # file: dimensionless

    with xr.open_dataset(argo_bgc_like_nc, decode_times=False) as ds:
        found = check_units(ds, tolerant)   # must not raise

    assert found["TEMP"] == "degree_Celsius"
    assert found["PSAL"] == "psu"
