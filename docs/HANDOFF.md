# HANDOFF — Read this first (for the new agent & every teammate)

You are joining **SagarDrishti**, our entry for **Smart India Hackathon (SIH) 2026**, problem statement **SIH26067** (Ministry of Earth Sciences / INCOIS). This file is the complete context of how we got here and how we intend to win. Read it before touching anything. Companion docs: `PRD.md` (what & why), `TRD.md` (how), `ROADMAP.md` (when), `TEAM-ROLES.md` (who), `SUBMISSION-GUIDE.md` (the 6-slide idea PDF).

## 1. What SIH is (mechanics that matter)

- National hackathon by MoE/AICTE. 9th edition, launched **21 Aug 2026**: 226 problem statements (172 software / 54 hardware) from 30 ministries/PSUs.
- Funnel: **internal college hackathon** → SPOC nominates teams (~25–30 per institute) → **idea submission by 20 Sep 2026** (6-slide PDF, max 2 ideas/team, cap 500 ideas/PS with a live public counter on sih.gov.in) → national screening by the sponsoring ministry → **Grand Finale ~Dec 2026** (36h software build at a nodal centre) → typically 1 winner per PS (₹1,00,000–1,50,000; sometimes 2 joint winners).
- Team: exactly 6 students, same institute, ≥1 female member, 2 mentors.
- GF structure: **3 unscored mentoring rounds + 3 scored evaluation rounds + a decisive "power round" final demo.** Judges come from the sponsoring ministry.

## 2. Why we chose SIH26067 (the evidence)

We read **all 172 software PS** in full, analyzed **322 SIH 2025 winners** and **315 SIH 2024 winners**, and mined winner write-ups and community intel. Key findings:

1. **PS selection is a 10x odds lever.** Flooded PS hit the 500-idea cap (~1.2% odds to reach GF); niche PS get 30–50 ideas (~15%). SIH26067 has no AI buzzwords in the title and needs NetCDF+WebGL skills → predicted low competition. **Action standing:** re-check the live counter before 20 Sep; if SIH26067 crosses ~150 ideas, escalate to backup **SIH26176** (ISRO ORCA multi-agent marine assistant — full analysis in our research notes).
2. **Deployment-readiness beats novelty.** 2025 winners integrated with real govt systems by name. SIH26067 *is* an internal INCOIS tool request — our deployment story is native.
3. **Offline/air-gapped demos keep winning** (offline translation, offline SAR analytics, offline-first advisory all won in 2025). Our entire demo runs with WiFi off.
4. **Winners ship a quantified output**, not just pictures — ours is the model-vs-observation RMSE scorecard.
5. **Mid-finale pivots decide winners** (in 2025, NTRO changed data rules mid-finale; the team that rebuilt overnight won). Our architecture isolates swappable parts (`sources.yaml`, provider adapters, detachable agent plane).
6. **Institute prestige is irrelevant** — IITs/NITs were <10% of 2025 winners. Execution + PS choice decide.
7. MoES posted 27 software PS in 2026 and produced 10 winners in 2025 → engaged ministry, many slots.

## 3. The idea in one paragraph

A browser-native **3D digital twin of India's ocean**: INCOIS numerical model fields (temperature, salinity, currents, chlorophyll) rendered volumetrically on a Cesium globe, fused with **real Argo float / glider observations** you can click into; a **model-vs-reality RMSE scorecard**; and **Samudra Sahayak**, an LLM agent that flies the camera, slices the water column, runs comparisons and generates cited PDF briefs — on **voice command in Indian languages** (Bhashini). Everything also runs **fully offline** from a preloaded ocean cube. P0 features map 1:1 to the PS's written requirements; the agent + scorecard + voice are our ≥30% uniqueness on top.

## 4. Non-negotiables (learned from winners — do not violate)

1. **Ship every P0 requirement before polishing any P1.** Screening reviewers grade against their own PS text.
2. **The demo must run offline**, on our laptop, with a recorded video as last-ditch fallback.
3. **Write down every judge/mentor suggestion at GF and visibly implement at least one per round.** Judges' modifications outrank our original plan.
4. **Numbers in the pitch**: license cost ₹0, one GPU server, time-to-insight <30 s, RMSE reproduced against published reference, FPS on stage.
5. **Code freeze at T-2h** in the finale. No exceptions.
6. **Beginners own real deliverables** (storyboards, UI content, testing, pitch) from day 1 — six people must visibly contribute; judges ask members questions individually.
7. **Contact real stakeholders before the finale** (INCOIS scientists, oceanography professors) — winners did stakeholder validation and said so on stage.

## 5. Current state & next actions

- **Done (as of Sep 7, 2026):** research + PS selection (user-approved); PRD/TRD/ROADMAP/TEAM-ROLES/SUBMISSION-GUIDE; repo created at **D:\Projects\SagarDrishti** with this pack in `docs/`; mentor-directed **prior-art & literature review → docs/PRIOR-ART.md** (read it before claiming anything is "new"); PS re-verified live — INCOIS changed the theme to **Disaster Management** and added official dataset links (in TRD §3, ★ rows); live counter Sep 7: **SIH26067 = 0/500**, early flood is hitting our predicted trap PS.
- **Sep 7 additions (mentor directives):** **F13 HazardWatch** CAP-based disaster-warning layer (PRD §5, TRD M8) and **SagarNode** ESP32 live-sensor mini-rig for the internal round (PRD §5, TRD M9, ~₹1.6–3k).
- **Next:** (1) execute ROADMAP Phase 1 spikes (volumetric NetCDF render in browser; `sources.yaml` ingestion skeleton; profile chart); (2) order SagarNode parts NOW (delivery lead time); (3) confirm internal-hackathon date with SPOC; (4) alpha before the internal round; (5) idea PDF per SUBMISSION-GUIDE.md, submit via SPOC before **20 Sep 2026**; re-check the idea counter Sep 15 & 19.

## 6. Research sources (verify claims here)

- Official: sih.gov.in (PS list `/sih2026PS`, guidelines PDF `/letters/2026/SIH 2026 Guidelines.pdf`, results `/sih2025/sih2025-grand-finale-result`, `/sih2024/sih2024-grand-finale-result`)
- PS dataset mirror: github.com/vedantchalke36/sih-2026-problem-statements
- Winner write-ups & tactics: dev.to/macroandmicro (500 vs 30-idea spread), dev.to/ishikajain (stakeholder outreach, 30% uniqueness), hashnode BlazeBrains (financials in pitch), medium GDSC-BITW (500-cap + counter mechanics), educationworld.in (Team Waterloo/NTRO pivot story), somaiya.edu.in (Team nyx/Railways), mitaoe.ac.in (offline translation winner), greaterkashmir.com (NAMASTE↔ICD-11 winner), lords.ac.in, kgkite.ac.in, avenuemail.in (PM-AJAY winner)
- Data sources (verified live 24 Aug 2026): erddap.incois.gov.in · las.incois.gov.in · data-argo.ifremer.fr · argovis.colorado.edu · data.marine.copernicus.eu · ncei.noaa.gov/erddap — plus the PS's own official dataset links added by INCOIS post-launch (TRD §3 ★ rows, read 7 Sep 2026)
- Prior-art systems, literature (15 works), gap analysis, judge answers, hardware BOM, CAP/warning grounding: **docs/PRIOR-ART.md** (all with source URLs)
