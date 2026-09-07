# ADR-0005 - WMS tiles are coloured by our own LUT, not by matplotlib

**Date:** 2026-09-07 · **Status:** ACCEPTED 2026-09-07 by the team lead · **Owner:** lead

## Context

TRD M2 specifies the OGC endpoint as "PNG tiles via matplotlib colormaps
server-side". The implementation in `services/api/app/ogc.py` does not use
matplotlib in the render path. It calls `app/colormap.py:map_to_rgba`, the same
lookup tables the browser uses in `apps/web/lib/colormap.ts`.

CLAUDE.md forbids scope changes without the team lead's explicit approval, and
although this is an implementation detail rather than a scope change, it differs
from a sentence in a design document we may show judges. So it is recorded here
rather than left as a quiet divergence, the same way ADR-0001 recorded dropping
deck.gl from the scene.

## Decision

Colour the WMS tiles from our own LUT.

The reason is colour parity, and it is not cosmetic. A forecaster can open the
same field two ways: in our 3D scene, and as a WMS layer in QGIS or in INCOIS's
own tooling. If those two disagree about which colour 26 degrees is, the
colorbar stops being a measuring instrument, which is the one thing PRD F4 and
the design system both insist it must remain. matplotlib's `thermal` is not
cmocean's `thermal`, and neither is bit-identical to the anchor stops we
interpolate, so routing the server through matplotlib would guarantee the two
disagree.

Keeping one LUT means one place to change a palette and no possible drift.

## Consequences

- TRD M2's wording is now inaccurate on this point. Left unedited on purpose:
  the TRD is a document we may put in front of judges, and quietly editing a
  shown document is how a team loses track of what it claimed. This ADR is the
  record.
- matplotlib stays a dependency and is still used, including by the tests, which
  decode the served PNG with `matplotlib.image.imread` rather than trusting our
  own encoder to read back what it wrote.
- If the lead prefers the TRD wording followed literally, the change is small
  and local to one function in `ogc.py`. The cost is accepting that a WMS tile
  and the browser's own slice will be visibly different colours for the same
  value, which we would then have to be ready to explain on stage.

## Decision recorded

The team lead chose **option 1, keep colour parity** ("keep colour parity",
2026-09-07). TRD M2's "PNG tiles via matplotlib colormaps server-side" is
superseded on this point by this ADR, and the TRD text is left unedited on
purpose so the record of what changed lives here rather than in a silent diff.

Consequences now settled:

- `app/ogc.py` keeps calling `app/colormap.py:map_to_rgba`, which is the same
  function the `/field` responses and the tests use.

- **Correction to this ADR's first draft**, which said there is ONE lookup table
  that both the tile and the slice read. There are TWO: `PALETTE_STOPS` in
  `services/api/app/colormap.py` and `STOPS` in `apps/web/lib/colormap.ts`. The
  server cannot hand a lookup table to a browser that has to colour a canvas
  per frame, and generating one file from the other would put a build step in
  front of a project whose whole posture is that the demo runs from a clean
  checkout with the network off.

  They are byte-identical today: verified across all 6 palettes, 256 entries,
  3 channels, zero differing values. But they agreed because somebody kept them
  in step by hand, and the decision recorded here is worth no more than that
  habit. So three tests in `tests/test_colormap.py` now hold the line:

  1. the client's `STOPS` table is PARSED out of the real TypeScript source and
     compared stop for stop against the server's, so editing one ramp and
     forgetting the other is a failing build;
  2. the two languages' rounding rules are compared over every LUT entry.
     `np.round` is round-half-to-even and `Math.round` is round-half-away-from-
     zero, so 126.5 becomes 126 on the server and 127 in the browser. No
     current palette interpolates onto such a tie, and this test is what turns
     "does not happen to" into "cannot ship";
  3. 26 degrees, the isotherm the demo actually talks about, is asserted to be
     the same RGB triple on both sides, because that is the value a judge with
     a colour picker would check against a QGIS layer.

  The parity guard was verified by perturbing one channel of one stop by one:
  the test fails and names the palette.
- The answer to "why does your WMS not use matplotlib" on stage is one
  sentence: a forecaster who opens the same field in QGIS and in our scene must
  see 26 degrees as the same colour, or the colorbar stops being a measuring
  instrument.
- matplotlib remains a dependency and remains the test oracle: `test_ogc.py`
  decodes served PNGs with `matplotlib.image.imread` rather than trusting our
  own encoder to read back what it wrote.
- A future palette change is a single-file change. If the two ever diverge,
  that is a bug with one obvious cause rather than a design question.
