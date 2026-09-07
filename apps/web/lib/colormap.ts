/** Client-side colorbar, byte-identical in intent to services/api/app/colormap.py.
 *
 * The anchor stops are duplicated rather than fetched because the renderer maps
 * thousands of cells per frame and cannot wait on a request. If you change a
 * palette, change BOTH files in the same commit - a server tile and a client
 * slice that disagree would put two different colours on one value.
 *
 * Rules that are not negotiable, because a colorbar is a measuring instrument:
 *   - missing data is fully transparent AND black, so nothing bleeds under it
 *   - out-of-range values clamp and stay opaque; extremes are the data that
 *     matters most in a hazard context
 */

export type Palette = "thermal" | "haline" | "deep" | "balance" | "algae" | "gray";
export type Scale = "linear" | "log";

const STOPS: Record<Palette, [number, number, number][]> = {
  thermal: [
    [3, 35, 51], [24, 63, 124], [88, 79, 153], [153, 88, 132],
    [205, 109, 85], [238, 157, 59], [231, 215, 88],
  ],
  haline: [
    [41, 24, 107], [21, 72, 142], [19, 110, 133], [34, 146, 109],
    [105, 178, 72], [191, 199, 60], [253, 222, 144],
  ],
  deep: [
    [253, 253, 204], [178, 222, 166], [112, 190, 167], [68, 152, 166],
    [56, 110, 151], [60, 66, 116], [43, 32, 63],
  ],
  balance: [
    [24, 28, 110], [60, 110, 190], [160, 200, 230], [247, 247, 247],
    [230, 170, 150], [190, 80, 70], [110, 20, 40],
  ],
  algae: [
    [214, 249, 207], [155, 220, 160], [94, 189, 129], [44, 155, 105],
    [14, 119, 82], [10, 82, 61], [10, 45, 39],
  ],
  gray: [[10, 10, 10], [128, 128, 128], [245, 245, 245]],
};

const LUT_SIZE = 256;
const luts = new Map<Palette, Uint8Array>();

function lut(palette: Palette): Uint8Array {
  const cached = luts.get(palette);
  if (cached) return cached;

  const stops = STOPS[palette];
  const out = new Uint8Array(LUT_SIZE * 3);
  for (let i = 0; i < LUT_SIZE; i++) {
    const t = i / (LUT_SIZE - 1);
    const seg = t * (stops.length - 1);
    const a = Math.min(Math.floor(seg), stops.length - 2);
    const f = seg - a;
    for (let c = 0; c < 3; c++) {
      out[i * 3 + c] = Math.round(stops[a][c] + (stops[a + 1][c] - stops[a][c]) * f);
    }
  }
  luts.set(palette, out);
  return out;
}

/** Normalized position of a value in the colorbar, clamped to [0, 1]. */
export function normalize(v: number, vmin: number, vmax: number, scale: Scale): number {
  if (scale === "log") {
    if (vmin <= 0 || vmax <= 0) throw new Error("a log scale needs a positive vmin and vmax");
    const safe = v > 0 ? v : vmin;
    return clamp01((Math.log10(safe) - Math.log10(vmin)) / (Math.log10(vmax) - Math.log10(vmin)));
  }
  return clamp01((v - vmin) / (vmax - vmin));
}

function clamp01(t: number): number {
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

export function rgbFor(
  v: number,
  vmin: number,
  vmax: number,
  palette: Palette = "thermal",
  scale: Scale = "linear",
  reverse = false,
): [number, number, number] {
  let t = normalize(v, vmin, vmax, scale);
  if (reverse) t = 1 - t;
  const i = Math.round(t * (LUT_SIZE - 1)) * 3;
  const table = lut(palette);
  return [table[i], table[i + 1], table[i + 2]];
}

export function cssFor(
  v: number,
  vmin: number,
  vmax: number,
  palette: Palette = "thermal",
  scale: Scale = "linear",
): string {
  const [r, g, b] = rgbFor(v, vmin, vmax, palette, scale);
  return `rgb(${r} ${g} ${b})`;
}

/** A horizontal colorbar as a CSS gradient, for the sheet's legend field. */
export function rampCss(palette: Palette, steps = 24): string {
  const table = lut(palette);
  const parts: string[] = [];
  for (let s = 0; s < steps; s++) {
    const i = Math.round((s / (steps - 1)) * (LUT_SIZE - 1)) * 3;
    parts.push(`rgb(${table[i]} ${table[i + 1]} ${table[i + 2]}) ${(s / (steps - 1)) * 100}%`);
  }
  return `linear-gradient(90deg, ${parts.join(", ")})`;
}

/**
 * Paint one depth level onto a canvas, one grid cell per pixel, then let the
 * caller scale it with smoothing OFF.
 *
 * Nearest-neighbour is a deliberate choice, not a shortcut: the source is a
 * 1-degree analysis grid, and interpolating across a land boundary would bleed
 * a coastline into the water and invent values that were never measured. Crisp
 * cells state the grid's real resolution - and they read as a ruled sheet,
 * which is the world this scene is built in.
 */
export function paintLevel(
  values: (number | null)[],
  offset: number,
  ny: number,
  nx: number,
  vmin: number,
  vmax: number,
  palette: Palette,
  scale: Scale,
  alpha: number,
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = nx;
  canvas.height = ny;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  const img = ctx.createImageData(nx, ny);
  const a = Math.round(clamp01(alpha) * 255);

  for (let yi = 0; yi < ny; yi++) {
    // Row 0 of the data is the SOUTHERNMOST latitude; row 0 of an image is the
    // top. Flipping here is what keeps the field the right way up on the globe.
    const srcRow = ny - 1 - yi;
    for (let xi = 0; xi < nx; xi++) {
      const v = values[offset + srcRow * nx + xi];
      const p = (yi * nx + xi) * 4;
      if (v === null || !Number.isFinite(v)) {
        img.data[p] = 0;
        img.data[p + 1] = 0;
        img.data[p + 2] = 0;
        img.data[p + 3] = 0; // land and fill: transparent, and black underneath
        continue;
      }
      const [r, g, b] = rgbFor(v, vmin, vmax, palette, scale);
      img.data[p] = r;
      img.data[p + 1] = g;
      img.data[p + 2] = b;
      img.data[p + 3] = a;
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}
