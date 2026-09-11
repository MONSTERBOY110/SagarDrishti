"""Current vectors: decimating a velocity field without lying about it (F1).

The problem statement names current vectors among the fields F1 must render,
and this is the last clause of F1 that had no code behind it. The data arrived
on 2026-09-09 with the Copernicus account: 241 x 181 cells per level at 1/12
degree, which is 43,561 arrows if drawn one per cell.

Nobody can read 43,561 arrows, and the frame budget in TRD section 5 could not
draw them anyway, so the field is REDUCED before it is drawn. That reduction is
the whole subject of this module, and every test here is about doing it without
misrepresenting the ocean:

  * a block is AVERAGED, not sampled. Taking every Nth cell is aliasing, and on
    a velocity field it invents structure that is not there.
  * a block that is mostly land is REFUSED, not averaged from the two wet cells
    that remain, which is exactly the coastline where a forecaster is reading.
  * a refused block is COUNTED, so a sparse-looking arrow field can be told
    apart from a broken one.
  * the reduction is DISCLOSED: the response says the stride it used, how many
    source cells went into each arrow, and how many blocks it dropped.

Speed is computed here rather than in the browser for the ordinary reason:
it is a number, so it comes from the data plane with the rest of them.
"""

from __future__ import annotations

import numpy as np
import pytest

from app import currents


def field(ny: int, nx: int, u: float = 1.0, v: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    return np.full((ny, nx), u), np.full((ny, nx), v)


def axes(ny: int, nx: int) -> tuple[np.ndarray, np.ndarray]:
    """Degrees, one per cell, spaced a twelfth apart like the real product."""
    return (
        np.arange(ny, dtype="float64") / 12.0 + 5.0,
        np.arange(nx, dtype="float64") / 12.0 + 80.0,
    )


# --------------------------------------------------------------------------
# The reduction itself
# --------------------------------------------------------------------------


def test_a_block_is_averaged_rather_than_sampled():
    """Sampling every Nth cell aliases, and on a velocity field aliasing
    invents eddies. The arrow has to be the block's mean flow."""
    u = np.array([[1.0, 3.0], [5.0, 7.0]])
    v = np.array([[0.0, 0.0], [0.0, 0.0]])
    lats, lons = axes(2, 2)

    grid = currents.decimate(u, v, lats, lons, stride=2)

    assert len(grid.arrows) == 1
    a = grid.arrows[0]
    assert a["u"] == pytest.approx(4.0), "the mean of 1, 3, 5 and 7"
    assert a["n"] == 4, "and it says how many cells that was"


def test_the_arrow_sits_at_the_centre_of_the_block_it_summarises():
    u, v = field(4, 4)
    lats, lons = axes(4, 4)

    grid = currents.decimate(u, v, lats, lons, stride=4)

    assert len(grid.arrows) == 1
    a = grid.arrows[0]
    assert a["lat"] == pytest.approx(float(lats.mean()))
    assert a["lon"] == pytest.approx(float(lons.mean()))


def test_speed_is_computed_here_rather_than_in_the_browser():
    """It is a number, so it comes from the data plane with the rest of them."""
    u, v = field(2, 2, u=3.0, v=4.0)
    lats, lons = axes(2, 2)

    a = currents.decimate(u, v, lats, lons, stride=2).arrows[0]

    assert a["speed"] == pytest.approx(5.0), "3-4-5, from the block mean"


def test_a_ragged_edge_still_produces_an_arrow_from_the_cells_it_has():
    """A 5-cell axis at stride 2 leaves a block of one column. That is a real
    block with real values, not an error."""
    u, v = field(5, 5)
    lats, lons = axes(5, 5)

    grid = currents.decimate(u, v, lats, lons, stride=2)

    assert len(grid.arrows) == 9, "3 x 3 blocks, the last of each row ragged"
    assert grid.refused == 0


# --------------------------------------------------------------------------
# What it refuses, which is the coast
# --------------------------------------------------------------------------


def test_a_block_that_is_mostly_land_is_refused_rather_than_averaged():
    """Two wet cells out of sixteen is not a current, it is a coastline. And
    the coast is exactly where a forecaster is reading."""
    u = np.full((4, 4), np.nan)
    v = np.full((4, 4), np.nan)
    u[0, 0] = u[0, 1] = 1.0
    v[0, 0] = v[0, 1] = 1.0
    lats, lons = axes(4, 4)

    grid = currents.decimate(u, v, lats, lons, stride=4)

    assert grid.arrows == []
    assert grid.refused == 1


def test_a_block_that_is_mostly_water_is_kept_and_says_how_much():
    u = np.full((4, 4), 2.0)
    v = np.zeros((4, 4))
    u[0, 0] = np.nan
    v[0, 0] = np.nan
    lats, lons = axes(4, 4)

    grid = currents.decimate(u, v, lats, lons, stride=4)

    assert len(grid.arrows) == 1
    a = grid.arrows[0]
    assert a["n"] == 15, "fifteen wet cells of sixteen"
    assert a["u"] == pytest.approx(2.0), "and the land cell contributes nothing"


def test_a_wholly_dry_block_is_refused_and_counted():
    u = np.full((4, 4), np.nan)
    v = np.full((4, 4), np.nan)
    lats, lons = axes(4, 4)

    grid = currents.decimate(u, v, lats, lons, stride=2)

    assert grid.arrows == []
    assert grid.refused == 4


def test_a_cell_finite_in_u_but_not_in_v_is_not_half_a_current():
    """A velocity needs both components. Averaging u over cells where v is
    missing would produce an arrow pointing somewhere nothing measured."""
    u = np.full((2, 2), 1.0)
    v = np.full((2, 2), 1.0)
    v[0, 0] = np.nan
    lats, lons = axes(2, 2)

    a = currents.decimate(u, v, lats, lons, stride=2).arrows[0]

    assert a["n"] == 3, "only the cells with BOTH components"


# --------------------------------------------------------------------------
# Choosing the stride, and saying which one was chosen
# --------------------------------------------------------------------------


def test_the_stride_is_chosen_to_hit_an_arrow_budget():
    """43,561 cells is the real number for one GLORYS level over the demo box.
    Nobody can read that many arrows and the frame budget cannot draw them."""
    stride = currents.stride_for(241, 181, budget=600)

    assert stride > 1
    assert (241 // stride) * (181 // stride) <= 600


def test_a_field_already_small_enough_is_not_reduced_at_all():
    """The INCOIS analysis is 21 x 16. Thinning that would be damage for no
    gain, so the stride comes back as 1."""
    assert currents.stride_for(21, 16, budget=600) == 1


def test_the_reduction_is_disclosed_on_the_result():
    """A thinned field must never be presented as the grid the model ran on."""
    u, v = field(24, 24)
    lats, lons = axes(24, 24)

    grid = currents.decimate(u, v, lats, lons, stride=4)

    assert grid.stride == 4
    assert grid.source_cells == 24 * 24
    assert len(grid.arrows) == 36
    assert "averaged" in grid.note.lower()
    assert "4" in grid.note


def test_an_empty_field_is_an_empty_grid_rather_than_an_error():
    grid = currents.decimate(
        np.zeros((0, 0)), np.zeros((0, 0)), np.array([]), np.array([]), stride=4
    )
    assert grid.arrows == [] and grid.refused == 0


# --------------------------------------------------------------------------
# Over the API, against the real Copernicus cube
# --------------------------------------------------------------------------


def test_the_route_serves_real_arrows_from_the_real_currents(shipped_currents_client):
    r = shipped_currents_client.get(
        "/currents/glorys12_cur",
        params={"bbox": "80,5,95,25", "time": "2026-07-30", "depth": 100},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["count"] > 50, "a readable arrow field, not three arrows"
    assert body["count"] <= body["budget"]
    assert body["stride"] > 1, "the native grid is far too dense to draw"
    assert body["units"] == "m s-1"
    assert "Copernicus" in body["citation"]

    # The DEPTH IT ACTUALLY SERVED, not the depth asked for. GLORYS has its own
    # levels and none of them is exactly 100 m; saying 100 would be a small
    # lie that costs nothing to avoid.
    assert body["depth"] != 100
    assert 90 < body["depth"] < 110
    assert body["requested_depth"] == 100

    speeds = [a["speed"] for a in body["arrows"]]
    assert max(speeds) < 5.0, "ocean currents, not a typo in the units"
    assert all(a["n"] >= 1 for a in body["arrows"])


def test_the_route_counts_the_coastal_blocks_it_refused(shipped_currents_client):
    """The Bay of Bengal box has a lot of land in it. A sparse arrow field has
    to be distinguishable from a broken one."""
    body = shipped_currents_client.get(
        "/currents/glorys12_cur",
        params={"bbox": "80,5,95,25", "time": "2026-07-30", "depth": 100},
    ).json()

    assert body["refused"] > 0, "there is land in this box"
    assert body["count"] + body["refused"] == body["blocks"]
    assert "averaged" in body["note"].lower()


def test_the_route_refuses_a_variable_pair_the_dataset_does_not_have(
    shipped_currents_client,
):
    r = shipped_currents_client.get(
        "/currents/incois_vam_argo",
        params={"bbox": "80,5,95,25", "time": "2026-07-30", "depth": 100},
    )
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "uo" in detail and "vo" in detail
    # It says which dataset DOES carry them, so the caller is not left guessing.
    assert "glorys12_cur" in detail


def test_the_route_refuses_an_unknown_dataset(shipped_currents_client):
    r = shipped_currents_client.get(
        "/currents/not_a_dataset",
        params={"bbox": "80,5,95,25", "time": "2026-07-30", "depth": 100},
    )
    assert r.status_code == 404
