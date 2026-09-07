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
    // We must NOT claim a skill figure from a nearest-cell comparison.
    await expect(panel).toContainText(/not Class-4 co-location/i);

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
    await page.mouse.move(960, 12);
    await page.waitForTimeout(6_000);
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
    const legend = page.locator(".legend");
    await expect(legend).toContainText("Argo float");
    await expect(legend).toContainText("BGC float");

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

    const toggle = page.getByRole("button", { name: /^(On|Off)$/ });
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
