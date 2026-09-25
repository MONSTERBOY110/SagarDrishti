# What remains, measured against the problem statement

**Written 23 September 2026, for tonight's session.** Every line below was
checked against the PS text in `PRD.md` section 2 and section 5 and against
`P0-STATUS.md`, not from memory. Where something is a deliberate refusal rather
than unfinished work, it says so.

---

## Update, 25 September: what tonight closed

- **F5 Docker: Met.** Three Dockerfiles written (there were none), compose
  rewritten to the three services the app actually has, and the full browser
  suite passes against the containers (`./tasks.ps1 docker`). The air-gapped
  API container answers with no network at all. Evidence in `P0-STATUS.md` F5.
  **All seven PS requirements now have evidence; F1 keeps its one deliberate
  refusal (gridded chlorophyll), explained below.**
- **Voice (F10, P1): built, key pending.** `services/agent/app/voice.py` calls
  Bhashini's ULCA pipeline (ASR, translation, TTS) from the agent SERVER only,
  so the key never reaches a browser and the off-origin guard still holds. The
  ask panel has a language picker (English, Hindi, Telugu, Tamil), push to
  talk, and a read-aloud switch. The English answer stays the one the guard
  checked; a translation is printed beside it, labelled as machine
  translation. Offline, the microphone says in words why it cannot listen, and
  English answers are read aloud by the OS voice with no network. Noto Sans
  Devanagari, Telugu and Tamil are vendored (OFL), so Indian text renders
  offline. Tests: 12 new agent tests against a stubbed Bhashini (83 total), and
  the browser suite checks the offline degradation.
  **Still open: the live round trip.** The key request is with Bhashini for
  approval (`required.md` 16). When it lands: key into `.env`, run with
  `OFFLINE=0`, speak one Hindi question end to end, and record it.
- **Demo video**: `tools/record_demo.mjs` records the running build (real GPU,
  1080p, H.264, silent) with a timing sheet for the voiceover, into
  `docs/submission/video/`.

---

## The short answer (23 September)

**One P0 item is actionable: Docker.** That is the whole of the PS's own list
that is still open, and it is open because Docker is not installed on this
machine rather than because anything is unwritten.

**Bhashini is not in the problem statement.** I checked, because it changes what
tonight is worth spending on. The PS names seven requirements and voice is not
among them. What the PS *does* name is public outreach, education, exhibitions
and e-learning, and we already answer that with the six guided tours. Voice is
our own P1 differentiator (`PRD.md` F10), chosen because it is a strong one, not
because it was asked for.

That does not mean skip it. It means **do Docker first**, because CLAUDE.md's
rule is P0 before P1 and because Docker is thirty minutes of work against a
requirement a judge can point at, and then spend the rest of the night on voice
knowing exactly what it is: a differentiator, not a hole.

---

## 1. The PS's own requirement list, F1 to F7

This is the list the screening reviewers score. Five of seven have no gap at
all.

| # | Requirement | State | What is left |
|---|---|---|---|
| F1 | 3D volumetric rendering | **Partly met** | One field, and it is a refusal. See below. |
| F2 | Instrument data overlay | **Met** | Nothing. |
| F3 | Multi-format data ingestion | **Met** | Nothing. |
| F4 | Colorbar and variable controls | **Met** | Nothing. |
| F5 | Web-based, scalable architecture | **Partly met** | **Docker has never been run.** Tonight. |
| F6 | Extensible design | **Met** | Nothing. |
| F7 | Open standards, OGC and CF | **Met** | Nothing. |

### F5, the one real item: Docker

The compose files are written and have never been executed, because Docker is
not on this machine. It is the last unproven claim in the PS's
"deployable on INCOIS infrastructure" clause, and it is the kind of thing an IT
person on the panel asks about.

**What I will do once Docker Desktop is installed and you tell me:**

1. Build the images and bring the stack up from a clean checkout.
2. Run the demo path against the containerised stack, not the local one, so the
   claim is "it runs in Docker" and not "it built in Docker".
3. Fix whatever the first real run turns up. Nothing authored and never
   executed survives its first execution unchanged, so budget for this.
4. Turn F5 from **Partly met** to **Met** in `P0-STATUS.md`, with the commands
   that prove it, the way every other row in that file carries its evidence.

**If you decide not to install it,** say so and I will write plainly in the docs
that the Docker path is authored and unverified. That is a worse answer than
running it, and a much better answer than leaving it ambiguous.

### F1, the one that is a refusal rather than a gap

Every technique the PS names is built, and since yesterday so is a fourth it
asks for before it names any technique: a GPU ray-marched volume. Every field it
names is drawn except chlorophyll as a **gridded** field, and that is a
deliberate position, not an omission: the INCOIS chlorophyll series ends in
2020 and cannot share a time scrubber with a 2026 analysis without the interface
making a false statement silently. It ships as contemporary BGC-float data
instead, which is real and current.

**There is a version of this worth considering tonight if Docker finishes
early.** We could render the 2020 chlorophyll as its own clearly dated layer,
refused by the scrubber and labelled with its own epoch, exactly as the 2018
glider and the 1990 CTD casts already are. That would close the last F1 field
and the honesty machinery to do it already exists. It is your call whether the
extra layer is worth the extra thing to explain.

---

## 2. Voice and Bhashini, stated accurately

**Not a PS requirement.** `PRD.md` section 5 marks it F10, under
"P1, differentiators", and its own justification says it "supports the PS's
outreach mandate" rather than answering a named requirement.

**The outreach mandate it supports IS in the PS**, explicitly: public outreach,
education, exhibitions, e-learning. We answer that today with six guided tours
that drive the real scene, one of which is the submission video. So the outreach
box is already ticked; voice makes it louder.

The architecture is already specified in `TRD.md` M8: push-to-talk, STT, the
existing agent, TTS reply, language auto-detect for Hindi, Telugu, Tamil and
English. Nothing is built yet.

### Three things to settle before writing any code

**1. Bhashini needs credentials, and I cannot get them.** The API needs
registration at bhashini.gov.in. If you can get a key tonight, the online path
is real. If not, we build the offline path and name Bhashini as the production
route, which is honest and still demonstrates the capability.

**2. The air-gap claim is at stake.** CLAUDE.md is unambiguous: every feature
must work with `OFFLINE=1`, and the demo runs with the WiFi off. That is one of
our strongest moments on camera. A cloud STT call is a request that leaves the
machine, and the browser test fails the build when one does. So:

- **Text to speech is genuinely free.** The browser's own `speechSynthesis`
  uses the operating system's installed voices and needs no network. It can
  narrate an answer, and a tour, today.
- **Speech to text is the hard half.** Chrome's `SpeechRecognition` sends audio
  to Google's servers, so it is not offline whatever it looks like. A truly
  offline microphone needs a local model, which is what TRD M8 already
  specifies: AI4Bharat IndicConformer as ONNX, or a small Whisper.

**My recommendation for tonight, in order:** narrated answers with
`speechSynthesis` first, because it is offline, it is quick, and it is the half
an audience actually hears. Then push-to-talk behind a flag, with Bhashini
online and a local model as the `OFFLINE=1` swap, exactly as the TRD says.

**3. We cannot render Hindi, Telugu or Tamil text yet.** Both vendored typefaces
are latin-subset only, so Devanagari, Telugu and Tamil would fall back to a
system font, and in an air-gapped demo a missing glyph is a row of empty boxes
on screen. `ROADMAP.md` flagged this on 7 September and parked it for
"alongside the voice layer", which is now. Adding Noto Sans Devanagari, Telugu
and Tamil subsets is small and must happen before any multilingual text is set,
not after.

---

## 3. Everything else that is open, so the list is complete

Neither of these is a PS requirement and neither blocks the submission.

| Item | State | Needs |
|---|---|---|
| India EEZ boundary | Not built, deliberately | A citable boundary file. I will not draw a maritime boundary from memory in front of MoES. Marine Regions publishes one under CC-BY |
| Export button, pointer readout | Not built | Tier 2 in `beat-competition.md`. Neither is in the PS. I would leave both |
| The agent's planner | Built, rule-based | It prints `planner: rules` under every answer and refuses anything outside its tools. An LLM planner is a week and a live failure mode; the honest version already lands |
| Superseded `SagarDrishti_SIH2026_Idea.pdf` | Still in `docs/submission/` | Your call to delete. It is the wrong deck |

---

## 4. Tonight, in order

1. **Docker.** You install Desktop, I build, run, fix and re-verify, and F5 goes
   to Met with its evidence. This is the only item on the PS's own list.
2. **Fonts.** Noto Sans Devanagari, Telugu and Tamil subsets vendored, so
   nothing we build next renders as empty boxes.
3. **Narrated answers.** `speechSynthesis` on the agent's replies and on tour
   narration. Offline, no credentials, works tonight.
4. **Push to talk**, behind a flag, with Bhashini online if you have a key and a
   local model as the offline swap.
5. Optional, only if the above lands: the dated chlorophyll layer that closes
   the last F1 field.

Each step ends green or it does not land: 512 data plane, 71 agent, 12 browser,
plus the typography and contrast guards. The freeze is tomorrow evening and the
recording is on the 25th, so anything not finished by the freeze gets cut rather
than carried into recording day.
