/** Which overlays are on screen.
 *
 * SEPARATE FROM SceneState ON PURPOSE. `lib/scene.ts` mirrors
 * packages/scene/scene.schema.json, the agent may only mutate it through a
 * validated patch, and a test in the agent suite fails if the TypeScript and
 * Python views of those keys drift apart. Panel visibility is chrome, not
 * scene: it does not belong in a deep link, the agent has no business setting
 * it, and putting it there would break that check for nothing.
 *
 * WHY ANY OF THIS EXISTS. Judges reviewing the prototype said the panels
 * covered so much of the screen that the globe had no room to breathe, and
 * that the result did not read as a 3D model. They were right: nine overlays
 * were mounted on load and the water was a letterbox between them. The first
 * frame is now the globe, the provenance cartouche and the verification card,
 * which is also the strongest thing we have to show and was previously
 * competing with eight neighbours for attention.
 */

import { create } from "zustand";

export type PanelId =
  | "scorecard"
  | "sheet"
  | "catalog"
  | "legend"
  | "hazards"
  | "sensor"
  | "tours"
  | "agent";

/** Label for the dock control, and the accessible name of the panel it owns. */
export const PANEL_LABELS: Record<PanelId, string> = {
  scorecard: "Verification",
  sheet: "Station sheet",
  catalog: "Layers",
  legend: "Marks",
  hazards: "Hazards",
  sensor: "Sensor",
  tours: "Tours",
  // "Agent", not "Ask": the ask panel's own submit button is called Ask,
  // and two buttons with the same accessible name is an ambiguity for a
  // screen reader as much as for a test.
  agent: "Agent",
};

/** Surfaces a guided tour may raise that are NOT scene state.
 *
 * THE CLIENT IS THE AUTHORITY, the way the scene store is for patch keys. The
 * loader in services/api/app/storyboards.py keeps a hand-written copy so a
 * malformed tour is refused before it is served, and a test in the agent suite
 * fails if the two drift. What it may not do is let this file get behind: the
 * player checks a step's stage against THIS set and says so on screen if it
 * does not know it, exactly as it already does for an unknown patch key. A
 * step that silently raises nothing is the failure the whole tour format is
 * built to prevent.
 */
export const STAGES = new Set(["studio"]);

/** Reading order in the dock: what a forecaster reaches for, most first. */
export const PANEL_ORDER: PanelId[] = [
  "scorecard",
  "sheet",
  "catalog",
  "legend",
  "hazards",
  "sensor",
  "tours",
  "agent",
];

/** The opening state.
 *
 * Only the verification card. It is the one panel that answers a question
 * nobody else on this problem statement answers, so it is the one that earns
 * the empty screen. Everything else is a click away and says so. */
const OPENING: Record<PanelId, boolean> = {
  scorecard: true,
  sheet: false,
  catalog: false,
  legend: false,
  hazards: false,
  /* The live rig. It was the last overlay mounted unconditionally, and on the
     opening frame it was a 370 px block of caveat text across the middle of
     the water: exactly the complaint that produced this file. It is one of
     the strongest things we have, and it earns its own tab rather than the
     first frame. */
  sensor: false,
  tours: false,
  agent: false,
};

/** Everything, which is what a guided tour needs.
 *
 * A tour narrates the hazard card and the mark legend by name. Playing one
 * against a bare globe would describe panels that are not there, so starting a
 * tour opens the chrome and ending it restores what the user had. */
const ALL: Record<PanelId, boolean> = {
  scorecard: true,
  sheet: true,
  catalog: true,
  legend: true,
  hazards: true,
  sensor: true,
  tours: true,
  agent: true,
};

interface PanelStore {
  open: Record<PanelId, boolean>;
  /** The pure-globe shot: every overlay suppressed without forgetting which
   *  ones were open, so the same key brings them all back. */
  chromeHidden: boolean;
  /** What was open before a tour took over, restored when it ends. */
  beforeTour: Record<PanelId, boolean> | null;
  /** The water column studio, which is a modal rather than a dock panel: it
   *  belongs to the cast that is open, not to the dock. It lives here and not
   *  in page-local state because a guided tour has to be able to raise it, and
   *  the volumetric cube is the one thing the submission video most needs to
   *  show. It is chrome, so it is still out of the agent's reach. */
  studioOpen: boolean;
  setStudio: (open: boolean) => void;
  toggle: (id: PanelId) => void;
  show: (id: PanelId) => void;
  hide: (id: PanelId) => void;
  toggleChrome: () => void;
  openAll: () => void;
  reset: () => void;
  beginTour: () => void;
  endTour: () => void;
}

export const usePanels = create<PanelStore>((set, get) => ({
  open: { ...OPENING },
  chromeHidden: false,
  beforeTour: null,
  studioOpen: false,
  setStudio: (studioOpen) => set({ studioOpen }),
  /* A TAB DOES WHAT IT SAYS. The dock draws a tab's pressed state as
     `!chromeHidden && open[id]`, so while chrome is hidden every tab reads
     OFF. Flipping the underlying value then meant clicking a tab that reads
     off could CLOSE the panel it claims is closed: press `h`, then click
     Verification, which is open by default, and you get the chrome back with
     the one panel the opening frame exists to show now missing. Clicking a
     control that reads off must show the thing. */
  toggle: (id) =>
    set((s) =>
      s.chromeHidden
        ? { open: { ...s.open, [id]: true }, chromeHidden: false }
        : { open: { ...s.open, [id]: !s.open[id] } },
    ),
  show: (id) => set((s) => ({ open: { ...s.open, [id]: true }, chromeHidden: false })),
  hide: (id) => set((s) => ({ open: { ...s.open, [id]: false } })),
  toggleChrome: () => set((s) => ({ chromeHidden: !s.chromeHidden })),
  openAll: () => set({ open: { ...ALL }, chromeHidden: false }),
  reset: () =>
    set({ open: { ...OPENING }, chromeHidden: false, beforeTour: null, studioOpen: false }),
  beginTour: () =>
    set((s) => ({
      // Only remember the first time: a tour that re-enters must not overwrite
      // the user's own layout with the layout the last tour left behind.
      beforeTour: s.beforeTour ?? { ...s.open },
      open: { ...ALL },
      chromeHidden: false,
    })),
  endTour: () => {
    const prior = get().beforeTour;
    // The studio closes with the tour whatever the last step raised, so a tour
    // never hands the screen back with a modal still over it.
    set({
      open: prior ?? { ...OPENING },
      beforeTour: null,
      chromeHidden: false,
      studioOpen: false,
    });
  },
}));

/** Is this panel actually on screen right now? */
export function panelVisible(
  open: Record<PanelId, boolean>,
  chromeHidden: boolean,
  id: PanelId,
): boolean {
  return !chromeHidden && open[id];
}
