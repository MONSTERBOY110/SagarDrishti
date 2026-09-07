# PRD — SagarDrishti (सागर दृष्टि): Digital Twin of the Indian Ocean

**Problem Statement:** SIH26067 — "Develop a web-based interactive 3D visualization platform that integrates numerical ocean model outputs and in-situ observations"
**Organization:** Ministry of Earth Sciences (MoES) / INCOIS (Indian National Centre for Ocean Information Services, Hyderabad)
**Category:** Software · **Theme (portal):** **Disaster Management** (INCOIS updated the PS post-launch; August snapshot said "Smart Automation") · **Idea deadline:** 20 September 2026
**Team:** 6 members (≥1 female, per SIH rules) · **Working name:** SagarDrishti · **Agent persona:** Samudra Sahayak

---

## 1. One-liner

> A browser-native 3D digital twin of India's ocean — INCOIS's numerical model fields and live Argo/Glider observations rendered volumetrically in one interactive scene — with an embodied AI agent that flies the camera, slices the water column, compares model vs. reality, and explains what it sees, on voice command in Indian languages.

**Name rationale:** "SagarDrishti" (Ocean Vision) deliberately echoes the PM's **SAGAR doctrine** (Security and Growth for All in the Region) and MoES's **Deep Ocean Mission / Samudrayaan**. Ministry judges notice policy-aligned naming.

---

## 2. The problem (from the PS, verbatim gaps)

INCOIS generates 3D ocean model outputs (temperature, salinity, currents, chlorophyll — NetCDF) and in-situ observations (Argo floats, Gliders, CTD, BGC — NetCDF/ASCII) daily. INCOIS's own words in the PS:

- "**No integrated, web-based 3D visualization platform currently exists** that can simultaneously render model fields and in-situ instrument observations in a single interactive environment."
- Existing tools are "desktop-bound, support only 2D plan views, or lack the ability to co-visualize model outputs alongside instrument profiles."
- Forecasters are "forced to toggle between disparate software packages."
- This "impedes timely hazard assessment, search-and-rescue support, fishery advisories, climate monitoring — all operational mandates of INCOIS."

The PS names five explicit gap areas: (1) no web 3D volumetric rendering, (2) no unified Argo/Glider display alongside model fields, (3) no interactive variable/depth/time/colorbar controls, (4) no re-engineering-free ingestion of new data streams, (5) no tools for rapid intuitive understanding of 3D ocean phenomena.

**Read the PS 20 times. Every feature below maps to a numbered requirement in it.**

## 3. Why this PS (evidence-based win strategy)

| Factor | Evidence |
|---|---|
| **Competition** | Idea cap is 500/PS with a live public counter; flooded PS (agri-AI, edtech, chatbots) hit 500 → ~1.2% screening odds; niche PS get 30–50 ideas → ~15% odds. SIH26067 has zero AI buzzwords in its title and demands NetCDF + WebGL skills most teams lack → predicted low competition. **Verified Sep 7: SIH26067 = 0/500, while the early flood leads exactly on our trap-list PS.** Re-check the counter ~Sep 15 and Sep 19; if >~150 ideas, escalate to backup PS SIH26176. |
| **Ministry engagement** | MoES posted 27 software PS this year (they want solutions) and produced 10 winners in SIH 2025. |
| **Deployment-readiness wins** | 2025 winners integrated with real govt systems by name (NAMASTE↔ICD-11; PM-AJAY). Our PS *is* an internal INCOIS tooling request — the deployment story is built in. The PS even specifies "deployable on INCOIS infrastructure without client-side dependencies." |
| **Demo theatre** | 3D volumetric ocean + voice-driven agent camera is a demo no other team at the nodal centre will have. Judges cited "live working demonstration" as decisive (power round). |
| **Team fit** | Zero ML-model-training risk. Core work = data pipeline + WebGL + agent orchestration (lead's proven skills). Beginners contribute real work (UI, colormaps, scenario content, testing, pitch). |

## 4. Users & stakeholders

1. **INCOIS operational forecasters** (primary; the PS authors) — rapid model-vs-observation correlation for advisories.
2. **Disaster managers** (cyclone/high-wave/tsunami advisory consumers; INCOIS runs the national Tsunami Early Warning Centre).
3. **Search-and-rescue coordinators** (Coast Guard/Navy use INCOIS SAR-drift aids) — current fields at depth matter.
4. **Fishery advisory services** (PFZ advisories to ~9 lakh fisherfolk households).
5. **Ocean researchers & students** — the PS explicitly calls out public outreach, education, exhibitions, e-learning.
6. **Policymakers** — Blue Economy / Deep Ocean Mission communication.

## 5. Product scope & features

### P0 — Core (every explicit PS requirement; non-negotiable for screening)

| # | Feature | PS requirement it satisfies |
|---|---|---|
| F1 | **3D volumetric rendering** of model fields (temperature, salinity, current vectors, chlorophyll) over the full water column: depth-slice views, isosurface extraction, time-step animation | "3D Volumetric Rendering … WebGL / Three.js or Cesium.js" |
| F2 | **Instrument overlay**: Argo floats, Gliders, CTD, BGC as geospatially accurate clickable markers → depth-vs-variable profile chart with timestamps | "Instrument Data Overlay" |
| F3 | **Multi-format ingestion**: automated NetCDF (xarray) + delimited-text parsers; modular source registry so a new variable/source is a config entry, not a rewrite | "Multi-format Data Ingestion" |
| F4 | **Controls**: dynamic colorbar editor (palette, min/max, log/linear), variable selector, layer opacity, **vertical exaggeration slider**, depth navigation, time scrubber | "Customizable Colorbar & Variable Controls" |
| F5 | **Web-scale architecture**: modern JS frontend + lightweight REST/OPeNDAP-compatible API; no client-side installs; deployable on INCOIS infra (Docker) | "Web-based, Scalable Architecture" |
| F6 | **Plugin extensibility**: documented plugin interface for future sensors (moorings, HF-radar, ADCP) and ML-derived products | "Extensible Design" |
| F7 | **Open standards**: OGC WMS/WCS endpoints; CF-convention NetCDF compliance | "open standards (OGC WMS/WCS, CF Conventions)" |

### P1 — Differentiators (the uncommon 30%+ that wins)

| # | Feature | Why it wins |
|---|---|---|
| F8 | **Samudra Sahayak — embodied scene agent**: LLM agent with tools to fly the camera, select variables/depths/times, extract isosurfaces, run model-vs-float comparisons, and generate cited PDF reports. Ask: *"Show me the thermocline near the Andamans during Cyclone Mocha"* → the camera dives, slices, overlays the track, cites the Argo profiles used. | No student team will fuse volumetric WebGL with an agentic controller. Positions against the PS's own "ML-derived products" extensibility clause. |
| F9 | **Model-vs-observation scorecard**: automatic RMSE/bias between model fields and co-located Argo/Glider profiles, per region/depth/time — a quantified output, not just pictures. | 2025 winners always shipped a quantified metric (e.g. "volume of ore removed"). This is the forecaster's actual daily question: *can I trust today's model run?* |
| F10 | **Voice, multilingual**: agent accepts Hindi/Telugu/Tamil/English speech (Bhashini / AI4Bharat), answers with narrated summaries. | Inclusion features are scored; ties to lead's proven vernacular-voice strength; supports the PS's outreach mandate. |
| F11 | **Offline/air-gapped demo mode**: preloaded Bay-of-Bengal + Arabian Sea data cube; the entire demo runs with WiFi off. | Recurring 2025 winner trait; also survives nodal-centre network failure (a documented team-killer). |
| F12 | **Scenario storyboards**: curated case studies (a cyclone's cold wake, monsoon-onset upwelling, an eddy carrying a glider) as one-click guided tours — doubles as the outreach/education mode the PS requests. | Beginners build these; judges remember stories, not sliders. |
| F13 | **HazardWatch — disaster-warning layer**: INCOIS multi-hazard advisories (tsunami / high wave / swell surge) rendered as **CAP-style warning polygons** on the globe (severity→color), an active-warnings banner, threshold-based alerts, and the agent narrating any live warning ("high-wave warning active off Kerala coast — here is the wave field driving it") with a camera fly-to. | The PS's portal theme IS **Disaster Management**, and "timely hazard assessment" is the PS's first stated mandate. INCOIS is a UNESCO-IOC Tsunami Service Provider using CAP (NDMA SACHET is India's CAP backbone) — speaking CAP is speaking their language. See PRIOR-ART.md §D. |

### P2 — Stretch (only if GF time allows)

- Shareable scene-state URLs (deep links reproducing exact view/time/variable).
- WebXR mode (walk through the water column) for the exhibition/outreach story.
- HF-radar/ADCP plugin demo proving F6 in front of judges.
- Comparison A/B of two model runs (forecast bust analysis).

### Internal-round special — "SagarNode" hardware mini-rig (mentor directive)

A tabletop **live underwater sensor station**: ESP32 + waterproof DS18B20 temperature probe + TDS (conductivity-derived **salinity proxy** — never say "salinity sensor") + turbidity sensor in an aquarium/bucket. Streams 1 Hz readings over MQTT (HTTP POST fallback — campus WiFi often blocks port 8883) → appears on the SagarDrishti globe as a **live "virtual mooring"** at the college's coordinates with a real-time profile/trend chart. Pour in warm/salty water → thresholds trip → a **CAP-shaped local alert** fires in HazardWatch and Samudra Sahayak narrates it and flies the camera there.

- **Why it's not scope creep:** the PS's own "Extensible Design" requirement lists "future integration of additional sensors (CTDs, moorings…)" — SagarNode is that requirement *demonstrated live with physical hardware*. It gives internal-round judges something to touch, per mentor's advice.
- **Budget:** ≈ ₹1,650 (clone parts) – ₹3,000 (branded) — verified Indian retail prices and citable low-cost-buoy literature in PRIOR-ART.md §F.
- **Owners:** Beginners 2 & 3 + Analytics dev (50%); wiring is 3 components on a breadboard. Low-voltage USB only; probe in water, electronics outside.
- **Honesty rule for the pitch:** the sensor alert is a *pedagogical stand-in* for INCOIS's real hazard products, and we say so explicitly.

### Out of scope (say no — YAGNI)

- Training any ocean-forecast ML model (we visualize model output; we don't compete with INCOIS's models).
- Mobile-native apps; general-purpose GIS features; user management beyond basic roles.

## 6. Impact & government-approval story

- **Operational:** minutes-not-hours correlation of model vs. observation → faster, more confident advisories (hazard, SAR, PFZ) — INCOIS's own stated mandates.
- **National alignment:** Deep Ocean Mission (₹4,077 cr), Blue Economy policy, SAGAR doctrine, PM's "Viksit Bharat 2047" science communication push. INCOIS's existing "Digital Ocean" portal proves the ministry funds this direction; SagarDrishti is its missing browser-native 3D layer.
- **Public value:** the same engine powers outreach exhibitions, schools and e-learning (explicitly requested in the PS) — one platform, two mandates.
- **Financial slide (BlazeBrains pattern — give judges numbers):** built on 100% open-source (₹0 license vs. proprietary 3D viz suites); runs on one commodity GPU server INCOIS already owns; incremental cost ≈ maintenance manpower only; national scale = one deployment (it's a central web tool).

## 7. Success metrics

**Product:** time-to-insight for a model-vs-float check (baseline: multi-tool minutes → target: <30 s); ≥60 FPS scene at 1080p on integrated GPU (30 FPS floor); <3 s first render of a preloaded region; RMSE scorecard reproducible against a published reference profile.
**Competition:** clear internal-round selection → idea PDF scoring hits every published screening criterion → GF: implement ≥1 judge-suggested change per mentoring round (documented) → power-round demo executes 100% offline.

## 8. Timeline

| Date | Milestone |
|---|---|
| Sep 7–10 | Repo live (done Sep 7: docs in D:\Projects\SagarDrishti), 3D + pipeline spikes (prove volumetric NetCDF render in browser), SagarNode parts ordered |
| Sep 10–16 | Working alpha (F1–F4 partial) + SagarNode streaming + a first HazardWatch overlay — needed to dominate the **internal college hackathon** (confirm its date with SPOC NOW) |
| Sep 16–20 | 6-slide idea PDF (see SUBMISSION-GUIDE.md) + SPOC submission; **re-check live idea counter (Sep 15/19)** |
| Oct–Nov | Full P0 + P1 build, INCOIS-real-data hardening, offline cube packaging, pitch rehearsals, stakeholder outreach (email INCOIS scientists/professors of physical oceanography for feedback — winners contacted domain experts) |
| Dec (GF) | 36-hour finale execution per TRD build plan; code freeze T-2h |

## 9. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| PS floods unexpectedly (>150 ideas) | Low | Live counter watch before Sep 20; backup PS SIH26176 (ORCA) pre-analyzed |
| Volumetric rendering perf on judge hardware | Medium | Adaptive LOD; precomputed tiles; 30 FPS floor mode; demo laptop is ours |
| INCOIS ERDDAP/LAS downtime during demo | Medium | F11 offline cube — demo never touches the network |
| Copernicus login friction | Low | Mirror needed subsets ahead; Argo GDAC + INCOIS ERDDAP are open |
| Judges want a different variable/region mid-finale | High (by design of SIH) | F3 source registry — new NetCDF variable = config change; rehearsed pivot drill |
| Lead over-loaded (2.5 real builders) | High | Strict module ownership (TEAM-ROLES.md); beginners own storyboards/UI/test/pitch from week 1 |

## 10. Judge Q&A prep (rehearse verbatim)

1. *Why you, and not INCOIS's existing Digital Ocean portal?* — **Careful: Digital Ocean's launch materials claim "3D/4D visualization" — never say "no 3D exists at INCOIS."** Correct answer: Digital Ocean is a data-management and fusion portal whose 3D is a georeferenced globe with draped layers and time animation. We build *with* it — consuming INCOIS's own ERDDAP/THREDDS so there's zero data duplication — and add what it demonstrably lacks: true volumetrics (ray-cast slabs, isosurfaces), a live Class-4-style skill panel, and natural-language control. (Full landscape + 4 more rehearsed answers: PRIOR-ART.md §D.)
2. *How is this different from Windy/Earth.nullschool?* — Those are surface-only particle animations (nullschool's multiple levels are *atmospheric*). We render the **full water column in 3D**, fuse **in-situ instruments** with model fields, quantify model skill (Class-4-style RMSE scorecard) and follow OGC/CF so INCOIS can adopt it. 90% of ocean state — the physics behind cyclone intensification, fisheries, SAR — lives below the pixel they render.
3. *What happens with 10× data?* — Chunked zarr tiles + LOD streaming; rendering cost is view-dependent, not dataset-dependent.
4. *Who maintains it?* — Standard Python/JS stack, Dockerized, plugin registry documented; INCOIS's own stack (they run ERDDAP/LAS already).
5. *Is the AI safe/accurate?* — The agent only orchestrates deterministic tools and cites the exact datasets/floats used; it never invents numbers; offline mode uses a local model or disables narration gracefully.
6. *National scale?* — One central deployment serves all users; outreach mode reuses the same engine for schools and exhibitions.

## 11. Demo script (10 minutes, power round)

1. **(0:00)** WiFi visibly OFF. "Everything you see runs air-gapped on this laptop — deployable inside INCOIS today."
2. **(0:30)** Globe → Bay of Bengal. Drag depth slice 0→1000 m; temperature volume with thermocline isosurface; vertical exaggeration slider.
3. **(2:00)** Click an Argo float → live profile chart vs. model curve at the same point/time; **RMSE scorecard** appears.
4. **(3:30)** Voice (Hindi): *"अंडमान के पास पिछले चक्रवात के समय की थर्मोक्लाइन दिखाओ"* — Samudra Sahayak plans (visible tool-trace), flies the camera, slices the column, overlays the cyclone track, narrates the cold wake, cites floats.
5. **(6:00)** Agent generates a one-page cited PDF advisory brief; open it.
6. **(7:00)** Extensibility proof: register a new NetCDF variable via config → it appears in the selector (F6, live).
7. **(7:45)** **HazardWatch beat**: toggle the warnings layer — a CAP-style high-wave polygon lights up off the coast; the agent narrates the active warning and shows the wave/temperature field driving it.
8. **(8:30)** **SagarNode beat (internal round / if hardware allowed at GF)**: point to the tank — its live glyph is on the globe; pour in warm water; the threshold trips, a local CAP-shaped alert fires, agent announces it. "This is the PS's 'future sensor integration' requirement, running live."
9. **(9:15)** Financial + deployment close: ₹0 licenses, one GPU server, OGC-interoperable, INCOIS-ready. Storyboard/outreach mode shown as the closing visual if time allows.

---
*Sources for all competition/judging claims: HANDOFF.md §Research (URLs). Prior-art landscape, literature, gap analysis and rehearsed "vs X" answers: **PRIOR-ART.md**. PS text: sih.gov.in/sih2026PS (SIH26067).*
