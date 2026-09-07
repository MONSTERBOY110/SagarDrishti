# ROADMAP — SagarDrishti (Aug 2026 → Dec 2026)

Dates anchored to: idea deadline **20 Sep 2026** · Grand Finale **~8–12 Dec 2026** (2025 pattern; confirm when announced).

## Phase 0 — Team & repo — ✅ DONE Sep 7 (repo D:\Projects\SagarDrishti, docs moved, PRIOR-ART.md added; mentor onboarded)
- [x] Repo created; doc pack in `docs/`; prior-art & literature review done (docs/PRIOR-ART.md)
- [ ] Brief the team with HANDOFF.md + PRD.md; confirm 6-member roster (≥1 female) + 2 mentors; register per SPOC instructions
- [ ] **Confirm internal-hackathon date with college SPOC (URGENT — decides Phase 1 pace)**
- [ ] Everyone reads the PS 5×; each member writes a 3-line paraphrase (catches misreadings early — winner tactic)
- [ ] **Order SagarNode parts NOW** (ESP32, DS18B20 waterproof, TDS, turbidity — BOM in PRIOR-ART.md §F / TRD M9; delivery lead time is the risk)

## Phase 1 — Proof spike (Sep 7 → 11)
Goal: kill the two technical risks before the internal round.
- [ ] Spike A (lead): one NetCDF timestep → depth-sliced volumetric render in Cesium+deck.gl at ≥30 FPS
- [ ] Spike B (70% dev): `sources.yaml` walking skeleton — Argo GDAC + one GLORYS12/INCOIS field (PS-official ★ sources, TRD §3) → zarr → `/field` + `/profiles` endpoints
- [ ] Spike C (50% dev): clicked float → ECharts profile chart from real data
- [ ] Beginners: collect cyclone case-study material (IMD best track + dates); draft storyboard scripts; set up test checklist; SagarNode wiring on arrival
- [ ] Decision gate: if FPS floor unreachable → slices-only mode is the plan (TRD §6.4), not a crisis

## Phase 2 — Internal-hackathon alpha (Sep 11 → 16, compress if internal round is earlier)
Goal: walk into the internal round with the only live 3D demo in the college — plus hardware on the table (mentor's advice).
- [ ] F1–F4 minimum: globe + one variable volumetric + depth/time controls + colorbar editor + float click-through
- [ ] First agent trick (scripted): "fly to Bay of Bengal and show 100 m temperature" via tool-calling
- [ ] **SagarNode live**: tank → ESP32 → MQTT/HTTP → glyph on globe + trend chart; warm-water pour trips a CAP-shaped alert (TRD M9)
- [ ] **HazardWatch v0**: one CAP-style warning polygon rendered + agent narration (TRD M8)
- [ ] 3-minute internal pitch: problem (INCOIS's own words) → live demo incl. hardware beat → win-evidence (competition math) → team roles

## Phase 3 — Idea submission (Sep 16 → 20)
- [ ] 6-slide PDF per SUBMISSION-GUIDE.md; architecture diagram from TRD §1
- [ ] **Check live idea counter on sih.gov.in for SIH26067** — if >~150, convene team, consider backup SIH26176 (max 2 ideas/team allows submitting both — decide deliberately)
- [ ] Submit via SPOC; archive the exact PDF in `docs/submissions/`

## Phase 4 — Full build (21 Sep → 15 Nov)
- [ ] All P0 complete + OGC WMS/WCS endpoints (screening reviewers may probe standards claims)
- [ ] P1: agent tools complete + voice (Bhashini online, ONNX offline) + RMSE scorecard validated against published reference + offline cube build + storyboards ×4
- [ ] CI: Playwright demo-path test green online AND with `OFFLINE=1`
- [ ] Stakeholder outreach: email 3–5 INCOIS scientists / phys-ocean professors with a demo video; log feedback (mention on stage)

## Phase 5 — Finale prep (15 Nov → GF)
- [ ] Results of screening → if selected, book travel early; if not selected, retro + archive (the platform is still a flagship portfolio project)
- [ ] Demo laptop + identical spare, both tested offline; fallback video recorded
- [ ] Pitch: 10-min power-round script (PRD §11) rehearsed ≥5×, every member speaks; judge Q&A drill (PRD §10)
- [ ] Pivot drills: add-a-variable in <30 min; swap LLM provider; slices-only fallback
- [ ] Financial slide numbers finalized (BlazeBrains pattern)

## Phase 6 — Grand Finale (36h)
Execute TRD §7 hour-by-hour plan. Rules of engagement: implement ≥1 judge suggestion per mentoring round; task board visible; code freeze T-2h; sleep in shifts (2 awake minimum); beginners run the test checklist after every merge.
