/** Current vectors: which dataset they come from, and how to describe one.
 *
 * PS requirement F1 names current vectors among the fields to render. INCOIS's
 * free ERDDAP publishes SURFACE geostrophic currents only, so this is the one
 * clause of F1 that a second dataset had to answer, and it is Copernicus
 * GLORYS. The client says so on screen rather than letting a reader assume
 * everything on the globe came from the same place.
 */

import type { CurrentField } from "./api";

/**
 * The dataset the arrows come from, named here rather than discovered.
 *
 * Deliberately NOT the scene's own `sourceId`. The scalar field on screen is
 * INCOIS's analysis and the arrows are Copernicus, on a different grid with
 * different levels, and pretending one dataset supplies both is exactly the
 * conflation the depth readout exists to prevent.
 */
export const CURRENT_SOURCE = "glorys12_cur";

/** One line for the sheet: what was drawn, at what depth, and what was not.
 *
 * The DEPTH SERVED, not the depth asked for. GLORYS has its own 40 levels and
 * none of them is exactly where the cursor is; the sheet says where the arrows
 * actually are, so a reader comparing them against the slice beside them knows
 * the two are a few metres apart.
 */
export function describeCurrents(field: CurrentField | null): string | null {
  if (!field) return null;
  if (field.count === 0) {
    return `No current arrows here: all ${field.blocks} blocks were more land than water.`;
  }
  const refused =
    field.refused > 0
      ? ` ${field.refused} coastal blocks refused for being more land than water.`
      : "";
  return (
    `${field.count} arrows at ${field.depth.toFixed(1)} m, each the mean of up to ` +
    `${field.stride * field.stride} cells of the 1/12 degree Copernicus grid.${refused}`
  );
}
