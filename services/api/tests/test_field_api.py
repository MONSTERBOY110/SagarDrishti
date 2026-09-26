"""API contract for /field and /profiles (TRD M2).

The browser and the agent call these same endpoints -- that shared surface is
what lets the agent plane be detached without touching P0 (TRD §6.5). So the
contract is tested, not assumed.
"""

from __future__ import annotations

import numpy as np
import pytest


def test_healthz_reports_offline_by_default(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["offline"] is True


def test_catalog_lists_only_enabled_sources_with_citations(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()

    ids = [d["id"] for d in body["datasets"]]
    assert "incois_vam_argo" in ids
    assert "glorys12" not in ids, "a source with no credentials must not be offered"

    vam = next(d for d in body["datasets"] if d["id"] == "incois_vam_argo")
    assert vam["citation"], "every dataset must ship a citation string"
    assert vam["depths"][0] == 5.0 and vam["depths"][-1] == 1000.0
    assert len(vam["times"]) == 3
    assert {v["name"] for v in vam["variables"]} >= {"TEMP"}


# --- Test 5: subsetting and error contract ----------------------------------

def test_field_returns_exactly_the_requested_cells(client):
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "86.0,11.0,88.0,13.0", "depth": 100.0, "time": "2026-07-30T00:00:00Z"},
    )
    assert r.status_code == 200
    body = r.json()

    # bbox 86-88 E x 11-13 N over a 1-degree grid -> lons 86.5,87.5 / lats 11.5,12.5
    assert body["shape"] == [2, 2]
    assert body["lons"] == [86.5, 87.5]
    assert body["lats"] == [11.5, 12.5]
    assert len(body["values"]) == 4

    # the depth actually served is the nearest available level, and it says so
    assert body["depth"] == 100.0
    assert body["time"].startswith("2026-07-30")

    vals = np.array([v for v in body["values"] if v is not None], dtype="float64")
    assert vals.size == 4
    assert 15.0 < vals.mean() < 30.0, "values are not plausible temperatures"


def test_field_reports_provenance_for_every_response(client):
    """CONTRIBUTING.md: numbers reach an answer only with dataset + timestamp. The
    API is where that guarantee has to originate."""
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "86.0,11.0,88.0,13.0", "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
    )
    body = r.json()

    assert body["source_id"] == "incois_vam_argo"
    assert body["citation"]
    assert body["units"] == "degC"
    assert body["variable"] == "TEMP"


def test_field_masks_land_as_null_not_a_number(client):
    """The fixture has a fill cell at (lat 10.5, lon 85.5). It must arrive as
    null, so the client cannot colour it."""
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "85.0,10.0,86.0,11.0", "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
    )
    assert r.status_code == 200
    assert r.json()["values"] == [None]


def test_field_full_column_returns_every_depth(client):
    """The volumetric renderer asks for the whole stack in one call, so this is
    the hot path for Spike A."""
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "86.0,11.0,88.0,13.0", "time": "2026-07-30T00:00:00Z", "all_depths": True},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["shape"] == [8, 2, 2]
    assert body["depths"] == [5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0]
    assert len(body["values"]) == 8 * 2 * 2

    # a thermocline must be present: the surface is much warmer than 1000 m
    col = np.array(body["values"], dtype="float64").reshape(8, 2, 2)
    assert np.nanmean(col[0]) - np.nanmean(col[-1]) > 10.0


def test_unknown_dataset_is_404(client):
    r = client.get(
        "/field/no_such_source/TEMP",
        params={"bbox": "86,11,88,13", "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
    )
    assert r.status_code == 404
    assert "no_such_source" in r.json()["detail"]


def test_unknown_variable_is_404_and_lists_what_exists(client):
    r = client.get(
        "/field/incois_vam_argo/BANANAS",
        params={"bbox": "86,11,88,13", "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
    )
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "BANANAS" in detail and "TEMP" in detail, "tell the caller what is available"


def test_malformed_bbox_is_400_with_a_useful_message(client):
    for bad in ["1,2,3", "a,b,c,d", "88,13,86,11", "86,11,86,13"]:
        r = client.get(
            "/field/incois_vam_argo/TEMP",
            params={"bbox": bad, "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
        )
        assert r.status_code == 400, f"bbox {bad!r} should be rejected"
        assert "bbox" in r.json()["detail"].lower()


def test_bbox_outside_the_domain_is_400_not_an_empty_array(client):
    """An empty grid renders as a blank globe and looks like a bug in the
    renderer. Fail loudly at the source instead."""
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "-40,-80,-30,-70", "depth": 5.0, "time": "2026-07-30T00:00:00Z"},
    )
    assert r.status_code == 400
    assert "outside" in r.json()["detail"].lower()


def test_time_outside_the_range_is_400(client):
    r = client.get(
        "/field/incois_vam_argo/TEMP",
        params={"bbox": "86,11,88,13", "depth": 5.0, "time": "1999-01-01T00:00:00Z"},
    )
    assert r.status_code == 400
    assert "time" in r.json()["detail"].lower()


# --- GET /isosurface (PS requirement F1) ------------------------------------
#
# The extraction maths is tested in test_isosurface.py. What is tested here is
# the seam: that the route inherits the same bbox and time refusals /field
# already has, that the isovalue's units are checked rather than assumed, and
# that the response carries enough provenance for a saved payload to be
# explained without the URL that produced it.

ISO = "/isosurface/incois_vam_argo/TEMP"


def _iso(client, **extra):
    params = {
        "value": "26",
        "value_units": "degC",
        "bbox": "85,10,88,14",
        "time": "2026-07-30",
    }
    params.update(extra)
    return client.get(ISO, params=params)


def test_isosurface_returns_a_mesh_with_its_provenance(client):
    r = _iso(client)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["source_id"] == "incois_vam_argo"
    assert body["variable"] == "TEMP"
    assert body["units"] == "degC"
    assert body["value"] == 26.0
    # The SNAPPED time, not the request string: a mesh labelled with what was
    # asked for rather than what was served is a number without provenance.
    assert body["time"].startswith("2026-07-30T")
    assert body["citation"], "every mesh must carry a citation"
    assert body["extractor"] == "marching_cubes"
    assert body["extractor_version"]

    # The method has to be specific enough to argue with, at the same standard
    # the D26 plugin's method string already sets.
    method = body["method"]
    for phrase in ("marching cubes", ">= the isovalue", "all eight corners", "non-uniform"):
        assert phrase in method, f"the method does not mention {phrase!r}"

    assert body["n_triangles"] > 0
    assert len(body["positions"]) == body["n_vertices"] * 3
    assert len(body["indices"]) == body["n_triangles"] * 3
    assert len(body["dz_bracket"]) == body["n_vertices"]
    assert len(body["on_edge"]) == body["n_vertices"]


def test_the_mesh_is_anchored_to_the_grid_it_came_from(client):
    """A vertex must be traceable back to cube cells, not float free."""
    body = _iso(client).json()

    assert body["lats"] and body["lons"] and body["depths"]
    assert body["depths"] == sorted(body["depths"])
    positions = body["positions"]
    lons = positions[0::3]
    lats = positions[1::3]
    depths = positions[2::3]
    assert min(lons) >= min(body["lons"]) - 1e-6
    assert max(lons) <= max(body["lons"]) + 1e-6
    assert min(lats) >= min(body["lats"]) - 1e-6
    assert max(lats) <= max(body["lats"]) + 1e-6
    # Depth positive down, inside the levels the cube actually holds.
    assert min(depths) >= min(body["depths"]) - 1e-6
    assert max(depths) <= max(body["depths"]) + 1e-6


def test_the_honesty_counters_are_all_present(client):
    """The mesh analogue of n_cells and n_valid.

    Land and the seabed leave a hole in the surface, and the count of cells
    that straddled the isovalue but were refused for a missing corner is what
    makes that hole a stated decision rather than something a reviewer finds.
    """
    body = _iso(client).json()

    for key in (
        "n_vertices", "n_triangles", "n_cells", "n_cells_active",
        "n_cells_skipped_missing_corner", "n_cells_straddling_but_masked",
        "n_cells_exact_tie", "n_ambiguous_cells", "n_degenerate_culled",
        "n_components", "n_boundary_edges", "depth_min", "depth_max",
        "max_bracket_thickness",
    ):
        assert key in body, f"missing counter {key}"

    assert body["n_cells_active"] > 0
    assert body["n_cells_skipped_missing_corner"] > 0, "the fixture has land in it"
    # A surface that leaves the box has a legitimate rim, so this is expected
    # rather than a defect. Its being zero on a field with land would be the
    # surprise.
    assert body["n_boundary_edges"] > 0


def test_a_mismatched_isovalue_unit_is_refused(client):
    """26 degC and 26 K are different surfaces and both look reasonable in a
    URL. Relabelling a number whose units were never converted is exactly the
    failure the CF work exists to prevent."""
    r = _iso(client, value="299", value_units="K")

    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "value_units" in detail and "'K'" in detail
    assert "degC" in detail
    assert "Convert the value first" in detail


def test_value_units_is_required_not_defaulted(client):
    """Defaulting it would make the dangerous case the silent one."""
    r = client.get(ISO, params={"value": "26", "bbox": "85,10,88,14", "time": "2026-07-30"})
    assert r.status_code == 422


def test_an_isovalue_outside_the_field_is_an_empty_mesh_not_an_error(client):
    """"No 500 degC surface exists in this box at this time" is a true answer
    with a dataset and a timestamp behind it. A 404 would say the request was
    malformed, which it was not."""
    r = _iso(client, value="500")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_vertices"] == 0
    assert body["n_triangles"] == 0
    assert body["positions"] == [] and body["indices"] == []
    # The provenance block is still complete, so the emptiness is citable.
    assert body["citation"] and body["time"] and body["method"]
    assert body["n_cells"] > 0, "it still looked at the whole grid"


def test_the_bbox_and_time_refusals_are_inherited_not_reimplemented(client):
    bad_box = _iso(client, bbox="200,10,88,14")
    assert bad_box.status_code == 400
    assert "must lie in [-180, 180]" in bad_box.json()["detail"]

    bad_time = _iso(client, time="1999-01-01")
    assert bad_time.status_code == 400
    assert "outside the available range" in bad_time.json()["detail"]


def test_an_unknown_variable_names_what_is_available(client):
    r = client.get(
        "/isosurface/incois_vam_argo/NOPE",
        params={"value": "26", "value_units": "degC", "bbox": "85,10,88,14", "time": "2026-07-30"},
    )
    assert r.status_code == 404
    assert "TEMP" in r.json()["detail"]


def test_a_derived_surface_product_cannot_be_meshed(client):
    """D26 is already a surface. Asking for the isosurface of a depth field is
    a different question, and answering it as though it were the same one would
    produce a confident picture of nothing in particular."""
    r = client.get(
        "/isosurface/incois_vam_argo/D26",
        params={"value": "60", "value_units": "m", "bbox": "85,10,88,14", "time": "2026-07-30"},
    )
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "no volume to mesh" in detail


def test_an_unknown_dataset_points_at_the_catalog(client):
    r = client.get(
        "/isosurface/nope/TEMP",
        params={"value": "26", "value_units": "degC", "bbox": "85,10,88,14", "time": "2026-07-30"},
    )
    assert r.status_code == 404
    assert "GET /catalog" in r.json()["detail"]


@pytest.fixture
def shipped_iso_client(monkeypatch):
    """Pointed at the REAL cube, for the claims that are about real ocean.

    The synthetic fixture is a smooth exponential profile with one land column,
    which is right for testing the contract and useless for testing whether the
    Bay of Bengal actually behaves the way the method choice assumed.
    """
    import pathlib

    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    root = pathlib.Path(__file__).resolve().parents[3] / "data" / "cube"
    if not (root / "incois_vam_bob.zarr").is_dir():
        pytest.skip("no local cube; run tools/fetch_sample.py then tools/preprocess.py")

    monkeypatch.setenv("SAGAR_CUBE", str(root))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    clear_caches()


def test_the_real_coastal_refusals_are_counted(shipped_iso_client):
    """Land and the shelf put a hole in the surface exactly where a cyclone
    forecaster looks. The count is what makes that a disclosed refusal instead
    of an artifact a reviewer discovers."""
    r = shipped_iso_client.get(
        "/isosurface/incois_vam_argo/TEMP",
        params={"value": "26", "value_units": "degC", "bbox": "80,5,95,25", "time": "2026-07-30"},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["n_cells_straddling_but_masked"] > 0
    assert body["n_cells_skipped_missing_corner"] > body["n_cells_active"]
    assert "INCOIS" in body["citation"]
    # The 26 degC isotherm sits in the upper hundred-odd metres of this basin.
    assert 20.0 < body["depth_min"] < 80.0
    assert 60.0 < body["depth_max"] < 250.0


def test_the_salinity_surface_is_multi_valued_which_is_the_whole_point(shipped_iso_client):
    """A single-depth-per-column product cannot represent this at all.

    The 35 psu isohaline in the Bay of Bengal is crossed several times in
    nearly every valid column, because monsoon and river freshwater cap saltier
    water beneath. A height field would have to pick one crossing and call it
    the surface, which would be wrong rather than merely lossy. This is the
    concrete reason marching cubes was chosen over a depth-per-column product.
    """
    r = shipped_iso_client.get(
        "/isosurface/incois_vam_argo/SAL",
        params={"value": "35", "value_units": "1", "bbox": "80,5,95,25", "time": "2026-07-30"},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["n_triangles"] > 0
    assert body["n_components"] > 1, (
        "the isohaline should break into several surfaces; one component would "
        "suggest the extractor is collapsing the structure"
    )
    assert body["depth_max"] > body["depth_min"] + 50, (
        "a multi-valued surface should span a real depth range"
    )


def test_the_inversion_date_yields_a_second_component_over_the_api(shipped_iso_client):
    """End to end, the structure that justifies the whole method choice."""
    def mesh(when):
        r = shipped_iso_client.get(
            "/isosurface/incois_vam_argo/TEMP",
            params={"value": "26", "value_units": "degC",
                    "bbox": "80,5,95,25", "time": when},
        )
        assert r.status_code == 200, r.text
        return r.json()

    inverted = mesh("2026-07-10")
    plain = mesh("2026-07-30")

    assert inverted["n_components"] == 2, (
        "the Bay of Bengal barrier-layer inversion should separate a warm lens "
        "from the main thermocline sheet"
    )
    assert plain["n_components"] == 1
    assert inverted["depth_max"] > plain["depth_max"]


# --- a date outside the observations is a refusal, not an empty list --------
#
# /field has refused an out-of-range time since the beginning, through
# store.nearest_time. /profiles did not: it compared the requested day for
# equality and returned whatever matched, so a date years away from the
# observations answered HTTP 200 with count 0.
#
# The two must agree. An empty list is a statement about the OCEAN ("no floats
# in this box"); the true statement is about the REQUEST ("no observations from
# that date"). A client holding a 2020 field and a 2026 float set would be told
# nothing at all, which is exactly the failure mode the epoch work exists to
# prevent.


def test_profiles_refuses_a_date_outside_the_observations(shipped_iso_client):
    r = shipped_iso_client.get("/profiles", params={"time": "1999-01-01"})

    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    # Measured against the NEAREST observation rather than the span's ends.
    # Once the archive glider and CTD casts joined the table the holdings
    # stopped being one cluster, and a span test would call 1999 "in range" on
    # the strength of observations nine and nineteen years away from it.
    assert "from the nearest observation" in detail
    # It must say what the table actually holds, or the caller guesses again.
    assert "2026" in detail
    # And it must say why an empty list would have been the wrong answer.
    assert "no floats in this box" in detail


def test_a_date_in_a_gap_between_two_eras_is_refused_not_answered_empty(
    shipped_iso_client,
):
    """The failure a min-to-max range test cannot see.

    The profile table holds three clusters: shipboard CTD casts from 1990 and
    1991, a glider deployment in 2018, and the Argo floats of July 2026.
    Between them are decades in which this box holds nothing. Asking for a date
    inside one of those gaps is the same request as asking for 1999 from a
    table that stops in 2026, and it has to get the same refusal rather than a
    200 whose empty list reads as a statement about the ocean.
    """
    import datetime

    everything = shipped_iso_client.get("/profiles").json()["profiles"]
    days = sorted({p["time"][:10] for p in everything})
    if len(days) < 2:
        pytest.skip("only one observed day; there is no gap to ask about")

    # The midpoint of the widest gap, which is as far from any observation as
    # this table allows.
    parsed = [datetime.date.fromisoformat(d) for d in days]
    widest = max(zip(parsed, parsed[1:]), key=lambda pair: (pair[1] - pair[0]).days)
    span = (widest[1] - widest[0]).days
    if span <= 20:
        pytest.skip("no gap wide enough to fall outside the ten-day slack")
    middle = widest[0] + datetime.timedelta(days=span // 2)

    r = shipped_iso_client.get("/profiles", params={"time": middle.isoformat()})

    assert r.status_code == 400, r.text
    assert "from the nearest observation" in r.json()["detail"]


def test_profiles_still_returns_an_empty_list_for_a_quiet_day_in_range(shipped_iso_client):
    """The refusal must not swallow the legitimate empty case.

    A day inside the observed window on which nothing reported is a real answer
    about the OCEAN, and it stays a 200 with count 0.

    The quiet day is FOUND rather than hardcoded. It used to be 2026-07-09, and
    adding the RAMA mooring broke the test because the mooring reports that
    day: a test that pins a date is really pinning which instruments exist,
    which is not what it is for.
    """
    import datetime

    everything = shipped_iso_client.get("/profiles").json()["profiles"]
    busy = {p["time"][:10] for p in everything}
    days = sorted(busy)
    first = datetime.date.fromisoformat(days[0])
    last = datetime.date.fromisoformat(days[-1])

    quiet = None
    day = first
    while day <= last:
        if day.isoformat() not in busy:
            quiet = day.isoformat()
            break
        day += datetime.timedelta(days=1)
    if quiet is None:
        pytest.skip("every day in the observed window has a profile")

    r = shipped_iso_client.get("/profiles", params={"time": quiet})

    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0, f"{quiet} was expected to be quiet"


def test_profiles_accepts_a_day_that_has_floats(shipped_iso_client):
    r = shipped_iso_client.get("/profiles", params={"time": "2026-07-30"})

    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1


def test_profiles_refuses_an_unusable_timestamp(shipped_iso_client):
    """NaT parses without raising and compares False against everything, so it
    would have produced an empty list rather than an error.

    Uses the real cube because the endpoint returns early when there are no
    profiles at all, which is correct (there is nothing to filter) but means
    the synthetic fixture never reaches this validation.
    """
    r = shipped_iso_client.get("/profiles", params={"time": "not-a-date"})

    assert r.status_code == 400
    assert "time" in r.json()["detail"]


def test_the_time_refusal_does_not_depend_on_the_bbox(shipped_iso_client):
    """Narrowing the box must not change which DATES are legal.

    The range is taken from the whole profile table before any spatial filter.
    Computing it from the filtered subset instead would mean a date that was
    valid a moment ago becomes invalid after panning the map, and the caller
    would have no way to tell which of their two parameters the service was
    objecting to.
    """
    tiny_box = "86,11,87,12"

    in_range = shipped_iso_client.get(
        "/profiles", params={"time": "2026-07-09", "bbox": tiny_box}
    )
    assert in_range.status_code == 200, in_range.text

    out_of_range = shipped_iso_client.get(
        "/profiles", params={"time": "1999-01-01", "bbox": tiny_box}
    )
    assert out_of_range.status_code == 400
    # The dates quoted are the whole table's, not the tiny box's.
    assert "2026-07-30" in out_of_range.json()["detail"]
