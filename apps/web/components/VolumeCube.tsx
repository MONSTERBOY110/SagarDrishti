"use client";

/** A GPU ray-marched volume of the water column (PS requirement F1).
 *
 * WHY THIS EXISTS, IN ONE PARAGRAPH. The globe draws this field as stacked
 * depth-slice rectangles with an opacity transfer function, which TRD 6.4
 * calls the slices-only fallback floor. It is 3D-positioned but it is not a
 * volume render, and judges reviewing the prototype said so within seconds:
 * "it does not look like a 3D model". TRD M3 strategy (c), the ray-marched
 * volume, was specified and never built. This is it, and the problem statement
 * names the tool: "3D Volumetric Rendering ... WebGL / Three.js or Cesium.js".
 * Cesium keeps the geodesy; Three.js gets the volumetrics.
 *
 * WHY IT IS CHEAP. The demo cube is 16 longitudes by 21 latitudes by 24 depth
 * levels, about 8,000 voxels. That is a rounding error for a GPU: the whole
 * field fits in one small 3D texture and hardware trilinear filtering smooths
 * it for free. The expensive axis is screen pixels times steps, not data.
 *
 * WHAT KEEPS IT HONEST. The colour ramp is built by calling `rgbFor` from
 * lib/colormap.ts, the same function the globe and the profile chart use, at
 * the same vmin and vmax. The cube cannot disagree with the colorbar about
 * what a colour means. Cells with no data carry a validity channel and are
 * never coloured, so a gap in the analysis stays a gap instead of becoming
 * cold water.
 */

import { useEffect, useRef, useState } from "react";

import type { FieldColumn } from "@/lib/api";
import { rgbFor, type Palette, type Scale } from "@/lib/colormap";

/** Box proportions. Not geographic: the Bay is about 1,600 km across and 2 km
 *  deep, so a true-scale box is a sheet of paper. The globe solves this with a
 *  200x vertical exaggeration and so does this, by making the depth axis the
 *  tallest one. Roughly cubic reads as a block of water. */
const BOX = { x: 1.0, y: 1.15, z: 1.25 };

/** Samples along each ray. 64 is comfortably above the 24 levels the data
 *  actually has, so the limit is interpolation smoothness rather than detail,
 *  and it holds the frame budget on an integrated chip. */
const STEPS = 64;

export default function VolumeCube({
  column,
  palette,
  scale,
  vmin,
  vmax,
  reverse,
  opacity = 0.9,
  /** Fractions of the column, 0 at the surface and 1 at the deepest level.
   *  The slab between them is drawn and the rest is discarded, which is the
   *  cutaway an oceanographer actually wants: it exposes the thermocline. */
  sliceTop = 0,
  sliceBottom = 1,
  spin = true,
  label,
  onError,
}: {
  column: FieldColumn | null;
  /** What is IN the box, for the accessible name. A screen reader meets this
   *  element as a picture and needs to be told which field it is a picture
   *  of, the same way the residual plot beside it is labelled. */
  label?: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  opacity?: number;
  sliceTop?: number;
  sliceBottom?: number;
  spin?: boolean;
  onError?: (m: string) => void;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<any>(null);
  const [failed, setFailed] = useState<string | null>(null);
  /* The scene is built in an async effect, so the effects that push the data
     and the colour ramp into it can and do run first, find no renderer, and
     return. Their dependencies never change again, so they never run again and
     the cube draws its wireframe over an empty volume. OceanGlobe carries the
     same gate for the same reason. */
  const [ready, setReady] = useState(false);

  /* --- build the scene once ------------------------------------------------ */
  useEffect(() => {
    let disposed = false;
    const host = hostRef.current;
    if (!host) return;

    (async () => {
      let THREE: typeof import("three");
      let OrbitControls: any;
      try {
        THREE = await import("three");
        ({ OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js"));
      } catch (e) {
        const m = `The 3D volume library did not load: ${String(e)}`;
        if (!disposed) { setFailed(m); onError?.(m); }
        return;
      }
      if (disposed) return;

      /* WebGL2 is required: a 3D texture has no WebGL1 equivalent, and saying
         so beats rendering an empty box. PROBED ON A THROWAWAY CANVAS, not
         asked of the renderer: `renderer.capabilities.isWebGL2` is hardcoded
         `true` in three 0.186 and kept only for backwards compatibility, so
         the guard that used to stand here could never fire. What actually
         happens without WebGL2, or with the GPU blocklisted, or with too many
         live contexts, is that the WebGLRenderer CONSTRUCTOR throws, one line
         above where that guard sat, and the throw escaped this effect
         entirely: the panel stayed blank and black and said nothing, which on
         this surface is the one outcome that is worse than the error. */
      const probe = document.createElement("canvas").getContext("webgl2");
      if (!probe) {
        const m = "This browser has no WebGL2, which a 3D texture requires.";
        setFailed(m);
        onError?.(m);
        return;
      }
      probe.getExtension("WEBGL_lose_context")?.loseContext();

      let renderer: import("three").WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      } catch (e) {
        const m = `The 3D volume could not start: ${String(e)}`;
        if (!disposed) { setFailed(m); onError?.(m); }
        return;
      }

      /* And if the context is lost later, say so rather than freezing on the
         last frame. three's own handler only stops the loop. */
      renderer.domElement.addEventListener("webglcontextlost", (e) => {
        e.preventDefault();
        const m = "The browser took the 3D context back, so the volume stopped.";
        setFailed(m);
        onError?.(m);
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(host.clientWidth || 480, host.clientHeight || 420);
      // --abyss, alpha 0: the canvas is transparent so the studio's own
      // radial ground shows through. A hand copy of the token, because WebGL
      // cannot read a CSS custom property; it survived the 22 September plate
      // inversion only because --abyss did not move.
      renderer.setClearColor(0x05080c, 0);
      host.replaceChildren(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(
        42,
        (host.clientWidth || 480) / (host.clientHeight || 420),
        0.01,
        100,
      );
      camera.position.set(1.45, 0.95, 1.6);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.minDistance = 1.15;
      controls.maxDistance = 6;
      controls.enablePan = false;
      controls.autoRotate = spin;
      controls.autoRotateSpeed = 0.7;
      controls.target.set(0, 0, 0);

      /* The box is at the origin with no transform of its own, so object space
         and world space are the same thing and the shader can use Three's
         world-space `cameraPosition` as the ray origin without inverting a
         matrix every fragment. */
      const geometry = new THREE.BoxGeometry(BOX.x, BOX.y, BOX.z);

      const material = new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        transparent: true,
        depthWrite: false,
        // Back faces: the camera is outside the box, so the far wall is what
        // every ray must be able to start from.
        side: THREE.BackSide,
        uniforms: {
          uData: { value: null },
          uRamp: { value: null },
          uHalf: { value: new THREE.Vector3(BOX.x / 2, BOX.y / 2, BOX.z / 2) },
          uOpacity: { value: opacity },
          uSliceTop: { value: sliceTop },
          uSliceBottom: { value: sliceBottom },
          uSteps: { value: STEPS },
        },
        vertexShader: /* glsl */ `
          out vec3 vOrigin;
          out vec3 vDirection;
          void main() {
            vOrigin = cameraPosition;
            vDirection = position - cameraPosition;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          precision highp float;
          precision highp sampler3D;

          in vec3 vOrigin;
          in vec3 vDirection;
          out vec4 outColor;

          uniform sampler3D uData;   // R: value normalised to vmin..vmax, G: validity
          uniform sampler2D uRamp;   // the scene's own colorbar, 256 wide
          uniform vec3 uHalf;
          uniform float uOpacity;
          uniform float uSliceTop;
          uniform float uSliceBottom;
          uniform float uSteps;

          vec2 hitBox(vec3 orig, vec3 dir) {
            vec3 inv = 1.0 / dir;
            vec3 a = (-uHalf - orig) * inv;
            vec3 b = ( uHalf - orig) * inv;
            vec3 lo = min(a, b);
            vec3 hi = max(a, b);
            return vec2(max(max(lo.x, lo.y), lo.z), min(min(hi.x, hi.y), hi.z));
          }

          void main() {
            vec3 dir = normalize(vDirection);
            vec2 t = hitBox(vOrigin, dir);
            if (t.x > t.y) discard;
            t.x = max(t.x, 0.0);

            vec3 step = dir * ((t.y - t.x) / uSteps);
            vec3 p = vOrigin + dir * t.x;

            vec4 acc = vec4(0.0);
            for (float i = 0.0; i < 512.0; i += 1.0) {
              if (i >= uSteps) break;

              // Object space to texture space. The depth axis is INVERTED on
              // purpose: level 0 is the sea surface and belongs at the top of
              // the box, so a reader sees the column the way a column is.
              vec3 uvw = vec3(
                p.x / (uHalf.x * 2.0) + 0.5,
                p.z / (uHalf.z * 2.0) + 0.5,
                0.5 - p.y / (uHalf.y * 2.0)
              );

              if (uvw.z >= uSliceTop && uvw.z <= uSliceBottom) {
                vec2 s = texture(uData, uvw).rg;
                // Validity is interpolated at the edge of a gap, so it fades
                // rather than cutting, and below a half it is not data.
                if (s.g > 0.5) {
                  // UNDO THE PREMULTIPLY. The texture is filtered trilinearly,
                  // so both channels arrive as weighted averages of the eight
                  // surrounding voxels. A missing voxel is written as 0 in
                  // BOTH channels, which means R is effectively premultiplied
                  // by validity: at the edge of a gap the interpolated R is
                  // pulled toward zero by neighbours that hold no value, and
                  // reading it raw painted a fringe of water colder than any
                  // cell in the box actually is. That is the same class of lie
                  // the two-channel split was introduced to prevent, just at
                  // one voxel's width. Dividing by the interpolated validity
                  // recovers the average over the valid neighbours alone, and
                  // the guard above keeps the divisor off zero.
                  vec3 rgb = texture(uRamp, vec2(s.r / s.g, 0.5)).rgb;
                  float a = uOpacity * 0.055 * s.g;
                  acc.rgb += (1.0 - acc.a) * rgb * a;
                  acc.a   += (1.0 - acc.a) * a;
                  // Early ray termination (Yu, Qin and Xu 2025, adopted in
                  // PRIOR-ART section E): once the ray is opaque, every
                  // further sample is invisible and is pure cost.
                  if (acc.a > 0.96) break;
                }
              }
              p += step;
            }

            if (acc.a < 0.004) discard;
            outColor = acc;
          }
        `,
      });

      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      /* A wireframe edge, so the block reads as a bounded volume of water
         rather than as fog. Cheap, and it gives the eye something to hold
         while the thing rotates. */
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        // --stamp-soft, hand copied for the same reason as the clear colour.
        new THREE.LineBasicMaterial({ color: 0x7f8f99, transparent: true, opacity: 0.45 }),
      );
      scene.add(edges);

      let raf = 0;
      const loop = () => {
        controls.update();
        renderer.render(scene, camera);
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);

      const resize = () => {
        const w = host.clientWidth || 480;
        const h = host.clientHeight || 420;
        renderer.setSize(w, h);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      const ro = new ResizeObserver(resize);
      ro.observe(host);

      apiRef.current = { THREE, renderer, scene, camera, controls, material, mesh, edges, ro,
        stop: () => cancelAnimationFrame(raf) };
      setReady(true);
    })();

    return () => {
      disposed = true;
      const a = apiRef.current;
      if (!a) return;
      a.stop?.();
      a.ro?.disconnect();
      a.controls?.dispose?.();
      a.material?.uniforms?.uData?.value?.dispose?.();
      a.material?.uniforms?.uRamp?.value?.dispose?.();
      a.material?.dispose?.();
      a.mesh?.geometry?.dispose?.();
      a.edges?.geometry?.dispose?.();
      a.edges?.material?.dispose?.();
      a.renderer?.dispose?.();
      /* AND ACTUALLY GIVE THE CONTEXT BACK. dispose() frees the objects but a
         browser may hold the WebGL context itself until it collects the
         renderer, and Chrome caps a page at roughly sixteen live contexts.
         That cap is reachable here: a guided tour raises and lowers this
         studio on its own, and a presenter rehearsing a take opens it again
         every run. When the cap is hit the browser drops the OLDEST context,
         which is Cesium's, and the demo becomes a black globe with every
         panel working perfectly. forceContextLoss is the documented way to
         hand it back now rather than eventually. */
      a.renderer?.forceContextLoss?.();
      a.renderer?.domElement?.remove?.();
      apiRef.current = null;
      setReady(false);
    };
    // Built once. The data and the colour ramp are pushed in by the effects
    // below, because rebuilding a WebGL context on every colorbar drag is how
    // a browser runs out of contexts mid demonstration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* --- the field becomes a 3D texture -------------------------------------- */
  useEffect(() => {
    const a = apiRef.current;
    if (!ready || !a || !column) return;
    const { THREE, material } = a;
    const [nz, ny, nx] = column.shape;

    /* Two channels, both bytes, because RG8 is filterable everywhere while a
       float texture is not guaranteed to be. R carries the value normalised to
       the colorbar; G carries whether there was a measurement at all. Folding
       the two into one channel was the first attempt and it was wrong: a
       missing cell reads as the bottom of the scale, so every gap in the
       analysis rendered as the coldest water in the box. */
    const data = new Uint8Array(nx * ny * nz * 2);
    const span = vmax - vmin || 1;
    for (let i = 0; i < nx * ny * nz; i++) {
      const v = column.values[i];
      if (v === null || !Number.isFinite(v)) continue;
      const t = Math.min(1, Math.max(0, (v - vmin) / span));
      data[i * 2] = Math.round(t * 255);
      data[i * 2 + 1] = 255;
    }

    /* The source array is already ordered longitude fastest, then latitude,
       then depth, which is exactly what a Data3DTexture wants, so no
       transpose is needed and none is done. */
    const tex = new THREE.Data3DTexture(data, nx, ny, nz);
    tex.format = THREE.RGFormat;
    tex.type = THREE.UnsignedByteType;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.wrapS = tex.wrapT = tex.wrapR = THREE.ClampToEdgeWrapping;
    tex.unpackAlignment = 1;
    tex.needsUpdate = true;

    material.uniforms.uData.value?.dispose?.();
    material.uniforms.uData.value = tex;
  }, [ready, column, vmin, vmax]);

  /* --- the colour ramp, taken from the scene's own colorbar ----------------- */
  useEffect(() => {
    const a = apiRef.current;
    if (!ready || !a) return;
    const { THREE, material } = a;
    const N = 256;
    /* RGBA, not RGB. Three still exports RGBFormat, but an unsized RGB8 data
       texture is not reliably supported in WebGL2 and the failure mode is a
       silently black ramp. A fourth byte costs 256 bytes in total. */
    const px = new Uint8Array(N * 4);
    const span = vmax - vmin || 1;
    for (let i = 0; i < N; i++) {
      // Sampled at the value that position represents, so a log colorbar
      // stays a log colorbar inside the cube.
      const [r, g, b] = rgbFor(vmin + (i / (N - 1)) * span, vmin, vmax, palette, scale, reverse);
      px[i * 4] = r;
      px[i * 4 + 1] = g;
      px[i * 4 + 2] = b;
      px[i * 4 + 3] = 255;
    }
    const ramp = new THREE.DataTexture(px, N, 1, THREE.RGBAFormat);
    ramp.minFilter = ramp.magFilter = THREE.LinearFilter;
    ramp.unpackAlignment = 1;
    ramp.needsUpdate = true;
    material.uniforms.uRamp.value?.dispose?.();
    material.uniforms.uRamp.value = ramp;
  }, [ready, palette, scale, vmin, vmax, reverse]);

  /* --- cheap uniforms ------------------------------------------------------- */
  useEffect(() => {
    const a = apiRef.current;
    if (!ready || !a) return;
    a.material.uniforms.uOpacity.value = opacity;
    a.material.uniforms.uSliceTop.value = sliceTop;
    a.material.uniforms.uSliceBottom.value = sliceBottom;
    a.controls.autoRotate = spin;
  }, [ready, opacity, sliceTop, sliceBottom, spin]);

  if (failed) {
    return (
      <div className="cube cube--failed" role="note">
        {failed} The profile and the residual beside this are unaffected.
      </div>
    );
  }
  /* role="img", because a bare div has the implicit `generic` role and a
     generic element cannot be named by the author: the aria-label was on the
     element and simply never reached the accessibility tree, so the headline
     feature of this build had no accessible name at all. The canvas three
     appends inside it has no alt text either, which is why the name belongs on
     the host rather than on the canvas. */
  return (
    <div
      ref={hostRef}
      className="cube"
      role="img"
      aria-label={`${label ?? "The field"} through the water column, rendered as a volume`}
    />
  );
}
