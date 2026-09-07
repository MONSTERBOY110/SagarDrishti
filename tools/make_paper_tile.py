"""Generate the manila form-stock texture for the station sheet.

The direction contract's OWN-WORLD block promises "opaque manila form stock".
A flat hex fill is not form stock, so this produces the substrate as a real
raster: a seamlessly tiling patch of manila paper with fibre grain and faint
laid lines, whose mean colour IS the plate token (#c4b89a) so the tile can be
painted directly rather than washed over with a colour that would bury it.

Seamlessness comes from filtering white noise in the frequency domain: an FFT
low-pass is inherently periodic, so the tile wraps on both axes with no visible
seam and no mirroring trick.

Run:  python tools/make_paper_tile.py
Out:  apps/web/public/textures/manila.png  (+ a provenance sidecar)

This script IS the asset's provenance. Regenerating with the same seed
reproduces the file byte-for-byte, which is a stronger record than an embedded
prompt: anyone can audit exactly what the texture is made of.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "apps" / "web" / "public" / "textures" / "manila.png"

SIZE = 160          # px; tiles at 1:1 CSS pixels
SEED = 20260907     # the date this world was chosen; keeps the build reproducible
PLATE = (0xC4, 0xB8, 0x9A)   # must equal --plate in globals.css


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


def main() -> int:
    rng = np.random.default_rng(SEED)

    # Three scales of paper structure, coarsest first.
    blotch = periodic_noise(rng, SIZE, cutoff=2.2)                 # sheet-scale mottling
    fibre = periodic_noise(rng, SIZE, cutoff=11.0, aniso=3.4)      # directional fibre
    grain = periodic_noise(rng, SIZE, cutoff=34.0)                 # tooth

    # Faint laid lines, the mould marks in laid paper. Periodic by definition.
    y = np.arange(SIZE)[:, None]
    laid = 0.30 * np.sin(2 * np.pi * y * 6 / SIZE)

    # Amplitudes in 8-bit levels. Chosen to read at 100% zoom without becoming
    # noise: a texture nobody can see is the same failure as no texture.
    field = 4.6 * blotch + 3.4 * fibre + 2.6 * grain + 1.5 * laid

    # Paper darkens slightly warmer than it lightens, so scale the blue channel
    # a little harder; this is what stops the grain reading as grey speckle.
    weights = (1.00, 1.03, 1.22)
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
        "manila.png - SagarDrishti station-sheet substrate\n"
        "\n"
        "Origin: generated procedurally by tools/make_paper_tile.py in this\n"
        f"repository. Seed {SEED}, size {SIZE}x{SIZE}, seamlessly tiling via an\n"
        "FFT low-pass (periodic by construction).\n"
        "\n"
        "Not sourced, not stock, not AI-image-generated. No third-party rights\n"
        "attach to it. Re-run the script to reproduce it byte-for-byte.\n"
        "\n"
        f"Mean RGB: ({mean[0]:.1f}, {mean[1]:.1f}, {mean[2]:.1f}) - matches the\n"
        f"--plate token #c4b89a = ({PLATE[0]}, {PLATE[1]}, {PLATE[2]}), so the tile\n"
        "is painted directly on the sheet rather than under a colour wash.\n"
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
