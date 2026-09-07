"""API contract for /field and /profiles (TRD M2).

The browser and the agent call these same endpoints -- that shared surface is
what lets the agent plane be detached without touching P0 (TRD §6.5). So the
contract is tested, not assumed.
"""

from __future__ import annotations

import numpy as np


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
    """CLAUDE.md: numbers reach an answer only with dataset + timestamp. The
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
