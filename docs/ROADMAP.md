# ROADMAP - SagarDrishti (Aug 2026 → Dec 2026)

Dates anchored to: idea deadline **20 Sep 2026** · Grand Finale **~8-12 Dec 2026** (2025 pattern; confirm when announced).

> **Re-baseline, 7 Sep 2026.** The internal-hackathon date is still unconfirmed
> by the SPOC, so every date below is planned against the **worst case of
> Sep 12**, and each Phase 1 spike was built to be independently demoable - an
> earlier date cannot strand us mid-feature. Trigger conditions: a confirmed
> date **before Sep 12** cuts Spike A to slices-only and moves straight to
> alpha; a date **after Sep 20** makes Phase 3 (the idea PDF) preempt alpha
> polish. Idea-counter re-checks stay on **Sep 15** and **Sep 19**
> (sih.gov.in/sih2026PS, SIH26067 - escalate if >~150).

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
| **Copernicus Marine credentials** | GLORYS12 is the only source with **depth-resolved currents**, so PRD F1's current-vector layer is blocked without it | `glorys12` sits in `sources.yaml` with `enabled: false`; enabling is a config edit + `.env` |
| **p1 frame time (23 FPS)** | Median is fine; the 1-in-100 frame still stutters, and 60 FPS target is not met | Re-measure on a production build and the discrete RTX 3050 before any FPS number goes on a slide |
| **`docker compose up` unverified** | PS requirement F5 is a screening claim | Docker not installed on the build machine (`adr/0004`); compose files authored, marked unexecuted |
| **1° / 10-day source resolution** | Coarse for a hero shot | Honest framing on stage; GLORYS12 at 1/12° is the visual upgrade |
| **Fonts are latin-subset only** | PRD requires Hindi, Telugu and Tamil, and both vendored faces carry latin glyphs only, so Devanagari, Telugu and Tamil text would fall back to a system font | Add Noto Sans Devanagari/Telugu/Tamil subsets in Phase 2 alongside the voice layer, when there is finally multilingual text to set. Flagged by the design documenter 2026-09-07. |

## Phase 2 - Internal-hackathon alpha (Sep 11 → 16, compress if internal round is earlier)
Goal: walk into the internal round with the only live 3D demo in the college - plus hardware on the table (mentor's advice).
- [ ] F1-F4 minimum: globe + one variable volumetric + depth/time controls + colorbar editor + float click-through
- [ ] First agent trick (scripted): "fly to Bay of Bengal and show 100 m temperature" via tool-calling
- [ ] **SagarNode live**: tank → ESP32 → MQTT/HTTP → glyph on globe + trend chart; warm-water pour trips a CAP-shaped alert (TRD M9)
- [ ] **HazardWatch v0**: one CAP-style warning polygon rendered + agent narration (TRD M8)
- [ ] 3-minute internal pitch: problem (INCOIS's own words) → live demo incl. hardware beat → win-evidence (competition math) → team roles

## Phase 3 - Idea submission (Sep 16 → 20)
- [ ] 6-slide PDF per SUBMISSION-GUIDE.md; architecture diagram from TRD §1
- [ ] **Check live idea counter on sih.gov.in for SIH26067** - if >~150, convene team, consider backup SIH26176 (max 2 ideas/team allows submitting both - decide deliberately)
- [ ] Submit via SPOC; archive the exact PDF in `docs/submissions/`

## Phase 4 - Full build (21 Sep → 15 Nov)
- [ ] All P0 complete + OGC WMS/WCS endpoints (screening reviewers may probe standards claims)
- [ ] P1: agent tools complete + voice (Bhashini online, ONNX offline) + RMSE scorecard validated against published reference + offline cube build + storyboards ×4
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
