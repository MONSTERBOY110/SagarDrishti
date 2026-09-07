// Copy Cesium's runtime assets into public/cesium so the globe needs no network
// and no Cesium ion token (ADR-0001). Runs on postinstall; idempotent.
//
// Resolve through require.resolve rather than a hardcoded node_modules path:
// pnpm's isolated layout puts the package under apps/web/node_modules, not the
// workspace root, and hoisting differs per package manager.
import { createRequire } from "node:module";
import { cp, mkdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

let src;
try {
  src = join(dirname(require.resolve("cesium/package.json")), "Build", "Cesium");
  await stat(src);
} catch {
  console.error("[copy-cesium] could not locate cesium/Build/Cesium. Run pnpm install first.");
  process.exit(1);
}

const dest = join(here, "..", "public", "cesium");
await mkdir(dest, { recursive: true });
for (const dir of ["Assets", "ThirdParty", "Widgets", "Workers"]) {
  await cp(join(src, dir), join(dest, dir), { recursive: true });
}

// The PREBUILT bundle, and the reason it is here rather than in the webpack
// graph: importing cesium as an ES module pulls ~3000 unbundled source files
// through Next's production optimizer, which silently breaks. A production
// build emitted a lazy chunk the browser then failed to execute (an octal
// escape sequence rejected in a template string), so the globe rendered as an
// empty black frame while every panel around it worked. Serving Cesium's own
// prebuilt file sidesteps the bundler entirely, builds far faster, and cannot
// regress that way again.
await cp(join(src, "Cesium.js"), join(dest, "Cesium.js"));

console.log(`[copy-cesium] ${src} -> ${dest}`);
