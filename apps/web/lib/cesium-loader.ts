/** Load CesiumJS from its own prebuilt bundle, not through the bundler.
 *
 * WHY THIS EXISTS. `import * as Cesium from "cesium"` resolves to the package's
 * unbundled ES source, roughly 3000 files, which Next's production optimizer
 * does not survive: the build emitted a lazy chunk whose execution failed with
 * "octal escape sequences are not allowed in template strings", and because
 * next/dynamic swallows load failures, the globe rendered as an empty black
 * frame while every panel around it worked perfectly. It looked like a data
 * problem and was a bundler problem, and it only appeared in `next build`,
 * never in `next dev`.
 *
 * Loading Cesium's own prebuilt Cesium.js from public/cesium removes it from
 * the webpack graph entirely. Consequences, all of them good for us:
 *   - the production build cannot regress this way again;
 *   - builds are much faster, since 3000 modules stop being traversed;
 *   - the file is already vendored for OFFLINE=1, so this costs no new asset
 *     and still makes no network request beyond our own origin.
 *
 * The script is injected on demand rather than blocking in <head>, because it
 * is a 6 MB file and the station sheet must paint before the globe.
 */

export type CesiumModule = typeof import("cesium");

declare global {
  interface Window {
    Cesium?: CesiumModule;
    CESIUM_BASE_URL?: string;
  }
}

const SCRIPT_ID = "cesium-prebuilt";
const SRC = "/cesium/Cesium.js";

let pending: Promise<CesiumModule> | null = null;

export function loadCesium(): Promise<CesiumModule> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Cesium can only load in a browser"));
  }
  if (window.Cesium) return Promise.resolve(window.Cesium);
  if (pending) return pending;

  pending = new Promise<CesiumModule>((resolve, reject) => {
    // Cesium reads this when it needs Workers, Assets and ThirdParty. It is
    // also set in the document head; setting it again is harmless and makes
    // this module correct on its own.
    window.CESIUM_BASE_URL = window.CESIUM_BASE_URL ?? "/cesium";

    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");

    const onLoad = () => {
      if (window.Cesium) resolve(window.Cesium);
      else reject(new Error("Cesium.js loaded but window.Cesium is undefined"));
    };

    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener(
      "error",
      () => reject(new Error(`failed to load ${SRC}; is public/cesium populated?`)),
      { once: true },
    );

    if (!existing) {
      script.id = SCRIPT_ID;
      script.src = SRC;
      script.async = true;
      document.head.appendChild(script);
    }
  });

  // A failed load must not be cached, or a transient error becomes permanent.
  pending.catch(() => {
    pending = null;
  });

  return pending;
}
