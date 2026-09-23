import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "SagarDrishti - Digital Twin of the Indian Ocean",
  description:
    "Browser-native 3D visualization of INCOIS ocean model fields fused with in-situ Argo observations (SIH26067, MoES/INCOIS).",
};

/* Cesium resolves its Workers/Assets/Widgets from this base at load time. The
   assets are vendored into public/cesium by scripts/copy-cesium.mjs, so the
   globe needs no ion token and no network - OFFLINE=1 covers the scene, not
   just the data. This must run before the app bundle evaluates. */
const CESIUM_BASE = `window.CESIUM_BASE_URL='/cesium';`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: CESIUM_BASE }} />
        <link rel="stylesheet" href="/cesium/Widgets/widgets.css" />
      </head>
      <body>
        {/*
          THESIS: A CTD station sheet clipped over the open water column.
          This surface refuses the category default, which is the dashboard
          with floating translucent panels and glowing cyan accents, because a
          translucent panel over a moving 3D scene is unreadable exactly when a
          forecaster needs it, and because glow spends hue that belongs to the
          measurement.

          THE GROUND INVERTED ON 22 SEPTEMBER 2026, and the thesis above is
          the reason it survived rather than the reason it changed. Judges
          reviewing the prototype said the colour was off and that the result
          did not read as a 3D model. It read as a document, because it was
          one: warm manila paper (#c4b89a) carrying near-black ink took the
          eye first and left the water as a letterbox between panels. What
          moved is the ground and the inks. What did not move is everything
          the refusal above is actually about. The panels are still OPAQUE,
          still square, still ruled, still hold hue in reserve for the field,
          and there is still no glow anywhere on this surface. A dark ground
          is not what makes a dashboard a dashboard.

          That distinction is now load-bearing rather than decorative. Nine
          public repositories on this problem statement were read on 22
          September and every one of them that ships a UI ships the dark cyan
          dashboard: translucent cards, accent glow, hue spent on chrome. This
          build shares their ground and nothing else about them.

          OWN-WORLD: Opaque cool slate form stock (#222B36) with a punched
          binding margin, square guillotined corners, a hairline edge and one
          offset shadow, laid on near-black water (#05080c). The stock is a
          real raster, not a hex fill: tools/make_plate_tile.py generates a
          seamless fibre-and-laid-line tile whose mean RGB IS the plate token,
          reads that token out of globals.css and refuses to run if the two
          disagree. It refuses because the tile is opaque, and an opaque tile
          carrying a stale mean is exactly how the first attempt at this
          inversion silently did nothing at all.

          Slate is 1.40:1 against the water where manila was 10.2:1, so the
          sheet gains an explicit hairline: light stock separated itself from
          dark water by luminance and needed no edge, and a black drop shadow
          on a black ground draws nothing.

          Engraved Archivo Narrow labels in uppercase at 0.09em; every measured
          value in Courier Prime with tabular figures. Process-blue ruling
          carries state as rule FORM, single available, doubled active, dashed
          pending, so hue survives only in the field's colorbar and one
          reserved caution ink. That ink still has two values, because no one
          hue is legible on both the plate and the water, but they have SWAPPED
          SIDES: #7e2110 was darkened to gain contrast against light paper and
          measures 1.4:1 here, so caution text on the plate is now the light
          tint (#F08A72) and the dark value is retired. A half-height "stale"
          form stood here originally and is struck: nothing in this build is
          ever stale, so it was a promise the render could not keep.

          STORY: The forecaster sees the model and the floats that measure it in
          one scene, reads the value at a chosen depth off the sheet, and can
          name the dataset and timestamp it came from without leaving the page.

          FIRST VIEWPORT: Full-bleed dark globe over the Bay of Bengal, and
          almost nothing else. The same review that moved the ground found
          nine overlays mounted on load with the water squeezed between them,
          so the opening frame now carries the provenance cartouche and the
          verification card alone, with every other panel one labelled click
          away in the dock along the foot. The sheet, when opened, sits at the
          left, its 24 ruled rows the Niskin bottle rack of the water column,
          active row doubled. Time scrub beneath it, provenance
          cartouche boxed along the bottom rule, and a water-column scale bar
          bottom-right carrying the vertical exaggeration, the depth cursor and
          the frame-rate readout. That last item replaces an earlier promise of
          "FPS stamped in the top-right margin": the top right is where a
          clicked instrument's profile opens, and a bare readout floating over
          empty sky read as a browser overlay rather than part of the form.

          FORM: Station logsheet + Niskin rack - candidate 4 of 7 on the ordered
          grounded list, dealt by seed key 486080dd. Raised by three named
          donors: hue reserved for the measurement (Emission-Line Rail), panel
          opacity solved against the luminance behind it and stepped state
          changes (Acetate Tab Board), one depth axis driving sheet, scene and
          readout together (Mesophotic Dive).

          FINISH: unreviewed and undocumented is unfinished; this build ends
          with the finish review, the verdict, DESIGN.md, and every shipping
          raster carrying its provenance.
        */}
        {children}
      </body>
    </html>
  );
}
