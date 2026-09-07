# ADR-0001 - Depth slices as Cesium primitives; deck.gl as a camera-synced overlay

**Date:** 2026-09-07 · **Status:** accepted (Phase 1) · **Owner:** lead

## Context

TRD M3 calls for "deck.gl custom layers + raw WebGL2 shaders" interleaved with a
CesiumJS globe, and TRD §1 shows deck.gl and Cesium as peers in the client. In
practice there are two ways to combine them:

1. **Context sharing / interleaving** - deck.gl draws into Cesium's WebGL
   context so geometry depth-tests against the globe. Correct occlusion, one
   render loop. It is also the most fragile integration in our stack: it depends
   on internal Cesium render-state details, breaks across minor Cesium versions,
   and debugging it means debugging two engines' GL state at once.
2. **Overlay** - deck.gl renders to its own transparent canvas above the Cesium
   canvas, with the camera matrices synced each frame. Trivially robust, no
   coupling to Cesium internals. Cost: no depth interaction between deck.gl
   geometry and the globe or terrain.

Phase 1 exists to kill risk before the internal round, not to accumulate it.

## Decision

- **Volumetric depth slices are Cesium primitives**, not deck.gl layers. One
  textured, geodetically-placed primitive per depth level, back-to-front sorted,
  with an opacity transfer function. This is TRD M3 strategy (a), and it is
  simultaneously TRD §6.4's slices-only fallback - the floor and the first
  implementation are the same code, so the fallback is proven by construction.
- **deck.gl enters as a camera-synced overlay canvas**, carrying Argo and glider
  point/track layers, and later particle advection.
- Revisit interleaving only if a *specific* visual defect demands it, and never
  inside 72 hours of a demo.

## Consequences

- Argo glyphs will not occlude behind the globe's horizon in Phase 1.
  Acceptable: they are markers on the near face of a globe the user is already
  looking at.
- The GPU ray-marched volume layer (TRD M3 strategy (c), Yu et al. 2025) is
  unaffected - it will be a Cesium primitive with a custom shader, the same as
  the slices, so it inherits this decision rather than fighting it.
- Cesium is pinned at 1.145.0 with its runtime assets vendored into
  `public/cesium`, so no ion token and no network call is needed to draw a
  textured globe: the NaturalEarthII TMS imagery ships inside the npm package
  (7.6 MB). PRD F11 therefore holds for the globe, not only the data.

## Amendment, 2026-09-07 (after building Spike A)

**deck.gl is not used for the Argo glyphs either.** The overlay was chosen over
context-sharing to avoid Cesium-internals risk; building the scene made a
simpler fact obvious - Cesium's own billboard primitives are strictly better
for geodetic markers than a camera-synced overlay:

- they are positioned in true geodetic coordinates, including at depth, with no
  matrix-sync approximation to maintain every frame;
- `scene.pick` gives click-picking for free, which is exactly what Spike C needs;
- one render loop instead of two, which matters on the integrated-GPU target.

Using deck.gl here would have been worse engineering adopted to satisfy a label
in TRD M3. **deck.gl stays a dependency** for the layer that genuinely earns
it: GPU particle advection for current vectors (TRD M3, Phase 4), where a
custom deck.gl layer is the right tool and the overlay's lack of depth
interaction does not matter for surface-relative particles.

Flagged to the team lead as a deviation from TRD M3's wording. The requirement
it serves (F1/F2) is unaffected.

## Amendment, 2026-09-07 (frame budget, measured)

Spike A's first working render hit **12 FPS at 1080p on the Intel UHD** target - below TRD §5's 30 floor. Four changes, in measured order of impact, brought it
to **44 FPS median (p1 23)**:

1. **`scene.msaaSamples = 1`.** Current Cesium defaults to 4x MSAA, quadrupling
   fragment work on a scene made of large flat translucent quads. Biggest single
   win, and an instrument reading numeric values gains nothing from MSAA.
2. **Draw at most ~10 slices, chosen in depth space** (`sliceVisibility`).
   24 blended full-viewport quads is ~50M blended fragments a frame. Choosing
   levels log-spaced over the column rather than adjacent to the cursor also
   fixed a *correctness* problem: levels 5-50 m are within 45 m of each other
   and rendered as one coincident plane, so the naive index-window drew eight
   quads that looked like one lid and never showed the thermocline at all.
3. **`globe.translucency.rectangle`** confined to the data box, so the glass
   surface blends over a fraction of the viewport instead of all of it.
4. **`globe.maximumScreenSpaceError = 4`** and FXAA off.

p1 of 23 FPS means occasional stutter frames and is not yet at the 60 target;
both are dev-server measurements and want re-checking against a production
build and the discrete RTX 3050. Recorded as an open Phase 2 item.
