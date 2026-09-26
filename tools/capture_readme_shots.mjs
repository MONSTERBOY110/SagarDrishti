/** The screenshots in the README, taken from the running build.
 *
 * Checked in so the pictures on the repository's front page can be retaken
 * the moment the interface changes, rather than going stale in a folder.
 *
 * Run, with the stack up (docker compose up, or ./tasks.ps1 api, agent, demo):
 *   node tools/capture_readme_shots.mjs
 * then:
 *   python tools/capture_readme_shots.py   (PNG to JPEG, for page weight)
 */

import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const OUT = join(ROOT, "screenshots");
const WEB = process.env.SAGAR_WEB ?? "http://localhost:3000";
const URL = `${WEB}/?probe=1`;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  args: ["--use-gl=angle", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});

async function open(viewport = { width: 1920, height: 1080 }) {
  const page = await browser.newPage({ viewport });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 120_000 });
  await page.waitForFunction(() => window.__sagarScene?.sliceCount() > 0, undefined, {
    timeout: 120_000,
  });
  await page.waitForTimeout(7000);
  await page.mouse.move(-10, -10);
  return page;
}
const tab = async (page, name) => {
  const t = page.getByRole("button", { name, exact: true });
  if ((await t.getAttribute("aria-pressed")) !== "true") await t.click();
  await page.waitForTimeout(1200);
};
const column = async (page) => {
  await page.evaluate(() => window.__sagarColumnView?.());
  await page.waitForTimeout(5000);
};
const shot = async (page, name) => {
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`  ${name}.png`);
};

// 1. The opening frame: the whole globe, the Bay of Bengal box, the verdict.
{
  const page = await open();
  await shot(page, "01-opening");
  await page.close();
}

// 2. The water column from the side, with the station sheet and the marks.
{
  const page = await open();
  await column(page);
  await tab(page, "Station sheet");
  await tab(page, "Marks");
  await shot(page, "02-water-column");

  // 3. The 26 degC isosurface, the depth of cyclone fuel.
  // The toggle reads "Off" or "On"; it is found by the row it sits in.
  const iso = page.locator(".label:has(> span:text-is('Isosurface')) button").first();
  if (await iso.count()) {
    await iso.click();
    await page.waitForTimeout(6000);
    await shot(page, "03-isosurface");
  }
  await page.close();
}

// 4. HazardWatch: CAP warnings over the water, drills marked as drills.
{
  const page = await open();
  await column(page);
  await tab(page, "Hazards");
  const drills = page.getByLabel(/rehearsal bulletins/i);
  if (await drills.count()) {
    await drills.check();
    await page.waitForTimeout(4000);
  }
  await shot(page, "04-hazards");
  await page.close();
}

// 5. The water column studio on a BGC float: measured against the model.
{
  const page = await open();
  await column(page);
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
  if (mark) {
    await page.mouse.click(mark.x, mark.y);
    await page.locator('[aria-label="Instrument profile"]').waitFor({ timeout: 30_000 });
    await page.waitForTimeout(3000);
    await page.getByRole("button", { name: /Inspect the water column/i }).first().click();
    await page.locator("div.cube").waitFor({ timeout: 30_000 });
    await page.waitForTimeout(9000);
    // On the thermocline, so the readout shows measured, model and gap.
    const plot = await page.locator(".studio__plot").first().boundingBox();
    if (plot) {
      await page.mouse.move(plot.x + plot.width * 0.55, plot.y + plot.height * 0.12);
      await page.waitForTimeout(1500);
    }
    await shot(page, "05-studio");
  }
  await page.close();
}

// 6. Samudra Sahayak: an answer from tools, with its working and its source.
{
  const page = await open();
  await tab(page, "Agent");
  const ask = page.locator('[aria-label="Ask Samudra Sahayak"]');
  await ask.waitFor({ timeout: 30_000 });
  await ask.getByRole("button", { name: "How good is the model?" }).click();
  await ask.locator(".ask__text").waitFor({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  await ask.locator(".ask__tracetoggle").click();
  await page.waitForTimeout(1500);
  await shot(page, "06-agent");
  await page.close();
}

// 7. The same build at phone width.
{
  const page = await open({ width: 390, height: 844 });
  await tab(page, "Station sheet");
  await page.waitForTimeout(1500);
  await shot(page, "07-phone");
  await page.close();
}

await browser.close();
