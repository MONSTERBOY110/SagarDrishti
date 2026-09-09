# SagarDrishti — Smart India Hackathon 2026 (PS SIH26067, MoES/INCOIS)

Browser-native 3D digital twin of the Indian Ocean: INCOIS model fields (NetCDF) rendered volumetrically on a Cesium globe, fused with live Argo/Glider observations, a Class-4-style model-vs-obs RMSE scorecard, a CAP-based disaster-warning layer (HazardWatch), an ESP32 live-sensor station (SagarNode), and "Samudra Sahayak" — an LLM agent that controls the 3D scene by voice (Bhashini) with cited, tool-derived numbers only.

**This is a competition entry. The goal is to WIN. Every decision optimizes for: screening reviewers (MoES/INCOIS oceanographers), internal-round judges, and the 36h grand-finale power round.**

## Read these docs in order (docs/)
1. `HANDOFF.md` — how we got here, competition mechanics, non-negotiables
2. `PRD.md` — features P0/P1/P2, demo script, judge Q&A, timeline
3. `TRD.md` — architecture, stack, module specs M1–M9, repo layout (§8), 36h plan
4. `PRIOR-ART.md` — what exists, gap analysis, methodology adoptions (§E), framing rules
5. `ROADMAP.md` — current phase and dates · `TEAM-ROLES.md` — who owns what · `SUBMISSION-GUIDE.md` — the 6-slide idea PDF

## Hard rules
- **P0 before P1, always.** P0 = the PS's own requirement list (PRD §5). Nothing gets polished while a P0 item is missing.
- **Offline-first**: every feature must work with `OFFLINE=1` (local zarr cube, local LLM, local STT/TTS) — the demo runs air-gapped.
- **The agent never computes or invents numbers** — numbers enter answers only via tool results, with dataset + timestamp + float WMO ID citations.
- **Never claim "no 3D exists at INCOIS"** — their Digital Ocean portal claims 3D/4D. Framing rules in PRIOR-ART.md (top).
- **TDD on the data plane** (parsers, colocation math, colorbar mapping — CF edge cases: scale_factor, _FillValue, depth-positive-down). Verify before claiming done: run it, show output.
- **No scope changes without the team lead's explicit approval.** Backup PS (SIH26176) escalation only if the SIH26067 idea counter exceeds ~150 (check sih.gov.in/sih2026PS).
- Repo layout is TRD §8 — create it as specified (apps/web, services/api, services/agent, packages/scene, data/, firmware/sagarnode, tools/, storyboards/).
- Say "conductivity-derived salinity proxy," never "salinity sensor," for the TDS probe.

## Key dates (2026)
Idea PDF via college SPOC: **Sep 20** · Internal college hackathon: **Wed 16 Sep** (confirmed by the lead 9 Sep) · Grand finale: ~Dec (per 2025 pattern). Counter re-checks: Sep 15 & 19.

## Environment notes
- Windows 11, PowerShell primary. Python is `python` (not `python3`). Prefer `uv` for Python env if available.
- Demo laptop is the performance target: ≥60 FPS goal / 30 floor at 1080p (budgets in TRD §5).
