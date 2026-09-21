"""Assemble the SagarDrishti explainer and print it to PDF.

Chromium via Playwright rather than a Python PDF library, because the document
is laid out with CSS grid and inline SVG that only a real engine renders. The
fragments are kept apart so a section can be rewritten without touching the
stylesheet.

Run:  python docs/explainer/build.py
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT_HTML = HERE / "SagarDrishti-Explained.html"
OUT_PDF = HERE.parent / "SagarDrishti-Explained.pdf"
PARTS = ["_head.html", "_01.html", "_02.html", "_03.html", "_04.html", "_05.html"]

html = "\n".join((HERE / p).read_text(encoding="utf-8") for p in PARTS)

# The architecture diagram lives in its own file so the prose fragment stays
# readable. It is spliced in at its marker, and the marker must be there.
MARK = "<!--ARCH-->"
assert MARK in html, "the architecture diagram marker is missing"
html = html.replace(MARK, (HERE / "_arch.svg").read_text(encoding="utf-8").strip())

# The project's hard typography rule, checked before anything is rendered.
DASHES = (chr(0x2014), chr(0x2013))  # written as code points so this file
                                     # never itself trips tools/check_dashes.py
bad = {c: html.count(c) for c in DASHES if c in html}
if bad:
    for m in re.finditer("".join((".{0,60}[", *DASHES, "].{0,60}")), html):
        print("  dash:", m.group(0).replace("\n", " "))
    sys.exit(f"em or en dashes present: {bad}")

# Every image the document references must exist, or the PDF ships with holes.
missing = [src for src in re.findall(r'<img src="([^"]+)"', html)
           if not (HERE / src).resolve().exists()]
if missing:
    sys.exit(f"missing images: {missing}")

OUT_HTML.write_text(html, encoding="utf-8")
print(f"  html   {OUT_HTML.name}  {len(html) // 1024} KB")

from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.goto(OUT_HTML.as_uri(), wait_until="networkidle")
    # No Chromium header or footer: it cannot be suppressed on the cover, and
    # a page number printed over a full-bleed cover looks like a mistake. The
    # margins come from the CSS @page rules, which lets @page :first bleed.
    page.pdf(
        path=str(OUT_PDF),
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
    )
    b.close()

import pymupdf  # noqa: E402

# Page furniture, drawn here rather than by the browser so the cover stays
# clean and the numbering starts on the first page a reader would cite.
d = pymupdf.open(OUT_PDF)
GREY = (0.54, 0.60, 0.64)
for i, pg in enumerate(d, start=1):
    if i == 1:
        continue
    w, h = pg.rect.width, pg.rect.height
    y = h - 30
    pg.draw_line((45, y - 9), (w - 45, y - 9), color=(0.83, 0.86, 0.89), width=0.5)
    pg.insert_text((45, y + 2), "SagarDrishti  ·  SIH26067  ·  Team PixelPaws",
                   fontname="helv", fontsize=7.5, color=GREY)
    n = str(i)
    wn = pymupdf.get_text_length(n, fontname="helv", fontsize=7.5)
    pg.insert_text((w - 45 - wn, y + 2), n,
                   fontname="helv", fontsize=7.5, color=GREY)
print(f"  furniture drawn on {d.page_count - 1} pages")

d.set_metadata({
    "title": "SagarDrishti, explained from zero",
    "author": "Team PixelPaws",
    "subject": ("A complete introduction to SagarDrishti, the browser-native 3D "
                "digital twin of the Indian Ocean built for Smart India "
                "Hackathon 2026 problem statement SIH26067 (Ministry of Earth "
                "Sciences / INCOIS)."),
    "keywords": ("SIH26067, INCOIS, Ministry of Earth Sciences, ocean model, "
                 "in-situ observations, Argo, glider, CTD, NetCDF, CF, Zarr, "
                 "OGC WMS, OGC WCS, CesiumJS, WebGL2, FastAPI, Class-4 "
                 "verification, TEOS-10, CAP v1.2, digital twin"),
})
d.saveIncr()
d.close()

chk = pymupdf.open(OUT_PDF)
text = " ".join(pg.get_text() for pg in chk)
print(f"  pdf    {OUT_PDF.name}  {OUT_PDF.stat().st_size // 1024} KB  "
      f"{chk.page_count} pages  {len(text.split())} words")
assert not any(dsh in text for dsh in DASHES), "dash survived into the PDF"
print("  clean: no em or en dash in the rendered text")
