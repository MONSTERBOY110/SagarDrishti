/** Typed client for the SagarDrishti data plane (services/api).
 *
 * The agent plane calls these same endpoints. Nothing here invents a value or
 * a citation: every field on these responses comes from the API, which gets it
 * from a store's provenance.json. */

import type { IsosurfaceMesh } from "./isosurface";

export type { IsosurfaceMesh };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

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

/**
 * The registry `kind` of the instrument that took a profile.
 *
 * Carried through to the client because the PS asks for Argo floats, gliders,
 * CTD casts and BGC floats as distinguishable marks (PRD F2), and because a
 * BGC float's chlorophyll must never be cited to the core Argo daily files,
 * which carry no chlorophyll at all.
 */
export type PlatformKind =
  | "gdac_geo"
  | "gdac_bgc"
  | "file"
  | "mooring"
  | "glider"
  | "ctd"
  | "hf_radar"
  | "adcp";

/**
 * Whether an observation sits inside the model cube's own time window.
 *
 * The Bay of Bengal has no contemporaneous glider: on 2026-09-01 the entire
 * Copernicus near-real-time feed carried one Indian Ocean glider and it was in
 * the Mozambique Channel. The real one this scene shows flew in 2018. Marking
 * it is what makes showing it honest rather than misleading, so the mark is
 * drawn differently, the panel prints the reason, and the verification refuses
 * to pair it.
 */
export type Epoch = "contemporaneous" | "archive";

export interface ProfileGlyph {
  profile_id: string;
  wmo: string;
  time: string;
  lat: number;
  lon: number;
  n_levels: number;
  max_depth: number;
  source_id: string;
  platform_kind: PlatformKind;
  epoch: Epoch;
  /** Parameters this profile actually SERVES, not what its class can measure. */
  parameters: string[];
}

export interface ProfileParameter {
  name: string;
  label: string;
  /**
   * The unit the SOURCE FILE declares, verified against `data/sources.yaml` at
   * parse time by services/api/app/argo.py:check_units. Trustworthy enough to
   * label an axis with, which is why the client does not keep a units table of
   * its own to drift out of step.
   */
  units: string;
  canonical: string;
  /** Levels of this parameter that passed QC, so a reader knows how sparse it is. */
  n_values: number;
}

export interface ProfileDetail {
  profile_id: string;
  wmo: string;
  time: string;
  lat: number;
  lon: number;
  source_id: string;
  platform_kind: PlatformKind;
  epoch: Epoch;
  /** Why this instrument is outside the model's window. Null when it is not. */
  epoch_note: string | null;
  citation: string;
  qc_policy: string;
  adjusted_preferred: boolean;
  n_levels: number;
  parameters: ProfileParameter[];
  /**
   * `depth` and `pres` are always present. Every other key is a parameter this
   * profile served, so the set of keys varies by instrument class: a core
   * float has temp and psal, a BGC float adds doxy, chla, nitrate and pH.
   *
   * Nulls are gaps, NOT zeroes, and they are load-bearing. A BGC sensor
   * samples far more sparsely than the CTD beside it, so oxygen exists at
   * levels where temperature does not. Anything that plots these must leave
   * the gaps open rather than joining across them, or the chart invents
   * measurements between two real ones.
   */
  levels: {
    depth: number[];
    pres: number[];
  } & Record<string, (number | null)[]>;
}

/** One row of the verification card: the model's error over a depth band. */
export interface ScoreBin {
  depth_min: number;
  depth_max: number;
  n: number;
  /**
   * Model minus observation, averaged. Positive means the model runs warm (or
   * salty). Null when the band held no matched pairs, which is NOT zero: zero
   * would read as a perfect band.
   */
  bias: number | null;
  rmse: number | null;
  mae: number | null;
  /** Spread of the residual: the part a constant correction could not remove. */
  std: number | null;
}

/**
 * Class-4-style model-versus-observation verification (PS requirement F9).
 *
 * `caveat` is not a footnote and must be rendered wherever these numbers are:
 * the INCOIS analysis assimilates the very profiles it is scored against, so
 * the residual bounds the ANALYSIS FIT and is not forecast skill.
 */
export interface Scorecard {
  source_id: string;
  variable: string;
  units: string;
  observed_column: string;
  label: string;
  method: string;
  caveat: string;
  citation: string;
  retrieved_at: string | null;
  overall: Omit<ScoreBin, "depth_min" | "depth_max">;
  by_depth: ScoreBin[];
  n_profiles: number;
  n_platforms: number;
  platforms: string[];
  accept_flags: number[];
  max_time_offset_hours: number;
  time_offset_hours: { median: number | null; max: number | null };
  /** Every level that did NOT become a pair, and why. Part of the answer. */
  refused: {
    total: number;
    no_model_time: number;
    outside_grid: number;
    missing_stencil: number;
    outside_depth_range: number;
    no_observation: number;
    rejected_qc: number;
    no_qc_flag: number;
  };
  observation_sources: string[];
  /** Registry titles for those sources: what to print, since a source id is
   *  a database key and a reader needs the name of the instrument programme. */
  observation_titles: string[];
  observation_citations: string[];
}

/**
 * What to PRINT for a unit the API served. Display only, never sent back.
 *
 * The INCOIS analysis declares `units: "1"` for salinity, and that is correct:
 * CF stores practical salinity as a dimensionless quantity and puts the meaning
 * in the standard name. It is also unreadable on a form, where "34.05 1" looks
 * like a typo rather than like a measurement, and the salinity ramp was headed
 * "SCALE IN 1".
 *
 * So the number stays exactly what the source declared and only the LABEL is
 * translated, by standard name rather than by variable name: `units: "1"` on a
 * chlorophyll field would not mean PSU. A dimensionless quantity we cannot name
 * prints nothing at all, which is honest, rather than "1", which is noise.
 *
 * NOT for the wire. `/isosurface` checks the isovalue's units against the
 * served ones and would refuse "PSU" where the cube says "1", correctly, so
 * every request keeps using the raw string.
 */
export function displayUnits(units: string, canonical?: string | null): string {
  if (units !== "1") return units;
  if (canonical === "sea_water_practical_salinity") return "PSU";
  return "";
}

/** One CAP `<area>`: what it is called, and where it is if we can tell. */
export interface WarningArea {
  desc: string;
  /** Closed rings, LONGITUDE FIRST. CAP itself writes latitude first; the
   *  server transposes once, in app/cap.py, so nothing downstream has to. */
  polygons: [number, number][][];
  /** [lon, lat, radiusKm]. CAP's radius is KILOMETRES, not metres or degrees. */
  circles: [number, number, number][];
  geocodes: Record<string, string>;
  drawable: boolean;
}

/** CAP v1.2 severity, worst first. The vocabulary is closed; anything the
 *  server could not read arrives as "Unknown" and ranks BELOW Minor, so an
 *  unreadable alert can never displace a real Extreme one at the top of the
 *  banner. */
export type CapSeverity = "Extreme" | "Severe" | "Moderate" | "Minor" | "Unknown";
export type CapStatus = "Actual" | "Exercise" | "System" | "Test" | "Draft";

/**
 * One active warning (PRD F13, HazardWatch).
 *
 * `status` is the field that matters most on this type. `Actual` is a real
 * warning; `Exercise` is a drill, it reaches the client ONLY when the request
 * asked for rehearsals, and anything rendering it is required to say so.
 */
export interface WarningAlert {
  identifier: string;
  sender: string;
  sent: string | null;
  status: CapStatus;
  msg_type: string;
  scope: string;
  references: string[];
  source: string;
  event: string;
  severity: CapSeverity;
  /** 4 for Extreme down to 0 for Unknown. Sorting is done server-side; this is
   *  here so the panel can pick a treatment without re-deriving the order. */
  severity_rank: number;
  urgency: string;
  certainty: string;
  effective: string | null;
  expires: string | null;
  languages: string[];
  areas: WarningArea[];
  /** Which language block the text below actually came from. CAP blocks are
   *  authored per language rather than translated from a canonical one. */
  language: string;
  headline: string;
  description: string;
  instruction: string;
  area_desc: string;
  drawable: boolean;
  /** Every departure from the standard the parser had to cope with, and every
   *  change the ingest made, including geometry simplification. Rendered, so a
   *  thinned boundary is never presented as the one the agency drew. */
  notes: string[];
}

export interface WarningLayer {
  /** The instant validity was evaluated at, echoed back. */
  at: string;
  count: number;
  alerts: WarningAlert[];
  /** Why alerts are NOT shown. Part of the answer, never a log line. */
  refused: {
    total: number;
    not_actual: number;
    not_a_warning: number;
    cancelled: number;
    superseded: number;
    expired: number;
    not_yet_effective: number;
    not_drawable: number;
    outside_bbox: number;
  };
  language: string;
  rehearsal: boolean;
  /** How many of the alerts being shown are drills. Computed server-side so a
   *  client cannot forget to look. */
  exercise_count: number;
  method: string;
  sources: string[];
  citations: Record<string, string>;
  simplify_tolerance_deg: number;
  unreadable: { file: string; source?: string; reason: string }[];
}

/** One step of a guided tour (PRD F12).
 *
 * `patch` is applied to the live scene store, so a tour can do nothing a
 * presenter could not do by hand. `evidence` is the citation discipline
 * applied to PROSE: narration is the one place a number can reach a judge
 * without passing through a tool result, so every numeral in a narration line
 * has to appear either in the patch or here, and the server refuses a tour
 * where it does not. */
export interface TourStep {
  narration: string;
  /** seconds this step holds before the player advances */
  hold: number;
  patch: Record<string, unknown>;
  evidence: string[];
}

export interface Tour {
  id: string;
  title: string;
  subtitle: string;
  /** "judge" or "classroom": the same product, pitched differently */
  audience: string;
  source_id: string;
  steps: TourStep[];
  n_steps: number;
  seconds: number;
}

export interface TourIndex {
  tours: Tour[];
  count: number;
  /** Tour files that could not be read, with the reason. Served rather than
   *  logged: a tour that failed to load is one nobody can run, and finding
   *  that out on stage is the failure mode. */
  refused: { file: string; reason: string }[];
  /** What a step is allowed to patch, per the server. The client checks the
   *  same thing against its own store, so a disagreement surfaces as a visible
   *  refusal rather than a silent no-op. */
  patchable: string[];
}

/** One current arrow: the MEAN flow of a block of model cells, not one cell.
 *
 * `n` is how many source cells were behind it. The server block-averages
 * rather than sampling, because taking every Nth cell of a velocity field
 * aliases, and aliasing invents eddies that look exactly like the real ones. */
export interface CurrentArrow {
  lat: number;
  lon: number;
  /** eastward and northward components, in the response's own units */
  u: number;
  v: number;
  speed: number;
  n: number;
}

export interface CurrentField {
  source_id: string;
  variables: string[];
  units: string;
  time: string;
  /** The depth ASKED FOR and the depth SERVED. GLORYS has its own 40 levels
   *  and none is exactly 100 m, so the difference is information. */
  requested_depth: number;
  depth: number;
  bbox: [number, number, number, number];
  /** Block size used, in native cells. Disclosed so a thinned field is never
   *  mistaken for the grid the model actually ran on. */
  stride: number;
  budget: number;
  source_cells: number;
  blocks: number;
  count: number;
  /** Blocks dropped for being mostly land. A sparse arrow field has to be
   *  distinguishable from a broken one, which is why this is served. */
  refused: number;
  note: string;
  citation: string;
  retrieved_at: string | null;
  arrows: CurrentArrow[];
}

/** One telemetry frame from the tabletop rig (PS F6, TRD M9).
 *
 * `ts_source` is the field to read before the numbers. An ESP32 has no
 * battery-backed clock and an air-gapped hall has no time server, so the
 * normal case is `"server"`: the board sent no timestamp and the API stamped
 * the reading when it arrived. That is a RECEIPT time, not an observation
 * time, and anything printing `ts` has to say which it is looking at.
 */
export interface SagarNodeReading {
  station_id: string;
  ts: string;
  /** Optional, because the log is an append-only file that outlives a build:
   *  a row written before the server started recording this has none, and
   *  the honest reading of an absent value is "not known", not "device". */
  ts_source?: "server" | "device";
  received_at: string;
  temp_c: number;
  /** Total dissolved solids inferred from conductivity. A salinity PROXY, and
   *  uncalibrated: the firmware uses the vendor's nominal curve. */
  tds_ppm: number;
  turbidity_ntu: number;
}

/** The rig's threshold trip, shaped like a CAP alert and always a drill.
 *
 * `status` is fixed at `"Exercise"` by the server. A bucket of warm water in a
 * college hall is not a coastal hazard, and using CAP's own word for a drill
 * means every guard written for the rehearsal bulletins applies to it
 * unchanged. Nothing may render this without saying so.
 */
export interface SagarNodeAlert {
  status: "Exercise";
  source: string;
  event: string;
  severity: CapSeverity;
  urgency: string;
  certainty: string;
  headline: string;
  description: string;
  instruction: string;
  reading: SagarNodeReading;
  mean_before: number;
  delta_c: number;
}

/**
 * The live sensor station (PS requirement F6, TRD M9).
 *
 * Served EMPTY rather than 404 when no rig is plugged in, because no rig is
 * the normal state: on the judges' laptop, on CI, and on this machine most of
 * the time. `count === 0` is the signal to render nothing at all.
 *
 * The position is the REGISTRY's, never the device's. A board that could say
 * where it is could put a bucket in the Bay of Bengal on a globe carrying
 * twenty-five real ocean casts.
 */
export interface SagarNodeStation {
  station: {
    id: string;
    title: string;
    lat: number;
    lon: number;
    note: string;
  };
  parameters: Record<string, { label: string; units: string }>;
  count: number;
  latest: SagarNodeReading | null;
  readings: SagarNodeReading[];
  alert: SagarNodeAlert | null;
  citation: string;
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

  /** The surface where a field takes a given value, as a triangle mesh (F1).
   *
   * `valueUnits` is required rather than defaulted, and the server refuses a
   * mismatch: 26 degC and 26 K are different surfaces and both look equally
   * reasonable in a URL. */
  isosurface: (
    sourceId: string,
    variable: string,
    value: number,
    valueUnits: string,
    bbox: string,
    time: string,
  ) =>
    get<IsosurfaceMesh>(
      `/isosurface/${sourceId}/${variable}?value=${encodeURIComponent(String(value))}` +
        `&value_units=${encodeURIComponent(valueUnits)}` +
        `&bbox=${encodeURIComponent(bbox)}&time=${encodeURIComponent(time)}`,
    ),

  column: (sourceId: string, variable: string, bbox: string, time: string) =>
    get<FieldColumn>(
      `/field/${sourceId}/${variable}?bbox=${encodeURIComponent(bbox)}` +
        `&time=${encodeURIComponent(time)}&all_depths=true`,
    ),

  profiles: () => get<{ count: number; citation: string; profiles: ProfileGlyph[] }>("/profiles"),

  profile: (id: string) => get<ProfileDetail>(`/profiles/${encodeURIComponent(id)}`),

  /** Per-depth-bin bias and RMSE against the in-situ profiles (F9).
   *
   * `observed` names the profile column, and it is passed explicitly rather
   * than guessed from the model variable: scoring TEMP against psal would
   * produce a number that looks like an answer. */
  scorecard: (sourceId: string, variable: string, observed: string) =>
    get<Scorecard>(
      `/scorecard/${sourceId}/${variable}?observed=${encodeURIComponent(observed)}`,
    ),

  /** Active CAP warnings at an instant (F13, HazardWatch).
   *
   * `at` is the SCENE time, not the wall clock, so the hazard layer shares the
   * field's time axis and scrubbing moves both. `rehearsal` is passed
   * explicitly on every call: a drill must never reach the globe because a
   * default was forgotten. */
  /** The guided tours on the server (F12). One copy, so the files the
   *  data-plane tests validate are the files the browser plays. */
  storyboards: () => get<TourIndex>("/storyboards"),

  /** Depth-resolved current vectors, already reduced to a drawable count (F1).
   *
   * Not `/field` twice: at 1/12 degree the demo box is 43,621 cells per level,
   * and the server block-averages them into a few hundred arrows and says by
   * how much. The raw components are still on `/field` for anyone who wants
   * the grid the model ran on. */
  currents: (sourceId: string, bbox: string, time: string, depth: number) =>
    get<CurrentField>(
      `/currents/${sourceId}?bbox=${encodeURIComponent(bbox)}` +
        `&time=${encodeURIComponent(time)}&depth=${encodeURIComponent(String(depth))}`,
    ),

  /** The tabletop sensor station and its recent readings (F6).
   *
   * Polled rather than pushed: one small JSON document a couple of times a
   * second is a rounding error next to the field, and it keeps the data plane
   * a plain request-response service with no socket to fail on stage. */
  sagarnode: () => get<SagarNodeStation>("/sagarnode"),

  warnings: (at: string, rehearsal: boolean, bbox?: string, lang = "en") =>
    get<WarningLayer>(
      `/warnings?at=${encodeURIComponent(at)}` +
        `&rehearsal=${rehearsal ? "true" : "false"}` +
        `&lang=${encodeURIComponent(lang)}` +
        (bbox ? `&bbox=${encodeURIComponent(bbox)}` : ""),
    ),
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
 * see agreement, and it computes no skill number. Verification in observation
 * space - the model interpolated to the profile's own lat/lon/depth/time, with
 * per-depth-bin bias and RMSE - is `api.scorecard` (TRD M5, Ryan et al. 2015,
 * PRIOR-ART §B.12), served by the API and rendered by ScorecardPanel. NOTHING
 * derived from this function may be described as an RMSE, and the panel that
 * draws it says so on screen.
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
