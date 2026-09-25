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

/* EXTERNAL MODE: `SAGAR_E2E_EXTERNAL=1` runs the same twelve tests against a
   stack that is ALREADY RUNNING, and boots nothing itself. It exists for one
   job: proving the Docker deployment (`docker compose up`, then
   `./tasks.ps1 docker`), so that "deployable on INCOIS infrastructure" is a
   claim the full suite has checked against the containers rather than a
   compose file somebody wrote. Ports default to the compose file's. */
const EXTERNAL = !!process.env.SAGAR_E2E_EXTERNAL;

const WEB = process.env.SAGAR_E2E_WEB ?? (EXTERNAL ? "http://127.0.0.1:3000" : "http://127.0.0.1:3100");
const API = process.env.SAGAR_E2E_API ?? (EXTERNAL ? "http://127.0.0.1:8000" : "http://127.0.0.1:8100");
/* The agent plane. Booted here so the suite can prove the ask panel works,
   and on its own port so that killing it is a one-line change if we ever want
   to assert the "kill the agent and every P0 still passes" property directly. */
const AGENT =
  process.env.SAGAR_E2E_AGENT ?? (EXTERNAL ? "http://127.0.0.1:8010" : "http://127.0.0.1:8110");

// The spec posts to the data plane directly in one test, so it reads the same
// address rather than keeping a second copy of the port.
process.env.SAGAR_E2E_API = API;

export default defineConfig({
  testDir: "./e2e",
  /* MEASURED against a SOFTWARE renderer, which is the case that matters.
     Playwright's headless Chromium usually falls back to SwiftShader, and CI
     has no GPU at all, so software rendering is the normal condition here and
     a hardware GPU is the lucky one. Measured on this machine: the same four
     tests take 1.8 minutes with the Intel UHD GPU and 8.1 minutes on
     SwiftShader, and the longest single test goes from 46 seconds to 5.6
     minutes. A 120 s timeout passed locally on the GPU and would have failed
     every run on CI. The suite annotates the renderer it actually got, so a
     slow run is diagnosable rather than mysterious. */
  timeout: 420_000,
  expect: { timeout: 60_000 },
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

  webServer: EXTERNAL ? undefined : [
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
      // Samudra Sahayak. Depends on the API, so it is listed after it;
      // Playwright starts webServers in parallel and the agent tolerates the
      // API not being up yet (its /healthz reports that rather than failing).
      command: `"${PYTHON}" -m uvicorn app.main:app --port 8110 --log-level warning`,
      cwd: join(ROOT, "services", "agent"),
      url: `${AGENT}/healthz`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      // OFFLINE=1 stated for the agent too: voice (PRD F10) must degrade in
      // words, and a real environment variable beats anything in .env.
      env: { SAGAR_API_BASE: API, OFFLINE: "1" },
    },
    {
      /* The BUILD happens here, and that is the fix for a real bug rather than
         a tidy-up. `NEXT_PUBLIC_*` is inlined by Next at BUILD time, so setting
         NEXT_PUBLIC_API_BASE on `next start` did nothing at all: the served
         bundle carried the default http://127.0.0.1:8000 while this suite
         booted its API on 8100. It passed locally only because a development
         API happened to be listening on 8000. On CI nothing listens there, so
         every test would have failed with an empty scene and no clue why.
         Building inside this command is what makes the env var take effect,
         and it also retires the stale-build trap that has cost this project
         time three times: the suite can no longer serve a bundle older than
         the source it is testing. */
      command:
        "pnpm --filter @sagardrishti/web exec next build && " +
        "pnpm --filter @sagardrishti/web exec next start -p 3100",
      url: WEB,
      timeout: 600_000,
      reuseExistingServer: !process.env.CI,
      // BOTH bases at build time, for the reason spelled out above:
      // NEXT_PUBLIC_* is inlined by Next when it builds, so setting either of
      // these on `next start` would do nothing at all and the client would
      // call the default ports.
      env: { NEXT_PUBLIC_API_BASE: API, NEXT_PUBLIC_AGENT_BASE: AGENT },
    },
  ],
});
