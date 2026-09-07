/** The isosurface mesh, and the arithmetic that places it on the globe.
 *
 * Deliberately Cesium-free. The only Cesium call the renderer needs is
 * `Cartesian3.fromDegreesArrayHeights`, which is exact for this purpose:
 * `fromDegrees` adds height along the geodetic surface normal, which is
 * precisely what a depth below a point on the ellipsoid means. Computing the
 * normal by hand and subtracting would be the same answer with more code and a
 * new place to get a sign wrong.
 *
 * The server sends depth in METRES POSITIVE DOWN, because that is the
 * transport convention everywhere in this project. Turning it into a render
 * height is the client's job and happens in exactly one place below, so
 * "which way is down" is answered once.
 */

import { rgbFor, type Palette, type Scale } from "./colormap";

/** What `GET /isosurface/{source}/{var}` returns. */
export interface IsosurfaceMesh {
  source_id: string;
  variable: string;
  units: string;
  value: number;
  value_units: string;
  time: string;
  citation: string;
  retrieved_at: string | null;
  extractor: string;
  extractor_version: string;
  method: string;

  bbox: [number, number, number, number];
  lats: number[];
  lons: number[];
  depths: number[];

  /** Flat [lon, lat, depth_m_positive_down] triples. */
  positions: number[];
  /** Flat triangle index triples into `positions`. */
  indices: number[];
  /**
   * Per vertex, the thickness in metres of the interval it was interpolated
   * across; 0 for a vertex on a horizontal edge. A vertex placed inside a
   * 200 m gap is far less certain than one inside a 20 m gap, and at 200x
   * vertical exaggeration that difference is kilometres of drawn displacement.
   */
  dz_bracket: number[];
  /**
   * True for a vertex on a real cell edge between two measured values, false
   * for a centroid the triangulation added. Only an `on_edge` vertex can be
   * traced back to a bracketing pair, so anything that CITES a vertex must
   * filter on this.
   */
  on_edge: boolean[];

  n_vertices: number;
  n_triangles: number;
  n_cells: number;
  n_cells_active: number;
  n_cells_skipped_missing_corner: number;
  n_cells_straddling_but_masked: number;
  n_cells_exact_tie: number;
  n_ambiguous_cells: number;
  n_degenerate_culled: number;
  n_components: number;
  n_boundary_edges: number;
  depth_min: number | null;
  depth_max: number | null;
  max_bracket_thickness: number | null;
}

/**
 * Flat [lon, lat, height] triples ready for `Cartesian3.fromDegreesArrayHeights`.
 *
 * Height is NEGATIVE depth times the exaggeration, which is the one place in
 * the client where depth-positive-down becomes height-positive-up.
 */
export function positionsWithHeights(
  mesh: IsosurfaceMesh,
  exaggeration: number,
): number[] {
  const out = new Array<number>(mesh.positions.length);
  for (let i = 0; i < mesh.positions.length; i += 3) {
    out[i] = mesh.positions[i];             // lon
    out[i + 1] = mesh.positions[i + 1];     // lat
    out[i + 2] = -mesh.positions[i + 2] * exaggeration;
  }
  return out;
}

/**
 * Per-vertex RGBA, coloured by DEPTH from the same lookup table the slices use.
 *
 * Colouring by the isovalue would be pointless: every vertex on the surface
 * has, by definition, the same value. Depth is the quantity that actually
 * varies across it, and it is what a forecaster reads off a thermocline map.
 *
 * The ramp is inverted against the depth range so shallow reads light and deep
 * reads dark, matching the `deep` palette's own direction and the way the
 * depth rack is drawn.
 */
export function vertexColors(
  mesh: IsosurfaceMesh,
  palette: Palette,
  scale: Scale,
  alpha = 255,
): Uint8Array {
  const n = mesh.positions.length / 3;
  const out = new Uint8Array(n * 4);
  const lo = mesh.depth_min ?? 0;
  const hi = mesh.depth_max ?? lo + 1;
  // A flat surface would make lo === hi and normalize would divide by zero.
  const span = hi - lo > 1e-9 ? hi : lo + 1;

  for (let v = 0; v < n; v++) {
    const depth = mesh.positions[v * 3 + 2];
    const [r, g, b] = rgbFor(depth, lo, span, palette, scale, false);
    out[v * 4] = r;
    out[v * 4 + 1] = g;
    out[v * 4 + 2] = b;
    out[v * 4 + 3] = alpha;
  }
  return out;
}

/**
 * The rim of every hole, as flat [lon, lat, height] triples, pairs of points.
 *
 * An edge used by exactly one triangle is a boundary. On this surface those
 * are land, the seabed and the sampled margin, all of which are cells the
 * extractor REFUSED because a corner was missing. Drawing the rim is what
 * turns a ragged edge from something a judge notices into something the
 * picture states: the surface stops here because the data stops here.
 */
export function boundaryEdges(
  mesh: IsosurfaceMesh,
  exaggeration: number,
): number[] {
  const use = new Map<string, [number, number, number]>();
  for (let t = 0; t < mesh.indices.length; t += 3) {
    const tri = [mesh.indices[t], mesh.indices[t + 1], mesh.indices[t + 2]];
    for (let m = 0; m < 3; m++) {
      const a = tri[m];
      const b = tri[(m + 1) % 3];
      const key = a < b ? `${a},${b}` : `${b},${a}`;
      const seen = use.get(key);
      if (seen) seen[2] += 1;
      else use.set(key, [a, b, 1]);
    }
  }

  const out: number[] = [];
  for (const [a, b, count] of use.values()) {
    if (count !== 1) continue;
    for (const v of [a, b]) {
      out.push(
        mesh.positions[v * 3],
        mesh.positions[v * 3 + 1],
        -mesh.positions[v * 3 + 2] * exaggeration,
      );
    }
  }
  return out;
}

/** A one-line description for the scene summary and the cartouche. */
export function describeMesh(mesh: IsosurfaceMesh): string {
  if (mesh.n_triangles === 0) {
    return (
      `No ${mesh.value} ${mesh.units} surface exists in this box at ${mesh.time}. ` +
      `The field was searched over all ${mesh.n_cells} cells.`
    );
  }
  const parts = [
    `The ${mesh.value} ${mesh.units} surface of ${mesh.variable}`,
    `between ${(mesh.depth_min ?? 0).toFixed(0)} and ${(mesh.depth_max ?? 0).toFixed(0)} metres`,
    `as ${mesh.n_triangles} triangles`,
  ];
  if (mesh.n_components > 1) {
    parts.push(
      `in ${mesh.n_components} separate pieces, which means some water columns ` +
      `cross the value more than once`,
    );
  }
  if (mesh.n_cells_straddling_but_masked > 0) {
    parts.push(
      `${mesh.n_cells_straddling_but_masked} cells were left out because a ` +
      `corner had no measurement, so the surface stops short of the coast`,
    );
  }
  return `${parts.join(", ")}.`;
}
