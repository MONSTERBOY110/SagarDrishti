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
          THESIS: A CTD station sheet clipped over the open water column. This
          surface refuses the category default - the dark-navy dashboard with
          floating translucent panels and glowing cyan accents - because a
          translucent panel over a moving 3D scene is unreadable exactly when a
          forecaster needs it, and because glow spends hue that belongs to the
          measurement.

          OWN-WORLD: Opaque manila form stock (#c4b89a) with a punched binding
          margin, square guillotined corners and one offset shadow, laid on
          near-black water (#05080c). Engraved Archivo Narrow labels in uppercase
          at 0.09em; every measured value in Courier Prime with tabular figures.
          Process-blue ruling carries state as rule FORM - single available,
          doubled active, dashed pending - so hue survives only in the field's
          colorbar and one reserved caution ink (#b23a22, darkened to #7e2110
          where it must carry text on the plate). A half-height "stale" form
          stood here originally and is struck: nothing in this build is ever
          stale, so it was a promise the render could not keep.

          STORY: The forecaster sees the model and the floats that measure it in
          one scene, reads the value at a chosen depth off the sheet, and can
          name the dataset and timestamp it came from without leaving the page.

          FIRST VIEWPORT: Full-bleed dark globe over the Bay of Bengal. The sheet
          sits at the left, its 24 ruled rows the Niskin bottle rack of the
          water column, active row doubled. Time scrub beneath it, provenance
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
