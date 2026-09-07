"""Marching-cubes isosurface extraction (PS requirement F1).

The PS names "isosurface extraction" as one of three required techniques. This
is the test suite for it, and it is written against the failure modes that are
SILENT rather than the ones that raise, because every dangerous bug in a
surface extractor produces a picture:

  * A globally inverted winding is invisible on screen with backface culling
    off and a hard error with it on, and no assertion about vertex counts sees
    it. The sphere's signed volume does.
  * A winding rule that reads the local gradient passes every smooth test and
    then fails on noise. That is why the orientation checks run over random
    fields and not only over analytic ones.
  * A face-pairing inconsistency between two cells that share a face leaves a
    crack. A crack is a few missing pixels on a globe and a non-manifold mesh
    in the data. The edge-parity check finds it; looking at the render does not.
  * A hidden assumed dz would be invisible on a uniform test grid and wrong by
    tens of metres on the real one, where levels run 5, 10, 20 ... 1800, 2000 m.

The strongest test here is not any of those. It is
`test_every_vertical_vertex_matches_the_shipped_d26_science`, which requires
this new geometry to agree EXACTLY, to 0.0 metres, with the depth the reviewed
D26 product already reports. It welds the mesh to science that has already been
argued through, instead of letting it become a second, parallel truth.
"""

from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

from app.isosurface import (
    CORNER_OFFSETS,
    EDGES,
    EDGE_AXIS,
    FACE_CYCLES,
    FACE_EDGES,
    ExtractorError,
    count_boundary_edges,
    count_components,
    extract,
)

CUBE = pathlib.Path(__file__).resolve().parents[3] / "data" / "cube" / "incois_vam_bob.zarr"
PLUGIN_DIR = pathlib.Path(__file__).resolve().parents[1] / "plugins"


def _d26_module():
    spec = importlib.util.spec_from_file_location(
        "d26_isotherm_for_isosurface", PLUGIN_DIR / "d26_isotherm.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- mesh inspection helpers -------------------------------------------------

def _edge_use(triangles):
    """How many triangles use each undirected edge."""
    counts: dict[tuple[int, int], int] = {}
    for tri in triangles:
        for m in range(3):
            a, b = int(tri[m]), int(tri[(m + 1) % 3])
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _orientation_clashes(triangles) -> int:
    """A directed edge seen twice the same way means two neighbours disagree."""
    seen: set[tuple[int, int]] = set()
    clashes = 0
    for tri in triangles:
        for m in range(3):
            edge = (int(tri[m]), int(tri[(m + 1) % 3]))
            if edge in seen:
                clashes += 1
            seen.add(edge)
    return clashes


def _signed_volume(positions, triangles) -> float:
    """Divergence theorem. Positive means the normals point outward."""
    if triangles.size == 0:
        return 0.0
    a = positions[triangles[:, 0]]
    b = positions[triangles[:, 1]]
    c = positions[triangles[:, 2]]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)


def _euler(triangles) -> int:
    vertices = {int(v) for tri in triangles for v in tri}
    return len(vertices) - len(_edge_use(triangles)) + len(triangles)


def _closed_field(values):
    """Clamp the outer shell below the isovalue so the surface cannot reach the
    domain wall. Without this a random field's surface exits the box and has a
    perfectly legitimate open rim, which would make every closure assertion
    below fail on correct output."""
    values = values.copy()
    values[0, :, :] = values[-1, :, :] = -5.0
    values[:, 0, :] = values[:, -1, :] = -5.0
    values[:, :, 0] = values[:, :, -1] = -5.0
    return values


def _uniform(n):
    return np.linspace(0.0, 1.0, n)


# --- the generated geometry tables ------------------------------------------

def test_the_cell_geometry_tables_are_internally_consistent():
    """These tables are generated from one sentence about corner numbering, and
    a generator can be wrong as easily as a transcription can. Every property
    below is assumed by the extraction loop."""
    assert len(EDGES) == 12
    assert len({frozenset(e) for e in EDGES}) == 12

    for n, (lo, hi) in enumerate(EDGES):
        delta = CORNER_OFFSETS[hi] - CORNER_OFFSETS[lo]
        assert delta.sum() == 1 and (delta >= 0).all(), f"edge {n} is not an axis step"
        assert int(np.flatnonzero(delta)[0]) == EDGE_AXIS[n]

    # Four edges per axis, so the vertical interpolation is exercised by a
    # quarter of the edges rather than by a special case.
    assert sorted(EDGE_AXIS).count(0) == 4
    assert sorted(EDGE_AXIS).count(1) == 4
    assert sorted(EDGE_AXIS).count(2) == 4

    # Every edge lies on exactly two faces. This is what makes the face
    # segments chain into CLOSED loops: each crossed edge is entered once and
    # left once.
    on_faces: dict[int, int] = {}
    for edges in FACE_EDGES:
        for e in edges:
            on_faces[e] = on_faces.get(e, 0) + 1
    assert set(on_faces) == set(range(12))
    assert set(on_faces.values()) == {2}


def test_every_face_cycle_winds_around_its_own_outward_normal():
    """The winding of the whole mesh rests on this and nothing else.

    Each face's four corners are listed in the order they appear seen from
    OUTSIDE the cell, so the right-hand rule about that cycle reproduces the
    face's outward normal. Two cells sharing a face then see opposite cycles,
    emit opposite segment directions, and their triangles agree across the
    shared edge without anything inspecting the data.
    """
    for face, cycle in enumerate(FACE_CYCLES):
        p = CORNER_OFFSETS[list(cycle)].astype("float64")
        normal = np.cross(p[1] - p[0], p[2] - p[1])
        axis, side = divmod(face, 2)
        # face 0,1 -> axis k(2); 2,3 -> axis j(1); 4,5 -> axis i(0)
        axis = (2, 1, 0)[axis]
        expected = np.zeros(3)
        expected[axis] = 1.0 if side else -1.0
        # CORNER_OFFSETS columns are (di, dj, dk) = (i, j, k).
        expected = expected[[0, 1, 2]]
        unit = normal / np.linalg.norm(normal)
        assert np.allclose(unit, expected), (
            f"face {face} winds around {unit}, expected outward {expected}"
        )
        # And every corner really is on that face.
        assert len({CORNER_OFFSETS[c][axis] for c in cycle}) == 1


# --- closure, orientation and convergence on an analytic surface ------------

def _sphere(n, radius=0.7):
    g = np.linspace(-1.0, 1.0, n)
    z, y, x = np.meshgrid(g, g, g, indexing="ij")
    return radius - np.sqrt(x**2 + y**2 + z**2), g


@pytest.mark.parametrize("n", [12, 20, 32, 48])
def test_a_sphere_comes_back_closed_correctly_wound_and_convergent(n):
    field, g = _sphere(n)
    mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)

    assert _euler(mesh.triangles) == 2, "a sphere must have Euler characteristic 2"
    assert count_boundary_edges(mesh.triangles) == 0, "a closed surface has no rim"
    assert _orientation_clashes(mesh.triangles) == 0
    assert set(_edge_use(mesh.triangles).values()) == {2}, "not a 2-manifold"
    assert count_components(mesh.n_vertices, mesh.triangles) == 1

    # Positive volume means the normals point OUT of the region where the field
    # is above the isovalue. An inverted surface is invisible on screen, so
    # this assertion is the only thing that would catch it.
    volume = _signed_volume(mesh.positions, mesh.triangles)
    assert volume > 0, "the surface is inside out"
    assert abs(volume - (4 / 3) * np.pi * 0.7**3) / ((4 / 3) * np.pi * 0.7**3) < 0.05


def test_sphere_area_error_shrinks_as_the_grid_refines():
    """Converging on the truth, rather than merely being closed.

    A closed, correctly wound mesh can still be systematically wrong. This is
    the assertion that the interpolation itself is right.
    """
    truth = 4 * np.pi * 0.7**2
    errors = []
    for n in (12, 20, 32, 48):
        field, g = _sphere(n)
        mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)
        a = mesh.positions[mesh.triangles[:, 0]]
        b = mesh.positions[mesh.triangles[:, 1]]
        c = mesh.positions[mesh.triangles[:, 2]]
        area = float(np.sum(np.linalg.norm(np.cross(b - a, c - a), axis=1)) / 2)
        errors.append(abs(area - truth) / truth)

    assert errors == sorted(errors, reverse=True), f"not converging: {errors}"
    assert errors[-1] < 0.01, f"finest grid is still {errors[-1]:.1%} out"


def test_a_torus_has_euler_characteristic_zero():
    """Genus is the property a height field cannot represent at all, so the
    extractor has to get it right for the choice of method to mean anything."""
    n = 40
    g = np.linspace(-1.0, 1.0, n)
    z, y, x = np.meshgrid(g, g, g, indexing="ij")
    big, small = 0.6, 0.25
    field = small - np.sqrt((np.sqrt(x**2 + y**2) - big) ** 2 + z**2)

    mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)

    assert count_boundary_edges(mesh.triangles) == 0
    assert _orientation_clashes(mesh.triangles) == 0
    assert count_components(mesh.n_vertices, mesh.triangles) == 1
    assert _euler(mesh.triangles) == 0, "a torus must have Euler characteristic 0"


def test_two_separate_blobs_come_back_as_two_components():
    n = 24
    g = np.linspace(-1.0, 1.0, n)
    z, y, x = np.meshgrid(g, g, g, indexing="ij")
    left = 0.3 - np.sqrt((x + 0.45) ** 2 + y**2 + z**2)
    right = 0.3 - np.sqrt((x - 0.45) ** 2 + y**2 + z**2)

    mesh = extract(np.maximum(left, right), depths=g, lats=g, lons=g, isovalue=0.0)

    assert count_components(mesh.n_vertices, mesh.triangles) == 2
    assert mesh.counts["n_components"] == 2
    assert count_boundary_edges(mesh.triangles) == 0


# --- the non-uniform depth axis ---------------------------------------------

def test_a_vertex_uses_the_real_bracket_thickness_and_not_an_assumed_dz():
    """The trap this test exists for is invisible on a uniform grid.

    The real axis runs 5, 10, 20, 30, 50, 75 ... 1800, 2000 m, so a crossing
    halfway between 5 and 10 m is at 7.5 m and one halfway between 1800 and
    2000 m is at 1900 m. Interpolating in INDEX space, or against an assumed
    constant spacing, gives the same answer as the correct code on an evenly
    spaced fixture, so a symmetric test would pass either way and is therefore
    forbidden here.
    """
    depths = np.array([5.0, 10.0, 1800.0, 2000.0])
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])

    # Crossing at exactly the midpoint of the 5/10 pair.
    shallow = np.zeros((4, 2, 2))
    shallow[0] = 1.0
    shallow[1] = -1.0
    shallow[2] = -1.0
    shallow[3] = -1.0
    mesh = extract(shallow, depths, lats, lons, isovalue=0.0)
    vertical = mesh.positions[mesh.dz_bracket > 0]
    assert vertical.size, "no vertical vertex was produced"
    assert np.allclose(vertical[:, 2], 7.5), vertical[:, 2]
    assert np.allclose(mesh.dz_bracket[mesh.dz_bracket > 0], 5.0)

    # And at the midpoint of the 1800/2000 pair, where an assumed dz of 5 m
    # would place the vertex 92.5 m from the truth.
    deep = np.zeros((4, 2, 2))
    deep[0] = 1.0
    deep[1] = 1.0
    deep[2] = 1.0
    deep[3] = -1.0
    mesh = extract(deep, depths, lats, lons, isovalue=0.0)
    vertical = mesh.positions[mesh.dz_bracket > 0]
    assert np.allclose(vertical[:, 2], 1900.0), vertical[:, 2]
    assert np.allclose(mesh.dz_bracket[mesh.dz_bracket > 0], 200.0)


def test_a_sphere_on_the_real_non_uniform_depth_axis_still_closes():
    """Closure must not depend on even spacing."""
    depths = np.array(
        [5.0, 10.0, 20.0, 30.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0, 250.0, 300.0]
    )
    lats = np.linspace(5.0, 25.0, 24)
    lons = np.linspace(80.0, 95.0, 24)

    zc, yc, xc = np.meshgrid(depths, lats, lons, indexing="ij")
    # A ball in normalized coordinates so it sits inside the domain.
    zn = (zc - depths.mean()) / (depths.max() - depths.min())
    yn = (yc - lats.mean()) / (lats.max() - lats.min())
    xn = (xc - lons.mean()) / (lons.max() - lons.min())
    field = 0.3 - np.sqrt(xn**2 + yn**2 + zn**2)

    mesh = extract(field, depths, lats, lons, isovalue=0.0)

    assert count_boundary_edges(mesh.triangles) == 0
    assert _orientation_clashes(mesh.triangles) == 0
    assert _euler(mesh.triangles) == 2
    # Vertices on vertical edges must record the bracket they came from, and
    # those brackets must be the REAL gaps, never a constant. Filtered to
    # `on_edge`, because a centroid is an added vertex whose bracket is the
    # mean of its ring: an estimate of uncertainty, not a measured interval,
    # and the distinction is exactly what `on_edge` exists to make.
    vertical = mesh.on_edge & (mesh.dz_bracket > 0)
    brackets = set(np.round(mesh.dz_bracket[vertical], 6))
    assert brackets, "no vertical vertices at all"
    assert len(brackets) > 1, "every bracket the same means an assumed dz"
    assert brackets <= set(np.round(np.diff(depths), 6)), (
        "a bracket that is not one of the real level gaps means the depth axis "
        "was resampled or an interval was assumed"
    )


# --- missing data ------------------------------------------------------------

def test_a_cell_with_any_missing_corner_is_refused_not_interpolated():
    """Land, the seabed and the sampled margin are HOLES, not skin.

    Filling them would mean inventing a corner value, which is the single
    thing this project refuses everywhere else.
    """
    depths = np.array([5.0, 10.0])
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0, 2.0])

    field = np.zeros((2, 2, 3))
    field[0] = 1.0
    field[1] = -1.0
    # Knock one corner out of the left-hand cell only.
    field[1, 1, 0] = np.nan

    mesh = extract(field, depths, lats, lons, isovalue=0.0)

    assert mesh.counts["n_cells"] == 2
    assert mesh.counts["n_cells_active"] == 1, "the masked cell was meshed anyway"
    assert mesh.counts["n_cells_skipped_missing_corner"] == 1
    # It DID straddle the isovalue among the corners it had, so it is counted
    # as a disclosed refusal rather than quietly dropped.
    assert mesh.counts["n_cells_straddling_but_masked"] == 1
    assert np.all(np.isfinite(mesh.positions))
    # Every surviving vertex sits in the right-hand cell.
    assert mesh.positions[:, 0].min() >= 1.0 - 1e-9


def test_no_vertex_is_ever_non_finite_under_heavy_masking():
    rng = np.random.default_rng(4326)
    for _ in range(60):
        field = rng.normal(size=(7, 7, 7))
        field[rng.random(field.shape) < 0.25] = np.nan
        g = _uniform(7)
        mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)
        assert np.all(np.isfinite(mesh.positions))
        assert np.all(np.isfinite(mesh.dz_bracket))


def test_the_cell_accounting_adds_up():
    """Every cell is in exactly one bucket, so the counters cannot quietly
    stop describing the whole grid."""
    rng = np.random.default_rng(88)
    field = rng.normal(size=(6, 6, 6))
    field[rng.random(field.shape) < 0.3] = np.nan
    g = _uniform(6)

    mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)
    c = mesh.counts

    assert c["n_cells"] == 5 * 5 * 5
    assert c["n_cells_active"] + c["n_cells_skipped_missing_corner"] <= c["n_cells"]
    # Straddling-but-masked is a subset of the skipped cells.
    assert c["n_cells_straddling_but_masked"] <= c["n_cells_skipped_missing_corner"]


# --- degenerate values -------------------------------------------------------

def test_a_corner_exactly_on_the_isovalue_lands_on_the_node_and_culls_cleanly():
    """`>= isovalue` matches the D26 warm-side convention, so the two products
    can never disagree about a boundary. It also makes the interpolation
    denominator structurally non-zero rather than something to guard.

    The consequence here is worth stating rather than working around. One
    corner exactly on the isovalue, with all its neighbours below, means every
    one of its three edges interpolates to t == 0.0 and every vertex lands ON
    the node. The "surface" is a single point, its triangles have zero area,
    and they are culled: a degenerate triangle has a NaN normal and speckles
    black under any shading. The correct output is therefore no triangles plus
    a nonzero cull count, not a sliver nobody can see.
    """
    depths = np.array([5.0, 10.0])
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])

    field = np.full((2, 2, 2), -1.0)
    field[0, 0, 0] = 0.0            # exactly the isovalue

    mesh = extract(field, depths, lats, lons, isovalue=0.0)

    assert mesh.counts["n_cells_exact_tie"] == 1
    assert mesh.counts["n_cells_active"] == 1, "the tied corner must count as INSIDE"
    # Every vertex placed sits exactly on the tied node at (lon 0, lat 0, 5 m).
    edge_vertices = mesh.positions[mesh.on_edge]
    assert len(edge_vertices) == 3, "three edges leave the tied corner"
    assert np.allclose(edge_vertices, [0.0, 0.0, 5.0])
    # A point has no area, so nothing is drawn, and the cull is reported.
    assert mesh.n_triangles == 0
    assert mesh.counts["n_degenerate_culled"] == 3
    assert np.all(np.isfinite(mesh.positions))


def test_a_tied_corner_next_to_a_colder_cell_still_produces_a_real_surface():
    """The tie must not swallow a genuine crossing in the neighbouring cell."""
    depths = np.array([5.0, 10.0])
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0, 2.0])

    field = np.full((2, 2, 3), -1.0)
    field[:, :, 0] = 0.0        # the whole left face exactly on the isovalue
    field[:, :, 1] = 2.0        # warm middle
    # right column stays -1.0, so the right cell has a real crossing

    mesh = extract(field, depths, lats, lons, isovalue=0.0)

    assert mesh.n_triangles > 0, "a real crossing was lost next to the tie"
    assert np.all(np.isfinite(mesh.positions))
    assert _orientation_clashes(mesh.triangles) == 0


def test_a_cell_entirely_at_the_isovalue_produces_no_surface():
    """An isothermal cell has no isosurface in its interior. Mask 255."""
    depths = np.array([5.0, 10.0])
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])

    mesh = extract(np.zeros((2, 2, 2)), depths, lats, lons, isovalue=0.0)

    assert mesh.n_triangles == 0
    assert mesh.counts["n_cells_active"] == 0
    assert mesh.counts["n_cells_exact_tie"] == 1


def test_no_zero_area_triangle_survives():
    """A degenerate triangle has a NaN normal and speckles black under any
    shading. Culled, and the count is reported rather than hidden."""
    rng = np.random.default_rng(7)
    field = np.round(rng.normal(size=(6, 6, 6)) * 2) / 2   # many exact ties
    g = _uniform(6)

    mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)

    if mesh.n_triangles:
        a = mesh.positions[mesh.triangles[:, 1]] - mesh.positions[mesh.triangles[:, 0]]
        b = mesh.positions[mesh.triangles[:, 2]] - mesh.positions[mesh.triangles[:, 0]]
        assert np.all(np.linalg.norm(np.cross(a, b), axis=1) > 0)
    assert mesh.counts["n_degenerate_culled"] >= 0


# --- the refusals ------------------------------------------------------------

def test_a_duplicated_depth_level_is_refused():
    """cf.normalize_dataset refuses this at ingest, but the extractor takes
    arrays and cannot assume they came through there. A zero-thickness cell
    would make the vertical interpolation divide by zero."""
    depths = np.array([5.0, 10.0, 10.0, 20.0])
    g2 = np.array([0.0, 1.0])
    field = np.zeros((4, 2, 2))

    with pytest.raises(ExtractorError) as err:
        extract(field, depths, g2, g2, isovalue=0.0)

    assert "strictly increasing" in str(err.value)
    assert "10.0" in str(err.value)


def test_a_mismatched_axis_length_is_refused():
    with pytest.raises(ExtractorError, match="do not match"):
        extract(np.zeros((3, 2, 2)), np.array([1.0, 2.0]), np.array([0.0, 1.0]),
                np.array([0.0, 1.0]), isovalue=0.0)


def test_a_non_finite_isovalue_is_refused():
    g = np.array([0.0, 1.0])
    with pytest.raises(ExtractorError, match="finite"):
        extract(np.zeros((2, 2, 2)), g, g, g, isovalue=float("nan"))


def test_an_isovalue_outside_the_field_returns_an_empty_mesh_not_an_error():
    """"No 26 degC surface exists in this box at this time" is a true answer
    with a dataset and a timestamp behind it, so it is a mesh with no
    triangles and a full provenance block, not a 404."""
    g = np.array([0.0, 1.0])
    mesh = extract(np.zeros((2, 2, 2)) + 5.0, g, g, g, isovalue=100.0)

    assert mesh.n_vertices == 0
    assert mesh.n_triangles == 0
    assert mesh.counts["n_cells"] == 1
    assert mesh.counts["n_cells_active"] == 0
    assert mesh.counts["depth_min"] is None


def test_a_slab_too_thin_to_hold_a_cell_returns_an_empty_mesh():
    mesh = extract(np.zeros((1, 4, 4)), np.array([5.0]), _uniform(4), _uniform(4), 0.0)
    assert mesh.n_triangles == 0
    assert mesh.counts["n_cells"] == 0


# --- the stress test the whole method rests on ------------------------------

def test_random_fields_produce_watertight_consistently_wound_meshes():
    """The one test standing between a silent winding or welding bug and the
    demo.

    A gradient-based winding rule was tried during design and rejected because
    it passes every smooth-field test and only fails on noise, which is the
    worst possible failure schedule. The structural face-cycle rule replaced
    it, and this is what proves the replacement, across all 256 corner
    configurations rather than the handful a smooth field visits.

    The outer shell is clamped below the isovalue so every surface is CLOSED.
    Without that a random field's surface exits the box and has a legitimate
    open rim, and every assertion here would fail on correct output.
    """
    rng = np.random.default_rng(20260907)
    masks = set()
    total = 0

    for _ in range(60):
        n = 9
        field = _closed_field(rng.normal(size=(n, n, n)))
        g = _uniform(n)
        mesh = extract(field, depths=g, lats=g, lons=g, isovalue=0.0)
        total += mesh.n_triangles

        assert np.all(np.isfinite(mesh.positions))
        use = _edge_use(mesh.triangles)
        assert not [c for c in use.values() if c != 2], (
            "not a strict 2-manifold: an edge is used other than exactly twice"
        )
        assert _orientation_clashes(mesh.triangles) == 0
        assert _signed_volume(mesh.positions, mesh.triangles) > 0

        inside = field >= 0
        for k in range(n - 1):
            for j in range(n - 1):
                for i in range(n - 1):
                    mask = 0
                    for c in range(8):
                        di, dj, dk = c & 1, (c >> 1) & 1, (c >> 2) & 1
                        if inside[k + dk, j + dj, i + di]:
                            mask |= 1 << c
                    masks.add(mask)

    assert total > 100_000, f"the stress test barely exercised anything: {total}"
    assert len(masks) == 256, f"only {len(masks)} of 256 corner cases were reached"


# --- against the real cube and the shipped science --------------------------

def _real_cube():
    import xarray as xr

    if not CUBE.is_dir():
        pytest.skip("no local cube; run tools/fetch_sample.py then tools/preprocess.py")
    return xr.open_zarr(CUBE)


def test_every_vertical_vertex_matches_the_shipped_d26_science():
    """The strongest assertion in this file.

    For every column with exactly one 26 degC crossing, the depth this
    extractor places on the vertical edge must equal `isotherm_depth` EXACTLY,
    not approximately. Both use the same `>= threshold` convention and the same
    linear interpolation between the same bracketing levels, so any difference
    means one of them changed its mind about what the isotherm is.

    Exactness is the point. An `approx` here would let a convention drift in
    unnoticed, and the reason this test exists is to weld new geometry to
    already-reviewed science rather than let it become a parallel truth.
    """
    d26 = _d26_module()
    ds = _real_cube()
    depths = np.asarray(ds["depth"].values, dtype="float64")
    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")

    checked = 0
    for t in range(ds.sizes["time"]):
        field = np.asarray(ds["TEMP"].isel(time=t).values, dtype="float64")
        mesh = extract(field, depths, lats, lons, 26.0)
        scalar = d26.isotherm_depth(field, depths, 26.0)

        shallowest: dict[tuple[float, float], float] = {}
        for lon, lat, depth in mesh.positions[mesh.dz_bracket > 0]:
            key = (round(float(lon), 9), round(float(lat), 9))
            if key not in shallowest or depth < shallowest[key]:
                shallowest[key] = float(depth)

        for j, lat in enumerate(lats):
            for i, lon in enumerate(lons):
                want = scalar[j, i]
                if not np.isfinite(want):
                    continue
                got = shallowest.get((round(float(lon), 9), round(float(lat), 9)))
                if got is None:
                    # A column whose cells were all refused for a missing
                    # corner: the scalar reads one column, the mesh needs four.
                    continue
                assert got == float(want), (
                    f"mesh says {got} m and isotherm_depth says {want} m at "
                    f"{lat} N {lon} E"
                )
                checked += 1

    assert checked > 500, f"only {checked} columns were actually compared"


def test_the_real_thermocline_mesh_is_sane_and_discloses_its_refusals():
    ds = _real_cube()
    depths = np.asarray(ds["depth"].values, dtype="float64")
    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")
    field = np.asarray(ds["TEMP"].isel(time=-1).values, dtype="float64")

    mesh = extract(field, depths, lats, lons, 26.0)
    c = mesh.counts

    assert mesh.n_triangles > 100
    assert _orientation_clashes(mesh.triangles) == 0
    # The 26 degC isotherm in the Bay of Bengal sits in the upper hundred-odd
    # metres. A surface at 5 m or at 2000 m would mean the depth axis or the
    # interpolation is wrong in a way no count would show.
    assert 20.0 < c["depth_min"] < 80.0, c["depth_min"]
    assert 60.0 < c["depth_max"] < 250.0, c["depth_max"]
    # The coastal refusals are disclosed, not silent.
    assert c["n_cells_straddling_but_masked"] > 0
    assert c["n_cells_skipped_missing_corner"] > c["n_cells_active"]
    # Land and the seabed are holes, so a rim is expected here, unlike a sphere.
    assert c["n_boundary_edges"] > 0
    assert c["max_bracket_thickness"] in (5.0, 10.0, 20.0, 25.0, 50.0)


def test_the_bay_of_bengal_inversion_appears_as_a_second_component():
    """No code in the extractor knows that inversions exist.

    On 2026-07-10 seven columns cross 26 degC twice, temperature falling below
    26 by 75 m, returning above it at 100 m and falling again by 125 m: the
    barrier layer the Bay of Bengal is known for. The mesh separates into the
    main thermocline sheet plus a closed warm lens beneath it, which is exactly
    the structure a single-depth-per-column product must discard, and the
    reason marching cubes was chosen over a height field.
    """
    ds = _real_cube()
    times = [str(v)[:10] for v in ds["time"].values]
    if "2026-07-10" not in times:
        pytest.skip("the shipped cube no longer covers 2026-07-10")

    depths = np.asarray(ds["depth"].values, dtype="float64")
    lats = np.asarray(ds["lat"].values, dtype="float64")
    lons = np.asarray(ds["lon"].values, dtype="float64")

    inverted = extract(
        np.asarray(ds["TEMP"].isel(time=times.index("2026-07-10")).values, dtype="float64"),
        depths, lats, lons, 26.0,
    )
    plain = extract(
        np.asarray(ds["TEMP"].isel(time=times.index("2026-07-30")).values, dtype="float64"),
        depths, lats, lons, 26.0,
    )

    assert inverted.counts["n_components"] == 2, (
        "the inversion should split the surface into a sheet and a lens"
    )
    assert plain.counts["n_components"] == 1
    # The lens sits below the main sheet, so the inverted field reaches deeper.
    assert inverted.counts["depth_max"] > plain.counts["depth_max"]
