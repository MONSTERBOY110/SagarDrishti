"""Class-4-style verification: the colocation maths and what it refuses (F9).

This is the module whose output is a CLAIM ABOUT THE MODEL rather than a
rendering of it, so it is the one place where a silent bug turns into a
sentence a judge could repeat and be wrong about. The tests are written in that
spirit: most of them assert a refusal rather than a value.

The analytic field below is linear in latitude, longitude and depth. Bilinear
interpolation reproduces a bilinear function exactly, and linear interpolation
in depth reproduces a linear one exactly even on a stretched depth axis, so any
departure from the closed form is a bug in our code and not a property of
interpolation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app import scorecard

LATS = np.array([10.0, 11.0, 12.0, 13.0], dtype="float64")
LONS = np.array([85.0, 86.0, 87.0, 88.0], dtype="float64")
DEPTHS = np.array([5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0], dtype="float64")
TIMES = pd.to_datetime(["2026-07-10", "2026-07-20", "2026-07-30"])


def analytic(depth: float, lat: float, lon: float) -> float:
    """The closed form the fixture field samples. Linear in all three axes."""
    return 10.0 + 0.5 * lat - 0.25 * lon + 0.01 * depth


def linear_cube() -> xr.Dataset:
    """A cube whose every cell is `analytic` evaluated at that cell's centre."""
    zz, yy, xx = np.meshgrid(DEPTHS, LATS, LONS, indexing="ij")
    field = analytic(zz, yy, xx)
    stacked = np.broadcast_to(field, (TIMES.size, *field.shape)).copy()
    ds = xr.Dataset(
        {"TEMP": (("time", "depth", "lat", "lon"), stacked)},
        coords={"time": TIMES, "depth": DEPTHS, "lat": LATS, "lon": LONS},
    )
    ds.TEMP.attrs["units"] = "degC"
    return ds


def profile_frame(
    *,
    profile_id: str = "P1",
    wmo: str = "2900001",
    time: str = "2026-07-20",
    lat: float = 11.4,
    lon: float = 86.7,
    depths: np.ndarray | None = None,
    temps: np.ndarray | None = None,
    qc: np.ndarray | None = None,
) -> pd.DataFrame:
    """A one-profile levels table shaped exactly like data/cube/profiles.parquet."""
    depths = DEPTHS[1:-1] if depths is None else np.asarray(depths, dtype="float64")
    if temps is None:
        temps = np.array([analytic(d, lat, lon) for d in depths], dtype="float64")
    temps = np.asarray(temps, dtype="float64")
    qc = np.ones(depths.size, dtype="float64") if qc is None else np.asarray(qc, dtype="float64")
    return pd.DataFrame(
        {
            "profile_id": [profile_id] * depths.size,
            "wmo": [wmo] * depths.size,
            "time": [pd.Timestamp(time)] * depths.size,
            "lat": np.full(depths.size, lat),
            "lon": np.full(depths.size, lon),
            "depth": depths,
            "temp": temps,
            "temp_qc": qc,
            "source_id": ["argo_gdac_indian"] * depths.size,
        }
    )


# --------------------------------------------------------------------------
# The interpolation itself
# --------------------------------------------------------------------------


def test_the_model_is_reproduced_exactly_where_the_field_is_linear():
    """Off-grid in all three axes, the residual must be machine zero.

    If this drifts, every RMSE the tool prints is contaminated by our own
    interpolation error and the number stops being about the model at all.
    """
    ds = linear_cube()
    lat, lon = 11.4, 86.7
    depths = np.array([7.5, 33.0, 137.0, 812.5])
    frame = profile_frame(lat=lat, lon=lon, depths=depths)

    matches, refusals = scorecard.colocate(ds, frame)

    assert len(matches) == depths.size
    assert refusals.total == 0
    for m in matches:
        assert abs(m.modelled - analytic(m.depth, lat, lon)) < 1e-9
        assert abs(m.residual) < 1e-9


def test_a_position_outside_the_grid_is_refused_not_clamped():
    """A clamp would compare a float against the edge of the domain silently."""
    ds = linear_cube()
    values = ds["TEMP"].isel(time=0).values

    inside = scorecard.model_column_at(values, LATS, LONS, 11.4, 86.7)
    assert inside is not None and np.all(np.isfinite(inside))

    for lat, lon in ((9.9, 86.7), (13.1, 86.7), (11.4, 84.9), (11.4, 88.1)):
        assert scorecard.model_column_at(values, LATS, LONS, lat, lon) is None


def test_a_level_is_refused_when_any_one_of_the_four_corners_is_missing():
    """Three good corners out of four is a two-thirds answer, not an answer.

    Near a coast this is the common case, so filling from the corners that
    remain would bias the shelf, which is exactly where a cyclone forecaster
    is reading.
    """
    ds = linear_cube()
    values = ds["TEMP"].isel(time=0).values.copy()
    # (lat 11.0, lon 87.0) is one of the four cells around 11.4 N, 86.7 E.
    values[3, 1, 2] = np.nan

    column = scorecard.model_column_at(values, LATS, LONS, 11.4, 86.7)
    assert column is not None
    assert np.isnan(column[3]), "the holed level must be refused"
    assert np.all(np.isfinite(np.delete(column, 3))), "only that level"

    # One cell away, the hole is out of the stencil and nothing is refused.
    away = scorecard.model_column_at(values, LATS, LONS, 10.4, 85.7)
    assert away is not None and np.all(np.isfinite(away))


def test_a_position_on_a_grid_line_does_not_require_the_far_corners():
    """Sitting on a grid line uses two cells, so demanding four would refuse it.

    An early version did exactly that, and it refused every float that happened
    to surface on a whole degree.
    """
    ds = linear_cube()
    values = ds["TEMP"].isel(time=0).values.copy()
    # Hole the two cells that carry zero weight when lat is exactly 11.0.
    values[:, 2, 2] = np.nan
    values[:, 2, 3] = np.nan

    column = scorecard.model_column_at(values, LATS, LONS, 11.0, 86.5)
    assert column is not None
    assert np.all(np.isfinite(column))
    assert abs(column[0] - analytic(DEPTHS[0], 11.0, 86.5)) < 1e-9


def test_depth_is_interpolated_not_extrapolated():
    """Below the deepest model level there is no model value, only a guess."""
    column = np.array([analytic(d, 11.0, 86.0) for d in DEPTHS])

    mid = scorecard._interp_depth(column, DEPTHS, 137.0)
    assert abs(mid - analytic(137.0, 11.0, 86.0)) < 1e-9

    assert np.isnan(scorecard._interp_depth(column, DEPTHS, 1200.0))
    assert np.isnan(scorecard._interp_depth(column, DEPTHS, 2.0))

    # The endpoints themselves are inside the range and must still work.
    assert abs(scorecard._interp_depth(column, DEPTHS, 5.0) - column[0]) < 1e-9
    assert abs(scorecard._interp_depth(column, DEPTHS, 1000.0) - column[-1]) < 1e-9


def test_a_single_valued_axis_matches_only_its_own_coordinate():
    """A one-cell axis has nothing to interpolate between, so it must not pretend."""
    axis = np.array([12.5])
    assert scorecard._bracket(axis, 12.5) == (0, 0, 0.0)
    assert scorecard._bracket(axis, 12.6) is None
    assert scorecard._bracket(np.array([]), 12.5) is None
    assert scorecard._bracket(DEPTHS, float("nan")) is None


# --------------------------------------------------------------------------
# The statistics
# --------------------------------------------------------------------------


def test_bias_alone_would_call_a_badly_wrong_model_perfect():
    """Two degrees warm here and two degrees cold there averages to nothing.

    This is the whole reason the card reports bias and RMSE side by side, and
    the reason a reviewer should distrust any viewer that prints only one.
    """
    cancelling = np.array([2.0, -2.0, 2.0, -2.0])
    uniform = np.array([2.0, 2.0, 2.0, 2.0])

    a = scorecard._stats(cancelling)
    b = scorecard._stats(uniform)

    assert a["bias"] == 0.0
    assert a["rmse"] == 2.0
    assert b["bias"] == 2.0
    assert b["rmse"] == 2.0
    # And the spread is what tells them apart: a constant correction fixes the
    # second model completely and the first one not at all.
    assert a["std"] == 2.0
    assert b["std"] == 0.0


def test_an_empty_bin_reports_no_number_rather_than_zero():
    """A bin with no observations has no bias. Zero would read as 'perfect'."""
    empty = scorecard._stats(np.array([], dtype="float64"))
    assert empty["n"] == 0
    assert empty["bias"] is None
    assert empty["rmse"] is None


def test_depth_bins_are_half_open_so_a_boundary_level_lands_in_exactly_one():
    """A level at exactly 50 m must be counted once, in 50-100, not twice."""
    ds = linear_cube()
    frame = profile_frame(depths=np.array([50.0]))
    matches, _ = scorecard.colocate(ds, frame)
    assert len(matches) == 1

    card = scorecard.score(matches, scorecard.Refusals(), variable="TEMP", units="degC")
    counted = [b for b in card["by_depth"] if b["n"] > 0]
    assert len(counted) == 1
    assert (counted[0]["depth_min"], counted[0]["depth_max"]) == (50.0, 100.0)
    assert sum(b["n"] for b in card["by_depth"]) == card["overall"]["n"]


# --------------------------------------------------------------------------
# What colocation refuses, and how it labels the refusal
# --------------------------------------------------------------------------


def test_an_observation_far_from_every_model_step_is_refused():
    """The analysis is a ten-day field, so five days is the furthest it reaches."""
    ds = linear_cube()

    near = profile_frame(time="2026-07-22")  # 2 days from the 2026-07-20 step
    matches, refusals = scorecard.colocate(ds, near)
    assert len(matches) == 6
    assert refusals.no_model_time == 0

    far = profile_frame(time="2026-08-20")  # 21 days past the last step
    matches, refusals = scorecard.colocate(ds, far)
    assert matches == []
    assert refusals.no_model_time == 6


def test_the_time_offset_is_reported_with_the_numbers():
    """A three-day-old comparison and a one-hour one are not the same evidence."""
    ds = linear_cube()
    frame = profile_frame(time="2026-07-22T12:00:00")
    matches, _ = scorecard.colocate(ds, frame)

    assert all(abs(m.time_offset_hours - 60.0) < 0.01 for m in matches)
    card = scorecard.score(matches, scorecard.Refusals(), variable="TEMP", units="degC")
    assert card["time_offset_hours"]["median"] == pytest.approx(60.0, abs=0.01)
    assert card["time_offset_hours"]["max"] == pytest.approx(60.0, abs=0.01)


def test_a_level_with_no_observation_is_never_counted_as_a_qc_rejection():
    """"Failed quality control" and "was never measured" are different sentences.

    A biogeochemical float reports oxygen at levels where its CTD reported
    nothing. Filing those under rejected_qc told a reader that thousands of
    observations had failed QC, which is a statement about the data nobody
    could then trust.
    """
    ds = linear_cube()
    depths = np.array([10.0, 20.0, 50.0, 100.0])
    temps = np.array([analytic(10.0, 11.4, 86.7), np.nan, np.nan, analytic(100.0, 11.4, 86.7)])
    # Unmeasured levels usually carry flag 9, "no QC performed", so a naive
    # order of checks would file them as rejections.
    frame = profile_frame(depths=depths, temps=temps, qc=np.array([1, 9, 9, 1]))

    matches, refusals = scorecard.colocate(ds, frame)

    assert len(matches) == 2
    assert refusals.no_observation == 2
    assert refusals.rejected_qc == 0


def test_flags_outside_the_accepted_set_are_rejected():
    """Wong et al. 2020: flags 1 and 2 only, the same filter /profiles uses."""
    ds = linear_cube()
    depths = np.array([10.0, 20.0, 50.0, 100.0])
    frame = profile_frame(depths=depths, qc=np.array([1, 2, 3, 4]))

    matches, refusals = scorecard.colocate(ds, frame)

    assert len(matches) == 2
    assert refusals.rejected_qc == 2
    assert refusals.no_observation == 0
    assert sorted(m.depth for m in matches) == [10.0, 20.0]


def test_a_value_with_no_flag_at_all_is_refused_and_counted_apart():
    """accept_flags is a whitelist, so an unflagged value has passed nothing."""
    ds = linear_cube()
    depths = np.array([10.0, 20.0])
    frame = profile_frame(depths=depths, qc=np.array([1.0, np.nan]))

    matches, refusals = scorecard.colocate(ds, frame)

    assert len(matches) == 1
    assert refusals.no_qc_flag == 1
    assert refusals.rejected_qc == 0


def test_every_level_is_either_matched_or_counted_as_refused():
    """No level may vanish. The refusal count is part of the answer, not a log.

    One profile of eight levels, arranged so that every refusal path fires at
    least once, plus one profile parked outside the grid.
    """
    ds = linear_cube()
    lat, lon = 11.4, 86.7
    depths = np.array([2.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1500.0])
    temps = np.array([analytic(d, lat, lon) for d in depths])
    temps[2] = np.nan
    frame = profile_frame(
        depths=depths, temps=temps, qc=np.array([1, 1, 9, 3, 1, 1, np.nan, 1])
    )
    outside = profile_frame(profile_id="P2", wmo="2900002", lat=30.0, lon=86.7)
    both = pd.concat([frame, outside], ignore_index=True)

    matches, refusals = scorecard.colocate(ds, both)

    assert len(matches) + refusals.total == len(both)
    assert refusals.outside_depth_range == 2  # 2 m above the top, 1500 m below the floor
    assert refusals.no_observation == 1
    assert refusals.rejected_qc == 1
    assert refusals.no_qc_flag == 1
    assert refusals.outside_grid == 6
    assert len(matches) == 3


def test_a_missing_stencil_is_reported_as_such_and_not_as_a_match():
    """The one refusal that only appears once the model itself is holed."""
    ds = linear_cube()
    holed = ds.copy(deep=True)
    holed["TEMP"][:, :, 1, 2] = np.nan  # one of the four cells around 11.4 N, 86.7 E

    matches, refusals = scorecard.colocate(holed, profile_frame())

    assert matches == []
    assert refusals.missing_stencil == 6


def test_an_unknown_variable_or_column_yields_nothing_rather_than_an_exception():
    ds = linear_cube()
    frame = profile_frame()

    assert scorecard.colocate(ds, frame, variable="SAL") == ([], scorecard.Refusals())
    assert scorecard.colocate(ds, frame, observed_column="psal") == (
        [],
        scorecard.Refusals(),
    )
    assert scorecard.colocate(ds, frame.iloc[0:0]) == ([], scorecard.Refusals())


# --------------------------------------------------------------------------
# What the card says about itself
# --------------------------------------------------------------------------


def test_the_card_carries_the_caveat_that_this_is_not_forecast_skill():
    """The analysis assimilates these profiles. Every number inherits that.

    If this assertion is ever deleted the tool starts publishing a skill claim
    it cannot defend, which is the single most likely way this feature could
    embarrass us in front of an INCOIS reviewer.
    """
    ds = linear_cube()
    matches, refusals = scorecard.colocate(ds, profile_frame())
    card = scorecard.score(matches, refusals, variable="TEMP", units="degC")

    assert "NOT forecast skill" in card["caveat"]
    assert "assimilates" in card["caveat"]
    assert "observation space" in card["method"]
    assert card["label"] == "Class-4-style verification"


def test_the_card_names_the_instruments_behind_the_number():
    """A skill number with no platforms behind it is not attributable."""
    ds = linear_cube()
    both = pd.concat(
        [profile_frame(), profile_frame(profile_id="P2", wmo="2900002", lat=12.4)],
        ignore_index=True,
    )
    matches, refusals = scorecard.colocate(ds, both)
    card = scorecard.score(matches, refusals, variable="TEMP", units="degC")

    assert card["n_profiles"] == 2
    assert card["n_platforms"] == 2
    assert card["platforms"] == ["2900001", "2900002"]
    assert card["overall"]["n"] == 12


def test_a_perfect_model_scores_zero_and_says_how_many_pairs_it_used():
    """The sanity anchor: identical fields must not produce a non-zero RMSE."""
    ds = linear_cube()
    matches, refusals = scorecard.colocate(ds, profile_frame())
    card = scorecard.score(matches, refusals, variable="TEMP", units="degC")

    assert card["overall"]["n"] == 6
    assert card["overall"]["bias"] == 0.0
    assert card["overall"]["rmse"] == 0.0
    assert card["refused"]["total"] == 0


# --------------------------------------------------------------------------
# Over the API
# --------------------------------------------------------------------------


@pytest.fixture
def scored_client(tmp_path, monkeypatch):
    """A cube plus a profiles table, both synthetic, wired to the real app."""
    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.provenance import write_provenance
    from app.store import clear_caches

    root = tmp_path / "cube"
    root.mkdir()
    ds = linear_cube()
    ds.depth.attrs.update(units="m", positive="down", standard_name="depth")
    ds.attrs["source_id"] = "incois_vam_argo"
    store_path = root / "incois_vam_bob.zarr"
    ds.to_zarr(store_path, mode="w")
    write_provenance(
        store_path,
        source_id="incois_vam_argo",
        title="linear analytic field (test fixture)",
        citation="test fixture -- not real data",
        variables=["TEMP"],
        extra={"fixture": True},
    )

    frame = pd.concat(
        [profile_frame(), profile_frame(profile_id="P2", wmo="2900002", lat=12.4)],
        ignore_index=True,
    )
    frame.to_parquet(root / "profiles.parquet")

    monkeypatch.setenv("SAGAR_CUBE", str(root))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    clear_caches()


def test_the_scorecard_endpoint_serves_a_complete_card(scored_client):
    r = scored_client.get("/scorecard/incois_vam_argo/TEMP")
    assert r.status_code == 200
    body = r.json()

    assert body["variable"] == "TEMP"
    assert body["units"] == "degC"
    assert body["source_id"] == "incois_vam_argo"
    assert body["observed_column"] == "temp"
    assert body["overall"]["n"] == 12
    assert body["overall"]["rmse"] == 0.0
    assert body["observation_sources"] == ["argo_gdac_indian"]
    # The registry TITLE as well as the id. A panel that printed the id was
    # attributing the number to a database key rather than to an instrument
    # programme, which is the same information and none of the meaning.
    assert body["observation_titles"] == ["Argo GDAC (Ifremer) - Indian Ocean daily profile files"]
    assert body["observation_citations"] and body["observation_citations"][0]
    assert body["citation"]
    assert len(body["by_depth"]) == len(scorecard.DEPTH_BINS)
    assert "NOT forecast skill" in body["caveat"]


def test_the_scorecard_endpoint_honours_a_bounding_box(scored_client):
    r = scored_client.get(
        "/scorecard/incois_vam_argo/TEMP", params={"bbox": "86.0,11.0,87.0,12.0"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["n_profiles"] == 1
    assert body["platforms"] == ["2900001"]


def test_the_scorecard_endpoint_refuses_what_it_does_not_have(scored_client):
    assert scored_client.get("/scorecard/not_a_dataset/TEMP").status_code == 404
    assert scored_client.get("/scorecard/incois_vam_argo/NOPE").status_code == 404

    r = scored_client.get("/scorecard/incois_vam_argo/TEMP", params={"observed": "doxy"})
    assert r.status_code == 404
    # The refusal must say what IS available, or the caller is left guessing.
    assert "temp" in r.json()["detail"]

    r = scored_client.get(
        "/scorecard/incois_vam_argo/TEMP", params={"bbox": "not,a,bounding,box"}
    )
    assert r.status_code == 400


def test_the_real_cube_scores_worst_in_the_thermocline(monkeypatch):
    """The claim we will actually make on stage, checked against the real cube.

    Not a tolerance on a magic number: the assertion is the SHAPE of the error
    profile. A model of the tropical Indian Ocean is nearly exact below a
    kilometre, where the water barely changes, and worst across the thermocline,
    where a metre of vertical displacement is a degree of temperature. If that
    ordering ever inverts, either the depth axis has been mishandled or the
    colocation is matching the wrong levels.
    """
    import pathlib

    from app.config import get_settings
    from app.store import clear_caches, load_profiles, open_cube

    root = pathlib.Path(__file__).resolve().parents[3] / "data" / "cube"
    if not (root / "incois_vam_bob.zarr").is_dir() or not (root / "profiles.parquet").is_file():
        pytest.skip("no local cube; run tools/fetch_sample.py then tools/preprocess.py")

    monkeypatch.setenv("SAGAR_CUBE", str(root))
    get_settings.cache_clear()
    clear_caches()
    try:
        ds, _ = open_cube("incois_vam_argo")
        matches, refusals = scorecard.colocate(ds, load_profiles())
        card = scorecard.score(matches, refusals, variable="TEMP", units="degC")
    finally:
        get_settings.cache_clear()
        clear_caches()

    by_bin = {(b["depth_min"], b["depth_max"]): b for b in card["by_depth"]}
    thermocline = by_bin[(50.0, 100.0)]
    deep = by_bin[(1000.0, 2000.0)]

    assert thermocline["n"] > 100 and deep["n"] > 100
    assert thermocline["rmse"] > deep["rmse"] * 5, (
        f"thermocline {thermocline['rmse']} vs deep {deep['rmse']}"
    )
    assert abs(card["overall"]["bias"]) < 0.5, "a whole degree of mean bias is a bug, not a model"
    # Every refused level accounted for, on real data with real coastlines.
    assert card["refused"]["total"] > 0
    assert card["refused"]["no_observation"] > card["refused"]["rejected_qc"]
