import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

/* __dirname, not import.meta: Playwright loads this config as CommonJS because
   the root package.json declares no "type": "module", and import.meta is a
   syntax error there. */
const ROOT = __dirname;

/* An ABSOLUTE interpreter path, chosen by platform. A relative one broke on
   Windows: Playwright runs webServer commands through the shell, and cmd.exe
   cannot resolve "../../.venv/Scripts/python.exe" as a command. The venv also
   sits in Scripts/ on Windows and bin/ on Linux, which CI needs. */
const PYTHON =
  process.platform === "win32"
    ? join(ROOT, ".venv", "Scripts", "python.exe")
    : join(ROOT, ".venv", "bin", "python");

/** End-to-end configuration for the demo-path test (TRD section 9).
 *
 * Two things about this config are deliberate and load-bearing.
 *
 * It runs against a PRODUCTION build, not the dev server. That is not
 * fussiness: a production-only failure has already bitten this project once.
 * Importing Cesium as an ES module survived `next dev` and did not survive
 * `next build`, so the globe rendered as an empty black frame while every panel
 * around it worked. A suite that only ever drove the dev server would have
 * reported that as green. See apps/web/lib/cesium-loader.ts.
 *
 * It boots both services itself, so `pnpm e2e` is one command and CI needs no
 * orchestration script. OFFLINE=1 is set for the API because that is the
 * default posture, not a special mode (TRD M6).
 */

const WEB = "http://127.0.0.1:3100";
const API = "http://127.0.0.1:8100";

export default defineConfig({
  testDir: "./e2e",
  // The scene needs time to build 24 textured slices on an integrated GPU.
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false, // one browser at a time: these tests measure frame rate
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],

  use: {
    baseURL: WEB,
    // ?probe=1 exposes the scene hook in a production build so the test can
    // assert the 3D scene actually built, rather than only that pixels exist.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    viewport: { width: 1920, height: 1080 },
  },

  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1920, height: 1080 } } },
  ],

  webServer: [
    {
      // The data plane. OFFLINE=1 is the default and is stated here anyway, so
      // a reader of this file knows the suite never touches the network.
      command: `"${PYTHON}" -m uvicorn app.main:app --port 8100 --log-level warning`,
      cwd: join(ROOT, "services", "api"),
      url: `${API}/healthz`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: { OFFLINE: "1" },
    },
    {
      command: "pnpm --filter @sagardrishti/web exec next start -p 3100",
      url: WEB,
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
      env: { NEXT_PUBLIC_API_BASE: API },
    },
  ],
});
