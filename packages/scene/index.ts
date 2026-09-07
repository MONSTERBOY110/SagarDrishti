// SceneState types (TRD M3).
//
// scene.schema.json is the SOURCE OF TRUTH. These TS types mirror it by hand
// for Phase 1; codegen (json-schema-to-typescript + a pydantic emitter) lands
// in Phase 2 when the agent plane needs the Python side. If you edit one, edit
// the other in the same commit.

export interface Camera {
  lon: number;
  lat: number;
  height: number;
  heading?: number;
  pitch?: number;
  roll?: number;
}

export interface VariableRef {
  /** id from data/sources.yaml */
  sourceId: string;
  /** variable name as declared in sources.yaml */
  name: string;
}

/** metres, positive down (CF "positive: down") */
export interface DepthRange {
  min: number;
  max: number;
  focus?: number;
}

export interface TimeState {
  current: string;
  playing?: boolean;
  speed?: number;
}

export interface Colorbar {
  palette: string;
  min: number;
  max: number;
  scale: "linear" | "log";
  reverse?: boolean;
  /** land/fill cells must never paint as a real value */
  nanTransparent?: boolean;
}

export type LayerKind =
  | "depth_slices"
  | "isosurface"
  | "particles"
  | "argo_points"
  | "glider_tracks"
  | "warnings"
  | "sagarnode";

export interface Layer {
  id: string;
  kind: LayerKind;
  visible: boolean;
  opacity?: number;
  params?: Record<string, unknown>;
}

export interface Selection {
  kind: "argo" | "glider" | "ctd" | "sagarnode" | "gridpoint";
  /** WMO id for Argo, station id for SagarNode */
  id?: string;
  lon?: number;
  lat?: number;
  time?: string;
}

export interface SceneState {
  camera: Camera;
  variable: VariableRef;
  depthRange: DepthRange;
  time: TimeState;
  colorbar: Colorbar;
  /** 1-200; the ocean is 4 km deep over 1000 km, so 1x is unreadable */
  exaggeration: number;
  layers: Layer[];
  selection?: Selection | null;
}

/** A validated partial mutation. The agent may emit ONLY this (TRD M4). */
export type SceneCommand = {
  patch: Partial<SceneState>;
  /** why the agent asked for this - shown in the tool-trace panel */
  reason?: string;
};
