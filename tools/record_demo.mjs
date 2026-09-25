/** Record the submission video: about three and a half minutes, 1080p.
 *
 * THE SHAPE, as the lead set it on 25 September:
 *   1. the problem and the core challenge          (card, about 18 s)
 *   2. why this changes the job                    (card, about 17 s)
 *   3. the core innovation                         (card, about 20 s)
 *   4. the prototype walkthrough, core first       (the running app, about 2 min)
 *      then the agent answering aloud              (about 20 s)
 *   5. long-term impact                            (card, about 16 s)
 * Additional features (currents, the glider, density) get five seconds each;
 * the time goes to the water column, the instruments, the Class-4 scorecard
 * and the CAP warnings, which are what the problem statement asks for.
 *
 * NOTHING IS STAGED. The cards sit over the live globe, the walkthrough is the
 * guided tour driving the real scene through the same store a click goes
 * through, and every number on a card is read from the running data plane at
 * the moment of recording rather than typed here.
 *
 * SOUND. The only sound is the app's own voice: Samudra Sahayak reading its
 * answer aloud (the computer's own voice, offline) and, when the agent reports
 * voice as available (OFFLINE=0 and a Bhashini key in .env), the same answer in
 * Hindi through Bhashini. The screen grabber cannot hear the machine, so each
 * utterance is logged with its start time and laid onto the video afterwards:
 * Bhashini's audio exactly as it came back, English rendered by the same
 * Windows voice the page used (tools/tts_winrt.ps1). Everything else is left
 * quiet for the voiceover, whose script is written beside the video.
 *
 * HOW. A real, headed Chromium on the laptop's own GPU, fullscreen at 1:1
 * pixels, captured by ffmpeg's gdigrab at 30 fps into H.264.
 *
 * Run, with the stack up (./tasks.ps1 docker, or api + agent + demo):
 *   node tools/record_demo.mjs
 * Keep the laptop plugged in, notifications off, and do not touch it for about
 * four minutes: gdigrab records the whole screen.
 */

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const WEB = process.env.SAGAR_WEB ?? "http://localhost:3000";
const API = process.env.SAGAR_API ?? "http://127.0.0.1:8000";
const AGENT = process.env.SAGAR_AGENT ?? "http://127.0.0.1:8010";
const DATE = new Date().toISOString().slice(0, 10);
const OUT_DIR = join(ROOT, "docs", "submission", "video");
const OUT = join(OUT_DIR, `SagarDrishti-demo-${DATE}.mp4`);
const RAW = OUT.replace(/\.mp4$/, ".video-only.mp4");
const SHEET = join(OUT_DIR, `SagarDrishti-demo-${DATE}-script.md`);
const FFMPEG = process.env.FFMPEG ?? "ffmpeg";
const TOUR = "The whole story, in two minutes";
const rel = (p) => p.slice(ROOT.length + 1).replace(/\\/g, "/");

mkdirSync(OUT_DIR, { recursive: true });

// --- the numbers, read from the running system ------------------------------
const card = await (await fetch(`${API}/scorecard/incois_vam_argo/TEMP`)).json();
const fmt = (n) => n.toLocaleString("en-IN");
const N = {
  rmse: card.overall.rmse.toFixed(3),
  bias: (card.overall.bias >= 0 ? "+" : "") + card.overall.bias.toFixed(3),
  pairs: fmt(card.overall.n),
  casts: card.n_profiles,
  platforms: card.n_platforms,
  refused: fmt(card.refused.total),
};
console.log("scorecard", N);

/* The walkthrough: tour step, seconds on screen, the caption shown in place
   of the tour's own text, and the voiceover line written for that time (about
   2.5 words a second). `extra` marks the additional features kept short. */
const WALK = [
  { step: 0, s: 10, cap: "The whole water column, in a browser",
    vo: "This is the Bay of Bengal from INCOIS's own ERDDAP server: the whole water column, twenty four levels from five metres to two kilometres." },
  { step: 1, s: 10, cap: "Travel down the column",
    vo: "Move the depth cursor and you travel down it. About twenty nine degrees at the surface, under three at two kilometres." },
  { step: 2, s: 11, cap: "The 26 degC surface: cyclone fuel",
    vo: "This sheet is the twenty six degree surface, the depth of cyclone fuel, extracted from the grid itself." },
  { step: 3, s: 5, extra: true, cap: "Currents at depth, second agency",
    vo: "Currents at depth, from a second agency, and labelled as one." },
  { step: 4, s: 10, cap: "Every mark is a real instrument",
    vo: "Every mark is a real instrument: Argo floats, BGC floats, a RAMA buoy, a glider and ship casts." },
  { step: 5, s: 5, extra: true, cap: "A 2018 glider, dated, not scored",
    vo: "The glider flew in 2018, so it is dated, and never scored." },
  { step: 6, s: 12, cap: "What it measured, against the model",
    vo: "Click one and you see what it measured, against the model at the same place and time, and the gap between them." },
  { step: 7, s: 13, cap: "The ray-marched volume, beside the cast",
    vo: "The same cast in the volume studio: the model ray marched on the GPU, cut away by depth, with the measured profile beside it." },
  { step: 8, s: 11, cap: `Class-4: RMSE ${N.rmse} degC over ${N.pairs} pairs`,
    vo: `And this is the core. Every cast scored where it was taken, Class 4 style. R M S E ${N.rmse} degrees over ${N.pairs} pairs.` },
  { step: 9, s: 9, cap: "The caveat travels with the number",
    vo: "With its caveat attached: this analysis has already seen these floats, so it is analysis fit, not forecast skill." },
  { step: 10, s: 5, extra: true, cap: "Density, derived by a plugin (TEOS-10)",
    vo: "Density, derived by a plugin with TEOS-10." },
  { step: 11, s: 11, cap: "CAP warnings from NDMA SACHET, drills marked",
    vo: "Warnings drawn over the water, parsed from India's national CAP feed, NDMA SACHET. A drill can never pass for a real alert." },
  { step: 12, s: 9, cap: "Served over OGC WMS and WCS",
    vo: "All of it served through OGC WMS and WCS, so the tools INCOIS already runs can read it." },
];

const CARDS = {
  problem: {
    kicker: "01  The problem",
    title: "Three dimensional ocean models, read through flat tools",
    lines: [
      "INCOIS runs ocean models in three dimensions, and forecasters toggle between separate packages to read them, one file and one depth at a time.",
      "The core challenge: the model is a volume, the instruments are points, and the question that matters is how far apart they are.",
    ],
    foot: "SIH26067, MoES / INCOIS",
    s: 18,
    vo: "INCOIS runs its ocean models in three dimensions, but forecasters read them by toggling between separate tools, one file and one depth at a time. The core challenge: the model is a volume, the instruments are points, and what a forecaster needs is how far apart they are.",
  },
  change: {
    kicker: "02  Why it changes the job",
    title: "One page. The whole column. A number for the gap.",
    lines: [
      "The model field and every instrument in the water, on one 3D globe, 24 levels from 5 m to 2000 m.",
      "The model scored against each cast, at the cast's own place and depth.",
      "Nothing to install. It runs from one docker compose up, with the network off.",
    ],
    s: 17,
    vo: "SagarDrishti puts the model and every instrument in the water on one page, the whole column in 3D, with a number for the gap. Nothing to install, and it runs with the network switched off.",
  },
  core: {
    kicker: "03  The core innovation",
    title: "Class-4 verification, in observation space",
    stats: [
      [N.rmse, "RMSE, degC"],
      [N.bias, "bias, degC"],
      [N.pairs, "matched pairs"],
      [N.refused, "levels refused, each with a reason"],
    ],
    lines: [
      `The model is interpolated to each of ${N.casts} casts from ${N.platforms} platforms, the way operational centres verify (Ryan et al. 2015). What cannot be matched honestly is refused and counted, never guessed.`,
    ],
    s: 20,
    vo: `The core innovation is Class 4 verification in observation space, the method operational centres use. The model is interpolated to each cast's own position and depth. R M S E ${N.rmse} degrees over ${N.pairs} pairs, and ${N.refused} levels refused, each with a printed reason, rather than guessed.`,
  },
  impact: {
    kicker: "05  Long-term impact",
    title: "Deployable on INCOIS infrastructure as it stands",
    lines: [
      "Three containers, open standards (OGC WMS and WCS, CF, CAP v1.2), no licences.",
      "A new model or instrument is a YAML entry and a plugin, not a rewrite.",
      "Every field ships with its own skill number, so a forecast can be defended.",
      "Next: the full Indian Ocean grid, cyclone season operations, and voice in the coastal languages through Bhashini.",
    ],
    foot: "SagarDrishti  ·  Team PixelPaws  ·  SIH26067",
    s: 16,
    vo: "It deploys on INCOIS infrastructure as it stands: three containers, open standards, no licences. A new model or instrument is a configuration entry, not a rewrite. Next, the full Indian Ocean, cyclone season operations, and voice in the coastal languages through Bhashini.",
  },
};

// --- the browser ----------------------------------------------------------
const browser = await chromium.launch({
  headless: false,
  args: [
    "--start-fullscreen",
    // 1:1 pixels. The laptop runs Windows at 125%, which would hand the page
    // a 1536x864 viewport; the design target and the budgets are 1080p.
    "--force-device-scale-factor=1",
    "--ignore-gpu-blocklist",
    "--use-angle=d3d11",
    "--disable-infobars",
    "--hide-scrollbars",
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const context = await browser.newContext({ viewport: null });
const page = await context.newPage();

// FULLSCREEN THROUGH THE BROWSER ITSELF. --kiosk and --start-fullscreen are
// both ignored by a Playwright-launched Chromium, and the first take of this
// video was a small window with the desktop and the taskbar around it.
const cdp = await context.newCDPSession(page);
const { windowId } = await cdp.send("Browser.getWindowForTarget");
await cdp.send("Browser.setWindowBounds", { windowId, bounds: { windowState: "fullscreen" } });
await page.waitForTimeout(1500);
const vp = await page.evaluate(() => [innerWidth, innerHeight, devicePixelRatio]);
console.log(`viewport ${vp.join(" x ")}`);
if (vp[0] !== 1920 || vp[1] !== 1080) {
  throw new Error(`expected a 1920x1080 fullscreen page, got ${vp[0]}x${vp[1]}`);
}

// ?probe=1 exposes the scene counters only; it changes nothing on screen.
await page.goto(`${WEB}/?probe=1`, { waitUntil: "networkidle", timeout: 120_000 });
await page.waitForFunction(() => window.__sagarScene?.sliceCount() > 0, undefined, {
  timeout: 120_000,
});
await page.waitForTimeout(6000);
await page.mouse.move(-10, -10);

/* The card and caption layer: injected by the recorder, not part of the app.
   Same world as the app (the slate ground, Archivo Narrow for words, Courier
   Prime for numbers); the one colour is the field's own colorbar as a rule. */
await page.addStyleTag({
  content: `
  #rec-card { position: fixed; inset: 0; z-index: 99999; display: grid; place-items: center;
    background: rgba(5, 8, 12, 0.88); opacity: 0; transition: opacity 0.7s ease; pointer-events: none;
    font-family: "Archivo Narrow", sans-serif; color: #E3EBF0; }
  #rec-card.on { opacity: 1; }
  #rec-card .in { width: 1240px; }
  #rec-card .k { font-size: 22px; letter-spacing: 0.16em; text-transform: uppercase; color: #9fb0ba; }
  #rec-card .bar { height: 5px; width: 360px; margin: 18px 0 28px;
    background: linear-gradient(90deg, #1d2c6b, #2f6fb3, #5fb3c9, #e8c15a, #f08a3c); }
  #rec-card h1 { font-size: 64px; line-height: 1.08; font-weight: 700; margin: 0 0 34px; }
  #rec-card p { font-size: 30px; line-height: 1.42; margin: 0 0 18px; color: #cdd7dd; max-width: 1180px; }
  #rec-card .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 28px; margin: 0 0 34px; }
  #rec-card .stats b { display: block; font-family: "Courier Prime", monospace; font-size: 56px; color: #fff; }
  #rec-card .stats span { font-size: 22px; color: #9fb0ba; }
  #rec-card .f { margin-top: 40px; font-size: 22px; letter-spacing: 0.08em; color: #7f8f99; }
  body[data-rec-tour] .tour__stage { opacity: 0 !important; }
  #rec-cap { position: fixed; left: 50%; bottom: 150px; transform: translateX(-50%); z-index: 99998;
    padding: 14px 28px; background: rgba(5, 8, 12, 0.9); border: 1px solid #7f8f99;
    font-family: "Archivo Narrow", sans-serif; font-size: 34px; font-weight: 600; color: #E3EBF0;
    opacity: 0; transition: opacity 0.4s ease; pointer-events: none; white-space: nowrap; }
  #rec-cap.on { opacity: 1; }
  #rec-cap .x { font-size: 20px; letter-spacing: 0.12em; color: #9fb0ba; margin-right: 16px;
    text-transform: uppercase; }
  `,
});
await page.evaluate(() => {
  for (const id of ["rec-card", "rec-cap"]) {
    const d = document.createElement("div");
    d.id = id;
    document.body.appendChild(d);
  }
});

const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;");
async function showCard(c) {
  const html =
    `<div class="in"><div class="k">${esc(c.kicker)}</div><div class="bar"></div>` +
    `<h1>${esc(c.title)}</h1>` +
    (c.stats
      ? `<div class="stats">${c.stats.map(([v, l]) => `<div><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join("")}</div>`
      : "") +
    c.lines.map((l) => `<p>${esc(l)}</p>`).join("") +
    (c.foot ? `<div class="f">${esc(c.foot)}</div>` : "") +
    `</div>`;
  await page.evaluate((h) => {
    const el = document.getElementById("rec-card");
    el.innerHTML = h;
    el.classList.add("on");
  }, html);
}
const hideCard = () => page.evaluate(() => document.getElementById("rec-card").classList.remove("on"));
async function caption(text, tag = "") {
  await page.evaluate(
    ([t, x]) => {
      const el = document.getElementById("rec-cap");
      el.innerHTML = (x ? `<span class="x">${x}</span>` : "") + t;
      el.classList.add("on");
    },
    [esc(text), esc(tag)],
  );
}
const hideCaption = () => page.evaluate(() => document.getElementById("rec-cap").classList.remove("on"));

// The first card is up BEFORE the first frame, so the video opens on it.
await showCard(CARDS.problem);
await page.waitForTimeout(900);

// --- record ---------------------------------------------------------------
const ff = spawn(
  FFMPEG,
  ["-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0",
   "-i", "desktop", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
   "-pix_fmt", "yuv420p", "-movflags", "+faststart", RAW],
  { stdio: ["pipe", "inherit", "inherit"] },
);
const t0 = Date.now();
const now = () => (Date.now() - t0) / 1000;
const marks = [];
const mark = (segment, onScreen = "", vo = "") => {
  marks.push({ t: now().toFixed(1), segment, onScreen, vo });
  console.log(`${now().toFixed(1)} s  ${segment}`);
};
const speech = [];
const wavSeconds = (b64) => {
  const b = Buffer.from(b64, "base64");
  return b.length > 44 ? (b.length - 44) / b.readUInt32LE(28) : 0;
};
const hold = (s) => page.waitForTimeout(s * 1000);

try {
  // 1 to 3: the three cards
  for (const key of ["problem", "change", "core"]) {
    const c = CARDS[key];
    if (key !== "problem") await showCard(c);
    mark(c.kicker, c.title, c.vo);
    await hold(c.s - 0.8);
    if (key !== "core") {
      await hideCard();
      await hold(0.8);
    }
  }
  await hideCard();

  // 4: the prototype
  mark("04  The prototype, opening frame", "The whole globe, the Bay of Bengal box",
    "Here is the prototype, running on this laptop. It opens on the whole globe, with the Bay of Bengal in the box.");
  await caption("SagarDrishti, running: one browser page", "04  Prototype");
  await hold(4);
  const toursTab = page.getByRole("button", { name: "Tours", exact: true });
  if ((await toursTab.getAttribute("aria-pressed")) !== "true") await toursTab.click();
  await hold(0.6);
  await page.locator(".tour__open").click();
  await hold(0.8);
  await page.evaluate(() => document.body.setAttribute("data-rec-tour", ""));
  await page.locator(".tour__pick").filter({ hasText: TOUR }).click();
  const stage = page.locator('[aria-label="Guided tour"]');
  await stage.waitFor({ timeout: 20_000 });
  await page.keyboard.press("Space"); // paused: the recorder sets the pace
  await hideCaption();
  await hold(3.2); // the flight down to the column

  let at = 0;
  for (const w of WALK) {
    while (at < w.step) {
      await page.keyboard.press("ArrowRight");
      at++;
    }
    await caption(w.cap, w.extra ? "also" : "");
    mark(`Walkthrough, tour step ${w.step + 1}${w.extra ? " (additional)" : ""}`, w.cap, w.vo);
    await hold(w.s);
  }
  await hideCaption();
  await page.keyboard.press("Escape");
  await page.evaluate(() => document.body.removeAttribute("data-rec-tour"));
  await hold(1.5);

  // the agent, answering aloud
  const agentTab = page.getByRole("button", { name: "Agent", exact: true });
  if ((await agentTab.getAttribute("aria-pressed")) !== "true") await agentTab.click();
  const ask = page.locator('[aria-label="Ask Samudra Sahayak"]');
  await ask.waitFor({ timeout: 20_000 });
  await ask.locator(".ask__aloud input").check();
  await caption("Samudra Sahayak: answers from tools, aloud", "also");
  mark("Walkthrough, the agent (additional)", "Ask: How warm is it at 100 m?",
    "Ask Samudra Sahayak a question, and it answers only from the data plane's own tools, cites the source, and reads the answer aloud.");
  const Q = "How warm is it at 100 m?";
  await ask.locator(".ask__input").fill(Q);
  await hold(0.8);
  await ask.getByRole("button", { name: "Ask" }).click();
  const text = ask.locator(".ask__text");
  await text.waitFor({ timeout: 30_000 });
  await page.waitForFunction(() => window.speechSynthesis?.speaking, undefined, { timeout: 10_000 })
    .catch(() => {});
  speech.push({ t: now(), kind: "local", text: (await text.innerText()).trim() });
  await page.waitForFunction(() => !window.speechSynthesis.speaking, undefined, { timeout: 40_000 })
    .catch(() => {});
  await hold(1.2);

  const status = await page.evaluate(async (base) => {
    try {
      return await (await fetch(`${base}/voice/status`)).json();
    } catch {
      return null;
    }
  }, AGENT);
  if (status?.available) {
    await caption("The same answer in Hindi, through Bhashini", "also");
    await ask.locator(".ask__lang select").selectOption("hi");
    await hold(0.8);
    const spoke = page.waitForResponse((r) => r.url().endsWith("/voice/speak"), { timeout: 60_000 });
    await ask.locator(".ask__input").fill(Q);
    await ask.getByRole("button", { name: "Ask" }).click();
    const res = await (await spoke).json();
    speech.push({ t: now(), kind: "wav", b64: res.audio });
    mark("Walkthrough, Hindi through Bhashini (additional)", res.text, "(the app speaks)");
    await hold(wavSeconds(res.audio) + 1.5);
  } else {
    console.log(`Hindi skipped: voice ${status?.reason ?? "unreachable"}`);
  }
  await hideCaption();

  // 5: impact
  await showCard(CARDS.impact);
  mark(CARDS.impact.kicker, CARDS.impact.title, CARDS.impact.vo);
  await hold(CARDS.impact.s);
  mark("End");
} finally {
  ff.stdin.write("q");
  await new Promise((r) => ff.on("close", r));
  await browser.close();
}

// --- the audio pass -------------------------------------------------------
const tmp = join(OUT_DIR, ".audio");
mkdirSync(tmp, { recursive: true });
const inputs = [];
for (const [i, u] of speech.entries()) {
  const wav = join(tmp, `u${i}.wav`);
  if (u.kind === "wav") {
    writeFileSync(wav, Buffer.from(u.b64, "base64"));
  } else {
    const txt = join(tmp, `u${i}.txt`);
    writeFileSync(txt, u.text, "utf8");
    const r = spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
      join(ROOT, "tools", "tts_winrt.ps1"), "-TextFile", txt, "-Out", wav], { encoding: "utf8" });
    if (r.status !== 0) throw new Error(`tts failed: ${r.stderr}`);
  }
  inputs.push({ wav, ms: Math.round(u.t * 1000) });
}
if (inputs.length) {
  const args = ["-y", "-loglevel", "error", "-i", RAW];
  inputs.forEach((x) => args.push("-i", x.wav));
  const chains = inputs.map((x, i) => `[${i + 1}:a]aresample=48000,adelay=${x.ms}:all=1[a${i}]`);
  const mix = `${inputs.map((_, i) => `[a${i}]`).join("")}amix=inputs=${inputs.length}:normalize=0,apad[aout]`;
  args.push("-filter_complex", [...chains, mix].join(";"), "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT);
  const r = spawnSync(FFMPEG, args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`mux failed: ${r.stderr}`);
} else {
  copyFileSync(RAW, OUT);
}
rmSync(tmp, { recursive: true, force: true });

// --- the voiceover script -----------------------------------------------
const cell = (s) => String(s).replace(/\|/g, "/").replace(/\n+/g, " ");
const rows = marks.map((m) => `| ${m.t} | ${cell(m.segment)} | ${cell(m.onScreen)} | ${cell(m.vo)} |`).join("\n");
writeFileSync(
  SHEET,
  `# Demo video and voiceover script, ${DATE}

Video: \`${rel(OUT)}\` (1920x1080, 30 fps, H.264, ${Math.round(now())} s).
Its only sound is the app's own voice (${speech.length} utterance${speech.length === 1 ? "" : "s"}), so the
voiceover fits everywhere else. The same take with no sound at all:
\`${rel(RAW)}\`.

Recorded by \`node tools/record_demo.mjs\` from the running build. Every number
on a card was read from the data plane at recording time: RMSE ${N.rmse} degC,
bias ${N.bias} degC, ${N.pairs} matched pairs, ${N.casts} casts from ${N.platforms}
platforms, ${N.refused} levels refused.

**How to read it:** start each line at its time. Each is written to fit its
segment at about 2.5 words a second; if a line runs long, drop its last clause
rather than speeding up. Do not speak over the agent's own voice.

| t (s) | Segment | On screen | Voiceover |
|---|---|---|---|
${rows}
`,
  "utf8",
);
console.log(`\nwrote ${OUT}\nwrote ${SHEET}`);
