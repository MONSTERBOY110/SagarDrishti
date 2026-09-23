/** Take the four screenshots the idea deck uses, from the running build.
 *
 * WHY THIS IS CHECKED IN. The deck claims its pictures are of the real system
 * and its numbers were measured rather than estimated. Until 23 September the
 * pictures came from a script in a session scratchpad, so the claim rested on
 * a file nobody else had, and the deck went a full day showing an interface
 * that had been replaced. `tools/capture_evidence.mjs` is the same argument
 * for the evidence folder; this is the deck's half of it.
 *
 * `.ppt-build/refresh_23sep.py` consumes these four by name and crops them to
 * their slots. Run this first, then that, then the PDF export.
 *
 * Run:
 *   ./tasks.ps1 api        (port 8000, OFFLINE=1)
 *   ./tasks.ps1 agent      (port 8010)
 *   ./tasks.ps1 demo       (port 3000, production build)
 *   node tools/capture_deck_assets.mjs
 */

import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const OUT = join(ROOT, ".ppt-build", "assets");
const WEB = process.env.SAGAR_WEB ?? "http://localhost:3000";
const URL = `${WEB}/?probe=1`;

mkdirSync(OUT, { recursive: true });

/** 3x, because the deck is read as a PDF and a reviewer zooms. */
const SCALE = 3;

const ready = async (page) => {
  await page.waitForFunction(() => window.__sagarScene?.sliceCount() > 0, undefined, {
    timeout: 120_000,
  });
  await page.waitForTimeout(7000);
};

const launch = () =>
  chromium.launch({ args: ["--use-gl=angle", "--enable-unsafe-swiftshader"] });

// --- 1 and 2: the scene, and the volume studio ------------------------------
{
  const browser = await launch();
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: SCALE,
  });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 120_000 });
  await ready(page);

  /* The pure-globe shot, CLIPPED TO THE WATER. The dock stays on screen in
     this mode on purpose (a screen with no way back is broken, not minimal),
     and it is cropped out here because the caption calls this one scene, not
     one screen. The numbers are the measured column: the field runs from
     about y 400 to y 930 at this camera, and the dock's top edge is y 927. */
  await page.getByRole("button", { name: /Water only/ }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: join(OUT, "ui-scene-strip.png"),
    clip: { x: 250, y: 395, width: 1450, height: 531 },
  });
  await page.getByRole("button", { name: /Show panels/ }).click();
  await page.waitForTimeout(900);

  // The studio, opened on a biogeochemical float, with the readout on a depth:
  // an evidence shot of this panel with no numbers in it is a picture of the
  // argument rather than the argument.
  const mark = await page.evaluate(() => {
    const s = window.__sagarScene;
    let seen = -1;
    for (const e of s.viewer.entities.values) {
      const p = e.properties;
      if (!p || !p.platformKind) continue;
      seen += 1;
      if (p.platformKind.getValue() !== "gdac_bgc") continue;
      const m = s.floatWindowPos(seen);
      if (m && m.x > 60 && m.y > 60 && m.x < 1860 && m.y < 1020) return m;
    }
    return null;
  });
  if (!mark) throw new Error("no BGC float is on screen at the home camera");
  await page.mouse.click(mark.x, mark.y);
  await page.locator('[aria-label="Instrument profile"]').waitFor({ timeout: 30_000 });
  await page.waitForTimeout(3000);
  await page.getByRole("button", { name: /Inspect the water column/i }).first().click();
  await page.locator("div.cube").waitFor({ timeout: 30_000 });
  await page.waitForTimeout(9000);
  const plot = await page.locator(".studio__plot").first().boundingBox();
  await page.mouse.move(plot.x + plot.width * 0.55, plot.y + plot.height * 0.12);
  await page.waitForTimeout(1500);
  await page.locator(".studio__sheet").screenshot({ path: join(OUT, "ui-studio-cube.png") });

  console.log("  ui-scene-strip.png, ui-studio-cube.png");
  await browser.close();
}

// --- 3: the verification certificate ----------------------------------------
{
  const browser = await launch();
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: SCALE,
  });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 120_000 });
  await ready(page);
  const toggle = page.locator(".verdict__toggle");
  if ((await toggle.count()) && (await toggle.first().getAttribute("aria-expanded")) !== "true") {
    await toggle.first().click();
    await page.waitForTimeout(1200);
  }
  await page
    .locator('[aria-label="Model verification"]')
    .screenshot({ path: join(OUT, "ui-verification.png") });
  console.log("  ui-verification.png");
  await browser.close();
}

// --- 4: the same build at phone width ---------------------------------------
{
  const browser = await launch();
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: SCALE,
  });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 120_000 });
  await ready(page);
  const tab = page.getByRole("button", { name: "Station sheet", exact: true });
  if ((await tab.getAttribute("aria-pressed")) !== "true") await tab.click();
  await page.waitForTimeout(2500);
  // The panel itself, not the viewport: a narrow window stacks the scene above
  // the sheet, and half a screenshot of empty water says nothing about whether
  // the controls survive the width.
  await page.locator(".panel-stack").screenshot({ path: join(OUT, "ui-phone-sheet.png") });
  console.log("  ui-phone-sheet.png");
  await browser.close();
}

console.log(`\n4 deck assets in ${OUT}`);
console.log("next: .ppt-build/refresh_23sep.py, then .ppt-build/export_pixelpaws_pdf.py");
