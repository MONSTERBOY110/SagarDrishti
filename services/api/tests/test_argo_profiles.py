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
    """
    df = parse_profiles(argo_like_nc, argo_spec)

    assert set(df["temp_qc"].unique()) <= {1, 2}
    # 3 profiles x 6 levels = 18, minus the 2 rejected levels in profile 1
    assert len(df) == 16
    # the rejected values themselves must be gone, not merely flagged
    assert 28.40 not in df["temp"].values   # the level flagged 4
    assert 21.90 not in df["temp"].values   # the level flagged 3


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
