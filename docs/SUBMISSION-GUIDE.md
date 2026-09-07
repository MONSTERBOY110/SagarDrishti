# SUBMISSION-GUIDE — The 6-Slide Idea PDF (deadline 20 Sep 2026)

**Format rules (official):** exactly the SIH template structure, exported as **PDF only** (no PPT/DOC), submitted via your college SPOC after internal-round selection. Max 2 ideas per team. Reviewers are from **MoES/INCOIS** — write for oceanographers, not for a general audience.

**Screening criteria (published):** novelty · complexity · clarity & detail in the prescribed format · feasibility & practicability · sustainability · scale of impact · user experience · future work potential. Evidence from past cycles: *incomplete documentation eliminates strong ideas* and *diagrams carry the feasibility argument*.

---

## Slide 1 — Problem statement details
- PS ID SIH26067, exact title, org (MoES/INCOIS), category Software, theme, team name/ID.
- One line of intent: "A browser-native 3D digital twin of India's ocean, fusing INCOIS model fields with Argo/Glider observations, driven by a multilingual voice AI agent — fully deployable on INCOIS infrastructure."

## Slide 2 — Proposed solution (innovation & uniqueness)
- 3 bullets mapping to the PS's 5 stated gaps (quote their phrases: "single interactive environment", "depth-resolved volumetric views", "without significant re-engineering").
- **Uniqueness block (the ≥30%):** (1) Samudra Sahayak — an agent that *operates the 3D scene itself* and cites datasets; (2) **Class-4-style** model-vs-observation scorecard (quantified model skill — today those metrics live only in offline PDF reports, per PRIOR-ART.md); (3) **HazardWatch** CAP-based disaster-warning layer (theme = Disaster Management); (4) multilingual voice via Bhashini; (5) fully offline demo cube; (6) live extensibility proof — the **SagarNode** physical sensor station streams onto the globe (PS's "future sensor integration" requirement, demonstrated). One hero mock image of the Bay of Bengal volumetric view (Design owner produces; screenshots from the alpha are 10× better than mockups).
- Positioning line (from PRIOR-ART.md): "Desktop tools (pyParaOcean, IDV) have volumetrics without the web; web viewers (MyOcean, Argovis) have the web without volumetrics; Copernicus's own roadmap puts their 3D globe at Jan 2027. SagarDrishti occupies the empty intersection — for the Indian Ocean."

## Slide 3 — Technical approach
- The TRD §1 architecture diagram, redrawn clean (this slide wins or loses screening).
- Stack line: Next.js + CesiumJS/deck.gl (WebGL2) · FastAPI + xarray/zarr · OGC WMS/WCS + CF conventions · LLM tool-calling + Bhashini/AI4Bharat · Docker.
- Flow: NetCDF/ASCII → registry → zarr → REST/OGC → 3D scene ⇄ agent. Mention "PS-suggested Three.js/Cesium adopted" — reviewers wrote that suggestion.

## Slide 4 — Feasibility & viability
- Data proof: name the live sources (INCOIS ERDDAP/LAS, Argo GDAC, Copernicus Marine) — all open, all verified.
- Working-prototype line: by submission date we will have the Phase-2 alpha — say so and include a QR link to a 60-second demo video (winners did this; it converts).
- Risks & mitigations (3 max): render performance → LOD + slice fallback; data outages → offline cube; scope → P0/P1 split with P0 = the PS's own requirement list.

## Slide 5 — Impact & benefits
- **Disaster management (the PS theme — lead with it):** faster hazard assessment via model-vs-obs checks; HazardWatch renders INCOIS multi-hazard warnings (CAP, the same protocol behind NDMA's SACHET) in their 3D ocean context — from bulletin text to visual situational awareness.
- Operational: minutes→seconds model-vs-obs checks for hazard/SAR/fishery advisories (INCOIS's stated mandates); one deployment serves the nation.
- Social/outreach: the PS's own education mandate — storyboard mode for schools/exhibitions; voice in Indian languages widens access.
- Economic: ₹0 licenses (fully open-source) vs. proprietary 3D suites; runs on one commodity GPU server; alignment with Deep Ocean Mission / Blue Economy / SAGAR.

## Slide 6 — Research & references (pull from PRIOR-ART.md — must-cite ★ list)
- SIH26067 text (sih.gov.in/sih2026PS) · INCOIS Digital Ocean portal (prior art we extend, not duplicate) · **Qin et al. 2021 EMS** (web 3D ocean viz) · **Yu et al. 2025 Appl. Sci.** (WebGPU ocean volume rendering) · **Ryan et al. 2015 JOO** (GODAE Class-4 verification — our scorecard methodology) · **Tucker et al. 2020 JTECH** (Argovis) · **Wong et al. 2020 Frontiers** (Argo QC) · **Balakrishnan Nair et al. 2013 Current Science** (INCOIS OSF validation — Indian precedent) · **pyParaOcean (IISc, CGF 2025)** (desktop volumetrics we bring to the browser) · **Tzachor et al. 2023 npj** (digital twins of the ocean) · FathomGPT UIST 2024 (NL ocean-data interface) · CF Conventions + OGC WMS/WCS + CAP v1.2 · Bhashini/AI4Bharat · Albaladejo et al. 2012 *Sensors* (low-cost buoy — grounds SagarNode).
- A 12–15-entry annotated bibliography exists in docs/PRIOR-ART.md if reviewers ask for depth.

---

## Checklist before SPOC submission
- [ ] Every slide ≤ ~80 words + one visual; no walls of text
- [ ] PDF export checked on a second machine (fonts, diagram legibility at 100%)
- [ ] PS phrases quoted verbatim at least 3 times across slides 2–4
- [ ] Demo-video QR tested from a phone
- [ ] Live idea counter for SIH26067 checked and screenshotted (decision log)
- [ ] Second idea slot: decide deliberately whether to also submit backup PS SIH26176 (max 2 ideas/team)
- [ ] Team roster: 6 members, ≥1 female, names exactly as in college records
- [ ] Verification flags from PRIOR-ART.md cleared: do.incois.gov.in screenshot taken; Copernicus 3D-viewer roadmap date re-checked; Resch 2014 + deck.gl author lists verified before printing
