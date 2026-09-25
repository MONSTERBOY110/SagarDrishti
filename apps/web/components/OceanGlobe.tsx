"use client";

/** The volumetric scene (TRD M3, PS requirement F1).
 *
 * Strategy (a) from TRD M3: the water column is a stack of textured,
 * geodetically-placed depth slices with an opacity transfer function, drawn as
 * Cesium primitives. Per ADR-0001 this is both the first implementation and
 * TRD §6.4's slices-only fallback floor - the fallback is proven by
 * construction rather than promised.
 *
 * Two Cesium details make the column visible at all:
 *   - globe translucency turns the sea surface into glass, so slices below the
 *     ellipsoid are not occluded by it;
 *   - collision detection is off, so the camera may descend into the column.
 */

import { useEffect, useRef, useState } from "react";

import { loadCesium } from "@/lib/cesium-loader";
import { paintLevel, type Palette, type Scale } from "@/lib/colormap";
import {
  boundaryEdges,
  positionsWithHeights,
  vertexColors,
  type IsosurfaceMesh,
} from "@/lib/isosurface";
import {
  MAX_DRAWN_SLICES,
  MAX_DRAWN_SLICES_WITH_ISOSURFACE,
  sliceVisibility,
} from "@/lib/scene";
import type {
  CurrentField,
  FieldColumn,
  ProfileGlyph,
  SagarNodeStation,
  WarningAlert,
} from "@/lib/api";

export interface FpsSample {
  fps: number;
  p1: number;
  /** Was the camera moving while this was measured? A still scene has no
   *  frame rate worth quoting: the browser throttles rAF on a window it
   *  thinks is inactive, so an idle reading is its refresh choice rather
   *  than our cost. The readout says which it is looking at. */
  moving: boolean;
}

interface Props {
  column: FieldColumn | null;
  /** The extracted isosurface, or null when the layer is off (PS F1). */
  isosurface: IsosurfaceMesh | null;
  profiles: ProfileGlyph[];
  /** Active CAP warnings at the scene time (PS F13, HazardWatch). */
  warnings: WarningAlert[];
  /** Decimated current vectors at the depth cursor, or null when the layer is
   *  off (PS F1). Already reduced by the server; the client draws what it is
   *  given and never thins further. */
  currents: CurrentField | null;
  /** The tabletop sensor station (PS F6), or null when nothing is plugged in,
   *  which is the normal state. Null draws no mark: a rig glyph on the globe
   *  with no rig behind it would be the one claim on this surface that costs
   *  nothing to make and everything to be caught making. */
  sagarnode: SagarNodeStation | null;
  selection: string | null;
  focusDepth: number;
  exaggeration: number;
  opacity: number;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  onFps: (s: FpsSample) => void;
  onPickProfile: (profileId: string | null) => void;
  onReady: () => void;
  /** next/dynamic swallows load failures, so the scene reports its own */
  onError: (message: string) => void;
}

const ABYSS = "#05080c";

/* THE MARK PALETTE, which lives on the WATER and not on the plate.
   A station mark is a light body with a near-black edge, and the edge is not
   decoration: the mark has to stay legible when it lands on the brightest
   patch of the colorbar, and only a dark outline does that. The body used to
   be the manila plate colour; the plate is now dark slate and would vanish
   into the water, so the body follows the ink instead. Hand copies of the
   globals.css tokens, because a canvas cannot read a custom property. */
const MARK_BODY = "#E3EBF0"; /* --ink */
const MARK_EDGE = ABYSS;
const MARK_ARCHIVE = "#7f8f99"; /* --stamp-soft: the not-live value */
/** The Bay of Bengal opening view.
 *
 * Framed with lookAt on a point PART WAY DOWN the column rather than on the
 * sea surface, so the stack sits in the middle of the frame instead of hanging
 * off the bottom of it. A setView with a pitched orientation puts most of the
 * viewport in empty space, which is the mistake this replaces. */
const HOME = {
  lon: 87.0,
  lat: 15.0,
  /** ON THE SURFACE, and that is a correctness requirement rather than a
   *  framing choice.
   *
   *  It used to be 190 km down, which is the middle of the column once 2000 m
   *  of water is exaggerated 200 times, and it framed the stack beautifully.
   *  It also put the camera's whole frame of reference underground: Cesium
   *  measures `minimumZoomDistance` from the transform origin, so a 120 km
   *  floor left the camera 70 km BELOW the sea floor at full zoom, inside the
   *  Earth, with the water behind it. A browser test found that at 151 km
   *  before collision detection was turned on and at 70 km after. No value of
   *  the zoom floor fixes it, because at a shallow pitch the camera barely
   *  rises from the origin at all.
   *
   *  With the origin at the surface, a camera at ANY range and ANY pitch in
   *  the upper hemisphere is above the ellipsoid, so one bound holds
   *  everywhere. The column is framed by pitch and range instead. */
  centreDepth: 0,
  /** Low, because a slice stack seen from above is one opaque lid; the
   *  stratification only reads from the side. Lowered further when the origin
   *  came up to the surface: the column hangs BELOW the point the camera is
   *  aimed at, so a shallower angle is what brings it back into the middle of
   *  the frame. */
  pitchDeg: -90,
  /** Far enough out that the stack covers part of the viewport instead of all
   *  of it: overdraw is the dominant cost in this scene. Raised from 3.0 Mm
   *  when the aim point came up to the surface, because the column then hangs
   *  BELOW that point instead of straddling it and ran off the bottom of the
   *  frame. Measured at 3.9 Mm: the warm surface, the gradient and the blue
   *  deep water all sit inside the viewport with the limb behind them. */
  range: 13_300_000,
};
/* THE OPENING FRAME CHANGED ON 25 SEPTEMBER 2026, at the lead's request: the
   whole globe, straight down, India and the Bay of Bengal in the middle, the
   way a forecaster first meets the ocean on every portal they already use.
   The low oblique shot above is what the tours and the studio show when they
   need the stratification; the first frame's job is to say WHERE we are.
   13.3 Mm is measured, not guessed: Cesium's 60 degree field of view is taken
   across the wider axis, so at 1920 px the focal length is about 1663 px, and
   a disc about 1130 px across (the reference frame) needs the Earth to
   subtend 18.9 degrees of half-angle, which is 13.3 Mm above the surface. The
   comments on pitch and range above record why the oblique shot was chosen
   and still apply to it. */

/** The side-on view of the water column that a guided tour flies to. These
 *  are the opening frame's old values; see HOME for why they were chosen. */
const COLUMN = { pitchDeg: -20, range: 3_900_000, flySeconds: 3.0 };

/** How close and how far the camera may get to the water.
 *
 * WHY THIS EXISTS. Judges reported that the scene "gets lost" and that zooming
 * and rotating felt bad. It was not a feel problem, it was a frame-of-reference
 * problem: the opening shot used lookAt and then immediately released the
 * transform with `lookAtTransform(Matrix4.IDENTITY)`, which hands the camera
 * back to Cesium's default controller. That controller orbits the CENTRE OF THE
 * PLANET. At basin scale, with collision detection off and no zoom bounds, a
 * drag rotates the whole Earth under you and a scroll flies straight through
 * it, so the box of water you were looking at leaves the screen and there is no
 * way back.
 *
 * Holding the transform on the data box instead makes every drag an orbit AROUND
 * THE WATER and every scroll a dolly towards it, which is the Google Earth
 * behaviour that was asked for. The bounds then stop the two remaining ways to
 * lose it: pushing through the far side, and retreating until the box is a dot.
 */
const CAMERA = {
  /** Closer than this and the near plane starts clipping the slice stack. */
  minZoom: 120_000,
  /** Far enough to see the whole Bay in context, not so far that the data box
   *  becomes a speck with nothing to grab. */
  maxZoom: 20_000_000,
  /** Cesium's defaults are 0.9, which on a scene this size reads as drift.
   *  Lower is crisper: the motion stops close to when the hand stops. */
  inertiaSpin: 0.55,
  inertiaTranslate: 0.55,
  inertiaZoom: 0.6,
  /** Seconds for the Recentre flight. Long enough to read as a move rather
   *  than a cut, short enough not to stall a demo. */
  recentreSeconds: 1.2,
};

export default function OceanGlobe(props: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const creditRef = useRef<HTMLDivElement>(null);
  /* The viewer is built asynchronously while the field is being fetched, so the
     two race. Without this gate the slice effect can run first, find no viewer,
     bail out, and never run again because its dependencies never change. */
  const [ready, setReady] = useState(false);

  // Live refs so the render loop and Cesium callbacks read current values
  // without the effect re-running and rebuilding the whole scene.
  const latest = useRef(props);
  latest.current = props;

  const cesiumRef = useRef<{
    viewer: any;
    Cesium: any;
    slices: any[];
    floats: any[];
    /** HazardWatch polygons and circles. Their own list, so a change to the
     *  warning layer does not rebuild the 24-slice stack beside it. */
    hazards: any[];
    /** Current-vector arrows. Their own list for the same reason, and they
     *  rebuild on every depth change, which the slices do not. */
    arrows: any[];
    /** The tabletop rig's mark. At most one, and usually none, but a list so
     *  the teardown reads the same as every other layer's. */
    nodes: any[];
    /** The isosurface primitive and the polyline drawing the rim of its holes.
     *  These live in `scene.primitives`, NOT in `viewer.entities`, which is why
     *  the teardown below had to learn about them: the existing cleanup removed
     *  entities only, and a leaked primitive shows up as a slow frame-rate
     *  decay over a long demo rather than as a failing test. */
    isosurface: any | null;
    isoRim: any | null;
    /** The mesh the primitive was BUILT from. The probe hooks read this rather
     *  than the prop, so what they report is what is on screen: a hook keyed on
     *  a prop can say a surface exists while the effect that draws it has not
     *  run, which is the trap the drawnSlices readout already fell into once. */
    isoMesh: IsosurfaceMesh | null;
  } | null>(null);

  /* --- build the viewer once ---------------------------------------------- */
  useEffect(() => {
    let disposed = false;
    let handler: any = null;
    let removeFps: (() => void) | null = null;

    (async () => {
      // Cesium's own prebuilt bundle, not the bundler's idea of it. See
      // lib/cesium-loader.ts for the production failure this avoids.
      let Cesium: Awaited<ReturnType<typeof loadCesium>>;
      try {
        Cesium = await loadCesium();
      } catch (e) {
        latest.current.onError(
          `The 3D engine could not load: ${e instanceof Error ? e.message : String(e)}`,
        );
        return;
      }
      if (disposed || !hostRef.current) return;

      const viewer = new Cesium.Viewer(hostRef.current, {
        // No ion token, no network: NaturalEarthII ships inside the npm package
        // and was vendored into public/cesium at install time.
        baseLayer: Cesium.ImageryLayer.fromProviderAsync(
          Cesium.TileMapServiceImageryProvider.fromUrl("/cesium/Assets/Textures/NaturalEarthII"),
          {},
        ),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        // Cesium's attribution must stay visible; it lives in the cartouche.
        creditContainer: creditRef.current ?? undefined,
      });

      const scene = viewer.scene;

      // An instrument, not a planetarium: no sun, sky, stars or fog competing
      // with the field for the eye.
      scene.backgroundColor = Cesium.Color.fromCssColorString(ABYSS);
      scene.globe.baseColor = Cesium.Color.fromCssColorString(ABYSS);
      scene.globe.showGroundAtmosphere = false;
      scene.globe.enableLighting = false;
      if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
      if (scene.skyBox) scene.skyBox.show = false;
      if (scene.sun) scene.sun.show = false;
      if (scene.moon) scene.moon.show = false;
      scene.fog.enabled = false;
      scene.highDynamicRange = false;

      /* --- frame budget (TRD §5: 60 target / 30 floor at 1080p on the Intel
         UHD target) ---------------------------------------------------------
         Measured on that GPU, in this order of impact:
           - MSAA defaults to 4x in current Cesium, quadrupling fragment work
             on a scene that is mostly large flat quads. An instrument reading
             numeric values gains nothing from it.
           - A coarser screen-space error halves the tile draw calls.
           - FXAA on top of a translucent stack softens the grid cells we
             deliberately kept crisp. */
      scene.msaaSamples = 1;
      scene.globe.maximumScreenSpaceError = 4;
      if (scene.postProcessStages?.fxaa) scene.postProcessStages.fxaa.enabled = false;

      // Darken and desaturate the base imagery so land reads as context and
      // the coloured field is the only saturated thing on screen.
      const base = scene.imageryLayers.get(0);
      if (base) {
        // Land reads as context, never as content: bright enough that a
        // coastline is legible against the field, desaturated enough that the
        // only real colour on screen is the measurement. Costs no frame time.
        base.brightness = 0.52;
        base.saturation = 0.26;
        base.contrast = 1.24;
      }

      // Make the sea surface glass and let the camera go under it.
      scene.globe.translucency.enabled = true;
      // A single alpha, not a distance ramp: the column must stay readable
      // whether the camera is at basin scale or inside the water.
      scene.globe.translucency.frontFaceAlpha = 0.32;
      scene.globe.undergroundColor = Cesium.Color.fromCssColorString(ABYSS);
      /* Confine the glass surface to the region that actually has data. A
         globe-wide translucent pass blends the whole viewport every frame; the
         data box is a fraction of it, and outside the box an opaque Earth is
         also the more honest picture - there is nothing to see through. */
      scene.globe.translucency.rectangle = Cesium.Rectangle.fromDegrees(
        79.0,
        4.0,
        96.0,
        26.0,
      );
      scene.globe.depthTestAgainstTerrain = false;
      /* COLLISION DETECTION IS ON, and it was off until a browser test flew
         the camera 151 km underground with the mouse wheel.
         It was disabled alongside globe translucency, which is the usual
         pairing in Cesium's own samples: with a translucent globe you are
         meant to be able to go inside it. This scene never needs to. The water
         column is drawn BELOW the surface and read THROUGH the translucent
         globe from outside, so the only thing the camera gains underground is
         a view of the inside of the Earth with the data behind it, which is
         precisely the "it gets lost" the review reported. `lookAt` frames the
         shot on a point 190 km down (the middle of a 200x exaggerated column),
         so a 120 km minimum zoom still leaves the camera 150 km below the sea
         floor at the default pitch: the bound is measured from the transform
         origin, and the origin is underground. This clamps the camera itself,
         which is the only guard that holds at every pitch. */
      scene.screenSpaceCameraController.enableCollisionDetection = true;

      /* Orbit and zoom about the WATER, not the planet. See CAMERA above for
         why the transform is now held rather than released. */
      const ctl = scene.screenSpaceCameraController;
      ctl.minimumZoomDistance = CAMERA.minZoom;
      ctl.maximumZoomDistance = CAMERA.maxZoom;
      ctl.inertiaSpin = CAMERA.inertiaSpin;
      ctl.inertiaTranslate = CAMERA.inertiaTranslate;
      ctl.inertiaZoom = CAMERA.inertiaZoom;

      /* THE OPENING RANGE FOLLOWS THE VIEWPORT HEIGHT.
         A fixed range frames the column for one screen and no other. Measured
         at 1920 by 1080 the column clears every panel and none of the 149
         marks is under one; at 1366 by 768 the same range put sixteen of them
         behind the verification card, because the card is a third of a 1080 px
         screen and nearly half a 768 px one. Scaling the range by how short
         the viewport is keeps the column about the same size ON SCREEN, which
         is what the framing was actually chosen for. Clamped, so a very tall
         or very short window does not swing it absurdly. */
      /* SUPERSEDED 25 SEPTEMBER for the straight-down opening frame: the
         globe is sized to the WINDOW, so it reads the same on every screen.
         The disc is 1.3 times the window height (the lead's reference frame,
         top and bottom just cut), or 1.2 times the width on a portrait
         screen where the height rule would run it off the sides. Cesium's
         field of view spans the wider axis, which sets the focal length; the
         Earth then has to subtend that disc, which sets the distance. */
      const homeRange = () => {
        const w = viewer.scene.canvas.clientWidth || 1920;
        const h = viewer.scene.canvas.clientHeight || 1080;
        const fov = (viewer.camera.frustum as unknown as { fov?: number }).fov ?? Math.PI / 3;
        const focal = Math.max(w, h) / 2 / Math.tan(fov / 2);
        const radiusPx = Math.min(0.65 * h, 0.6 * w);
        const earth = 6_371_000;
        const range = earth / Math.sin(Math.atan(radiusPx / focal)) - earth;
        return Math.min(CAMERA.maxZoom, Math.max(HOME.range * 0.5, range));
      };

      const home = () =>
        viewer.camera.lookAt(
          Cesium.Cartesian3.fromDegrees(HOME.lon, HOME.lat, HOME.centreDepth),
          new Cesium.HeadingPitchRange(
            0,
            Cesium.Math.toRadians(HOME.pitchDeg),
            homeRange(),
          ),
        );
      home();

      /* Published so a control, a guided tour or the agent can all put the
         camera back the same way, rather than each computing its own idea of
         where home is. */
      (window as unknown as Record<string, unknown>).__sagarRecentre = () => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(
            HOME.lon,
            HOME.lat,
            homeRange(),
          ),
          orientation: {
            heading: 0,
            pitch: Cesium.Math.toRadians(HOME.pitchDeg),
            roll: 0,
          },
          duration: CAMERA.recentreSeconds,
          complete: home,
        });
      };

      /* THE COLUMN VIEW: the low oblique shot that was the opening frame until
         25 September, kept for what it was chosen for (the stratification
         reads only from the side) and flown to when a guided tour starts.
         Range scaled by viewport height as it always was, so the column
         clears the panels on a 768 px screen too. */
      (window as unknown as Record<string, unknown>).__sagarColumnView = () => {
        const h = viewer.scene.canvas.clientHeight || 1080;
        const k = Math.min(1.6, Math.max(1, 1080 / Math.max(600, h)));
        const target = Cesium.Cartesian3.fromDegrees(HOME.lon, HOME.lat, 0);
        const hpr = new Cesium.HeadingPitchRange(
          0,
          Cesium.Math.toRadians(COLUMN.pitchDeg),
          COLUMN.range * k,
        );
        // Released first: a flight is computed in world coordinates, and the
        // camera is otherwise held in the water's frame (see CAMERA). The
        // `complete` lookAt takes it back.
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
        viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(target, 1), {
          offset: hpr,
          duration: COLUMN.flySeconds,
          complete: () => viewer.camera.lookAt(target, hpr),
        });
      };

      cesiumRef.current = {
        viewer, Cesium, slices: [], floats: [], hazards: [], arrows: [], nodes: [],
        isosurface: null, isoRim: null, isoMesh: null,
      };

      /* --- FPS probe -------------------------------------------------------
         Frame durations, not a simple counter: the p1 (99th-percentile frame)
         is what a judge actually perceives as a stutter, and an average hides
         it completely.

         MEASURED ONLY WHILE THE CAMERA IS MOVING, and that correction matters
         more than it sounds. Cesium's render loop is driven by
         requestAnimationFrame, and a browser throttles rAF on a window it
         thinks is inactive. So on a still scene this probe was reporting the
         BROWSER'S CHOICE OF REFRESH RATE as though it were our frame cost.

         Measured on the target device (Intel UHD, production build, every
         layer on) the difference is not small: 27 renders per second while
         still, 72 while being orbited. The higher number is the true one, and
         the lower one was about to send me optimising a scene that is not
         slow. A readout that under-reports by a factor of three in front of a
         judge is worse than no readout.

         So: frames count towards the sample only when the camera has moved
         recently, and when it has not the last moving measurement is held and
         the readout says it is idle. That is the honest answer to "how fast
         is this", because a still picture has no frame rate worth quoting. */
      const frames: number[] = [];
      let last = performance.now();
      let reported = 0;
      let movingUntil = 0;
      let lastCam = scene.camera.positionWC.clone();
      let lastDir = scene.camera.directionWC.clone();
      let lastUp = scene.camera.upWC.clone();

      const onPostRender = () => {
        const now = performance.now();
        const gap = now - last;
        last = now;

        // A tenth of a metre of camera movement is far below anything a person
        // can see and far above floating-point noise.
        // OR a turn of the view with the camera standing still. From straight
        // above (the opening frame since 25 September) a spin moves neither
        // the position nor the view direction, only the camera's up vector:
        // the picture rotates, and a person sees it move.
        const cam = scene.camera.positionWC;
        const dir = scene.camera.directionWC;
        const up = scene.camera.upWC;
        if (
          Cesium.Cartesian3.distance(cam, lastCam) > 0.1 ||
          Cesium.Cartesian3.angleBetween(dir, lastDir) > 1e-5 ||
          Cesium.Cartesian3.angleBetween(up, lastUp) > 1e-5
        ) {
          lastCam = Cesium.Cartesian3.clone(cam, lastCam);
          lastDir = Cesium.Cartesian3.clone(dir, lastDir);
          lastUp = Cesium.Cartesian3.clone(up, lastUp);
          // Half a second of grace, so the sample survives the gap between one
          // drag and the next rather than resetting on every pause.
          movingUntil = now + 500;
        }
        const moving = now < movingUntil;
        if (moving) {
          frames.push(gap);
          if (frames.length > 180) frames.shift();
        }

        if (now - reported > 400 && frames.length > 20) {
          reported = now;
          const sorted = [...frames].sort((a, b) => a - b);
          const median = sorted[Math.floor(sorted.length / 2)];
          const worst = sorted[Math.floor(sorted.length * 0.99)];
          latest.current.onFps({
            fps: median > 0 ? 1000 / median : 0,
            p1: worst > 0 ? 1000 / worst : 0,
            moving,
          });
        } else if (now - reported > 400 && frames.length <= 20) {
          // Nothing measured yet: say so rather than printing a zero that
          // reads as a dead scene.
          reported = now;
          latest.current.onFps({ fps: 0, p1: 0, moving: false });
        }
      };
      scene.postRender.addEventListener(onPostRender);
      removeFps = () => scene.postRender.removeEventListener(onPostRender);

      /* --- picking: a float glyph is a station, and clicking it is the ask -- */
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      handler.setInputAction((movement: any) => {
        const picked = scene.pick(movement.position);
        const id = picked?.id?.properties?.profileId?.getValue?.();
        latest.current.onPickProfile(typeof id === "string" ? id : null);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      /* A hook for the Playwright demo-path test and the perf probe.
         Available in production behind ?probe=1 as well as in development: a
         test that can only drive the dev build cannot catch a production-only
         failure, which is exactly the class of bug that made the globe render
         black while every panel worked. */
      const probeRequested =
        typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).has("probe");
      if (process.env.NODE_ENV !== "production" || probeRequested) {
        (window as unknown as Record<string, unknown>).__sagarScene = {
          viewer,
          Cesium,
          sliceCount: () => cesiumRef.current?.slices.length ?? 0,
          floatCount: () => cesiumRef.current?.floats.length ?? 0,
          entityCount: () => viewer.entities.values.length,
          /** What the hazard layer actually drew, read from the entities
           *  rather than from the prop: a hook keyed on a prop can claim a
           *  warning is on screen before the effect that draws it has run. */
          arrowCount: () => cesiumRef.current?.arrows.length ?? 0,
          hazardCount: () => cesiumRef.current?.hazards.length ?? 0,
          /** 0 when no rig is plugged in, which is the state CI runs in, so a
           *  test can assert the globe invents no station. */
          sagarnodeCount: () => cesiumRef.current?.nodes.length ?? 0,
          sagarnodeTripped: () =>
            (cesiumRef.current?.nodes ?? []).some(
              (e: any) => e.properties?.tripped?.getValue?.() === true,
            ),
          hazardSeverities: () =>
            (cesiumRef.current?.hazards ?? []).map((e: any) =>
              e.properties?.severity?.getValue?.(),
            ),
          /** Window coordinates of a station mark, so a test can click the real
           *  glyph and exercise scene.pick rather than poking the store. */
          /** What the isosurface primitive actually carries, read from the
           *  mesh the build effect stored rather than from a prop. */
          isosurfaceTriangles: () => cesiumRef.current?.isoMesh?.n_triangles ?? 0,
          isosurfaceComponents: () => cesiumRef.current?.isoMesh?.n_components ?? 0,
          isosurfaceDepthRange: () => {
            const m = cesiumRef.current?.isoMesh;
            return m ? [m.depth_min, m.depth_max] : null;
          },
          /** So a test can prove a rebuild does not leak a primitive. */
          primitiveCount: () => viewer.scene.primitives.length,
          floatWindowPos: (i: number) => {
            const e = cesiumRef.current?.floats[i];
            if (!e) return null;
            const pos = e.position?.getValue(viewer.clock.currentTime);
            if (!pos) return null;
            const st: any = Cesium.SceneTransforms as any;
            const fn = st.worldToWindowCoordinates ?? st.wgs84ToWindowCoordinates;
            const win = fn.call(st, viewer.scene, pos);
            return win ? { x: win.x, y: win.y, wmo: e.properties?.wmo?.getValue?.() } : null;
          },
        };
      }

      setReady(true);
      latest.current.onReady();
    })();

    return () => {
      disposed = true;
      removeFps?.();
      handler?.destroy?.();
      const c = cesiumRef.current;
      if (c && !c.viewer.isDestroyed()) c.viewer.destroy();
      cesiumRef.current = null;
    };
    // Built once. Everything else is driven by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* --- rebuild the slice stack when the field itself changes --------------- */
  useEffect(() => {
    const c = cesiumRef.current;
    const { column, palette, scale, vmin, vmax } = props;
    if (!ready || !c || !column) return;
    const { viewer, Cesium } = c;

    for (const e of c.slices) viewer.entities.remove(e);
    c.slices = [];

    const [nz, ny, nx] = column.shape;
    const west = column.lons[0] - 0.5;
    const east = column.lons[column.lons.length - 1] + 0.5;
    const south = column.lats[0] - 0.5;
    const north = column.lats[column.lats.length - 1] + 0.5;
    const rectangle = Cesium.Rectangle.fromDegrees(west, south, east, north);

    for (let di = 0; di < nz; di++) {
      const canvas = paintLevel(
        column.values,
        di * ny * nx,
        ny,
        nx,
        vmin,
        vmax,
        palette,
        scale,
        1, // alpha rides on the material colour, so the texture never repaints
        props.reverse,
      );
      const entity = viewer.entities.add({
        rectangle: {
          coordinates: rectangle,
          height: -column.depths[di] * props.exaggeration,
          material: new Cesium.ImageMaterialProperty({
            image: canvas,
            transparent: true,
            color: Cesium.Color.WHITE.withAlpha(0.1),
          }),
          // Crisp cells: this is a 1-degree analysis grid and it should look
          // like one. Interpolation here would invent values.
          granularity: Cesium.Math.toRadians(1.0),
        },
      });
      c.slices.push(entity);
    }
    viewer.scene.requestRender();
    // Palette/range changes repaint textures; depth/exaggeration/opacity do not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.column, props.palette, props.scale, props.vmin, props.vmax, props.reverse]);

  /* --- the depth cursor: one gesture, three synchronized readouts ---------- */
  useEffect(() => {
    const c = cesiumRef.current;
    const { column, focusDepth, opacity, exaggeration } = props;
    if (!ready || !c || !column || c.slices.length === 0) return;
    const { Cesium } = c;

    let focusIndex = 0;
    let best = Infinity;
    column.depths.forEach((d, i) => {
      const gap = Math.abs(d - focusDepth);
      if (gap < best) {
        best = gap;
        focusIndex = i;
      }
    });

    // The stack yields budget to the surface when the surface is on: see
    // MAX_DRAWN_SLICES_WITH_ISOSURFACE for the measurement behind the number.
    const alphas = sliceVisibility(
      column.depths,
      focusIndex,
      opacity,
      props.isosurface ? MAX_DRAWN_SLICES_WITH_ISOSURFACE : MAX_DRAWN_SLICES,
    );
    let drawn = 0;
    c.slices.forEach((entity, i) => {
      const a = alphas[i];
      // `show` is what actually saves the frame: an alpha-0 quad is still
      // rasterized and blended, a hidden entity is not submitted at all.
      entity.show = a > 0;
      if (a > 0) {
        drawn++;
        entity.rectangle.material.color = Cesium.Color.WHITE.withAlpha(a);
      }
      entity.rectangle.height = -column.depths[i] * exaggeration;
    });
    /* Keyed on the hook EXISTING, not on NODE_ENV. The hook is created under
       either development or an explicit ?probe=1, and this write used to test
       NODE_ENV alone: in a production build the hook was therefore present but
       this field never written, so the end-to-end test could see the stack but
       not how much of it was blended. Two conditions that must agree are one
       condition too many. */
    const hook = (window as unknown as Record<string, any>).__sagarScene;
    if (hook) hook.drawnSlices = drawn;
    c.viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // props.isosurface is a dependency because the slice BUDGET depends on it:
    // without it the stack would keep drawing ten slices until some other
    // change happened to re-run this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.focusDepth, props.opacity, props.exaggeration, props.column, props.isosurface]);

  /* --- the isosurface, as real geometry (PS requirement F1) ---------------- */
  useEffect(() => {
    const c = cesiumRef.current;
    if (!ready || !c) return;
    const { viewer, Cesium } = c;
    const mesh = props.isosurface;

    /* Remove the previous primitive FIRST and unconditionally. This effect
       re-runs whenever the mesh or the exaggeration changes, and Cesium
       consumes Geometry attributes at construction, so tracking either means
       rebuilding. Forgetting the remove would leak a primitive per tick of the
       exaggeration slider, which presents as a slow frame-rate decay over a
       long demo rather than as a failure anything would catch. The existing
       teardown removes ENTITIES only; a primitive lives in a different
       collection. */
    if (c.isosurface) {
      viewer.scene.primitives.remove(c.isosurface);
      c.isosurface = null;
    }
    if (c.isoRim) {
      viewer.scene.primitives.remove(c.isoRim);
      c.isoRim = null;
    }
    c.isoMesh = mesh;

    if (!mesh || mesh.n_triangles === 0) {
      viewer.scene.requestRender();
      return;
    }

    // Depth positive down becomes height positive up in exactly one place,
    // lib/isosurface.ts, and fromDegreesArrayHeights puts that height along
    // the geodetic normal, which is what a depth below a surface point means.
    const cartesians = Cesium.Cartesian3.fromDegreesArrayHeights(
      positionsWithHeights(mesh, props.exaggeration),
    );
    const flat = new Float64Array(cartesians.length * 3);
    for (let i = 0; i < cartesians.length; i++) {
      flat[i * 3] = cartesians[i].x;
      flat[i * 3 + 1] = cartesians[i].y;
      flat[i * 3 + 2] = cartesians[i].z;
    }

    const geometry = new Cesium.Geometry({
      attributes: new Cesium.GeometryAttributes({
        position: new Cesium.GeometryAttribute({
          componentDatatype: Cesium.ComponentDatatype.DOUBLE,
          componentsPerAttribute: 3,
          values: flat,
        }),
        // Coloured by DEPTH from the same lookup table the slices use, so one
        // colorbar governs the scene. Colouring by the isovalue would say
        // nothing: every vertex on the surface has that value by definition.
        color: new Cesium.GeometryAttribute({
          componentDatatype: Cesium.ComponentDatatype.UNSIGNED_BYTE,
          componentsPerAttribute: 4,
          normalize: true,
          values: vertexColors(mesh, "deep", "linear"),
        }),
      }),
      indices: Cesium.IndexDatatype.createTypedArray(mesh.n_vertices, mesh.indices),
      primitiveType: Cesium.PrimitiveType.TRIANGLES,
      boundingSphere: Cesium.BoundingSphere.fromVertices(Array.from(flat)),
    });

    const primitive = new Cesium.Primitive({
      geometryInstances: new Cesium.GeometryInstance({ geometry }),
      /* Flat and OPAQUE, both deliberately.
         Opaque because the globe already runs translucency with up to ten
         translucent slices; an eleventh translucent surface adds a
         primitive-versus-entity depth-sort dependency Cesium will not resolve
         cleanly, and the artefact would only appear from certain angles.
         Flat because Gouraud-smoothing a facet 150 km across is a cosmetic lie
         about the resolution of a 1-degree analysis: it is the same argument
         the colorbar already makes for painting texels nearest-neighbour. */
      appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: false }),
      asynchronous: false,
    });
    viewer.scene.primitives.add(primitive);
    c.isosurface = primitive;

    /* The rim of every hole, drawn.
       An edge used by exactly one triangle is a boundary, and on this surface
       those are the cells the extractor REFUSED because a corner had no
       measurement: land, the seabed and the sampled margin. Drawing it turns a
       ragged edge from something a judge notices into something the picture
       states. */
    const rim = boundaryEdges(mesh, props.exaggeration);
    if (rim.length >= 6) {
      const rimPoints = Cesium.Cartesian3.fromDegreesArrayHeights(rim);
      const rimFlat = new Float64Array(rimPoints.length * 3);
      for (let i = 0; i < rimPoints.length; i++) {
        rimFlat[i * 3] = rimPoints[i].x;
        rimFlat[i * 3 + 1] = rimPoints[i].y;
        rimFlat[i * 3 + 2] = rimPoints[i].z;
      }
      const rimColors = new Uint8Array(rimPoints.length * 4);
      for (let i = 0; i < rimPoints.length; i++) {
        // The caution ink of the design system, which is what marks a refusal
        // everywhere else on this surface.
        rimColors[i * 4] = 0xe8;
        rimColors[i * 4 + 1] = 0x73;
        rimColors[i * 4 + 2] = 0x5a;
        rimColors[i * 4 + 3] = 0xff;
      }
      const rimGeometry = new Cesium.Geometry({
        attributes: new Cesium.GeometryAttributes({
          position: new Cesium.GeometryAttribute({
            componentDatatype: Cesium.ComponentDatatype.DOUBLE,
            componentsPerAttribute: 3,
            values: rimFlat,
          }),
          color: new Cesium.GeometryAttribute({
            componentDatatype: Cesium.ComponentDatatype.UNSIGNED_BYTE,
            componentsPerAttribute: 4,
            normalize: true,
            values: rimColors,
          }),
        }),
        indices: Cesium.IndexDatatype.createTypedArray(
          rimPoints.length,
          Array.from({ length: rimPoints.length }, (_, i) => i),
        ),
        primitiveType: Cesium.PrimitiveType.LINES,
        boundingSphere: Cesium.BoundingSphere.fromVertices(Array.from(rimFlat)),
      });
      const rimPrimitive = new Cesium.Primitive({
        geometryInstances: new Cesium.GeometryInstance({ geometry: rimGeometry }),
        appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: false }),
        asynchronous: false,
      });
      viewer.scene.primitives.add(rimPrimitive);
      c.isoRim = rimPrimitive;
    }

    viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.isosurface, props.exaggeration]);

  /* --- float glyphs: survey station marks, drawn not glyph-substituted ----- */
  useEffect(() => {
    const c = cesiumRef.current;
    if (!ready || !c || props.profiles.length === 0) return;
    const { viewer, Cesium } = c;

    for (const e of c.floats) viewer.entities.remove(e);
    c.floats = [];

    // One canvas per (kind, selected) pair, built once per pass. Cheap, and it
    // keeps the mark for a given instrument class identical everywhere.
    const marks = new Map<string, HTMLCanvasElement>();
    const markFor = (kind: string, selected: boolean, archive: boolean) => {
      const key = `${kind}:${selected}:${archive}`;
      let canvas = marks.get(key);
      if (!canvas) {
        canvas = stationMark(selected, kind, false, archive);
        marks.set(key, canvas);
      }
      return canvas;
    };

    for (const p of props.profiles) {
      const isPicked = p.profile_id === props.selection;
      const entity = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, 0),
        billboard: {
          image: markFor(p.platform_kind, isPicked, p.epoch === "archive"),
          width: isPicked ? 22 : 15,
          height: isPicked ? 22 : 15,
          // A station mark stays clickable even when the camera is inside the
          // water column and the mark sits behind a slice.
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        properties: {
          profileId: p.profile_id,
          wmo: p.wmo,
          platformKind: p.platform_kind,
          // Carried onto the entity so a test can assert what the RING says,
          // not merely that a ring was drawn. A silently-dropped archive flag
          // would leave a 2018 glider looking current and every count correct.
          epoch: p.epoch,
        },
      });
      c.floats.push(entity);
    }
    viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.profiles, props.selection]);

  /* --- the tabletop rig (PS requirement F6, TRD M9) -----------------------
     A SEPARATE LAYER from the float glyphs above, and the separation is the
     honest part. Everything in that layer is a profile: a cast down a water
     column, served by /profiles, clickable into a depth chart. SagarNode is a
     time series at one point on a table, served by /sagarnode, and it has no
     profile to open. Folding it into the float layer would have been fewer
     lines and would have made a bucket look like an Argo float in every
     count, every legend total and every spoken summary on this page.

     It rebuilds on the whole station object rather than on a reading, which
     is once every poll while a rig is live. One billboard, so that is cheap;
     and the mark has to change the moment the threshold trips, which is the
     one beat of this demo that has to land. */
  useEffect(() => {
    const c = cesiumRef.current;
    if (!ready || !c) return;
    const { viewer, Cesium } = c;

    for (const e of c.nodes) viewer.entities.remove(e);
    c.nodes = [];

    const node = props.sagarnode;
    // No rig, or a rig that has never reported. Nothing is drawn in either
    // case: a mark on the globe is a claim that something is measuring there.
    if (node && node.count > 0) {
      const tripped = node.alert !== null;
      c.nodes.push(
        viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(node.station.lon, node.station.lat, 0),
          billboard: {
            image: stationMark(false, "sagarnode", tripped),
            width: tripped ? 24 : 16,
            height: tripped ? 24 : 16,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: {
            // Deliberately NO profileId. The pick handler reads that key to
            // open a profile panel, and this station has no profile; a click
            // on it therefore behaves exactly like a click on open water.
            stationId: node.station.id,
            sagarnode: true,
            tripped,
          },
        }),
      );
    }

    viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.sagarnode]);

  /* --- HazardWatch: CAP warning areas (PS requirement F13) ----------------
     Drawn as entities on the ellipsoid rather than at depth. A CAP area is a
     statement about a stretch of coast and sea SURFACE, not about a water
     column, so hanging it at the depth cursor would invent a vertical extent
     the bulletin never claimed.

     COLOUR. Hue on this surface is reserved for the measurement (see the
     direction contract in layout.tsx), and that rule earns its keep here more
     than anywhere else: the field underneath is already using the whole
     spectrum, so a red-amber-yellow severity ramp would put a "yellow warning"
     next to yellow 28-degree water and neither would be readable. Every hazard
     is therefore drawn in the ONE reserved caution ink, and severity is
     carried by fill weight and border width, which is the same grammar the
     errata blocks and the scorecard worst-band rule already use.

     A DRILL LOOKS DIFFERENT. An Exercise alert gets no fill at all, only a
     dashed outline. It cannot be mistaken for a live warning at a glance, and
     that is a rendering guarantee on top of the server-side one. */
  useEffect(() => {
    const c = cesiumRef.current;
    if (!ready || !c) return;
    const { viewer, Cesium } = c;

    for (const e of c.hazards) viewer.entities.remove(e);
    c.hazards = [];

    // Alpha by severity, in the reserved ink. Extreme is not opaque: the field
    // it sits over is the evidence for the warning, and burying it would make
    // the layer decorative.
    const FILL: Record<string, number> = {
      Extreme: 0.34,
      Severe: 0.24,
      Moderate: 0.16,
      Minor: 0.1,
      Unknown: 0.08,
    };
    // TWO values of the one reserved ink, and using the right one matters.
    // globals.css defines --caution (#D4553C) for rules and borders ON THE
    // PLATE, and --caution-stamp (#e8735a) as the value that stays
    // legible ON THE WATER at 6.7:1. This layer is on the water. The first
    // version used the plate value and the warning outlines were nearly
    // invisible over a bright field, which for a hazard layer is not a
    // cosmetic miss.
    // ONE value, the on-water one, for both the stroke and the wash. The plate
    // value was a dark red, and a dark red at fifteen per cent over
    // near-black water adds nothing a viewer can see: the fill was invisible
    // until this changed.
    const CAUTION = Cesium.Color.fromCssColorString("#e8735a");
    const CAUTION_FILL = CAUTION;

    for (const w of props.warnings) {
      const drill = w.status !== "Actual";
      // A drill is drawn LIGHTER and DASHED, not invisible. The first version
      // gave it no fill at all, which distinguished it perfectly and also made
      // the only ocean hazards we have almost unreadable over a bright field.
      // Dash is the primary signal here, as it is everywhere else on this
      // surface, and the panel stamps itself besides.
      const alpha = (FILL[w.severity] ?? FILL.Unknown) * (drill ? 0.45 : 1);
      const stroke = drill
        ? new Cesium.PolylineDashMaterialProperty({ color: CAUTION, dashLength: 12.0 })
        : new Cesium.ColorMaterialProperty(CAUTION);
      const width = w.severity === "Extreme" ? 4 : w.severity === "Severe" ? 3 : 2;

      const common = {
        properties: {
          alertId: w.identifier,
          severity: w.severity,
          status: w.status,
          event: w.event,
        },
      };

      for (const area of w.areas) {
        for (const ring of area.polygons) {
          const flat: number[] = [];
          for (const [lon, lat] of ring) flat.push(lon, lat);
          const positions = Cesium.Cartesian3.fromDegreesArray(flat);
          c.hazards.push(
            viewer.entities.add({
              ...common,
              polygon: {
                hierarchy: new Cesium.PolygonHierarchy(positions),
                material: CAUTION_FILL.withAlpha(alpha),
                outline: false,
                perPositionHeight: false,
              },
              polyline: {
                positions,
                width,
                material: stroke,
                // NOT clampToGround. The terrain provider here is a bare
                // ellipsoid with no elevation, so draping would buy nothing
                // and would push every warning outline through Cesium's
                // ground-primitive pipeline, which is the expensive one and
                // this scene has a frame budget (TRD section 5).
              },
            }),
          );
        }

        for (const [lon, lat, radiusKm] of area.circles) {
          c.hazards.push(
            viewer.entities.add({
              ...common,
              position: Cesium.Cartesian3.fromDegrees(lon, lat, 0),
              ellipse: {
                // CAP gives the radius in KILOMETRES and Cesium wants metres.
                // A factor of a thousand here draws a tsunami warning the size
                // of a village, or of a hemisphere.
                semiMajorAxis: radiusKm * 1000,
                semiMinorAxis: radiusKm * 1000,
                // Explicitly at height 0 rather than clamped to terrain.
                // Cesium cannot outline a terrain-clamped ellipse and says so
                // in a console warning it then acts on: the tsunami circle was
                // drawing as a fill with NO EDGE, which is the one shape on
                // this layer whose boundary is the information.
                height: 0,
                material: CAUTION_FILL.withAlpha(alpha * 0.6),
                outline: true,
                outlineColor: CAUTION,
                outlineWidth: width,
              },
            }),
          );
        }
      }
    }

    viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.warnings]);

  /* --- current vectors at the depth cursor (PS requirement F1) ------------
     The last clause of F1 to get code behind it. INCOIS publish surface
     currents only, so these are Copernicus GLORYS, live since the team lead's
     account arrived, and the server has already block-averaged 43,621 native
     cells into a few hundred arrows.

     DRAWN AT THE SAME HEIGHT AS THE FOCUSED SLICE, so the arrows read as
     belonging to that layer of water rather than floating over the stack. That
     is why this effect depends on exaggeration and focusDepth: both move the
     plane the arrows live on.

     LENGTH CARRIES SPEED, NOT COLOUR. Hue on this surface belongs to the
     measurement and the colorbar has already spent it on the scalar field; a
     second colour scale would put a "fast" arrow in competition with warm
     water and make neither readable. Length is also the encoding a current
     chart has always used, and it is the one a reader does not need a legend
     for. */
  useEffect(() => {
    const c = cesiumRef.current;
    if (!ready || !c) return;
    const { viewer, Cesium } = c;

    for (const e of c.arrows) viewer.entities.remove(e);
    c.arrows = [];

    const field = props.currents;
    if (!field || field.arrows.length === 0) {
      viewer.scene.requestRender();
      return;
    }

    // Scaled against the FASTEST arrow in this field rather than a fixed
    // metres-per-second, so the picture stays legible at 1000 m where the
    // whole field is a fifth of the surface speed. The legend states the
    // scale, so the reader is never left to infer it.
    const fastest = Math.max(...field.arrows.map((a) => a.speed), 1e-6);
    // About two thirds of a degree for the longest arrow: long enough to read
    // direction at a glance, short enough that neighbours do not overlap at
    // the stride the server chose.
    const MAX_DEGREES = 0.65;
    const INK = Cesium.Color.fromCssColorString("#cfd8dc");
    // Behind the slices above them, an arrow is drawn DIMMER rather than not
    // at all. The first version left them occluded, which is geometrically
    // honest and useless: the arrows sit at the focus depth, so at 100 m there
    // are six translucent slices in front of every one of them and the layer
    // read as empty. The station marks solved the same problem with
    // disableDepthTestDistance; a polyline cannot take that, so this is the
    // polyline equivalent, and dimming rather than matching keeps the depth
    // cue instead of throwing it away.
    const BEHIND = INK.withAlpha(0.4);

    // The plane of the focused slice. Arrows sitting at sea level while the
    // water they describe is drawn 20 km below would be a different claim.
    const height = -props.focusDepth * props.exaggeration;

    for (const a of field.arrows) {
      const scale = (a.speed / fastest) * MAX_DEGREES;
      if (!Number.isFinite(scale) || scale <= 0) continue;
      // Unit direction, then scaled. cos(lat) corrects the longitude degree,
      // which is shorter than a latitude degree everywhere but the equator;
      // without it every arrow in the Bay of Bengal points slightly too far
      // east.
      const norm = Math.hypot(a.u, a.v) || 1;
      const dLat = (a.v / norm) * scale;
      const dLon = ((a.u / norm) * scale) / Math.cos((a.lat * Math.PI) / 180);

      c.arrows.push(
        viewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights([
              a.lon, a.lat, height,
              a.lon + dLon, a.lat + dLat, height,
            ]),
            // Wide enough to read over a bright slab. At 6 the arrows were
            // hairlines against a 29 degree surface layer and the field looked
            // empty from the default camera.
            width: 11,
            // Cesium's own arrow material: the head is drawn at the end of the
            // line, so direction reads without a second entity per arrow.
            material: new Cesium.PolylineArrowMaterialProperty(
              INK.withAlpha(0.7 + 0.3 * (a.speed / fastest)),
            ),
            depthFailMaterial: new Cesium.PolylineArrowMaterialProperty(BEHIND),
          },
          properties: { speed: a.speed, u: a.u, v: a.v, n: a.n },
        }),
      );
    }

    viewer.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, props.currents, props.focusDepth, props.exaggeration]);

  return (
    <>
      <div ref={hostRef} style={{ position: "absolute", inset: 0 }} />
      {/* Cesium's attribution, required and kept legible, styled as a footer note */}
      {/* Cesium's attribution is a licensing obligation, so it is given real
          room at the bottom-right rather than being pushed half off the
          viewport edge, and the scale bar above it is offset to clear it. */}
      <div
        ref={creditRef}
        style={{
          position: "absolute",
          right: "1.25rem",
          bottom: "0.625rem",
          maxWidth: "22rem",
          textAlign: "right",
          fontSize: "0.625rem",
          lineHeight: 1.3,
          color: "var(--stamp-soft)",
          pointerEvents: "auto",
          zIndex: 3,
        }}
      />
    </>
  );
}

/** A hydrographic station mark: a dark-outlined light figure with a centre
 *  tick, drawn rather than borrowed from an icon font, in the sheet's own ink.
 *
 *  INSTRUMENT CLASS IS CARRIED BY SILHOUETTE, NOT COLOUR. The PS asks for Argo
 *  floats, gliders, CTD casts and BGC floats as distinguishable marks (PRD F2),
 *  and on this surface hue belongs to the measurement: spending colour on a
 *  platform category would put the legend in competition with the colorbar,
 *  which has to stay readable as a measuring instrument. Chart practice agrees,
 *  giving each observation type its own symbol. Square, diamond and triangle
 *  are told apart by outline alone at 15 px, and stay told apart in a
 *  photograph of a projector screen.
 *
 *  Selection is likewise an added registration box, not a colour change, and
 *  `alarm` follows the same rule: a tripped threshold adds a ring around the
 *  mark and leaves the mark itself alone. */
export function stationMark(
  selected: boolean,
  kind = "gdac_geo",
  alarm = false,
  archive = false,
): HTMLCanvasElement {
  const s = 44;
  const canvas = document.createElement("canvas");
  canvas.width = s;
  canvas.height = s;
  const ctx = canvas.getContext("2d")!;
  ctx.translate(s / 2, s / 2);

  if (selected) {
    ctx.strokeStyle = MARK_EDGE;
    ctx.lineWidth = 2;
    ctx.strokeRect(-17, -17, 34, 34);
    ctx.strokeStyle = MARK_BODY;
    ctx.lineWidth = 1;
    ctx.strokeRect(-15, -15, 30, 30);
  }

  ctx.fillStyle = MARK_BODY;
  ctx.strokeStyle = MARK_EDGE;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  switch (kind) {
    case "gdac_bgc":
      // Diamond: a profiling float carrying biogeochemical sensors as well as
      // the CTD. Same platform family as the square, turned, because it is the
      // same kind of instrument with more on board.
      ctx.moveTo(0, -11);
      ctx.lineTo(11, 0);
      ctx.lineTo(0, 11);
      ctx.lineTo(-11, 0);
      ctx.closePath();
      break;
    case "glider":
      // A dart. A glider is the only instrument here that FLIES: it has wings,
      // no propeller, and it converts buoyancy into forward motion, so it
      // crosses the map instead of drifting with the water or staying put.
      // The notch in the tail is what separates it from the plain triangle a
      // ship cast gets, at the 15 px these are actually drawn at.
      ctx.moveTo(0, -11);
      ctx.lineTo(9.5, 9);
      ctx.lineTo(0, 4.5);
      ctx.lineTo(-9.5, 9);
      ctx.closePath();
      break;
    case "ctd":
    case "file":
      // Triangle: a cast lowered from a ship on a wire. `file` shares it on
      // purpose -- a CTD arriving as delimited text and one arriving as
      // archive NetCDF are the same instrument coming through different
      // doors, and the mark describes the instrument, not the door.
      ctx.moveTo(0, -10);
      ctx.lineTo(9.5, 7.5);
      ctx.lineTo(-9.5, 7.5);
      ctx.closePath();
      break;
    case "mooring":
    case "hf_radar":
    case "adcp":
      // Circle: a fixed station. It stays where it was put, which is the one
      // thing that matters about it on a map.
      ctx.arc(0, 0, 9.5, 0, Math.PI * 2);
      break;
    case "sagarnode":
      // The same circle as a mooring, HOLLOW. SagarNode is a bucket on the
      // demo table, drawn on a globe that otherwise carries twenty-five real
      // ocean casts and a RAMA buoy India helps run, so the one thing its
      // mark has to say before anybody reads the legend is "this is not an
      // ocean observation". A station that is not filled in says it.
      //
      // The first attempt broke the rim with a dash instead, on the grounds
      // that dash already means "rehearsal" everywhere else here. It did not
      // survive contact with 15 px: a dashed outline leaves the SILHOUETTE a
      // solid disc, and what it actually produced was a mooring with a ragged
      // edge, which reads as a rendering fault rather than as a distinction.
      // Inverting the fill changes the silhouette, so it reads at any size,
      // and it borrows the same convention a hollow symbol carries on a
      // scientific plot.
      ctx.fillStyle = ABYSS;
      ctx.strokeStyle = MARK_BODY;
      ctx.arc(0, 0, 9.5, 0, Math.PI * 2);
      break;
    default:
      // Square: a core Argo float, temperature and salinity.
      ctx.rect(-8, -8, 16, 16);
  }
  ctx.fill();
  ctx.stroke();

  // The centre tick, in whatever the outline was drawn in. That is deliberate
  // rather than incidental: on the hollow mark the fill is the dark of the
  // abyss, so a dark tick would be invisible and the light body is the only
  // one that reads.
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, -4.5);
  ctx.lineTo(0, 4.5);
  ctx.moveTo(-4.5, 0);
  ctx.lineTo(4.5, 0);
  ctx.stroke();

  /* A THRESHOLD TRIP, stamped around the mark rather than coloured into it.
   *
   * Screen space, not ground distance: a ring drawn on the ellipsoid would be
   * a pinhead from orbit and a continent from close in, and this one has to
   * be the same size at every camera range.
   *
   * The reserved caution ink, in its on-water value, and dashed. Both are
   * deliberate. Hue on this surface belongs to the measurement and caution is
   * its one exception; dashed, because the rig's alert carries CAP status
   * Exercise and a drill is drawn dashed everywhere else in this product. */
  /* AN ARCHIVE OBSERVATION, stamped the same way and for the same reason.
   *
   * This instrument is real and its measurements are real, but it was in the
   * water years before the model field under it. The ring says so without
   * touching the mark, so the glyph still reads as a glider and the reader
   * still learns it is not from now. Dashed, because dashed already means
   * "not the live thing" everywhere in this product; muted rather than the
   * caution coral, because being archive is not a warning. */
  if (archive) {
    // SOLID, and pushed out to the edge of the box. The first version of this
    // was dashed, on the grounds that dash means "not the live thing"
    // everywhere else in this product. Rendered and looked at, it was
    // invisible: these marks are drawn at 15 px from a 44 px canvas, so a
    // radius-14 ring lands at under 5 px and a [3,3] dash around it becomes
    // two or three loose pixels that read as speckle on the glyph.
    //
    // This is the SAME lesson the SagarNode mark records a few lines up, and
    // it was learned twice. What survives 15 px is a change to the
    // SILHOUETTE, not a texture inside it. A solid ring at the rim of the box
    // adds an unmistakable halo while leaving the dart a dart.
    // BACKED WITH THE EDGE, like the mark body is. The rule at the top of
    // this function is that a mark carries a dark outline because it has to
    // stay legible when it lands on the brightest patch of the colorbar, and
    // these two rings were the one thing drawn without one: a muted grey ring
    // over a warm patch of thermal is about 1.1:1, which is no ring at all.
    // These rings carry the two facts a reader most needs from a glance,
    // "this is not from now" and "this one tripped", so they are exactly the
    // marks that may not disappear. One extra stroke each.
    ctx.strokeStyle = MARK_EDGE;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(0, 0, 18.5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = MARK_ARCHIVE;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(0, 0, 18.5, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (alarm) {
    // Same treatment, and the dash is drawn in the caution ink OVER a solid
    // dark backing, so the gaps in the dash read against the edge rather than
    // against whatever the field happens to be doing.
    ctx.strokeStyle = MARK_EDGE;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(0, 0, 17, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#e8735a";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(0, 0, 17, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  return canvas;
}
