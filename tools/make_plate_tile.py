"""Generate the form-stock texture for the station sheet.

The direction contract's OWN-WORLD block promises real stock, not a hex fill,
so this produces the substrate as a raster: a seamlessly tiling patch with
fibre grain and faint laid lines, whose mean colour IS the plate token so the
tile can be painted directly rather than washed over with a colour that would
bury it.

REPOINTED 22 SEPTEMBER 2026, when the plate inverted from warm manila
(#c4b89a) to cool slate (#222B36). This script previously emitted an OPAQUE
tile at the manila mean, which meant the CSS token could be changed to anything
at all and the sheet would still render manila. That is exactly why the token
value is asserted against the tile mean below: the substrate and the token are
one decision. CI re-runs this script and fails on any diff under
apps/web/public/textures/, so the drift is caught by the build rather than by
whoever next happens to run it by hand, and the same job proves the sidecar's
claim that one seed reproduces the file byte for byte.

The grain amplitude came DOWN with the ground. The old figures were tuned
against a base of ~190 levels, where a five-level swing is a fraction of a
per cent of the local value; against a base of ~40 the same swing is an eighth
of it, and the paper reads as television snow. The amplitudes below are the
old ones scaled to hold roughly the same RELATIVE modulation.

Seamlessness comes from filtering white noise in the frequency domain: an FFT
low-pass is inherently periodic, so the tile wraps on both axes with no visible
seam and no mirroring trick.

Run:  python tools/make_plate_tile.py
Out:  apps/web/public/textures/plate.png  (+ a provenance sidecar)

This script IS the asset's provenance. Regenerating with the same seed
reproduces the file byte-for-byte, which is a stronger record than an embedded
prompt: anyone can audit exactly what the texture is made of.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "apps" / "web" / "public" / "textures" / "plate.png"
CSS = REPO / "apps" / "web" / "app" / "globals.css"

SIZE = 160          # px; tiles at 1:1 CSS pixels
SEED = 20260907     # the date this world was chosen; keeps the build reproducible
PLATE = (0x22, 0x2B, 0x36)   # must equal --plate in globals.css; asserted below


def periodic_noise(rng: np.random.Generator, size: int, cutoff: float, aniso: float = 1.0) -> np.ndarray:
    """Band-limited noise that tiles seamlessly.

    `cutoff` is in cycles per tile: higher means finer grain. `aniso` stretches
    the filter along y, which is what gives paper its directional fibre.
    """
    white = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size) * size
    fx = np.fft.fftfreq(size) * size
    ky, kx = np.meshgrid(fy, fx, indexing="ij")
    radius = np.sqrt((ky / aniso) ** 2 + kx**2)

    # Gaussian low-pass. Periodic by construction, so the tile wraps.
    envelope = np.exp(-(radius**2) / (2 * cutoff**2))
    filtered = np.fft.ifft2(np.fft.fft2(white) * envelope).real

    span = filtered.max() - filtered.min()
    return np.zeros_like(filtered) if span == 0 else (filtered - filtered.mean()) / (span / 2)


def plate_token() -> tuple[int, int, int]:
    """Read --plate straight out of globals.css, so the two cannot drift."""
    m = re.search(r"--plate:\s*#([0-9A-Fa-f]{6})\s*;", CSS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("could not find a --plate token in globals.css")
    h = m.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def main() -> int:
    token = plate_token()
    if token != PLATE:
        raise SystemExit(
            f"PLATE here is {PLATE} but globals.css says {token}. "
            "The tile is opaque: if these disagree the CSS token does nothing."
        )

    rng = np.random.default_rng(SEED)

    # Three scales of structure, coarsest first.
    blotch = periodic_noise(rng, SIZE, cutoff=2.2)                 # sheet-scale mottling
    fibre = periodic_noise(rng, SIZE, cutoff=11.0, aniso=3.4)      # directional fibre
    grain = periodic_noise(rng, SIZE, cutoff=34.0)                 # tooth

    # Faint laid lines, the mould marks in laid paper. Periodic by definition.
    y = np.arange(SIZE)[:, None]
    laid = 0.30 * np.sin(2 * np.pi * y * 6 / SIZE)

    # Amplitudes in 8-bit levels, roughly 45% of the manila figures: see the
    # module docstring. A texture nobody can see is the same failure as no
    # texture, and a texture everybody can see is worse than either.
    field = 2.1 * blotch + 1.5 * fibre + 1.2 * grain + 0.7 * laid

    # Slate lightens cooler than it darkens, so the blue channel is modulated
    # hardest; this is what stops the grain reading as grey speckle. The warm
    # plate used the same trick in the same direction for the opposite reason.
    weights = (1.00, 1.06, 1.20)
    rgb = np.empty((SIZE, SIZE, 3), dtype=np.float64)
    for c in range(3):
        rgb[..., c] = PLATE[c] + field * weights[c]

    out = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, mode="RGB").save(OUT, optimize=True)

    mean = out.reshape(-1, 3).mean(axis=0)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]

    sidecar = OUT.with_suffix(".provenance.txt")
    sidecar.write_text(
        "plate.png - SagarDrishti station-sheet substrate\n"
        "\n"
        "Origin: generated procedurally by tools/make_plate_tile.py in this\n"
        f"repository. Seed {SEED}, size {SIZE}x{SIZE}, seamlessly tiling via an\n"
        "FFT low-pass (periodic by construction).\n"
        "\n"
        "Not sourced, not stock, not AI-image-generated. No third-party rights\n"
        "attach to it. Re-run the script to reproduce it byte-for-byte.\n"
        "\n"
        f"Mean RGB: ({mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}) - matches the\n"
        f"--plate token #{PLATE[0]:02x}{PLATE[1]:02x}{PLATE[2]:02x} = "
        f"({PLATE[0]}, {PLATE[1]}, {PLATE[2]}), so the tile\n"
        "is painted directly on the sheet rather than under a colour wash.\n"
        "The script reads that token out of globals.css and refuses to run if\n"
        "the two disagree, because the tile is opaque and would otherwise\n"
        "silently override whatever the stylesheet says.\n"
        "\n"
        "Supersedes manila.png (warm stock, retired 22 September 2026).\n"
        "\n"
        f"sha256 (first 16): {digest}\n",
        encoding="utf-8",
    )

    print(f"wrote {OUT.relative_to(REPO)}  {OUT.stat().st_size / 1024:.1f} KB")
    print(f"  mean RGB ({mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}) vs plate {PLATE}")
    print(f"  level range {out.min()}..{out.max()}")
    print(f"  sidecar -> {sidecar.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
