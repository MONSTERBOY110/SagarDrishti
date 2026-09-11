/** SceneState store (TRD M3).
 *
 * One serializable object is the source of truth for the UI, for deep links,
 * and - from Phase 2 - for the agent, which may only mutate it through a
 * validated patch. Keeping the agent on the same store the sliders use is what
 * makes "kill the agent and every P0 still passes" true rather than hopeful.
 *
 * Shape mirrors packages/scene/scene.schema.json.
 */

import { create } from "zustand";

import type { Palette, Scale } from "./colormap";

export interface SceneState {
  sourceId: string;
  variable: string;
  /** metres, positive down - the level the depth cursor is parked on */
  focusDepth: number;
  time: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  /** The forecaster has set the range by hand, so stop re-deriving it from the
   *  data. Without this, editing a limit and then scrubbing time silently threw
   *  the edit away, which makes the control feel broken and, worse, changes the
   *  colours under a value the reader has already interpreted. */
  colorbarLocked: boolean;
  /** 1x-200x; the ocean is ~4 km deep over ~1000 km, so 1x is unreadable */
  exaggeration: number;
  /** peak alpha of the focused depth level */
  opacity: number;
  playing: boolean;
  selection: string | null;
  /** Draw the isosurface layer (PS requirement F1). Off by default: it is a
   *  second geometry pass and a second request, and the scene must open on the
   *  slices alone in case either is slow on the demo machine. */
  isosurfaceOn: boolean;
  /** The value the surface is drawn at, in the CURRENT variable's units. Reset
   *  when the variable changes, because 26 is a thermocline in degC and
   *  nothing at all in psu. */
  isovalue: number;
  /**
   * Show CAP alerts whose status is Exercise, that is, drills (PS F13).
   *
   * ON in this build, and that is a deliberate, stated choice rather than a
   * convenience. The three ocean hazards the problem statement names by name
   * (tsunami, high wave, swell surge) are the ones we could not obtain a live
   * machine feed for, so the only ocean bulletins we have are rehearsals. With
   * this off, the hazard layer over the demo's own timesteps is empty and the
   * feature reads as broken rather than as honest.
   *
   * It is safe because nothing hides what these are: they carry CAP status
   * Exercise in the file, the server refuses them unless this flag is passed,
   * the globe draws them unfilled, and the panel stamps itself. The control is
   * on screen so a judge can switch it off and watch them go.
   */
  rehearsal: boolean;
  /**
   * Draw the depth-resolved current arrows (PS F1).
   *
   * OFF by default, for the same reason the isosurface is: it is a second
   * request and a second geometry pass, and the scene must open on the slices
   * alone in case either is slow on the demo machine. It is also a different
   * DATASET (Copernicus, not INCOIS), so switching it on is a deliberate act
   * rather than something that happens to the viewer.
   */
  currentsOn: boolean;
}

export interface SceneActions {
  patch: (p: Partial<SceneState>) => void;
  setFocusDepth: (d: number) => void;
  setTime: (t: string) => void;
  togglePlaying: () => void;
  select: (id: string | null) => void;
  toggleIsosurface: () => void;
  setIsovalue: (v: number) => void;
}

export const INITIAL_SCENE: SceneState = {
  sourceId: "incois_vam_argo",
  variable: "TEMP",
  focusDepth: 20,
  time: "",
  palette: "thermal",
  scale: "linear",
  vmin: 0,
  vmax: 30,
  reverse: false,
  colorbarLocked: false,
  // 200x (TRD M3's top of range), not a timid 1x-40x: 2000 m of ocean becomes
  // 400 km, legible against a basin 1650 km across. At 1x the entire water
  // column is thinner than the coastline it sits against, which is precisely
  // why oceanographers expect this control (PRIOR-ART §E.6).
  exaggeration: 200,
  opacity: 0.72,
  playing: false,
  selection: null,
  isosurfaceOn: false,
  // 26 degC: the base of the layer that can fuel a cyclone, and the same
  // threshold the D26 product uses, so the surface and the scalar agree.
  isovalue: 26,
  rehearsal: true,
  currentsOn: false,
};

export const useScene = create<SceneState & SceneActions>((set) => ({
  ...INITIAL_SCENE,
  patch: (p) => set(p),
  setFocusDepth: (focusDepth) => set({ focusDepth }),
  setTime: (time) => set({ time }),
  togglePlaying: () => set((s) => ({ playing: !s.playing })),
  select: (selection) => set({ selection }),
  toggleIsosurface: () => set((s) => ({ isosurfaceOn: !s.isosurfaceOn })),
  setIsovalue: (isovalue) => set({ isovalue }),
}));

/** A sensible isovalue for a variable, used when the variable changes.
 *
 * Named rather than computed from the data range, because these are the values
 * a forecaster actually asks for: 26 degC is the cyclone heat-potential
 * threshold, 35 psu is the isohaline that separates Bay of Bengal freshwater
 * from Arabian Sea water. A midpoint of the colour range would be a number
 * with no meaning behind it.
 */
export function defaultIsovalue(variable: string, fallback: number): number {
  if (variable === "TEMP") return 26;
  if (variable === "SAL") return 35;
  // Sigma-0 22 kg/m3 is the base of the Bay of Bengal's fresh surface layer
  // in the monsoon: our own 2026-07-30 cube runs about 19.8 at the surface to
  // 27.8 at 2000 m, and 22 sits at the foot of the river plume rather than in
  // the middle of the colour bar. An isopycnal is the surface an oceanographer
  // actually asks for, because water moves along one rather than across it.
  if (variable === "SIG0") return 22;
  return fallback;
}

/** Below this alpha a slice contributes nothing a person can see, so it is not
 *  drawn. This is the cheap half of Yu et al. 2025's early-ray-termination
 *  idea (PRIOR-ART §E.2): stop paying for samples that cannot change the
 *  picture. */
export const SLICE_CUTOFF_ALPHA = 0.035;

/** Frame-budget cap on simultaneously blended slices. Measured on the Intel
 *  UHD target at 1080p: 24 drawn = 12 FPS, 8-10 drawn = 50+ FPS. Overdraw of
 *  large translucent quads is the dominant cost in this scene. */
export const MAX_DRAWN_SLICES = 10;

/**
 * The slice budget while the isosurface layer is on.
 *
 * MEASURED, not guessed. With ten slices drawn and the surface on, the scene
 * fell to 28.7 fps median on the Intel UHD target, under TRD section 5's floor
 * of 30, from 51 with the surface off. The 780 opaque triangles of the surface
 * itself are nothing; the cost is OVERDRAW. The surface sits inside a stack of
 * large translucent quads, and a translucent fragment behind an opaque one is
 * still rasterized and blended because blending cannot early-out on depth.
 *
 * So this is a budget TRADE, not a free addition, and it is the right way
 * round: when a forecaster turns the surface on, the surface is the thing
 * being read and the stack is context. Cutting the stack also stops the
 * surface being buried in it, so the same change buys legibility and frame
 * rate at once.
 */
export const MAX_DRAWN_SLICES_WITH_ISOSURFACE = 6;

/**
 * Which depth levels to draw, and at what opacity.
 *
 * The naive transfer function - peak at the focus, gaussian falloff by level
 * INDEX - produced a scene that was both slow and wrong. Wrong because the
 * depth axis is savagely non-uniform: levels 5, 10, 20, 30, 50 m sit within
 * 45 m of each other, which at any usable camera range are the same plane. A
 * window of eight neighbouring levels therefore rendered eight coincident
 * quads and read as one flat lid, while the stratification that makes this a
 * water column - the thermocline, the cold deep - was not drawn at all.
 *
 * So visibility is chosen in DEPTH space, not index space:
 *
 *   - the focused level draws at full opacity: it is the one being inspected;
 *   - a set of structure levels, log-spaced over the column, draws faintly.
 *     Log spacing because ocean structure is logarithmic - the mixed layer and
 *     thermocline live in the top 200 m and deserve most of the samples;
 *   - everything else is not drawn at all.
 *
 * The result is a stack with real vertical extent inside a fixed budget: the
 * body of water reads, and the level under the cursor stands out of it.
 */
export function sliceVisibility(
  depths: number[],
  focusIndex: number,
  peak: number,
  maxDrawn: number = MAX_DRAWN_SLICES,
): number[] {
  const n = depths.length;
  const alphas = new Array<number>(n).fill(0);
  if (n === 0) return alphas;

  const structure = Math.max(0.1, peak * 0.28);
  const chosen = new Set<number>([focusIndex]);

  const shallow = Math.max(depths[0], 1);
  const deep = Math.max(depths[n - 1], shallow + 1);
  const want = Math.max(0, maxDrawn - 1);
  for (let k = 0; k < want; k++) {
    const t = want === 1 ? 0.5 : k / (want - 1);
    const target = Math.exp(Math.log(shallow) + t * (Math.log(deep) - Math.log(shallow)));
    let best = -1;
    let gap = Infinity;
    for (let i = 0; i < n; i++) {
      if (chosen.has(i)) continue;
      const g = Math.abs(depths[i] - target);
      if (g < gap) {
        gap = g;
        best = i;
      }
    }
    if (best >= 0) chosen.add(best);
  }

  for (const i of chosen) {
    alphas[i] = i === focusIndex ? peak : structure;
  }
  return alphas;
}
