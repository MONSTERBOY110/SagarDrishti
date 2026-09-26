"""Turn the README's PNG screenshots into JPEGs, for page weight.

A 1080p PNG of a textured globe is two to three megabytes; the same frame as
a quality-88 JPEG is a few hundred kilobytes and reads the same on GitHub.
Run after `node tools/capture_readme_shots.mjs`.
"""

from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "screenshots"

for png in sorted(OUT.glob("*.png")):
    jpg = png.with_suffix(".jpg")
    Image.open(png).convert("RGB").save(jpg, quality=88, optimize=True, progressive=True)
    png.unlink()
    print(f"{jpg.name}: {jpg.stat().st_size / 1e3:.0f} KB")
