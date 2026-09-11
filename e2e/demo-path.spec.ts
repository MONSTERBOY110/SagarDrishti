import { rmSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type ConsoleMessage, type Page, type Request } from "@playwright/test";

/** The demo path, asserted end to end (TRD section 9).
 *
 * This walks the power-round script in PRD section 11 and checks the claims we
 * intend to make in front of MoES/INCOIS judges. Every assertion here exists
 * because failing it would embarrass us on stage, not because it was easy to
 * write. In particular:
 *
 *   - The scene must actually BUILD. A production-only bundler failure once
 *     left the globe as an empty black frame while the sheet, the profile and
 *     the provenance all worked perfectly, so "the page loaded" and "the page
 *     works" are different assertions and both are made here.
 *   - Nothing may leave the origin. PRD F11 promises an air-gapped demo, and a
 *     single font or basemap request would break that the moment the WiFi is
 *     off. This is enforced mechanically rather than by inspection.
 *   - No em dashes and no en dashes may reach the screen. That is a standing
 *     project instruction, and a linter cannot see rendered text.
 */

const PROBE = "/?probe=1";
/** The data plane this suite boots (playwright.config.ts). Named here because
 *  one test posts to it directly: SagarNode's whole claim is that a device
 *  nobody had heard of can post to /ingest and appear on the globe, and the
 *  cheapest honest device to be is an HTTP client. */
const API = "http://127.0.0.1:8100";

interface Watchers {
  consoleErrors: string[];
  failedRequests: string[];
  offOrigin: string[];
}

/** Attach the guards that must hold for the whole visit, not just at the end. */
function watch(page: Page): Watchers {
  const w: Watchers = { consoleErrors: [], failedRequests: [], offOrigin: [] };

  page.on("console", (m: ConsoleMessage) => {
    if (m.type() === "error") w.consoleErrors.push(m.text().slice(0, 200));
  });

  page.on("response", (r) => {
    if (r.status() >= 400) w.failedRequests.push(`${r.status()} ${r.url()}`);
  });

  page.on("request", (r: Request) => {
    const url = r.url();
    // data: and blob: are in-page, never network.
    if (url.startsWith("data:") || url.startsWith("blob:")) return;
    const host = (() => {
      try {
        return new URL(url).hostname;
      } catch {
        return "";
      }
    })();
    const local = host === "127.0.0.1" || host === "localhost" || host === "";
    if (!local) w.offOrigin.push(url.slice(0, 160));
  });

  return w;
}

/** Record which renderer Chromium actually got.
 *
 * Not decoration. The whole suite is five times slower on SwiftShader than on
 * a real GPU, and when it timed out the failure looked like a broken scene
 * rather than a slow one, which cost a diagnosis. Software rendering is the
 * NORMAL case here (headless Chromium usually falls back to it, and CI has no
 * GPU), so this annotation is what tells a reader of a slow report whether the
 * machine or the code is at fault.
 */
async function recordRenderer(page: Page) {
  const renderer = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl2") ||
      canvas.getContext("webgl")) as WebGLRenderingContext | null;
    if (!gl) return "no webgl";
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    return info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "unknown";
  });
  const software = /swiftshader|llvmpipe|software/i.test(renderer);
  test.info().annotations.push({
    type: software ? "renderer (SOFTWARE, expect a slow run)" : "renderer (hardware)",
    description: renderer,
  });
  return { renderer, software };
}

/** Wait until the 3D scene has genuinely built AND painted its slice stack.
 *
 * Both conditions matter and they complete in separate effects: one builds the
 * 24 entities, a later one applies the opacity transfer function and records
 * how many are actually blended. Waiting only on the first left drawnSlices
 * unset and produced a confusing null in an assertion about the frame budget. */
async function sceneReady(page: Page) {
  await page.waitForFunction(
    () => {
      const s = (
        window as unknown as {
          __sagarScene?: { sliceCount(): number; drawnSlices?: number };
        }
      ).__sagarScene;
      return !!s && s.sliceCount() > 0 && typeof s.drawnSlices === "number" && s.drawnSlices > 0;
    },
    undefined,
    { timeout: 90_000 },
  );
}

test.describe("SagarDrishti demo path", () => {
  test("the water column renders, an instrument opens, and nothing leaves the machine", async ({
    page,
  }) => {
    const w = watch(page);

    // --- 0. the scene loads at all -------------------------------------------
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await recordRenderer(page);
    await sceneReady(page);

    const scene = await page.evaluate(() => {
      const s = (
        window as unknown as {
          __sagarScene?: { sliceCount(): number; floatCount(): number; drawnSlices?: number };
        }
      ).__sagarScene!;
      return { slices: s.sliceCount(), floats: s.floatCount(), drawn: s.drawnSlices ?? null };
    });

    // 24 depth levels from the real INCOIS analysis, not a placeholder.
    expect(scene.slices, "the depth-slice stack must be built").toBeGreaterThanOrEqual(20);
    // Frame budget: only a subset is blended at once (TRD section 5).
    expect(scene.drawn, "too many slices blended at once would cost the frame budget").toBeLessThanOrEqual(12);
    expect(scene.floats, "real Argo stations must be on the globe").toBeGreaterThan(0);

    // --- 1. the sheet prints the whole water column --------------------------
    const rows = page.locator('[role="option"]');
    await expect(rows).toHaveCount(scene.slices);
    // Surface warmer than the deep: a sanity check on the data itself, not just
    // on the DOM. A pipeline that inverted the depth axis would pass a count
    // assertion and fail this one.
    const first = Number((await rows.first().innerText()).match(/([\d.]+)\s*$/)?.[1]);
    const last = Number((await rows.last().innerText()).match(/([\d.]+)\s*$/)?.[1]);
    expect(first, "the surface must be warmer than 2000 m").toBeGreaterThan(last + 10);

    // --- 2. provenance is on screen (CLAUDE.md: no number without it) --------
    const cartouche = page.locator(".cartouche");
    await expect(cartouche).toContainText("INCOIS");
    await expect(cartouche).toContainText("incois_argo_10d_VAM");
    await expect(cartouche).toContainText(/\d{4}-\d{2}-\d{2}T/); // an actual timestamp

    // --- 3. the depth cursor drives sheet, scene and readout together --------
    const scaleBar = page.locator(".scalebar");
    await expect(scaleBar).toContainText("cursor");
    const before = await scaleBar.innerText();
    await rows.nth(12).click();
    await expect(scaleBar).not.toHaveText(before, { timeout: 15_000 });
    await expect(rows.nth(12)).toHaveAttribute("aria-selected", "true");

    // keyboard operable, because a forecast desk is not a mouse-only place
    await rows.nth(12).press("ArrowDown");
    await expect(rows.nth(13)).toHaveAttribute("aria-selected", "true");

    // --- 4. clicking a station mark opens its real profile -------------------
    const mark = await page.evaluate(() => {
      const s = (
        window as unknown as {
          __sagarScene?: {
            floatCount(): number;
            floatWindowPos(i: number): { x: number; y: number; wmo: string } | null;
          };
        }
      ).__sagarScene!;
      for (let i = 0; i < s.floatCount(); i++) {
        const m = s.floatWindowPos(i);
        if (m && m.x > 4 && m.y > 4) return m;
      }
      return null;
    });
    expect(mark, "at least one station mark must be on screen to click").not.toBeNull();

    await page.mouse.click(mark!.x, mark!.y);
    const panel = page.locator('[aria-label="Instrument profile"]');
    // The WMO id is the citation the agent plane will later be required to speak.
    await expect(panel.locator("h2")).toContainText(mark!.wmo, { timeout: 30_000 });
    await expect(panel).toContainText("Wong et al. 2020"); // the QC policy, cited
    await expect(panel).toContainText("Argo GDAC");
    // We must NOT claim a skill figure from a nearest-cell comparison, and now
    // that a real verification certificate exists this panel has to point at
    // it rather than only disclaim itself: a reader who sees "no skill figure
    // is claimed" beside a dashed model curve, with a certificate printing an
    // RMSE directly above, must be told the two are different comparisons.
    await expect(panel).toContainText(/nearest grid cell/i);
    await expect(panel).toContainText(/no skill figure is claimed/i);
    await expect(panel).toContainText(/verification certificate above/i);

    // --- 5. the colorbar is editable (PS requirement F4) ---------------------
    await page.getByRole("button", { name: "Edit" }).click();
    const inks = page.locator(".cbar__ink");
    await expect(inks).not.toHaveCount(0);
    await page.getByTitle("For salinity").click();
    await expect(page.locator('.cbar__ink[aria-pressed="true"] .cbar__inkname')).toHaveText(
      /haline/i,
    );

    // A hand-set limit must survive a timestep change, or the colours shift
    // under a value the reader has already interpreted.
    const min = page.locator(".cbar__input").first();
    await min.fill("12");
    await min.press("Enter");
    await expect(page.locator(".ramp__ends")).toContainText("held");
    const ticks = page.getByRole("radio");
    if ((await ticks.count()) > 1) {
      await ticks.first().click();
      await page.waitForTimeout(2500);
      await expect(page.locator(".ramp__ends")).toContainText("held");
      await expect(min).toHaveValue("12");
    }

    // A log scale cannot take a non-positive minimum, and must SAY it moved.
    await min.fill("-5");
    await min.press("Enter");
    await page.getByRole("button", { name: "log", exact: true }).click();
    await expect(page.locator(".cbar__errata")).toContainText(/positive minimum/i);
    await page.getByRole("button", { name: "Auto" }).click();

    // --- 6. the frame readout works, but is NOT graded here ------------------
    /* Deliberately no threshold assertion. Under Playwright the browser is
       instrumented (trace capture screenshots every action) and this same
       scene, which measures 51 FPS median with a 37 ms worst frame
       uninstrumented on the Intel UHD target, reads under 10 FPS here.
       Asserting the TRD section 5 floor inside an instrumented run would
       either fail a healthy build or, worse, be quietly lowered until it
       passed and then certify nothing.
       The graded measurement is taken uninstrumented and recorded, with its
       method and the four optimisations behind it, in docs/adr/0001 and
       docs/P0-STATUS.md under F1.
       What IS worth asserting is that the readout exists and reports real
       numbers, because a silent or absent readout is how a performance
       regression hides. */
    // ORBIT, not just a mouse move. The probe samples only while the camera
    // is actually moving, because Cesium's loop is driven by
    // requestAnimationFrame and a browser throttles that on a window it thinks
    // is inactive: a still scene was reporting the browser's refresh decision
    // as though it were our frame cost, three times slower than the truth.
    // Moving the pointer over the page does not move the camera, so it would
    // now leave the readout saying "move the scene to measure".
    await page.evaluate(async () => {
      const cam = (window as unknown as { __sagarScene?: any }).__sagarScene.viewer.camera;
      const spin = setInterval(() => cam.rotateRight(0.004), 16);
      await new Promise((r) => setTimeout(r, 6000));
      clearInterval(spin);
    });
    const render = await page.locator(".scalebar__render").innerText();
    const median = Number(render.match(/render\s+(\d+)/)?.[1] ?? NaN);
    const p1 = Number(render.match(/p1\s+(\d+)/)?.[1] ?? NaN);
    expect(median, `frame readout absent or unparseable: "${render}"`).toBeGreaterThan(0);
    expect(p1, `p1 readout absent or unparseable: "${render}"`).toBeGreaterThan(0);
    // The rule form must be one of the three the design system defines, so a
    // future refactor cannot leave the state unstyled and unreadable.
    const ruleState = await page.locator(".scalebar__render").getAttribute("data-state");
    expect(["floor", "ok", "target"]).toContain(ruleState);
    // Recorded for CI trend, not gated on. The description spells out that the
    // figure is instrumented, because a bare "render 7 fps" in a report reads
    // as the product's frame rate to anyone who did not write this test.
    test.info().annotations.push({
      type: "frame-rate (instrumented, NOT the product figure)",
      description:
        `${render} under Playwright trace capture. The uninstrumented ` +
        "measurement is in docs/P0-STATUS.md under F1; expect roughly 5x this.",
    });

    // --- 7. the guards that had to hold throughout ---------------------------
    expect(w.offOrigin, "PRD F11: the demo must make no off-origin request").toEqual([]);
    expect(w.failedRequests, "no request may fail").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);

    // --- 6b. keyboard and assistive-technology floor (TRD section 7) --------
    /* Both of these were real defects found by walking the tab order, and both
       are the kind that no screenshot shows. */
    const a11y = await page.evaluate(() => {
      const sel =
        'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';
      const focusable = [...document.querySelectorAll(sel)];
      const rows = [...document.querySelectorAll('[role="option"]')];
      return {
        // A listbox with focusable options must be ONE tab stop, not one per
        // row. It was 25 before the roving tabindex.
        tabbableRows: rows.filter((r) => r.getAttribute("tabindex") === "0").length,
        rackIsTabStop: document.querySelector(".rack")?.hasAttribute("tabindex") ?? false,
        activeDescendant: document.querySelector(".rack")?.getAttribute("aria-activedescendant"),
        rowHasName: !!rows[0]?.getAttribute("aria-label"),
        // The canvas is opaque to assistive technology, so the scene owes a
        // labelled region and a spoken equivalent.
        sceneRegion: document.querySelector('[role="region"][aria-label="Ocean scene"]') !== null,
        summary: document.querySelector('.sr-only[role="status"]')?.textContent ?? null,
        focusableTotal: focusable.length,
      };
    });
    expect(a11y.tabbableRows, "exactly one rack row may be tabbable").toBe(1);
    expect(a11y.rackIsTabStop, "the listbox itself must not add a tab stop").toBe(false);
    expect(a11y.activeDescendant, "the listbox must point at its active option").toBeTruthy();
    expect(a11y.rowHasName, "every level needs an accessible name").toBe(true);
    expect(a11y.sceneRegion, "the 3D scene needs a labelled region").toBe(true);
    expect(a11y.summary, "the scene needs a spoken equivalent").toContain("depth cursor");
    expect(a11y.summary).toContain("Argo");

    const rendered = await page.evaluate(() => document.body.innerText);
    // Built from code points rather than written literally. This guard is the
    // one place an em or en dash would otherwise have to appear in the source,
    // and a repository-wide search should be able to report zero of them
    // without anyone having to remember an exception for this line.
    const EN_DASH = 0x2013;
    const EM_DASH = 0x2014;
    const banned = new RegExp(`[${String.fromCharCode(EN_DASH, EM_DASH)}]`, "g");
    const dashes = rendered.match(banned) ?? [];
    expect(dashes, "no em dash or en dash may reach the screen").toEqual([]);
  });

  test("a BGC float is a different instrument, and says so", async ({ page }) => {
    /* PRD F2 asks for Argo floats, gliders, CTD and BGC as distinguishable
       marks. This asserts the half of that claim we can currently make with
       real data: three BGC floats in the Bay of Bengal box, carrying oxygen,
       chlorophyll, nitrate and pH from the Argo synthetic profile files.

       It is here rather than in a unit test because the failure modes are all
       at the seams: a BGC float cited to the core daily files (which contain no
       chlorophyll at all), a parameter offered that the profile does not
       actually serve, or a model curve implied for a quantity the INCOIS
       analysis does not carry. */
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    // The legend names only the classes present, so its rows ARE the claim.
    // Three instrument classes are live: core Argo floats, BGC floats, and a
    // RAMA moored buoy read through the plugin source-reader extension point.
    const legend = page.locator(".legend");
    await expect(legend).toContainText("Argo float");
    await expect(legend).toContainText("BGC float");
    await expect(legend).toContainText("Mooring");

    // Each class is told apart by SILHOUETTE, not colour, so the legend swatch
    // count must match the number of classes actually drawn.
    const classes = await page.evaluate(() => {
      const s = (
        window as unknown as { __sagarScene?: { viewer: { entities: { values: any[] } } } }
      ).__sagarScene!;
      const seen: Record<string, number> = {};
      for (const e of s.viewer.entities.values) {
        const props = e.properties;
        if (!props || !props.platformKind) continue;
        const kind = props.platformKind.getValue();
        seen[kind] = (seen[kind] ?? 0) + 1;
      }
      return seen;
    });
    expect(Object.keys(classes).sort()).toEqual(["gdac_bgc", "gdac_geo", "mooring"]);
    expect(classes.mooring).toBeGreaterThan(0);

    /* A MARK IS A CAST, NOT AN INSTRUMENT, and the page must not confuse the
       two. A float drifts and reports repeatedly, so the nine BGC marks in
       this box were made by three BGC floats and the three mooring marks by
       one buoy. Saying "nine BGC floats" would be a claim about the Indian
       Ocean observing system that is off by a factor of three, made to the
       people who run it. The legend and the spoken summary both said it until
       2026-09-10, which is why this is asserted rather than trusted. */
    const reconciled = await page.evaluate(() => ({
      legend: document.querySelector(".legend")?.textContent ?? "",
      spoken: document.querySelector('.sr-only[role="status"]')?.textContent ?? "",
    }));
    expect(reconciled.legend, "the legend counts casts, and says so").toMatch(/Casts/);
    expect(reconciled.legend, "and reconciles them to the instruments").toMatch(
      /from\s*\d+\s*instruments/,
    );
    expect(reconciled.spoken, "the spoken summary counts casts").toMatch(/instrument casts/);
    expect(
      reconciled.spoken,
      "and names the number of INSTRUMENTS per class, not the number of marks",
    ).toMatch(/\d+ biogeochemical Argo floats, \d+ casts between them/);

    // Find a BGC mark by the platform kind the entity carries, not by position.
    const mark = await page.evaluate(() => {
      const s = (
        window as unknown as {
          __sagarScene?: {
            viewer: { entities: { values: any[] } };
            floatCount(): number;
            floatWindowPos(i: number): { x: number; y: number; wmo: string } | null;
          };
        }
      ).__sagarScene!;
      let seen = -1;
      for (const e of s.viewer.entities.values) {
        const props = e.properties;
        if (!props || !props.platformKind) continue;
        seen += 1;
        if (props.platformKind.getValue() !== "gdac_bgc") continue;
        const m = s.floatWindowPos(seen);
        if (m && m.x > 4 && m.y > 4) return m;
      }
      return null;
    });
    expect(mark, "a BGC float must be on screen").not.toBeNull();

    await page.mouse.click(mark!.x, mark!.y);
    const panel = page.locator('[aria-label="Instrument profile"]');

    // Named as what it is. "Argo float" here would be true but incomplete, and
    // the point of the mark shape is that the two are told apart.
    await expect(panel.locator("h2")).toContainText("BGC float", { timeout: 30_000 });
    await expect(panel.locator("h2")).toContainText(mark!.wmo);

    // Cited to the Sprof files, NOT to the core daily files.
    await expect(panel).toContainText("BGC synthetic profiles");

    // The biogeochemistry is actually offered, with its own units. Chlorophyll
    // reaching the screen at all is the proof that the ADJUSTED product is
    // being read: every raw CHLA level on these floats is QC flag 3, so a
    // reader that took the raw values would show nothing here.
    const chla = panel.getByRole("button", { name: "Chlorophyll-a" });
    await expect(chla).toBeVisible();
    // The unit is asserted on the button's title, NOT on the panel text: the
    // axis label is painted into the ECharts canvas, so toContainText cannot
    // see it and an assertion against the panel text fails on a correct app.
    // The title is the DOM-visible statement of the same fact, and the unit
    // itself comes from the source file by way of check_units.
    await expect(chla).toHaveAttribute("title", /mg\/m3/);
    await chla.click();
    await expect(chla).toHaveAttribute("aria-pressed", "true");

    // The chart must actually hold points, not just an axis: chlorophyll
    // reaching the canvas is the end-to-end proof that the adjusted product
    // was read, since every raw CHLA level on these floats is QC flag 3.
    const drawn = await panel.locator("canvas").first().evaluate((el) => {
      const canvas = el as HTMLCanvasElement;
      const ctx = canvas.getContext("2d")!;
      const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
      let inked = 0;
      for (let i = 3; i < data.length; i += 4) if (data[i] > 0) inked += 1;
      return inked;
    });
    expect(drawn, "the chlorophyll chart must have something drawn in it").toBeGreaterThan(500);

    // No model comparison may be implied for a quantity the analysis lacks.
    await expect(panel).toContainText(/carries no chlorophyll/i);

    // And switching back to temperature restores it, because that one exists.
    await panel.getByRole("button", { name: "Temperature", exact: true }).click();
    await expect(panel).toContainText("nearest cell");

    expect(w.offOrigin, "PRD F11: still nothing off-origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("the isosurface draws, discloses what it refused, and leaks nothing", async ({
    page,
  }) => {
    /* PS requirement F1 names isosurface extraction alongside depth slices and
       time-step animation. The maths is tested in Python; what is asserted here
       is what only a browser can show:

         - the primitive is actually added to the scene, not merely fetched;
         - turning the layer off REMOVES it, and toggling repeatedly does not
           accumulate primitives. A leak here is not a failing test anywhere
           else: it presents as a slow frame-rate decay over a long demo, and
           the existing teardown removes entities only, which is a different
           collection;
         - the surface says on screen what it refused to draw. */
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const probe = () =>
      page.evaluate(() => {
        const s = (
          window as unknown as {
            __sagarScene?: {
              primitiveCount(): number;
              isosurfaceTriangles(): number;
              isosurfaceComponents(): number;
              isosurfaceDepthRange(): [number, number] | null;
              drawnSlices?: number;
            };
          }
        ).__sagarScene!;
        return {
          primitives: s.primitiveCount(),
          triangles: s.isosurfaceTriangles(),
          components: s.isosurfaceComponents(),
          depthRange: s.isosurfaceDepthRange(),
          drawnSlices: s.drawnSlices ?? null,
        };
      });

    const before = await probe();
    expect(before.triangles, "the layer must start off").toBe(0);

    // Scoped to its own block. The sheet grew a second On/Off control when
    // the current-vector layer landed, and a bare name match then resolved to
    // two buttons and failed as a strict-mode violation.
    const toggle = page
      .locator('[aria-label="Station sheet"] .block')
      .filter({ hasText: "Isosurface" })
      .getByRole("button", { name: /^(On|Off)$/ });
    await toggle.click();
    await page.waitForFunction(
      () =>
        (window as unknown as { __sagarScene?: { isosurfaceTriangles(): number } })
          .__sagarScene!.isosurfaceTriangles() > 0,
      undefined,
      { timeout: 45_000 },
    );

    const on = await probe();
    expect(on.triangles, "a real surface has hundreds of triangles").toBeGreaterThan(100);
    expect(on.primitives, "the primitive and its boundary rim must be added").toBeGreaterThan(
      before.primitives,
    );
    // The 26 degC isotherm in the Bay of Bengal lives in the upper hundred-odd
    // metres. A surface at 5 m or 2000 m would mean the depth axis is wrong in
    // a way no count would reveal.
    const [shallow, deep] = on.depthRange!;
    expect(shallow).toBeGreaterThan(20);
    expect(deep).toBeLessThan(250);
    expect(deep).toBeGreaterThan(shallow);

    // The stack yields budget to the surface, which is a measured trade rather
    // than a free addition: ten translucent quads plus the surface fell under
    // the TRD floor, six plus the surface is comfortably over it.
    expect(on.drawnSlices).toBeLessThan(before.drawnSlices!);

    // What it refused is on screen, not only in the payload.
    const sheet = page.locator('[aria-label="Station sheet"]');
    await expect(sheet).toContainText(/26 degC surface/i);
    await expect(sheet).toContainText(/no measurement/i);

    // Off again: the primitive must go, not just stop being updated.
    await toggle.click();
    await page.waitForFunction(
      () =>
        (window as unknown as { __sagarScene?: { isosurfaceTriangles(): number } })
          .__sagarScene!.isosurfaceTriangles() === 0,
      undefined,
      { timeout: 20_000 },
    );
    const off = await probe();
    expect(off.primitives, "turning the layer off must remove its primitives").toBe(
      before.primitives,
    );

    // And three more round trips must not accumulate anything. This is the
    // actual leak test: one toggle can pass while a rebuild path still leaks.
    for (let i = 0; i < 3; i++) {
      await toggle.click();
      await page.waitForFunction(
        () =>
          (window as unknown as { __sagarScene?: { isosurfaceTriangles(): number } })
            .__sagarScene!.isosurfaceTriangles() > 0,
        undefined,
        { timeout: 45_000 },
      );
      await toggle.click();
      await page.waitForFunction(
        () =>
          (window as unknown as { __sagarScene?: { isosurfaceTriangles(): number } })
            .__sagarScene!.isosurfaceTriangles() === 0,
        undefined,
        { timeout: 20_000 },
      );
    }
    const settled = await probe();
    expect(settled.primitives, "primitives accumulated across toggles").toBe(
      before.primitives,
    );

    expect(w.offOrigin, "PRD F11: the mesh must come from our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("the model is scored against the instruments, with its caveat attached", async ({
    page,
  }) => {
    // PS requirement F9. This is the one surface that makes a CLAIM ABOUT THE
    // MODEL rather than drawing it, so what is asserted here is not that a
    // number appears but that it cannot appear WITHOUT the two things that make
    // it defensible: the refusals it excluded, and the sentence saying it is an
    // analysis fit and not forecast skill.
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const card = page.locator('section[aria-label="Model verification"]');
    await expect(card).toBeVisible();

    // Collapsed, the certificate still carries the headline claim beside the
    // field. That IS the feature: PRIOR-ART section B.12 records that no
    // operational viewer shows skill next to what it is drawing.
    await expect(card).toContainText("Bias");
    await expect(card).toContainText("RMSE");
    // Bias AND RMSE, never one alone: a model 2 degrees warm in half the ocean
    // and 2 cold in the other half has a bias of zero.
    const figures = card.locator(".verdict__figvalue");
    await expect(figures).toHaveCount(3);

    // The caveat is visible BEFORE anything is expanded. If this ever fails,
    // the tool is publishing a skill claim it cannot defend.
    await expect(card.locator(".verdict__caveat")).toContainText("NOT forecast skill");
    await expect(card.locator(".verdict__caveat")).toContainText("assimilates");

    // --- the breakdown -------------------------------------------------------
    await card.locator("button.verdict__toggle").click();

    const bands = card.locator(".scoretable__row");
    await expect(bands).toHaveCount(7);

    // The refusals are served next to the pairs, so "11,718 pairs" can never be
    // read without "and this many levels could not be paired".
    await expect(card).toContainText("Levels not paired");

    // At most one band is ever marked as the worst. Deliberately NOT asserting
    // WHICH band: this suite runs against the synthetic fixture cube on CI and
    // against the downloaded one locally, and a claim about the real Bay of
    // Bengal must not rest on whichever cube happened to be on disk. That
    // claim is made where it belongs, against real data, in
    // services/api/tests/test_scorecard.py:
    // test_the_real_cube_scores_worst_in_the_thermocline, which skips when the
    // real cube is absent rather than quietly passing on a fixture.
    const marked = card.locator('.scoretable__row[data-worst="true"]');
    expect(await marked.count(), "never more than one worst band").toBeLessThanOrEqual(1);

    // Every printed RMSE is a real number, which is the contract this surface
    // owes regardless of which cube is behind it.
    const rmse = await card.locator(".scoretable__row").evaluateAll((rows) =>
      rows.map((r) => r.lastElementChild?.textContent?.trim() ?? ""),
    );
    expect(rmse).toHaveLength(7);
    for (const v of rmse) expect(v === "n/a" || Number.isFinite(Number(v))).toBe(true);

    // Attribution: the number belongs to instrument programmes, not to "data".
    await expect(card).toContainText("Scored against");
    await expect(card.locator(".verdict__sources li")).not.toHaveCount(0);

    expect(w.offOrigin, "PRD F11: the certificate must come from our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("a hazard is drawn over the water, and a drill can never pass for one", async ({
    page,
  }) => {
    // PS requirement F13. The problem statement's portal theme IS Disaster
    // Management, so this is the half of the brief the field layers do not
    // answer, and it is also the one layer where a bug is a FALSE ALARM rather
    // than a wrong number. Almost everything below asserts a negative.
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const panel = page.locator('[aria-label="HazardWatch warnings"]');
    await expect(panel).toBeVisible();

    // --- 1. the ocean hazards the PS names, drawn on the globe --------------
    await expect(panel.locator(".hazard__row")).not.toHaveCount(0);
    await expect(panel).toContainText("Tsunami");
    await expect(panel).toContainText("High Wave");

    const drawn = await page.evaluate(() => {
      const s = (window as unknown as { __sagarScene?: any }).__sagarScene;
      return { count: s.hazardCount(), severities: s.hazardSeverities() };
    });
    // A polygon and a circle for the tsunami, a polygon for the high wave.
    expect(drawn.count, "warning geometry must reach the globe").toBeGreaterThanOrEqual(2);
    expect(drawn.severities, "CAP severity travels to the entity").toContain("Extreme");

    // --- 2. a drill is stamped as one, everywhere ---------------------------
    // Four independent guards exist for this and the test checks the two a
    // user can see. If a rehearsal bulletin can reach the globe unmarked, this
    // tool is capable of announcing a tsunami that is not happening.
    await expect(panel.locator(".hazard__drill")).toHaveText(/exercise/i);
    await expect(panel.locator(".hazard__tag").first()).toHaveText(/exercise/i);

    // --- 3. and it disappears the moment rehearsals are switched off --------
    await panel.locator(".hazard__toggle input").uncheck();
    await expect(panel.locator(".hazard__drill")).toHaveCount(0);
    await expect(panel).toContainText(/no warning is valid/i);
    // The ledger, not a bare empty state: the count of what did not apply and
    // why is part of the answer here as it is on the scorecard.
    await expect(panel).toContainText(/drills/i);

    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.hazardCount() === 0,
      undefined,
      { timeout: 20_000 },
    );

    await panel.locator(".hazard__toggle input").check();
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.hazardCount() > 0,
      undefined,
      { timeout: 20_000 },
    );

    // --- 4. a warning opens into its own bulletin ---------------------------
    await panel.locator(".hazard__row").first().click();
    const detail = panel.locator(".hazard__detail");
    await expect(detail).toBeVisible();
    // Real CAP is multilingual, and the tsunami bulletin carries three
    // languages. That is the same fact the voice layer will rest on.
    await expect(detail).toContainText("hi-IN");
    await expect(detail).toContainText("ta-IN");
    await expect(detail).toContainText(/EXERCISE/);

    // --- 5. the layer shares the field's time axis --------------------------
    // Scrubbing to the first analysis step must change what is warned about.
    // A hazard layer pinned to the wall clock while the field showed July
    // would be two different days on one screen.
    // The ticks are radios, not buttons: the time rule is a radiogroup.
    await page.getByRole("radio", { name: "07-10" }).click();
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.hazardCount() === 0,
      undefined,
      { timeout: 30_000 },
    );
    await expect(panel).toContainText(/no warning is valid/i);

    expect(w.offOrigin, "PRD F11: warnings must come from our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("a guided tour drives the real scene and shows its evidence", async ({ page }) => {
    // PS requirement F12. Two things are being checked and the second is the
    // one that matters.
    //
    // That a tour drives the SAME scene the controls drive, so it can do
    // nothing a presenter could not do by hand, and a step that no-ops is
    // caught here rather than on stage where it looks exactly like a step that
    // worked.
    //
    // And that the narration carries its evidence. Narration is the one place
    // in this product where a number can reach a judge without passing through
    // a tool result, so the on-screen fact behind each sentence is rendered
    // beside it rather than trusted.
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    await page.locator(".tour__open").click();
    const picks = page.locator(".tour__pick");
    await expect(picks).not.toHaveCount(0);

    // The tour that opens an instrument, because it is the one whose patch has
    // to reach furthest into the application.
    await picks.filter({ hasText: "The instruments" }).click();

    const stage = page.locator('[aria-label="Guided tour"]');
    await expect(stage).toBeVisible();
    await expect(stage.locator(".tour__narration")).not.toBeEmpty();
    // One progress segment per step, so a presenter can see what is left.
    const segments = await stage.locator(".tour__ticks span").count();
    expect(segments).toBeGreaterThanOrEqual(5);

    // --- the tour really moves the scene ------------------------------------
    // Step forward until the step that selects a float, then check the
    // instrument panel actually opened on it. Paused first: an autoplaying
    // tour and a test stepping through it would race.
    await stage.getByRole("button", { name: "Pause" }).click();
    const profile = page.locator('[aria-label="Instrument profile"]');
    for (let i = 0; i < 6; i++) {
      const header = await profile.locator("h2").innerText();
      if (/2903831/.test(header)) break;
      await stage.getByRole("button", { name: "Next" }).click();
    }
    await expect(profile.locator("h2")).toContainText("2903831", { timeout: 30_000 });
    // Cited to the BGC files, which is the tour patching a real selection
    // rather than the panel happening to be open.
    await expect(profile).toContainText("BGC synthetic profiles");

    // --- and shows what the sentence rests on -------------------------------
    await expect(stage.locator(".tour__evidence li").first()).not.toBeEmpty();

    // --- a presenter can drive it from the keyboard -------------------------
    const before = await stage.locator(".tour__step").innerText();
    await page.keyboard.press("ArrowRight");
    await expect(stage.locator(".tour__step")).not.toHaveText(before);
    await page.keyboard.press("ArrowLeft");
    await expect(stage.locator(".tour__step")).toHaveText(before);

    // --- and get out of it --------------------------------------------------
    await page.keyboard.press("Escape");
    await expect(stage).toHaveCount(0);
    await expect(page.locator(".tour__open")).toBeVisible();

    // No tour file failed to load. A tour nobody can run is worse than no tour.
    await expect(page.locator(".tour__problem")).toHaveCount(0);

    expect(w.offOrigin, "PRD F11: tours must come from our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("the agent answers from tools, shows its working, and refuses the rest", async ({
    page,
  }) => {
    // PS requirement F8, TRD M4. The one surface in this product where a
    // sentence is COMPOSED rather than measured, so it is the one that owes
    // the most evidence, and this test is mostly about the evidence.
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const ask = page.locator('[aria-label="Ask Samudra Sahayak"]');
    await expect(ask).toBeVisible({ timeout: 30_000 });

    // --- an answer built from a tool ----------------------------------------
    await ask.getByRole("button", { name: "How good is the model?" }).click();
    const text = ask.locator(".ask__text");
    await expect(text).toContainText("RMSE", { timeout: 30_000 });
    // The figure the certificate shows, reached through the agent.
    await expect(text).toContainText("0.602");
    // And the caveat, which must travel with it wherever it is quoted.
    await expect(text).toContainText(/NOT forecast skill/i);

    // --- it says what produced it -------------------------------------------
    // "rules", because there is no language model in the loop. An audience
    // that assumes otherwise has been misled, and being found out is worse
    // than being modest.
    await expect(ask.locator(".ask__planner")).toContainText("rules");

    // --- and shows its working ----------------------------------------------
    await ask.locator(".ask__tracetoggle").click();
    const trace = ask.locator(".ask__trace > li");
    await expect(trace).not.toHaveCount(0);
    await expect(trace.first().locator(".ask__tool")).toContainText("compare_model_obs");
    // Every answer that quotes data cites it.
    await expect(ask.locator(".ask__cites li").first()).toContainText("INCOIS");

    // --- it moves the scene, through the same store a click goes through -----
    const depthBefore = await page.locator(".scalebar").innerText();
    await ask.locator(".ask__input").fill("how warm is it at 500 m?");
    await ask.getByRole("button", { name: "Ask" }).click();
    await expect(text).toContainText("500 m", { timeout: 30_000 });
    await expect(page.locator(".scalebar")).not.toHaveText(depthBefore);

    // --- and refuses what it cannot answer -----------------------------------
    // TRD M4 names this as something judges test. An ocean viewer asked about
    // the cricket should say it cannot, not produce a sentence shaped like an
    // answer.
    await ask.locator(".ask__input").fill("who won the cricket");
    await ask.getByRole("button", { name: "Ask" }).click();
    await expect(text).toContainText(/cannot answer that/i, { timeout: 30_000 });
    await expect(text).toHaveAttribute("data-refused", "true");
    // A refusal that lists what it CAN do is useful; one that just says no is
    // a dead end.
    await expect(text).toContainText(/I can tell you/i);

    // Nothing about a forecast, either, because nothing here forecasts.
    await ask.locator(".ask__input").fill("what will the temperature be next Tuesday");
    await ask.getByRole("button", { name: "Ask" }).click();
    await expect(text).toContainText(/nothing here forecasts/i, { timeout: 30_000 });

    expect(w.offOrigin, "PRD F11: the agent must be on our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);
  });

  test("currents draw at depth, from a second dataset that says so", async ({ page }) => {
    // The last clause of PS requirement F1 to get code behind it. INCOIS's
    // free ERDDAP publishes SURFACE currents only, so these are Copernicus
    // GLORYS, live since the team lead's account arrived on 2026-09-09.
    //
    // Two things are being defended. That the arrows are REAL and reduced
    // honestly, and that a viewer is never left thinking one dataset supplied
    // both the colours and the arrows when two did.
    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const sheet = page.locator('[aria-label="Station sheet"]');
    const block = sheet.locator(".block").filter({ hasText: "Currents" });

    // Off by default: a second agency's data should not appear unasked, and
    // it is a second request the opening scene does not need.
    await expect(block.getByRole("button")).toHaveText("Off");
    const before = await page.evaluate(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount(),
    );
    expect(before).toBe(0);

    // --- on ------------------------------------------------------------------
    await block.getByRole("button").click();
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount() > 0,
      undefined,
      { timeout: 40_000 },
    );
    const drawn = await page.evaluate(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount(),
    );
    // A readable field, not three arrows and not forty thousand.
    expect(drawn).toBeGreaterThan(50);
    expect(drawn).toBeLessThanOrEqual(600);

    // --- and the sheet says what was actually drawn --------------------------
    // The DEPTH SERVED, which is not the depth of the slice beside it: GLORYS
    // has its own 40 levels and none of them is exactly where the cursor is.
    await expect(block).toContainText(/\d+ arrows at [\d.]+ m/);
    // The reduction, disclosed. A thinned field must never be presented as the
    // grid the model actually ran on.
    await expect(block).toContainText(/mean of up to \d+ cells/);
    // And the coastal refusals, so a sparse field is distinguishable from a
    // broken one.
    await expect(block).toContainText(/refused for being more land than water/);
    // Named as a different dataset, in the control itself.
    await expect(block).toContainText(/Copernicus GLORYS, not the INCOIS analysis/);

    // --- moving the depth cursor moves the arrows ----------------------------
    // They belong to a level, not to the scene. Currents at 2000 m are a
    // different field from currents at 100 m, and the count changes because
    // the seafloor rises and more blocks become land.
    const summaryBefore = await block.innerText();
    // A MID-depth level, not the deepest. The deepest is 2000 m, where the
    // INCOIS field has a level and GLORYS does not, and that case is asserted
    // separately below because it is a real edge rather than a failure.
    await page.locator('[role="option"]').nth(14).click();
    await expect(block).not.toHaveText(summaryBefore, { timeout: 40_000 });
    await expect(block).toContainText(/\d+ arrows at [\d.]+ m/);

    // --- the two cubes do not share a depth axis, and it says so ------------
    // The INCOIS rack reaches 2000 m; GLORYS stops at 1941.89. A viewer who
    // simply moves the cursor to the bottom gets a sentence, not a stack
    // trace, and not an arrow drawn at the wrong depth.
    await page.locator('[role="option"]').last().click();
    await expect(block).toContainText(/has no currents at 2000 m/, { timeout: 40_000 });
    await expect(block).toContainText(/different axis/);
    await expect(block).not.toContainText("Error:");
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount() === 0,
      undefined,
      { timeout: 20_000 },
    );
    // Back to a level that has data, so the teardown below is meaningful.
    await page.locator('[role="option"]').nth(6).click();
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount() > 0,
      undefined,
      { timeout: 40_000 },
    );

    // --- off again -----------------------------------------------------------
    await block.getByRole("button").click();
    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.arrowCount() === 0,
      undefined,
      { timeout: 20_000 },
    );

    expect(w.offOrigin, "PRD F11: currents must come from our own origin").toEqual([]);
  });

  test("the sensor station appears only when one is plugged in", async ({ page, request }) => {
    /* PS requirement F6, TRD M9: "extensible design ... future integration of
       additional sensors". This test drives the whole clause with no hardware,
       which is the point: the server does not care what posts to it.

       THE FIRST HALF IS THE IMPORTANT HALF. No rig is the normal state, on the
       judges' laptop and on CI and on this machine most of the time, and a
       globe that draws a station mark with nothing behind it is making the one
       claim on this surface that costs nothing to make and everything to be
       caught making. So the log is emptied and the absence is asserted before
       anything is posted.

       Emptying it is safe and is not a special test affordance: the readings
       file is runtime state written by a device, gitignored, rebuilt by
       whatever is plugged in, and firmware/sagarnode/README.md already says it
       is safe to delete between demos. */
    const log = join(__dirname, "..", "data", "cube", "sagarnode.jsonl");
    rmSync(log, { force: true });

    const w = watch(page);
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    // --- 1. nothing plugged in, nothing drawn, nothing claimed --------------
    // The route answers an EMPTY station rather than a 404, because a 404
    // would read as a broken endpoint rather than as an idle feature.
    const empty = await (await request.get(`${API}/sagarnode`)).json();
    expect(empty.count, "the log was just emptied").toBe(0);
    await expect(page.locator(".node")).toHaveCount(0);
    const bare = await page.evaluate(() => {
      const s = (window as unknown as { __sagarScene?: any }).__sagarScene;
      return { nodes: s.sagarnodeCount(), floats: s.floatCount() };
    });
    expect(bare.nodes, "no rig means no mark on the globe").toBe(0);
    expect(bare.floats, "the real instruments are unaffected").toBeGreaterThan(0);
    // And the legend does not advertise a class that is not there.
    await expect(page.locator(".legend")).not.toContainText("Demonstration rig");

    // --- 2. a wiring fault is refused BY NAME -------------------------------
    // -127 is what a DS18B20 library reports when it cannot find the device,
    // and the refusal is the entire debugging loop for a headless board: the
    // sentence names the probe and the range it should be in.
    const broken = await request.post(`${API}/ingest/sagarnode`, {
      data: { station_id: "sagarnode-01", temp_c: -127, tds_ppm: 310, turbidity_ntu: 4.2 },
    });
    expect(broken.status()).toBe(400);
    expect((await broken.json()).detail).toMatch(/temp_c is -127\.0, outside the -5\.0 to 100\.0/);

    // --- 3. twenty quiet readings, and still no alarm -----------------------
    // A threshold that trips on the tank simply existing is a threshold nobody
    // would leave switched on.
    for (let i = 0; i < 20; i++) {
      const r = await request.post(`${API}/ingest/sagarnode`, {
        data: {
          station_id: "sagarnode-01",
          temp_c: 27 + ((i % 5) - 2) * 0.05,
          tds_ppm: 308 + (i % 3),
          turbidity_ntu: 4.2,
        },
      });
      expect(r.status(), "a plausible reading must be accepted").toBe(200);
    }
    const quiet = await (await request.get(`${API}/sagarnode`)).json();
    expect(quiet.count).toBe(20);
    expect(quiet.alert, "a settled tank must not trip anything").toBeNull();

    await page.reload({ waitUntil: "networkidle" });
    await sceneReady(page);

    const panel = page.locator(".node");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    // The label the SERVER serves, not one invented here. CLAUDE.md: it is a
    // conductivity-derived salinity PROXY, and an INCOIS oceanographer is
    // exactly the person who would notice the difference.
    await expect(panel).toContainText("Conductivity-derived salinity proxy");
    await expect(panel).not.toContainText(/salinity sensor/i);
    // Quiet: no drill stamp yet.
    await expect(panel.locator(".node__drill")).toHaveCount(0);
    // And the mark is on the globe now, in its own layer, NOT counted among
    // the profiling instruments.
    const withRig = await page.evaluate(() => {
      const s = (window as unknown as { __sagarScene?: any }).__sagarScene;
      return { nodes: s.sagarnodeCount(), tripped: s.sagarnodeTripped(), floats: s.floatCount() };
    });
    expect(withRig.nodes).toBe(1);
    expect(withRig.tripped).toBe(false);
    // The count of profiling instruments is UNCHANGED. That is the assertion
    // the separate layer exists for: fold the rig into the float layer and a
    // bucket becomes one of the Argo floats in every total on the page.
    expect(withRig.floats, "a bucket is not an Argo float").toBe(bare.floats);
    await expect(page.locator(".legend")).toContainText("Demonstration rig");

    // --- 4. the jug of warm water -------------------------------------------
    const warm = await request.post(`${API}/ingest/sagarnode`, {
      data: { station_id: "sagarnode-01", temp_c: 34.2, tds_ppm: 312, turbidity_ntu: 9.5 },
    });
    expect(warm.status()).toBe(200);
    expect((await warm.json()).alert).toMatch(/Rapid warming/);

    await page.reload({ waitUntil: "networkidle" });
    await sceneReady(page);
    await expect(panel).toBeVisible({ timeout: 30_000 });

    // The reading itself, on screen.
    await expect(panel).toContainText("34.2");
    // A drill, stamped as one. The rig's alert carries CAP status Exercise for
    // exactly the reason HazardWatch's rehearsals do, and this is the same
    // stamp: a bucket in a college hall must never read as a coastal hazard.
    await expect(panel.locator(".node__drill")).toHaveText(/exercise/i);
    await expect(panel.locator(".node__headline")).toContainText("DEMONSTRATION RIG");
    // The threshold is a jump against the tank's OWN recent spread, not a
    // fixed temperature, so the sentence has to carry the baseline it beat.
    await expect(panel.locator(".node__headline")).toContainText(/recent average of 27/);

    await page.waitForFunction(
      () => (window as unknown as { __sagarScene?: any }).__sagarScene.sagarnodeTripped() === true,
      undefined,
      { timeout: 20_000 },
    );

    // --- 5. and the spoken scene says all of that ---------------------------
    // Without the readings themselves: this region is aria-live and the rig is
    // polled twice a second, so a number in it would make a screen reader
    // recite the tank forever.
    const spoken = await page.evaluate(
      () => document.querySelector('.sr-only[role="status"]')?.textContent ?? "",
    );
    expect(spoken).toContain("demonstration sensor station");
    expect(spoken).toContain("not an ocean observation");
    expect(spoken).toMatch(/drill/i);
    expect(spoken).not.toMatch(/34\.2/);

    expect(w.offOrigin, "PRD F11: the rig must post to our own origin").toEqual([]);
    expect(w.consoleErrors, "no console error").toEqual([]);

    // Left empty, so the next run starts from the state CI starts from.
    rmSync(log, { force: true });
  });

  test("a narrow window is honest rather than broken", async ({ page }) => {
    // Not a target device (PRODUCT.md operating context is a forecast desk and
    // a stage), so this asserts truthfulness, not a mobile experience: nothing
    // overlaps, nothing is unreachable, and the citation stays readable.
    const w = watch(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(PROBE, { waitUntil: "networkidle" });
    await sceneReady(page);

    const overflow = await page.evaluate(
      () => document.body.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflow, "a narrow window must not scroll sideways").toBe(false);

    const boxes = await page.evaluate(() => {
      const pick = (q: string) => {
        const el = document.querySelector(q);
        return el ? el.getBoundingClientRect().toJSON() : null;
      };
      return {
        scene: pick(".scene"),
        stack: pick(".panel-stack"),
        panel: pick(".panel-right"),
        prov: pick(".provenance"),
      };
    });
    // Single column, in document order, with no two panels on top of each other.
    expect(boxes.scene!.bottom).toBeLessThanOrEqual(boxes.stack!.top + 1);
    expect(boxes.stack!.bottom).toBeLessThanOrEqual(boxes.panel!.top + 1);
    expect(boxes.panel!.bottom).toBeLessThanOrEqual(boxes.prov!.top + 1);

    await expect(page.locator(".cartouche")).toContainText("incois_argo_10d_VAM");
    expect(w.offOrigin).toEqual([]);
  });
});
