"""Current vectors, reduced for drawing (PS requirement F1).

The problem statement names current vectors among the fields F1 must render.
INCOIS's free ERDDAP publishes SURFACE geostrophic currents only, so this is
the one clause of F1 no INCOIS source can answer; the data comes from
Copernicus and arrived with the team lead's account on 2026-09-09.

WHY THIS MODULE EXISTS AT ALL
-----------------------------
Because 1/12 degree over the Bay of Bengal box is 241 x 181 = 43,561 cells per
level, against the INCOIS analysis's 336. Drawn one arrow per cell that is not
a current map, it is a grey rectangle, and the frame budget in TRD section 5
could not paint it anyway. So the field is REDUCED, and the whole design of
this module is about reducing it without misrepresenting the ocean.

Three decisions, each of which could have gone the other way:

**Blocks are AVERAGED, not sampled.** Taking every Nth cell is cheaper and it
aliases: on a velocity field, aliasing invents eddies that are not there, and
they look exactly like the real ones. A block mean is the standard way ocean
current fields are thinned for display and it is what a reader would assume.

**A block that is mostly land is REFUSED.** Two wet cells out of sixteen is a
coastline, not a current, and an arrow drawn from them would be longest and
most confident exactly where the shelf is, which is where a forecaster reads.
Refused blocks are counted and served, so a sparse arrow field can be told
apart from a broken one.

**A cell missing EITHER component contributes nothing.** A velocity needs both.
Averaging u over cells where v is absent would produce an arrow pointing
somewhere nothing was measured.

The reduction is disclosed on every response: the stride used, how many source
cells went into each arrow, and how many blocks were dropped. A thinned field
must never be presented as the grid the model actually ran on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

#: How many arrows a viewer can actually read on one screen, and the renderer
#: can draw inside the frame budget. Measured against the demo box: 43,561
#: cells reduce to about 500 arrows at stride 9, which is a legible field at
#: 1080p with room for the rest of the scene.
DEFAULT_BUDGET = 600

#: A block needs this fraction of its cells wet before it becomes an arrow.
#: Half, because below half the "mean flow" of a block is really the flow of
#: whichever corner happens to be water.
MIN_WET_FRACTION = 0.5


@dataclass
class VectorGrid:
    """A decimated velocity field, and everything needed to distrust it."""

    arrows: list[dict] = field(default_factory=list)
    #: Blocks dropped for being mostly land. Served, never swallowed.
    refused: int = 0
    stride: int = 1
    source_cells: int = 0
    note: str = ""

    @property
    def blocks(self) -> int:
        return len(self.arrows) + self.refused


def stride_for(ny: int, nx: int, budget: int = DEFAULT_BUDGET) -> int:
    """The smallest stride that brings a ny-by-nx field under `budget` arrows.

    Returns 1 for a field already small enough. The INCOIS analysis is 21 x 16
    and thinning that would be damage for no gain.
    """
    if ny <= 0 or nx <= 0 or budget <= 0:
        return 1
    stride = 1
    while (ny // stride) * (nx // stride) > budget:
        stride += 1
        if stride > max(ny, nx):
            break
    return max(1, stride)


def decimate(
    u: np.ndarray,
    v: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    stride: int,
    min_wet: float = MIN_WET_FRACTION,
) -> VectorGrid:
    """Block-mean a (lat, lon) velocity field into drawable arrows.

    `u` and `v` are (lat, lon) for one depth and one timestep. Every arrow
    carries the mean components of its block, the resulting speed, and `n`:
    how many source cells were behind it.
    """
    u = np.asarray(u, dtype="float64")
    v = np.asarray(v, dtype="float64")
    ny, nx = u.shape if u.ndim == 2 else (0, 0)
    grid = VectorGrid(stride=max(1, int(stride)), source_cells=ny * nx)
    if ny == 0 or nx == 0:
        return grid

    s = grid.stride
    # A cell counts only if BOTH components are there. A velocity is a pair.
    wet = np.isfinite(u) & np.isfinite(v)

    for y0 in range(0, ny, s):
        for x0 in range(0, nx, s):
            y1, x1 = min(y0 + s, ny), min(x0 + s, nx)
            block = wet[y0:y1, x0:x1]
            n = int(block.sum())
            total = block.size
            if total == 0:
                continue
            if n == 0 or n / total < min_wet:
                grid.refused += 1
                continue

            bu = float(u[y0:y1, x0:x1][block].mean())
            bv = float(v[y0:y1, x0:x1][block].mean())
            grid.arrows.append(
                {
                    # The centre of the block it summarises, not its corner:
                    # an arrow drawn at the corner is offset by half a block
                    # from the water it describes.
                    "lat": round(float(lats[y0:y1].mean()), 5),
                    "lon": round(float(lons[x0:x1].mean()), 5),
                    "u": round(bu, 4),
                    "v": round(bv, 4),
                    "speed": round(math.hypot(bu, bv), 4),
                    "n": n,
                }
            )

    grid.note = (
        f"Each arrow is the mean of up to {s * s} model cells, averaged over a "
        f"{s} by {s} block of the native 1/12 degree grid. A block less than "
        f"{int(min_wet * 100)} per cent water is refused rather than averaged "
        f"from the cells that remain, which is why the field thins towards the "
        f"coast. Averaged rather than sampled: taking every {s}th cell would "
        f"alias, and on a velocity field aliasing invents eddies."
    )
    return grid
