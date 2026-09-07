"""Colorbar mapping (PS requirement F4, TRD M3/M9).

The colorbar is a measuring instrument. Two rules follow from that:

  * A cell with no data gets alpha 0 and black RGB. If land paints as a colour,
    a forecaster reads a temperature off a coastline.
  * Out-of-range values clamp to the end stops -- they are still real values,
    so they stay opaque. Wrapping or hiding them would hide the extremes,
    which in a hazard context is the data that matters most.

Palettes are perceptually-uniform ramps in the cmocean idiom (thermal for
temperature, haline for salinity, deep for bathymetry, balance for anomalies),
defined here as anchor stops so we carry no extra dependency. They are
cmocean-*inspired* approximations, not the published tables; swapping in the
real cmocean LUTs is a drop-in change if a reviewer asks for exactness.
"""

from __future__ import annotations

import numpy as np

LUT_SIZE = 256

#: name -> anchor RGB stops, evenly spaced from the low end to the high end.
PALETTE_STOPS: dict[str, list[tuple[int, int, int]]] = {
    # sequential, dark-cool to bright-warm; monotonically increasing luminance
    "thermal": [(3, 35, 51), (24, 63, 124), (88, 79, 153), (153, 88, 132),
                (205, 109, 85), (238, 157, 59), (231, 215, 88)],
    # sequential, for salinity
    "haline": [(41, 24, 107), (21, 72, 142), (19, 110, 133), (34, 146, 109),
               (105, 178, 72), (191, 199, 60), (253, 222, 144)],
    # sequential, light-to-dark; reads as "deeper"
    "deep": [(253, 253, 204), (178, 222, 166), (112, 190, 167), (68, 152, 166),
             (56, 110, 151), (60, 66, 116), (43, 32, 63)],
    # diverging, for anomalies and model-minus-observation residuals
    "balance": [(24, 28, 110), (60, 110, 190), (160, 200, 230), (247, 247, 247),
                (230, 170, 150), (190, 80, 70), (110, 20, 40)],
    # sequential, for chlorophyll (usually paired with scale="log")
    "algae": [(214, 249, 207), (155, 220, 160), (94, 189, 129), (44, 155, 105),
              (14, 119, 82), (10, 82, 61), (10, 45, 39)],
    # perceptually uniform greyscale fallback, and the print-safe option
    "gray": [(10, 10, 10), (128, 128, 128), (245, 245, 245)],
}


def _build_lut(stops: list[tuple[int, int, int]]) -> np.ndarray:
    """Linear interpolation between anchor stops -> (LUT_SIZE, 3) uint8."""
    xs = np.linspace(0.0, 1.0, len(stops))
    grid = np.linspace(0.0, 1.0, LUT_SIZE)
    arr = np.asarray(stops, dtype="float64")
    lut = np.stack([np.interp(grid, xs, arr[:, c]) for c in range(3)], axis=1)
    return np.clip(np.round(lut), 0, 255).astype("uint8")


PALETTES: dict[str, np.ndarray] = {name: _build_lut(stops) for name, stops in PALETTE_STOPS.items()}


def map_to_rgba(
    values: np.ndarray,
    vmin: float,
    vmax: float,
    palette: str = "thermal",
    scale: str = "linear",
    reverse: bool = False,
) -> np.ndarray:
    """Map a 2-D field to an RGBA uint8 image.

    Returns an array shaped (..., 4). NaN -> (0, 0, 0, 0).
    """
    if palette not in PALETTES:
        raise ValueError(f"unknown palette {palette!r}; have {sorted(PALETTES)}")
    if scale not in ("linear", "log"):
        raise ValueError(f"unknown scale {scale!r}; expected 'linear' or 'log'")
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        raise ValueError("vmin and vmax must be finite")
    if vmin == vmax:
        raise ValueError("vmin must differ from vmax (a zero-width range paints one colour)")
    if vmin > vmax:
        raise ValueError("vmin must be less than vmax")

    vals = np.asarray(values, dtype="float64")
    missing = ~np.isfinite(vals)

    if scale == "log":
        if vmin <= 0 or vmax <= 0:
            raise ValueError("a log scale needs a strictly positive vmin and vmax")
        # Non-positive data cannot be logged; clamp it to the low end rather
        # than dropping it, so a zero-chlorophyll pixel is still drawn.
        safe = np.where(vals > 0, vals, vmin)
        t = (np.log10(safe) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin))
    else:
        t = (vals - vmin) / (vmax - vmin)

    t = np.clip(np.nan_to_num(t, nan=0.0), 0.0, 1.0)
    if reverse:
        t = 1.0 - t

    idx = np.round(t * (LUT_SIZE - 1)).astype("int32")
    rgb = PALETTES[palette][idx]

    rgba = np.empty(rgb.shape[:-1] + (4,), dtype="uint8")
    rgba[..., :3] = rgb
    rgba[..., 3] = 255
    rgba[missing] = 0            # transparent AND black, so nothing bleeds
    return rgba


def suggested_range(values: np.ndarray, pct: float = 2.0) -> tuple[float, float]:
    """A sensible default colorbar range: robust percentiles, not min/max.

    A single bad cell would otherwise flatten the whole ramp -- which is
    exactly what happens the first time you point this at an unfamiliar field
    on stage.
    """
    finite = np.asarray(values, dtype="float64")
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return (0.0, 1.0)
    lo, hi = np.percentile(finite, [pct, 100.0 - pct])
    if lo == hi:
        hi = lo + 1.0
    return (float(lo), float(hi))
