/** Re-take the prototype evidence set, reproducibly.
 *
 * The 19 September set was captured by hand from a script that lived in a
 * session scratchpad, which meant its own README could only say "run the
 * capture script in the session scratchpad". That is not a reproducible
 * record, and this project's whole argument is that its claims can be re-run
 * and disagreed with. So the capture is a checked-in tool, and the README it
 * writes carries the numbers it read off the running page rather than numbers
 * a human retyped.
 *
 * NOTHING HERE IS STAGED. Every figure in every shot is computed by the
 * services while the shot is taken. The script never injects a value, never
 * fakes a state and never edits an image.
 *
 * Run:
 *   ./tasks.ps1 api        (port 8000, OFFLINE=1)
 *   ./tasks.ps1 agent      (port 8010)
 *   ./tasks.ps1 demo       (port 3000, production build)
 *   node tools/capture_evidence.mjs [outDir]
 *
 * Default outDir is docs/evidence/prototype-<today>, so re-running on a new
 * day writes a new set rather than silently overwriting the record of an
 * older build.
 *
 * `?probe=1` is used only to READ the scene (which mark is a glider, where it
 * is on screen). Every state change below goes through the same controls a
 * judge would click, because a screenshot of a state no user can reach is not
 * evidence of anything.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const WEB = process.env.SAGAR_WEB ?? "http://localhost:3000";
const URL = `${WEB}/?probe=1`;
const VIEWPORT = { width: 1920, height: 1080 };

const today = new Date().toISOString().slice(0, 10);
const OUT = process.argv[2]
  ? resolve(process.argv[2])
  : join(ROOT, "docs", "evidence", `prototype-${today}`);

/** What each file shows, written into the README beside the shot. */
const CAPTIONS = {};
/** Anything that could not be captured, stated rather than silently dropped. */
const SKIPPED = [];
/** Numbers read off the running page, for the README's scene-state line. */
const MEASURED = {};

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  // ANGLE first, with the software path allowed as a fallback rather than as
  // the target. Which one Chromium actually got is READ BACK and printed in
  // the README, because the frame-rate readout is IN these shots: a number
  // taken on SwiftShader and a number taken on a discrete GPU are different
  // claims, and neither of them is the integrated chip the demo runs on.
  args: ["--use-gl=angle", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });

const offOrigin = [];
page.on("request", (r) => {
  const u = r.url();
  if (u.startsWith("data:") || u.startsWith("blob:")) return;
  let host = "";
  try {
    host = new URL(u).hostname;
  } catch {
    /* relative */
  }
  if (host && host !== "127.0.0.1" && host !== "localhost") offOrigin.push(u.slice(0, 160));
});

const sleep = (ms) => page.waitForTimeout(ms);

async function sceneReady() {
  await page.waitForFunction(
    () => {
      const s = window.__sagarScene;
      return !!s && s.sliceCount() > 0 && typeof s.drawnSlices === "number" && s.drawnSlices > 0;
    },
    undefined,
    { timeout: 120_000 },
  );
}

async function openPanel(label) {
  const tab = page.getByRole("button", { name: label, exact: true });
  await tab.waitFor({ timeout: 30_000 });
  if ((await tab.getAttribute("aria-pressed")) !== "true") await tab.click();
  await sleep(400);
}

async function closePanel(label) {
  const tab = page.getByRole("button", { name: label, exact: true });
  if ((await tab.getAttribute("aria-pressed")) === "true") await tab.click();
  await sleep(300);
}

/** A full frame. */
async function shot(name, caption) {
  await page.screenshot({ path: join(OUT, name) });
  CAPTIONS[name] = caption;
  console.log(`  ${name}`);
}

/** One element, for a panel whose detail is the point. */
async function shotOf(selector, name, caption) {
  const el = page.locator(selector).first();
  if (!(await el.count())) {
    SKIPPED.push(`${name}: no element matched \`${selector}\``);
    console.log(`  SKIP ${name} (no ${selector})`);
    return false;
  }
  await el.screenshot({ path: join(OUT, name) });
  CAPTIONS[name] = caption;
  console.log(`  ${name}`);
  return true;
}

/** The window position of the first on-screen mark of a platform class.
 *
 * Read through the probe rather than guessed, and the index walk mirrors the
 * browser suite's: floatWindowPos is indexed over the SAME entity order the
 * scene built, so the counter only advances on entities that carry a
 * platformKind. */
async function markOfKind(kind) {
  return page.evaluate((want) => {
    const s = window.__sagarScene;
    let seen = -1;
    for (const e of s.viewer.entities.values) {
      const props = e.properties;
      if (!props || !props.platformKind) continue;
      seen += 1;
      if (props.platformKind.getValue() !== want) continue;
      const m = s.floatWindowPos(seen);
      if (m && m.x > 60 && m.y > 60 && m.x < 1860 && m.y < 1020) return m;
    }
    return null;
  }, kind);
}

async function openCast(kind, label) {
  const mark = await markOfKind(kind);
  if (!mark) {
    SKIPPED.push(`${label}: no ${kind} mark was on screen at this camera position`);
    console.log(`  SKIP ${label} (no ${kind} on screen)`);
    return null;
  }
  await page.mouse.click(mark.x, mark.y);
  await page.locator('[aria-label="Instrument profile"]').waitFor({ timeout: 30_000 });
  await sleep(2500);
  return mark;
}

async function clearCast() {
  const clear = page.getByRole("button", { name: "Clear", exact: true });
  if (await clear.count()) {
    await clear.first().click();
    await sleep(600);
  }
}

/** A block control inside the station sheet, scoped by its own label.
 *
 * Scoped because the sheet grew a second On/Off control when the current
 * vector layer landed, and a bare name match then resolved to two buttons. */
function sheetToggle(blockText) {
  return page
    .locator('[aria-label="Station sheet"] .block')
    .filter({ hasText: blockText })
    .getByRole("button")
    .first();
}

// ---------------------------------------------------------------------------

console.log(`capturing to ${OUT}`);
await page.goto(URL, { waitUntil: "networkidle", timeout: 120_000 });
await sceneReady();
await sleep(6000);

// --- 1. the frame a judge actually sees first ------------------------------
await shot(
  "01-scene.png",
  "The opening view, exactly as the build loads it. The water column in colour, " +
    "the instrument marks, a CAP warning area, the verification card, and the " +
    "provenance cartouche naming the dataset and the timestamp. Every other panel " +
    "is one labelled button away in the dock along the foot.",
);

MEASURED.blockedOnOpen = await page.evaluate(() => {
  const s = window.__sagarScene;
  let blocked = 0;
  let total = 0;
  for (let i = 0; i < s.floatCount(); i++) {
    const m = s.floatWindowPos(i);
    if (!m || m.x < 4 || m.y < 4) continue;
    total++;
    const el = document.elementFromPoint(m.x, m.y);
    if (el && el.tagName !== "CANVAS") blocked++;
  }
  return `${blocked} of ${total}`;
});

// --- 2. the pure-globe shot ------------------------------------------------
await page.getByRole("button", { name: /Water only/ }).click();
await sleep(1200);
await shot(
  "02-water-only.png",
  'One key ("h") suppresses every overlay and leaves the water, the marks and ' +
    "the warning areas. The provenance cartouche, the scale bar and the dock " +
    "stay: provenance because a figure on this surface is never shown without " +
    "the dataset it came from, the scale bar because it carries the vertical " +
    "exaggeration that makes the column readable, and the dock because a screen " +
    "with no way back is not minimal, it is broken. The volumetric cube is not " +
    "here; it is in the studio, two shots down.",
);
await page.getByRole("button", { name: /Show panels/ }).click();
await sleep(800);

// --- 3. the volumetric cube, which is the headline ------------------------
const bgc = await openCast("gdac_bgc", "03-volume-cube.png");
if (bgc) {
  const studio = page.getByRole("button", { name: /Inspect the water column/i });
  if (await studio.count()) {
    await studio.first().click();
    await page.locator("div.cube").waitFor({ timeout: 30_000 });
    await sleep(8000);
    /* Put the readout on a depth before shooting. The right-hand column reads
       "Move down the column to read it" until the pointer is on the plot, and
       an evidence shot of this panel with no numbers in it is a picture of the
       argument rather than the argument: the whole claim is that the volume
       and the error are the same cast. */
    const plot = page.locator(".studio__plot").first();
    const pb = await plot.boundingBox();
    if (pb) {
      await page.mouse.move(pb.x + pb.width * 0.55, pb.y + pb.height * 0.12);
      await sleep(1200);
    }
    await shot(
      "03-volume-cube.png",
      "The Water Column Studio. The block on the right is a GPU ray-marched " +
        "volume (Three.js, a 3D texture, front-to-back accumulation with early " +
        "ray termination), not a stack of images; it orbits, and the slider cuts " +
        "it away by depth. Beside it the same cast is drawn as the measured " +
        "curve, the model curve and the residual shaded between them, with the " +
        "Class-4 figure for that depth band. A cube on its own is a prettier " +
        "picture of the same field. A cube next to its own error is a claim.",
    );
    const box = await page.locator("div.cube").first().boundingBox();
    MEASURED.cube = box ? `${Math.round(box.width)} by ${Math.round(box.height)}` : "unmeasured";
    await shotOf(
      ".studio__cube",
      "03b-cube-detail.png",
      "The volume alone. The thermocline is the band where the colour turns, " +
        "and it is a property of the data rather than a drawn line.",
    );
    const close = page.getByRole("button", { name: "Close", exact: true });
    if (await close.count()) await close.first().click();
    await sleep(800);
  } else {
    SKIPPED.push("03-volume-cube.png: the studio button was not offered for this cast");
  }
}

await shotOf(
  '[aria-label="Instrument profile"]',
  "04b-bgc-panel.png",
  "The biogeochemical float's own panel: every parameter the instrument served, " +
    "the measured profile against the model column, the Argo QC policy cited, and " +
    "the statement that the model curve is a nearest cell and therefore carries " +
    "no skill figure.",
);
await shot(
  "04-bgc-float.png",
  "A biogeochemical float opened from the globe. BGC floats are told apart from " +
    "core Argo floats by mark shape, never by colour.",
);
await clearCast();

// --- 5. the depth cursor at the bottom of the column -----------------------
await openPanel("Station sheet");
const rows = page.locator('[aria-label="Depth level"] [role="option"]');
const nRows = await rows.count();
if (nRows) {
  await rows.nth(nRows - 1).click();
  await sleep(2500);
  await shot(
    "05-depth-2000m.png",
    `The depth cursor taken to the bottom of the column. One gesture moves the ` +
      `sheet, the scene and the scale-bar readout together; ${nRows} levels are ` +
      `printed as ${nRows} ruled rows, because the rack is the water column.`,
  );
} else {
  SKIPPED.push("05-depth-2000m.png: the bottle rack rendered no rows");
}

// --- 6. the two extracted layers ------------------------------------------
const iso = sheetToggle("Isosurface");
if (await iso.count()) {
  await iso.click();
  await page.waitForFunction(() => window.__sagarScene.isosurfaceTriangles() > 0, undefined, {
    timeout: 60_000,
  });
  await sleep(2500);
  MEASURED.isosurface = await page.evaluate(() => ({
    triangles: window.__sagarScene.isosurfaceTriangles(),
    components: window.__sagarScene.isosurfaceComponents(),
  }));
  await shot(
    "06-isosurface.png",
    `The 26 degC isosurface, extracted by marching cubes on the native grid with ` +
      `no resampling: ${MEASURED.isosurface.triangles} triangles in ` +
      `${MEASURED.isosurface.components} components. The sheet states what the ` +
      `extraction refused rather than quietly closing the mesh over it.`,
  );
  await iso.click();
  await sleep(1200);
} else {
  SKIPPED.push("06-isosurface.png: no isosurface control in the station sheet");
}

/* Back up the column before turning the current layer on. The depth cursor is
   still at the bottom from the shot above, and GLORYS has little to say at
   2000 m in this box, so the first run of this script drew zero arrows and
   captured an empty frame as though the layer were broken. It is not: the
   layer draws at the cursor's depth, which is the point of it. */
if (nRows) {
  await rows.nth(Math.min(6, nRows - 1)).click();
  await sleep(2500);
}

const cur = sheetToggle("Currents");
if (await cur.count()) {
  await cur.click();
  await page
    .waitForFunction(() => window.__sagarScene.arrowCount() > 0, undefined, { timeout: 60_000 })
    .catch(() => SKIPPED.push("07-currents.png: the current layer drew no arrows"));
  await sleep(2500);
  MEASURED.arrows = await page.evaluate(() => window.__sagarScene.arrowCount());
  await shot(
    "07-currents.png",
    `${MEASURED.arrows} depth-resolved current vectors at the cursor depth, from ` +
      `Copernicus GLORYS, drawn at the depth the cursor is on rather than at the ` +
      `surface. The sheet names the cells it refused.`,
  );
  await cur.click();
  await sleep(1200);
} else {
  SKIPPED.push("07-currents.png: no currents control in the station sheet");
}

// --- 8. a derived field nothing measures -----------------------------------
const sig0 = page.getByRole("button", { name: "SIG0", exact: true });
if (await sig0.count()) {
  await sig0.click();
  await sleep(6000);
  await shot(
    "08-density-sig0.png",
    "Potential density anomaly, computed by a plugin through TEOS-10 from the " +
      "stored temperature and salinity. Nothing in the ocean measures density; it " +
      "is derived, and the layer catalog says so on its own badge.",
  );
  const temp = page.getByRole("button", { name: "TEMP", exact: true });
  if (await temp.count()) await temp.click();
  await sleep(5000);
} else {
  SKIPPED.push("08-density-sig0.png: no SIG0 variable control");
}

// --- 9. the instruments -----------------------------------------------------
await openPanel("Marks");
await sleep(1500);
MEASURED.legend = (await page.locator(".legend").innerText().catch(() => "")).replace(/\s+/g, " ");
await shot(
  "09-instruments.png",
  "All four instrument classes the problem statement names, plus a moored buoy " +
    "read through the source-reader extension point. They are told apart by " +
    "silhouette, not by hue, because hue on this surface belongs to the " +
    "measurement.",
);
await shotOf(
  ".legend",
  "09b-legend.png",
  "The cast legend, counting casts rather than instruments. A float drifts and " +
    "reports repeatedly, so nine BGC marks are not nine BGC floats, and the panel " +
    "prints both numbers rather than the flattering one.",
);

// --- 10 to 12. one cast of each remaining class -----------------------------
for (const [kind, base, what] of [
  ["gdac_geo", "10-argo", "A core Argo float, temperature and salinity"],
  ["glider", "11-glider", "A glider dive off southern Sri Lanka"],
  ["ctd", "12-ctd", "A shipboard CTD cast"],
]) {
  const m = await openCast(kind, `${base}-*.png`);
  if (!m) continue;
  await shot(`${base}.png`, `${what}, opened from the globe.`);
  await shotOf(
    '[aria-label="Instrument profile"]',
    `${base}-panel.png`,
    kind === "gdac_geo"
      ? "The float's own profile against the model column, with the QC policy and " +
          "the data centre cited by name."
      : "An archive observation, and the panel says so where its numbers are read. " +
          "A dive from an earlier year sitting unremarked among contemporary marks " +
          "is a false statement the interface would be making silently.",
  );
  await clearCast();
}
await closePanel("Marks");
await closePanel("Station sheet");

// --- 13. the verification certificate ---------------------------------------
await openPanel("Verification");
const showErr = page.locator(".verdict__toggle");
if (await showErr.count()) {
  if ((await showErr.first().getAttribute("aria-expanded")) !== "true") {
    await showErr.first().click();
    await sleep(1200);
  }
}
MEASURED.scorecard = (await page
  .locator('[aria-label="Model verification"]')
  .innerText()
  .catch(() => ""))
  .split("\n")
  .slice(0, 12)
  .join(" ")
  .replace(/\s+/g, " ");
await shotOf(
  '[aria-label="Model verification"]',
  "13-scorecard.png",
  "The Class-4-style verification certificate, opened on its error-by-depth " +
    "table. Bias, RMSE and mean absolute error against the instruments, the worst " +
    "depth band named, the count of levels refused with a reason for each, and " +
    "the analysis-fit caveat printed in the reserved ink at the foot where a " +
    "reader cannot reach the figures without passing it.",
);

// --- 14. the hazard layer ---------------------------------------------------
await openPanel("Hazards");
await sleep(2000);
await shot(
  "14-hazardwatch.png",
  "CAP v1.2 warning areas drawn over the water they concern, parsed from India's " +
    "own NDMA SACHET feed.",
);
await shotOf(
  ".hazard",
  "14b-hazard-panel.png",
  "The HazardWatch panel. Every ocean bulletin here is a rehearsal, stamped " +
    "EXERCISE from its own CAP status field, with the notice explaining why: the " +
    "live feed carried no ocean bulletin when this was ingested.",
);
await closePanel("Hazards");

// --- 15. what the platform can draw -----------------------------------------
await openPanel("Layers");
await sleep(1200);
await shotOf(
  ".catalog",
  "15-layer-catalog.png",
  "The layer catalog, stating capability on the first frame rather than in a " +
    "slide. Stored fields and plugin-computed ones are badged differently, and " +
    "the footer names the plugin surface, which is the extensibility requirement " +
    "answered with a running count instead of a paragraph.",
);
await closePanel("Layers");

// --- 16. the agent ----------------------------------------------------------
await openPanel("Agent");
/* The ask panel is ABSENT, not broken, when the agent service is unreachable,
   and it decides that from a health check that only runs once it mounts. It
   mounts when this tab is opened, not at page load, so the check is in flight
   for a moment after the click and a bare count() here reported the agent
   plane down while it was running perfectly. */
const ask = page.locator(".ask__input");
await ask.waitFor({ timeout: 15_000 }).catch(() => {});
if (await ask.count()) {
  await ask.fill("How good is the model?");
  await page.getByRole("button", { name: "Ask", exact: true }).first().click();
  await page.locator(".ask__answer").waitFor({ timeout: 60_000 }).catch(() => {});
  await sleep(2500);
  await shotOf(
    ".ask",
    "16-agent.png",
    "Samudra Sahayak answering from tool results. It prints planner: rules " +
      "under every answer, because it is a rule-based router over real tools and " +
      "not a language model, and it physically cannot state a number no tool " +
      "produced. The citations are the tools it actually called.",
  );
  await ask.fill("What is the weather in Delhi?");
  await page.getByRole("button", { name: "Ask", exact: true }).first().click();
  await sleep(3500);
  await shotOf(
    ".ask",
    "16b-agent-refuses.png",
    "The same assistant refusing a question outside the water on screen. The " +
      "refusal is the feature: an assistant that answers everything is an " +
      "assistant that will invent a number in front of an oceanographer.",
  );
} else {
  SKIPPED.push("16-agent.png: the ask panel is absent, which means the agent plane is not running");
}
await closePanel("Agent");

// --- 17. the tours ----------------------------------------------------------
await openPanel("Tours");
await sleep(1200);
await shotOf(
  ".tour",
  "17-tours.png",
  "The guided tours. The submission video is a replay of one of these driving " +
    "the real scene, not a performance over a recording.",
);
await closePanel("Tours");

// --- 18. the dock itself ----------------------------------------------------
await shotOf(
  ".dock",
  "18-panel-dock.png",
  "The dock. Every overlay the opening frame suppresses is named here with its " +
    "state visible, because a clean first frame is only an improvement if what it " +
    "hides is obviously reachable.",
);

// --- the frame rate, moved rather than idle ---------------------------------
for (let i = 0; i < 12; i++) {
  await page.mouse.move(1100, 600);
  await page.mouse.down();
  await page.mouse.move(1100 + (i % 2 ? 90 : -90), 600 + (i % 2 ? 40 : -40), { steps: 12 });
  await page.mouse.up();
  await sleep(120);
}
MEASURED.fps = (await page.locator(".scalebar__render").innerText().catch(() => "")).replace(
  /\s+/g,
  " ",
);
MEASURED.renderer = await page.evaluate(() => {
  const gl = document.createElement("canvas").getContext("webgl2");
  const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
  return info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "unknown";
});

// ---------------------------------------------------------------------------

const files = Object.keys(CAPTIONS).sort();
const table = files.map((f) => `| \`${f}\` | ${CAPTIONS[f]} |`).join("\n");

writeFileSync(
  join(OUT, "README.md"),
  `# Prototype screenshots, ${today}

Captured from the running production build against the local cube with
\`OFFLINE=1\`. **Nothing here is staged.** Every number visible in these images
was computed by the services while the shot was taken, and the frame-rate
readout in the corner is the real one.

Re-take them with:

\`\`\`
./tasks.ps1 api
./tasks.ps1 agent
./tasks.ps1 demo
node tools/capture_evidence.mjs
\`\`\`

That script is checked in, drives the product through the same controls a judge
would click, and writes this file from what it read off the page. The previous
set was taken by a script that lived in a session scratchpad, so its own
instructions could not be followed by anyone else.

## Scene state at capture

| | |
|---|---|
| Viewport | ${VIEWPORT.width} by ${VIEWPORT.height} |
| Renderer | ${MEASURED.renderer} |
| Frame rate, scene moving | ${MEASURED.fps || "not measured"} |
| Volume cube | ${MEASURED.cube ?? "not captured"} |
| Marks under a panel on the opening frame | ${MEASURED.blockedOnOpen ?? "not measured"} |
| Isosurface | ${MEASURED.isosurface ? `${MEASURED.isosurface.triangles} triangles in ${MEASURED.isosurface.components} component${MEASURED.isosurface.components === 1 ? "" : "s"}` : "not captured"} |
| Current vectors | ${MEASURED.arrows ?? "not captured"} |
| Requests that left the machine | ${offOrigin.length ? offOrigin.join(", ") : "none"} |

Legend as read off the page: ${MEASURED.legend || "not read"}

Verification card as read off the page: ${MEASURED.scorecard || "not read"}

## The shots

| File | What it shows |
|---|---|
${table}

${
  SKIPPED.length
    ? `## Not captured, and why\n\n${SKIPPED.map((s) => `- ${s}`).join("\n")}\n`
    : "Every shot in the list was captured.\n"
}
## Two things worth saying out loud on the day

**The WiFi is off.** It takes three seconds to show and it converts
"deployable on INCOIS infrastructure" from a promise into a demonstration. A
browser test fails the build if any request leaves the machine, and this
capture run recorded ${offOrigin.length} off-origin requests.

**The assistant has no language model in it yet.** It is a rule-based router
over real tools and it prints \`planner: rules\` under every answer. Being found
out is worse than being modest, and the honest version still lands: it
physically cannot state a number no tool produced.
`,
  "utf8",
);

console.log(`\n${files.length} shots + README.md in ${OUT}`);
if (SKIPPED.length) console.log(`skipped:\n  ${SKIPPED.join("\n  ")}`);
if (offOrigin.length) console.log(`OFF-ORIGIN REQUESTS: ${offOrigin.join(", ")}`);

await browser.close();
