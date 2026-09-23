# ROADMAP - SagarDrishti (Aug 2026 → Dec 2026)

Dates anchored to: idea deadline **20 Sep 2026** · Grand Finale **~8-12 Dec 2026** (2025 pattern; confirm when announced).

> **Date confirmed, 9 Sep 2026: the internal hackathon is Wednesday 16
> September.** That is seven days out and it is LATER than the worst case this
> file was re-baselined against, so nothing has to be cut. Phase 2 runs its
> full span, and Phase 3 (the idea PDF, due to the SPOC on Sep 20) starts the
> day after the round. Idea-counter re-checks stay on **Sep 15** and **Sep 19**
> (sih.gov.in/sih2026PS, SIH26067 - escalate if >~150).
>
> The earlier re-baseline of 7 Sep planned against a worst case of Sep 12 and
> built each Phase 1 spike to be independently demoable. That turned out to be
> unnecessary insurance, which is the right way for it to turn out.

## 2026-09-15, the idea-counter re-check, and what it turned up

The counter check was a scheduled chore and it returned three things worth more
than the count.

**The count.** SIH26067 stands at **4 of 500** ideas submitted, deadline
30 September 2026. The escalation trigger in CLAUDE.md is roughly 150, so the
backup problem statement stays on the shelf.

**The theme was contested, and is now settled.** Two third-party mirrors of the
SIH problem statement list disagree: `NoBugNinja/Smart-India-Hackathon-SIH-2026`
gives the theme as Smart Automation, `sih2026-ps-viewer.vercel.app` gives
Disaster Management. sih.gov.in itself, read live, says **Disaster Management**,
and so does INCOIS's own attachment for the neighbouring PS. Our docs were
right. The deck prints the theme on slide 1, so this mattered.

**The exact title was wrong in the deck**, and is now verbatim from the source:
"Develop a web-based interactive 3D visualization platform that integrates
numerical ocean model outputs and in-situ observations."

**And the Dataset Link field named an archive we had never read.** This is the
one that changed the product. INCOIS amended SIH26067 with four dataset links,
and the third is the Ifremer EGO glider FTP. Following it reopened F2, which
this project had investigated to exhaustion and written up as unachievable. The
full account is in `docs/P0-STATUS.md` under F2; in short:

- The EGO index file is 248 MB of whitespace, a broken build upstream.
- The same holdings are in the Copernicus in-situ TAC, whose `history` part we
  had never queried, having searched only the rolling thirty-day `latest` part.
  The absence of a glider in the last thirty days is not the absence of a
  glider, and that inference is what cost three weeks.
- Glider ru29 (Rutgers, WMO 2801900), 109 dives inside the box, August to
  October 2018. Fifteen shipboard CTD casts, SHINYO MARU, 1990 to 1991.
- Both predate the model cube, so the registry grew an `epoch` marker, the
  globe rings archive marks, the panel prints the reason, and the verification
  refuses all 13,622 of their levels and counts the refusal.

All four instrument classes the PS names are now live. The profile table went
from 25 casts and 16,390 levels to **149 casts and 30,012 levels**, and F2 moved
from "partly met" to met.

Tests: 512 data plane, 71 agent, 12 browser, **595** total, all green (re-counted 23 September; it was 485 / 71 / 11 = 567).

## Phase 0 - Team & repo - ✅ DONE Sep 7 (repo D:\Projects\SagarDrishti, docs moved, PRIOR-ART.md added; mentor onboarded)
- [x] Repo created; doc pack in `docs/`; prior-art & literature review done (docs/PRIOR-ART.md)
- [ ] Brief the team with HANDOFF.md + PRD.md; confirm 6-member roster (≥1 female) + 2 mentors; register per SPOC instructions
- [ ] **Confirm internal-hackathon date with college SPOC (URGENT - decides Phase 1 pace)**
- [ ] Everyone reads the PS 5×; each member writes a 3-line paraphrase (catches misreadings early - winner tactic)
- [ ] **Order SagarNode parts NOW** (ESP32, DS18B20 waterproof, TDS, turbidity - BOM in PRIOR-ART.md §F / TRD M9; delivery lead time is the risk)

## Phase 1 - Proof spike (Sep 7 → 11) - ✅ SPIKES A/B/C DONE Sep 7
Goal: kill the two technical risks before the internal round. **Both are dead.**

- [x] **Spike B** - `sources.yaml` → xarray → zarr → `/field` + `/profiles`, on **real data**.
      Primary source is INCOIS's own open ERDDAP griddap `incois_argo_10d_VAM`
      (24 levels, 5-2000 m, latest step 2026-07-30) + Argo GDAC daily
      Indian-Ocean profile files. **36 unit tests green**, covering the CF traps
      CLAUDE.md names - two `_FillValue` conventions, `scale_factor`/`add_offset`
      idempotency both directions, a vertical axis with no `positive` attribute,
      unit relabel vs. unit conversion, Argo QC flags 1/2 only, WMO char-array
      decode, pressure→depth - plus a colorbar test and an **offline guard that
      blocks non-loopback sockets and DNS** and still passes the demo path.
      Evidence: `docs/evidence/spike-b-api-openapi.png`.
- [x] **Spike A** - one timestep as **24 depth-sliced volumetric layers** on a
      Cesium globe, depth rack + time scrubber + exaggeration + opacity.
      **44 FPS median (p1 23) at 1080p on the Intel UHD integrated GPU** - TRD §5's
      stated target device. Started at 12 FPS; the four fixes and their measured
      impact are in `adr/0001`. Evidence: `docs/evidence/spike-a-globe.png`.
- [x] **Spike C** - clicking a station mark runs Cesium `scene.pick` → ECharts
      depth-vs-temperature for the real float, observed curve coloured by the
      field's own colorbar against a dashed model curve, with WMO id, timestamp,
      QC policy and citation on the panel. Verified on floats **1902681**
      (524 levels to 2002 m) and **7902073**.
      Evidence: `docs/evidence/spike-c-profile.png`.
- [x] Decision gate resolved: **the FPS floor was cleared**, and slices-only is
      not a fallback we had to take - it is what strategy (a) already is, so the
      TRD §6.4 floor is proven by construction rather than promised.
- [ ] Beginners: collect cyclone case-study material (IMD best track + dates);
      draft storyboard scripts; set up test checklist; SagarNode wiring on arrival - **unblocked**: the parts sheet is `docs/SAGARNODE-BOM.md`, awaiting purchase.

### Open items carried into Phase 2 (lead decisions needed)

| Item | Why it matters | Status |
|---|---|---|
| **Internal-hackathon date** | Decides whether Phase 2 compresses | Still unconfirmed by SPOC. Planning against the worst case (Sep 12). |
| ~~**Copernicus Marine credentials**~~ | ~~GLORYS12 is the only source with **depth-resolved currents**~~ | **DONE 9 Sep.** Ingested and serving: `glorys12_cur`, 40 levels to 1942 m at 1/12 deg. Logging in also revealed the configured dataset was the reanalysis, which ends 2026-06-23, before every date in the cube; switched to the analysis-and-forecast product. Drawn as arrows at the depth cursor since 10 Sep: 43,621 native cells block-averaged to a few hundred, coastal blocks refused rather than guessed |
| ~~**p1 frame time (23 FPS)**~~ | ~~the 1-in-100 frame still stutters~~ | **Re-measured 10 Sep and the worry was a measurement artefact.** Production build, Intel UHD (the WEAKER chip, per TRD section 5), every layer on: **72 FPS median, p1 57**. That beats the 60 target, not just the 30 floor. The old figure came from a probe timing the gaps between renders, which on a still scene is the BROWSER throttling its animation callback on a window it thinks is inactive, not our cost: 27 renders per second while still, 72 while being orbited. The probe now measures only while the camera is moving and the readout says "idle" otherwise |
| **`docker compose up` unverified** | PS requirement F5 is a screening claim | Docker not installed on the build machine (`adr/0004`); compose files authored, marked unexecuted |
| **1° / 10-day source resolution** | Coarse for a hero shot | Honest framing on stage; GLORYS12 at 1/12° is the visual upgrade |
| **Fonts are latin-subset only** | PRD requires Hindi, Telugu and Tamil, and both vendored faces carry latin glyphs only, so Devanagari, Telugu and Tamil text would fall back to a system font | Add Noto Sans Devanagari/Telugu/Tamil subsets in Phase 2 alongside the voice layer, when there is finally multilingual text to set. Flagged by the design documenter 2026-09-07. |

## Phase 2 - Internal-hackathon alpha (Sep 11 → 16, the round is Sep 16)
Goal: walk into the internal round with the only live 3D demo in the college - plus hardware on the table (mentor's advice).

**Landed EARLY, ahead of their planned phase** (each is done, tested and on
screen; the phase they were scheduled in is named so the plan stays readable):
OGC WMS and WCS and the plugin system (Phase 4), isosurface extraction
(Phase 4), the BGC-float and moored-buoy instrument classes (Phase 2's F2), and
the **Class-4-style verification scorecard** (Phase 4, TRD M5, PRD F9) and the
**guided tours** (Phase 4, TRD M7, PRD F12). The
scorecard is the one worth knowing about before the round: it is the feature
PRIOR-ART.md names as one of four defensible claims, and it is the reason the
profile panel no longer has to apologise for the absence of a skill number.

With HazardWatch now in as well, the two halves of the PS's own framing are
both answered: the ocean is drawn, and the danger in it is named. That was the
largest remaining gap against a portal whose theme is Disaster Management.
- [x] F1-F4 minimum: globe + one variable volumetric + depth/time controls +
      colorbar editor + float click-through. All four, and past the minimum:
      six gridded fields (two of them plugin-derived), three rendering
      techniques, depth-resolved currents from a second agency, seven measured
      in-situ parameters and three instrument classes. Verdicts and
      measurements in `docs/P0-STATUS.md`.
- [x] **First agent trick (scripted)** - DONE 9 Sep, and larger than a trick.
      Samudra Sahayak is a separate service on :8010 with 8 tools over the
      public API, a tool trace served with every answer, and a
      no-fabrication guard that WITHHOLDS an answer stating a number no tool
      produced. Deterministic planner, `planner: "rules"` printed everywhere,
      no LLM: PRD section 10 sanctions that and the shape is the one a model
      slots into. 68 tests.
- [x] **SagarNode live** - DONE 10 Sep, everything except the tank. HTTP path
      end to end: `POST /ingest/sagarnode` with per-probe range refusals that
      name the fault, a hollow station mark in its own layer on the globe, a
      panel with the three readings and a temperature trend, and a warm-water
      pour that trips a CAP-shaped alert marked `Exercise`. `curl` is a
      sufficient device, so the whole beat is demoable and tested with no
      hardware: 27 unit tests plus an end-to-end test that empties the log and
      asserts the panel and the mark are ABSENT before it posts anything.
      MQTT is deliberately not built (the HTTP fallback is the one that works
      on a network nobody controls). The sketch is written and marked as never
      having run on a board. **Blocked on the lead: buy the parts**
      (`docs/SAGARNODE-BOM.md`).
- [x] **Density as a derived field (SIG0)** - DONE 11 Sep. Potential density
      anomaly (sigma-0) computed from TEMP and SAL through TEOS-10, the
      international standard, using the `gsw` toolbox the repo already trusted
      for pressure-to-depth. A plugin, so it adds a selectable 3D variable
      with no change to the store and no extra bytes on disk, and it reached
      the OGC WMS and WCS surfaces without a line of OGC code changing. 19
      tests, including reproduction of the published TEOS-10 check values to
      six decimals. It also found that 213 of 225 wet columns in the bay are
      statically unstable, 208 of them in the top 30 m, which is the monsoon
      river plume rather than a defect; the census travels with the field
      instead of being smoothed away.
- [x] **HazardWatch v0** - DONE 9 Sep, and larger than v0. Real CAP v1.2 from
      NDMA SACHET, India's national alert backbone (99 live alerts on the feed
      when it was ingested), plus the three ocean hazards the PS names, authored
      and marked with CAP status `Exercise`. Warning areas on the globe, a panel
      with the ledger of what was withheld and why, and the layer shares the
      field's time axis. Agent narration of a live warning is the part still
      owed, and it belongs with the agent plane rather than here.
- [x] **3-minute internal pitch** - DRAFTED 10 Sep in
      [`docs/PITCH-INTERNAL.md`](PITCH-INTERNAL.md): problem in INCOIS's own
      words, a four-beat demo, the tank, the competition math, and a line each
      for six people. Every figure in it was read off the running service and
      is re-derivable from `docs/P0-STATUS.md`. It also carries the five
      questions to expect with answers, the cut order if the clock runs out,
      and the five things nobody may say on stage.
      **Still owed by the team: five rehearsals with a timer**, which is the
      half a document cannot do.

### Sep 15: the portal submission run

The college moved the internal round to 22 Sep and the mentor cleared us to
submit on the official SIH portal, so the work turned toward the submission
video and toward closing whatever could still be closed.

- [x] **The submission walkthrough tour.**
      `storyboards/00-the-whole-story.tour.json`: 12 steps, 150 seconds, every
      P0 requirement in the order a reviewer meets them. The video is recorded
      by replaying it rather than by performing a demo, so a retake is
      identical. Two tests pin it: one that it still drives every claim
      (isosurface, currents, an opened instrument, the derived density field,
      and the hazard layer appearing ON CUE rather than being on from the
      start), and one that it still fits a portal video. Recording procedure in
      [`docs/VIDEO-RECORDING.md`](VIDEO-RECORDING.md).
- [x] **A scene-patch range guard, written because the tour tripped over it.**
      The scene applies a tour patch verbatim by design, so a value in the
      wrong unit is not clamped, it is rendered: `opacity: 72` (the percentage
      the slider shows) instead of `0.72` (the fraction the store holds) put
      **"LAYER OPACITY 7200%"** on the sheet, and nothing else on screen looked
      wrong enough to notice. It reached a recorded walkthrough. `validate_tour`
      now range-checks opacity, exaggeration and focusDepth and type-checks
      every toggle, with three tests including one that reproduces the 7200%.
- [x] **F2 investigated to exhaustion rather than left as an excuse.** See
      `docs/P0-STATUS.md`. GTSPP's July 2026 Indian Ocean archive holds 5,247
      casts, 211 inside our box, and every one is a moored buoy. Copernicus's
      near-real-time glider feed runs 2026-08-15 to 2026-09-15, which starts
      eleven days after our cube's window closes, and on 1 September it carried
      42 gliders worldwide of which exactly one was in the Indian Ocean, in the
      Mozambique Channel. **There is no Bay of Bengal glider to draw.** The
      clause stays open and the answer is now evidence rather than an apology.
      Deliberately NOT done: ingesting the 211 buoy casts, which would raise the
      instrument count without answering the class the PS names.
- [x] Deliverables refreshed against the new count (567 tests): the six-slide
      idea deck and the four-page mentor brief both rebuilt and re-exported.

## Phase 3 - Idea submission (Sep 16 → 20)
- [ ] 6-slide PDF per SUBMISSION-GUIDE.md; architecture diagram from TRD §1.
      **Words drafted 10 Sep** in [`docs/IDEA-PDF-DRAFT.md`](IDEA-PDF-DRAFT.md):
      all six slides written to the guide's structure, every claim marked
      BUILT or PLANNED, and every built claim carrying a measured number.
      **Still owed: Design and Story sets it in the SIH template, redraws the
      TRD section 1 architecture diagram, and exports the PDF**; and every
      figure is re-run against the running service the day it is exported,
      because a stale number in a submitted PDF cannot be withdrawn.
- [ ] **Check live idea counter on sih.gov.in for SIH26067** - if >~150, convene team, consider backup SIH26176 (max 2 ideas/team allows submitting both - decide deliberately)
- [ ] Submit via SPOC; archive the exact PDF in `docs/submissions/`

## Phase 4 - Full build (21 Sep → 15 Nov)
- [ ] All P0 complete + OGC WMS/WCS endpoints (screening reviewers may probe standards claims)
- [ ] P1: agent tools complete + voice (Bhashini online, ONNX offline) + offline cube build
- [x] Storyboards x4 - DONE 9 Sep, and they double as the agent's patch channel
      (TRD M4's set_scene, with a JSON file in front of it instead of an LLM).
      Three of TRD M7's named tours are blocked on data rather than code: a
      cyclone case study, a west-coast box for the Kerala upwelling, and a
      glider file. Written up in storyboards/README.md.
- [ ] **Scorecard: the remaining half.** The scorecard itself shipped early (see
      Phase 2). What is still owed here is M5's VALIDATION clause: reproduce a
      published model-versus-Argo comparison number within tolerance, so the
      method is checkable against someone else's arithmetic and not only against
      our own. Also owed: the depth-by-time residual heatmap and CSV export.
- [ ] CI: Playwright demo-path test green online AND with `OFFLINE=1`
- [ ] Stakeholder outreach: email 3-5 INCOIS scientists / phys-ocean professors with a demo video; log feedback (mention on stage)

## Phase 5 - Finale prep (15 Nov → GF)
- [ ] Results of screening → if selected, book travel early; if not selected, retro + archive (the platform is still a flagship portfolio project)
- [ ] Demo laptop + identical spare, both tested offline; fallback video recorded
- [ ] Pitch: 10-min power-round script (PRD §11) rehearsed ≥5×, every member speaks; judge Q&A drill (PRD §10)
- [ ] Pivot drills: add-a-variable in <30 min; swap LLM provider; slices-only fallback
- [ ] Financial slide numbers finalized (BlazeBrains pattern)

## Phase 6 - Grand Finale (36h)
Execute TRD §7 hour-by-hour plan. Rules of engagement: implement ≥1 judge suggestion per mentoring round; task board visible; code freeze T-2h; sleep in shifts (2 awake minimum); beginners run the test checklist after every merge.
