"""Isosurface extraction: marching cubes on the ocean cube (PS requirement F1).

The PS names "isosurface extraction" as one of the three techniques under its
3D-rendering requirement, alongside depth-slice views and time-step animation.
This is that third technique: given a scalar field and a value, return the
surface in the water where the field takes that value, as a triangle mesh.

WHY MARCHING CUBES AND NOT THE OTHER TWO CANDIDATES
---------------------------------------------------
The decisive argument is provenance, not topology or triangle count.

Every vertex this produces sits on an axis-aligned cell edge, so every vertex
is a one-dimensional statement of exactly the kind this project has already
committed to elsewhere: "linear interpolation in depth between the two
bracketing finite levels" (the wording `plugins/d26_isotherm.py` already ships),
or its horizontal analogue between two adjacent grid columns at one measured
level. An oceanographer can ask which two measurements produced any vertex and
get a straight answer.

*Marching tetrahedra* was the tempting alternative, because decomposing each
cell into tetrahedra removes the ambiguous-face problem and is far easier to
implement correctly. It was rejected on this same ground: most of its vertices
land on decomposition DIAGONALS, joining, say, 75 m at 12.5 N to 100 m at
13.5 N. That is mathematically exact and physically unmotivated, it does not
answer "which water column is this", and worse, the answer depends on how the
cells were split, so the extracted surface is not reproducible without also
publishing a diagonal convention.

*A depth-of-crossing height field* (one depth per column, the shape
`d26_isotherm` already computes) was rejected because it cannot represent a
column that crosses the value more than once. Those are not hypothetical here:
on 2026-07-10 seven columns of our own Bay of Bengal cube cross 26 degC twice,
a real subsurface temperature inversion, and a height field must silently pick
one. For the 35 psu isohaline nearly every valid column is multi-valued, so a
single-valued surface would be scientifically wrong rather than merely lossy.

The per-column product is deliberately KEPT rather than replaced. It is the
number INCOIS publishes and a cyclone forecaster reads, and it is this module's
oracle: for every column with exactly one crossing, the vertex this extractor
places on the vertical edge must equal `isotherm_depth` exactly, which welds new
geometry to already-reviewed science.

WHAT THIS REFUSES TO DO
-----------------------
* A cell is meshed only if ALL EIGHT of its corners carry a finite value. Land,
  the seabed and the partially sampled margin therefore appear as a HOLE with a
  drawn boundary, not as an interpolated skin over a corner we invented. The
  count of cells that straddled the value but were refused for a missing corner
  ships in the response, so a ragged coastal edge is a disclosed refusal rather
  than an artifact a reviewer discovers.
* No extrapolation. A vertex only ever lies between two measured values.
* No resampling. The non-uniform depth axis (5, 10, 20, 30, 50, 75 ... 1800,
  2000 m) enters only as the real thickness of the bracketing pair.
* The mesh is a PICTURE OF A LEVEL SET, not a differentiable object. Slope,
  curvature, heat content and volume must be answered from the field, never
  derived from these vertices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class ExtractorError(RuntimeError):
    """The field cannot be meshed as given.

    Deliberately NOT a ValueError, mirroring `plugins.PluginError`: a caller's
    bad bbox is a 400 and is raised as `store.SubsetError`, while this means the
    data itself violates a contract the extractor depends on, which is a
    server-side fault.
    """


#: Bumped when a convention changes in a way that moves vertices. Served with
#: every mesh so a saved payload can be told apart from a later one.
EXTRACTOR = "marching_cubes"
EXTRACTOR_VERSION = "1.0.0"

METHOD = (
    "marching cubes on the native (depth, lat, lon) cell grid; a corner counts "
    "as inside when its value is finite and >= the isovalue, the same warm-side "
    "convention the D26 product uses, so the two can never disagree on a "
    "boundary; each crossed cell edge carries one vertex placed by linear "
    "interpolation in PHYSICAL coordinates on that edge's own axis, using the "
    "store's own non-uniform depth levels rather than an assumed spacing; a "
    "cell is meshed only if all eight corners are finite, so land and the "
    "seabed are holes rather than interpolated skin; faces crossed four times "
    "are resolved from that face's own four corner values alone, so two cells "
    "sharing a face always agree and the mesh is watertight by construction"
)

# --- cell geometry ----------------------------------------------------------
#
# Corner c in 0..7 carries offsets (di, dj, dk) = (c&1, (c>>1)&1, (c>>2)&1),
# where i indexes lon, j indexes lat and k indexes depth. Everything below is
# derived from that one sentence, so there is no transcribed table to mistype.

CORNER_OFFSETS = np.array(
    [[(c & 1), ((c >> 1) & 1), ((c >> 2) & 1)] for c in range(8)], dtype=np.int64
)

#: The 12 edges as (low corner, high corner), grouped by axis: 0 = lon (i),
#: 1 = lat (j), 2 = depth (k). An edge always runs from the lower corner up.
EDGES: list[tuple[int, int]] = []
EDGE_AXIS: list[int] = []
for _axis, _bit in ((0, 1), (1, 2), (2, 4)):
    for _c in range(8):
        if not (_c & _bit):
            EDGES.append((_c, _c | _bit))
            EDGE_AXIS.append(_axis)
EDGES_ARR = np.array(EDGES, dtype=np.int64)
EDGE_AXIS_ARR = np.array(EDGE_AXIS, dtype=np.int64)
#: corner-pair -> edge index, for looking an edge up from a face walk.
EDGE_OF_PAIR = {frozenset(pair): n for n, pair in enumerate(EDGES)}

#: The six faces, each as four corners in cyclic order AS SEEN FROM OUTSIDE the
#: cell, so the right-hand rule about that cycle gives the face's outward
#: normal. This ordering is what makes the winding come out right without a
#: gradient heuristic: two cells sharing a face see it with opposite outward
#: normals, hence opposite cycles, hence opposite segment directions, which is
#: exactly what makes their triangles agree across the shared edge.
#:
#: A gradient-based winding rule was considered and rejected. It passes every
#: smooth-field test and then fails on noise, which is the worst possible
#: failure schedule for a demo.
FACE_CYCLES: tuple[tuple[int, int, int, int], ...] = (
    (0, 2, 3, 1),   # k = 0, outward -k (toward the surface)
    (4, 5, 7, 6),   # k = 1, outward +k (toward the seabed)
    (0, 1, 5, 4),   # j = 0, outward -j
    (2, 6, 7, 3),   # j = 1, outward +j
    (0, 4, 6, 2),   # i = 0, outward -i
    (1, 3, 7, 5),   # i = 1, outward +i
)

#: The four edges of each face, edge m joining cycle[m] to cycle[m + 1].
FACE_EDGES: tuple[tuple[int, int, int, int], ...] = tuple(
    tuple(EDGE_OF_PAIR[frozenset((cycle[m], cycle[(m + 1) % 4]))] for m in range(4))
    for cycle in FACE_CYCLES
)


def _check_geometry_tables() -> None:
    """The tables are generated, but a generator can still be wrong.

    Runs at import because it is microseconds and because every one of these
    being true is assumed by the loop below.
    """
    assert len(EDGES) == 12, len(EDGES)
    assert len({frozenset(e) for e in EDGES}) == 12, "duplicate edge"
    for n, (a, b) in enumerate(EDGES):
        delta = CORNER_OFFSETS[b] - CORNER_OFFSETS[a]
        assert delta.sum() == 1 and (delta >= 0).all(), (n, a, b)
        assert int(np.flatnonzero(delta)[0]) == EDGE_AXIS[n], n
    # Every edge lies on exactly two faces, which is what lets segments chain
    # into closed loops.
    seen: dict[int, int] = {}
    for edges in FACE_EDGES:
        assert len(set(edges)) == 4
        for e in edges:
            seen[e] = seen.get(e, 0) + 1
    assert set(seen) == set(range(12)) and set(seen.values()) == {2}, seen


_check_geometry_tables()


@dataclass
class Mesh:
    """An indexed triangle mesh plus the counters that keep it honest."""

    #: (n_vertices, 3) as (lon degrees, lat degrees, depth metres positive down).
    positions: np.ndarray
    #: (n_triangles, 3) indices into positions.
    triangles: np.ndarray
    #: (n_vertices,) thickness of the interval each vertex was interpolated
    #: across, in metres, 0 for a vertex on a horizontal edge. A vertex placed
    #: inside a 200 m gap is far less certain than one inside a 20 m gap, and at
    #: 200x vertical exaggeration that difference is kilometres on screen.
    #: For an added centroid this is the mean of its ring, which is an estimate
    #: rather than a measured bracket, which is what `on_edge` distinguishes.
    dz_bracket: np.ndarray
    #: (n_vertices,) True for a vertex that lies on a real cell edge between two
    #: measured values, False for a centroid added to triangulate a loop.
    #: Only an `on_edge` vertex can be traced back to a bracketing pair, so
    #: anything that cites a vertex (a test, the agent, a hover readout) must
    #: filter on this rather than assume every vertex is a measurement.
    on_edge: np.ndarray
    counts: dict = field(default_factory=dict)

    @property
    def n_vertices(self) -> int:
        return int(self.positions.shape[0])

    @property
    def n_triangles(self) -> int:
        return int(self.triangles.shape[0])


def _face_segments(face: int, inside: tuple[bool, ...], rel: np.ndarray) -> list[tuple[int, int]]:
    """The directed surface segments this face contributes.

    Returns (from_edge, to_edge) pairs. The direction is fixed by walking the
    face's outside-view cycle and joining each ENTRY (a step from outside to
    inside) to an EXIT (inside to outside). Worked through by hand for the
    single-inside-corner case, the resulting triangle normal points away from
    the inside region, which is the outward orientation we want.

    `rel` holds every corner's value minus the isovalue.
    """
    cycle = FACE_CYCLES[face]
    edges = FACE_EDGES[face]

    entries: list[int] = []
    exits: list[int] = []
    for m in range(4):
        here, nxt = inside[cycle[m]], inside[cycle[(m + 1) % 4]]
        if here and not nxt:
            exits.append(m)
        elif nxt and not here:
            entries.append(m)

    if not entries:
        return []
    if len(entries) == 1:
        return [(edges[entries[0]], edges[exits[0]])]

    # Four crossings: the face is ambiguous and the two pairings describe
    # different topologies. It is resolved from THIS FACE'S four corner values
    # alone, so the cell on the other side of the face reaches the same answer
    # and the mesh cannot crack.
    #
    # The bilinear interpolant over the face has a saddle. If the saddle is on
    # the inside of the isovalue, the inside region is connected across the
    # face and the two curves cut off the two OUTSIDE corners; otherwise the
    # inside corners are two separate blobs. With cyclic values a, b, c, d
    # relative to the isovalue, the saddle sits on the inside exactly when
    # a*c > b*d.
    a, b, c, d = (float(rel[cycle[m]]) for m in range(4))
    connected = (a * c) > (b * d)
    # `connected` means the two curves separate the two outside corners, which
    # is the pairing joining each entry to the exit BEFORE it in the walk.
    # Otherwise each entry joins the exit that FOLLOWS it.
    out: list[tuple[int, int]] = []
    for m in entries:
        if connected:
            partner = max((e for e in exits if e < m), default=max(exits))
        else:
            partner = min((e for e in exits if e > m), default=min(exits))
        out.append((edges[m], edges[partner]))
    return out


def _cell_loops(inside: tuple[bool, ...], rel: np.ndarray) -> tuple[list[list[int]], bool]:
    """Chain this cell's face segments into closed loops of edge indices."""
    segments: dict[int, int] = {}
    ambiguous = False
    for face in range(6):
        pairs = _face_segments(face, inside, rel)
        if len(pairs) > 1:
            ambiguous = True
        for src, dst in pairs:
            segments[src] = dst

    loops: list[list[int]] = []
    unused = dict(segments)
    while unused:
        start = next(iter(unused))
        loop = [start]
        cursor = unused.pop(start)
        while cursor != start:
            loop.append(cursor)
            nxt = unused.pop(cursor, None)
            if nxt is None:
                # Not reachable for a well-formed cell: every crossed edge lies
                # on exactly two faces, so every vertex has one in and one out.
                raise ExtractorError(
                    "a cell produced an open surface segment chain, which means "
                    "the face pairing is inconsistent. This is an extractor bug, "
                    "not a data problem."
                )
            cursor = nxt
        loops.append(loop)
    return loops, ambiguous


def extract(
    values: np.ndarray,
    depths: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    isovalue: float,
) -> Mesh:
    """Marching cubes over `values`, shaped (depth, lat, lon).

    Coordinates are physical throughout: `depths` in metres positive down and
    strictly increasing, `lats` and `lons` in degrees. Vertices come back as
    (lon, lat, depth) so the client can place them without knowing the grid.
    """
    values = np.asarray(values, dtype="float64")
    depths = np.asarray(depths, dtype="float64")
    lats = np.asarray(lats, dtype="float64")
    lons = np.asarray(lons, dtype="float64")

    if values.ndim != 3:
        raise ExtractorError(
            f"the field must be (depth, lat, lon); got shape {values.shape}"
        )
    nz, ny, nx = values.shape
    if (depths.size, lats.size, lons.size) != (nz, ny, nx):
        raise ExtractorError(
            f"axis lengths {(depths.size, lats.size, lons.size)} do not match the "
            f"field shape {values.shape}"
        )
    if not np.isfinite(isovalue):
        raise ExtractorError(f"the isovalue must be a finite number, got {isovalue!r}")

    # The guard the whole method rests on. A duplicated level makes a cell of
    # zero thickness, and the vertical interpolation below would divide by it.
    # cf.normalize_dataset refuses this at ingest, but the extractor is called
    # with arrays and cannot assume it came through there.
    if nz > 1 and not np.all(np.diff(depths) > 0):
        bad = int(np.flatnonzero(np.diff(depths) <= 0)[0])
        raise ExtractorError(
            f"the depth axis must be strictly increasing: level {bad} is "
            f"{depths[bad]} m and level {bad + 1} is {depths[bad + 1]} m. A "
            "zero-thickness or reversed cell has no interior for a surface to "
            "cross, and the edge interpolation would divide by that thickness."
        )
    if not np.all(np.isfinite(depths)):
        raise ExtractorError("the depth axis carries a non-finite level")

    axis_coords = (lons, lats, depths)

    empty = Mesh(
        positions=np.zeros((0, 3), dtype="float64"),
        triangles=np.zeros((0, 3), dtype="int64"),
        dz_bracket=np.zeros((0,), dtype="float64"),
        on_edge=np.zeros((0,), dtype=bool),
    )
    if nz < 2 or ny < 2 or nx < 2:
        # Fewer than two levels on any axis means there are no cells at all.
        # A true answer, not an error: the caller asked about a slab too thin
        # to contain a surface.
        empty.counts = _counts(
            n_cells=0, active=0, skipped=0, straddling_masked=0, exact_tie=0,
            ambiguous=0, culled=0, positions=empty.positions, triangles=empty.triangles,
            dz=empty.dz_bracket,
        )
        return empty

    rel_grid = values - isovalue
    finite_grid = np.isfinite(values)
    # `inside` uses >= so a value exactly on the isovalue is on the warm side,
    # matching the D26 product. That also makes every crossed edge have
    # strictly opposite ends, so the interpolation denominator cannot be zero.
    inside_grid = finite_grid & (rel_grid >= 0.0)

    # Corner stacks: (8, nz-1, ny-1, nx-1), so the prefilter is vectorised and
    # only genuinely active cells reach the Python loop.
    corner_rel = np.empty((8, nz - 1, ny - 1, nx - 1), dtype="float64")
    corner_finite = np.empty((8, nz - 1, ny - 1, nx - 1), dtype=bool)
    corner_inside = np.empty((8, nz - 1, ny - 1, nx - 1), dtype=bool)
    for c, (di, dj, dk) in enumerate(CORNER_OFFSETS):
        sl = (
            slice(dk, dk + nz - 1),
            slice(dj, dj + ny - 1),
            slice(di, di + nx - 1),
        )
        corner_rel[c] = rel_grid[sl]
        corner_finite[c] = finite_grid[sl]
        corner_inside[c] = inside_grid[sl]

    all_finite = corner_finite.all(axis=0)
    n_inside = corner_inside.sum(axis=0)
    active = all_finite & (n_inside > 0) & (n_inside < 8)

    # Disclosed refusals: cells that DO straddle the isovalue among the corners
    # they have, but were skipped because a corner is missing. These are the
    # coastal and seabed margin, and their count is what makes the hole in the
    # mesh a stated decision rather than something a reviewer notices.
    has_finite_inside = (corner_finite & corner_inside).any(axis=0)
    has_finite_outside = (corner_finite & ~corner_inside).any(axis=0)
    straddling_masked = int(
        np.count_nonzero(~all_finite & has_finite_inside & has_finite_outside)
    )
    n_cells = int(all_finite.size)
    n_skipped = int(np.count_nonzero(~all_finite))
    exact_tie = int(np.count_nonzero(all_finite & (corner_rel == 0.0).any(axis=0)))

    cells = np.argwhere(active)
    if cells.size == 0:
        empty.counts = _counts(
            n_cells=n_cells, active=0, skipped=n_skipped,
            straddling_masked=straddling_masked, exact_tie=exact_tie, ambiguous=0,
            culled=0, positions=empty.positions, triangles=empty.triangles,
            dz=empty.dz_bracket,
        )
        return empty

    # A vertex is keyed by the GLOBAL edge it sits on, so the two cells sharing
    # that edge weld to one vertex and the mesh has no cracks and no duplicates.
    vertex_of_edge: dict[int, int] = {}
    positions: list[tuple[float, float, float]] = []
    brackets: list[float] = []
    on_edge: list[bool] = []
    triangles: list[tuple[int, int, int]] = []
    n_ambiguous = 0

    for kk, jj, ii in cells:
        k, j, i = int(kk), int(jj), int(ii)
        rel = corner_rel[:, k, j, i]
        inside = tuple(bool(v) for v in corner_inside[:, k, j, i])

        loops, ambiguous = _cell_loops(inside, rel)
        if ambiguous:
            n_ambiguous += 1

        for loop in loops:
            ring: list[int] = []
            for edge in loop:
                lo, hi = EDGES_ARR[edge]
                axis = int(EDGE_AXIS_ARR[edge])
                lo_off, hi_off = CORNER_OFFSETS[lo], CORNER_OFFSETS[hi]
                base = (i + int(lo_off[0]), j + int(lo_off[1]), k + int(lo_off[2]))
                key = ((base[2] * ny + base[1]) * nx + base[0]) * 3 + axis
                index = vertex_of_edge.get(key)
                if index is None:
                    a = float(rel[lo])
                    b = float(rel[hi])
                    # Strictly opposite signs by construction, so no guard.
                    t = a / (a - b)
                    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                    node_lo = (
                        i + int(lo_off[0]), j + int(lo_off[1]), k + int(lo_off[2])
                    )
                    node_hi = (
                        i + int(hi_off[0]), j + int(hi_off[1]), k + int(hi_off[2])
                    )
                    coord = [
                        float(lons[node_lo[0]]),
                        float(lats[node_lo[1]]),
                        float(depths[node_lo[2]]),
                    ]
                    lo_c = axis_coords[axis][node_lo[axis]]
                    hi_c = axis_coords[axis][node_hi[axis]]
                    coord[axis] = float(lo_c + t * (hi_c - lo_c))
                    index = len(positions)
                    positions.append((coord[0], coord[1], coord[2]))
                    brackets.append(
                        float(abs(hi_c - lo_c)) if axis == 2 else 0.0
                    )
                    on_edge.append(True)
                    vertex_of_edge[key] = index
                ring.append(index)

            if len(ring) < 3:
                continue
            # Triangulated around an ADDED CENTROID rather than fanned from a
            # ring vertex. Fanning keeps the surface closed but leaves a small
            # fraction of edges used four times under noisy data, which is not
            # a 2-manifold and is exactly the sort of defect that survives to
            # the finale. The centroid costs one vertex and two triangles per
            # loop and makes every interior edge used exactly twice.
            pts = np.array([positions[n] for n in ring], dtype="float64")
            centre = pts.mean(axis=0)
            centre_index = len(positions)
            positions.append((float(centre[0]), float(centre[1]), float(centre[2])))
            brackets.append(float(np.mean([brackets[n] for n in ring])))
            on_edge.append(False)
            for m in range(len(ring)):
                triangles.append((centre_index, ring[m], ring[(m + 1) % len(ring)]))

    pos = np.asarray(positions, dtype="float64").reshape(-1, 3)
    tri = np.asarray(triangles, dtype="int64").reshape(-1, 3)
    dz = np.asarray(brackets, dtype="float64").reshape(-1)
    edge_flag = np.asarray(on_edge, dtype=bool).reshape(-1)

    # A triangle of zero area yields a NaN normal and black speckle under any
    # shading. It happens when several corners sit exactly on the isovalue.
    culled = 0
    if tri.size:
        a = pos[tri[:, 1]] - pos[tri[:, 0]]
        b = pos[tri[:, 2]] - pos[tri[:, 0]]
        area = np.linalg.norm(np.cross(a, b), axis=1)
        keep = area > 0.0
        culled = int(np.count_nonzero(~keep))
        tri = tri[keep]

    mesh = Mesh(positions=pos, triangles=tri, dz_bracket=dz, on_edge=edge_flag)
    mesh.counts = _counts(
        n_cells=n_cells,
        active=int(cells.shape[0]),
        skipped=n_skipped,
        straddling_masked=straddling_masked,
        exact_tie=exact_tie,
        ambiguous=n_ambiguous,
        culled=culled,
        positions=pos,
        triangles=tri,
        dz=dz,
    )
    return mesh


def _counts(
    *,
    n_cells: int,
    active: int,
    skipped: int,
    straddling_masked: int,
    exact_tie: int,
    ambiguous: int,
    culled: int,
    positions: np.ndarray,
    triangles: np.ndarray,
    dz: np.ndarray,
) -> dict:
    """The honesty counters, the mesh analogue of n_cells and n_valid."""
    return {
        "n_vertices": int(positions.shape[0]),
        "n_triangles": int(triangles.shape[0]),
        "n_cells": n_cells,
        "n_cells_active": active,
        "n_cells_skipped_missing_corner": skipped,
        "n_cells_straddling_but_masked": straddling_masked,
        "n_cells_exact_tie": exact_tie,
        "n_ambiguous_cells": ambiguous,
        "n_degenerate_culled": culled,
        "n_components": count_components(positions.shape[0], triangles),
        "n_boundary_edges": count_boundary_edges(triangles),
        "depth_min": round(float(positions[:, 2].min()), 4) if positions.size else None,
        "depth_max": round(float(positions[:, 2].max()), 4) if positions.size else None,
        "max_bracket_thickness": round(float(dz.max()), 4) if dz.size else None,
    }


def count_boundary_edges(triangles: np.ndarray) -> int:
    """Edges used by exactly one triangle: the rim of every hole.

    Nonzero is expected and correct here, because land and the seabed are
    holes. What it must never be is nonzero on a closed test surface.
    """
    if triangles.size == 0:
        return 0
    counts: dict[tuple[int, int], int] = {}
    for tri in triangles:
        for m in range(3):
            a, b = int(tri[m]), int(tri[(m + 1) % 3])
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return sum(1 for n in counts.values() if n == 1)


def count_components(n_vertices: int, triangles: np.ndarray) -> int:
    """Connected components of the mesh.

    Worth serving: on 2026-07-10 the Bay of Bengal inversion makes the 26 degC
    surface separate into the main thermocline sheet plus a closed warm lens,
    and no code here knows that inversions exist. The count is how a reader
    finds out.
    """
    if triangles.size == 0:
        return 0
    parent = list(range(n_vertices))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for tri in triangles:
        union(int(tri[0]), int(tri[1]))
        union(int(tri[1]), int(tri[2]))
    used = {find(int(v)) for tri in triangles for v in tri}
    return len(used)
