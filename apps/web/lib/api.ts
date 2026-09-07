/** Typed client for the SagarDrishti data plane (services/api).
 *
 * The agent plane calls these same endpoints. Nothing here invents a value or
 * a citation: every field on these responses comes from the API, which gets it
 * from a store's provenance.json. */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface VariableInfo {
  name: string;
  label: string;
  units: string;
  canonical: string | null;
}

export interface DatasetInfo {
  id: string;
  title: string;
  kind: string;
  citation: string;
  variables: VariableInfo[];
  depths: number[];
  times: string[];
  bbox: [number, number, number, number];
  retrieved_at: string | null;
}

/** A full water column at one timestep: the volumetric renderer's hot path. */
export interface FieldColumn {
  source_id: string;
  variable: string;
  units: string;
  citation: string;
  time: string;
  lats: number[];
  lons: number[];
  depths: number[];
  /** [depth][lat][lon] flattened; null is missing data and must never be coloured */
  shape: [number, number, number];
  values: (number | null)[];
}

export interface ProfileGlyph {
  profile_id: string;
  wmo: string;
  time: string;
  lat: number;
  lon: number;
  n_levels: number;
  max_depth: number;
}

export interface ProfileDetail {
  profile_id: string;
  wmo: string;
  time: string;
  lat: number;
  lon: number;
  citation: string;
  qc_policy: string;
  n_levels: number;
  levels: {
    depth: number[];
    pres: number[];
    temp: (number | null)[];
    psal: (number | null)[];
  };
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* a non-JSON error body is still an error */
    }
    throw new Error(`${r.status} ${detail}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  catalog: () => get<{ datasets: DatasetInfo[] }>("/catalog"),

  column: (sourceId: string, variable: string, bbox: string, time: string) =>
    get<FieldColumn>(
      `/field/${sourceId}/${variable}?bbox=${encodeURIComponent(bbox)}` +
        `&time=${encodeURIComponent(time)}&all_depths=true`,
    ),

  profiles: () => get<{ count: number; citation: string; profiles: ProfileGlyph[] }>("/profiles"),

  profile: (id: string) => get<ProfileDetail>(`/profiles/${encodeURIComponent(id)}`),
};

/** Index into a FieldColumn's flattened values. */
export function columnValue(
  col: FieldColumn,
  di: number,
  yi: number,
  xi: number,
): number | null {
  const [, ny, nx] = col.shape;
  return col.values[di * ny * nx + yi * nx + xi];
}

/** Mean of the finite values on one depth level - the sheet's value column. */
export function levelMean(col: FieldColumn, di: number): number | null {
  const [, ny, nx] = col.shape;
  let sum = 0;
  let n = 0;
  const base = di * ny * nx;
  for (let i = 0; i < ny * nx; i++) {
    const v = col.values[base + i];
    if (v !== null && Number.isFinite(v)) {
      sum += v;
      n++;
    }
  }
  return n === 0 ? null : sum / n;
}

/** Robust range over the whole column, so the colorbar is not flattened by one
 *  outlier cell. Mirrors app/colormap.py:suggested_range. */
export function robustRange(col: FieldColumn, pct = 2): [number, number] {
  const finite: number[] = [];
  for (const v of col.values) if (v !== null && Number.isFinite(v)) finite.push(v);
  if (finite.length === 0) return [0, 1];
  finite.sort((a, b) => a - b);
  const lo = finite[Math.floor((finite.length - 1) * (pct / 100))];
  const hi = finite[Math.floor((finite.length - 1) * (1 - pct / 100))];
  return lo === hi ? [lo, lo + 1] : [lo, hi];
}

/**
 * The model's own water column at a float's position, taken from the nearest
 * grid cell.
 *
 * NEAREST CELL, NOT CLASS-4 CO-LOCATION. This is deliberately the honest cheap
 * version: it puts the model curve beside the observed one so a forecaster can
 * see agreement, and it computes no skill number. Proper verification in
 * observation space - interpolating the model to the profile's exact
 * lat/lon/depth/time and reporting per-depth-bin bias and RMSE - is TRD M5
 * (Ryan et al. 2015, PRIOR-ART §B.12) and lands in Phase 4. Until then nothing
 * here may be described as an RMSE, and the panel says so on screen.
 */
export function modelProfileAt(
  col: FieldColumn,
  lat: number,
  lon: number,
): { depths: number[]; values: (number | null)[]; cellLat: number; cellLon: number } | null {
  if (col.lats.length === 0 || col.lons.length === 0) return null;

  const yi = nearestIndexIn(col.lats, lat);
  const xi = nearestIndexIn(col.lons, lon);
  const [, ny, nx] = col.shape;

  const values = col.depths.map((_, di) => col.values[di * ny * nx + yi * nx + xi] ?? null);
  return { depths: col.depths, values, cellLat: col.lats[yi], cellLon: col.lons[xi] };
}

function nearestIndexIn(values: number[], target: number): number {
  let best = 0;
  let gap = Infinity;
  values.forEach((v, i) => {
    const g = Math.abs(v - target);
    if (g < gap) {
      gap = g;
      best = i;
    }
  });
  return best;
}
