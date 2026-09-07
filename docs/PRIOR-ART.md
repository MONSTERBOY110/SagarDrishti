# PRIOR-ART — What exists, what doesn't, and exactly where SagarDrishti is new

**Purpose:** mentor-directed literature & landscape review (done BEFORE building, Sep 7 2026). Feeds: Slide 6 references, judge Q&A, and our architecture decisions. Every claim carries a source (§F).

---

## ⚠️ Framing rule (memorize this)

INCOIS's own **Digital Ocean** platform (launched 30 Dec 2020) officially claims *"3D and 4D (3D in space with time animation) data visualization … from multiple sources viz., in-situ, remote sensing and model data, all of which is rendered on a georeferenced 3D Ocean."* An INCOIS judge knows this sentence. **Never say "no 3D exists at INCOIS."**

Our defensible position: *SagarDrishti is the analysis front-end that INCOIS's data holdings deserve* — it consumes INCOIS's own ERDDAP/THREDDS/LAS services and adds the four things no system (INCOIS's included) demonstrably does today (§C).

**Pre-pitch action item:** open `do.incois.gov.in` in a real browser and screenshot what its "3D" actually renders (our automated check got only a loading shell). If it is a draped-layer globe, that screenshot is the most valuable slide we can carry into an INCOIS judging room.

## A. Systems landscape (what INCOIS and the world already run)

### INCOIS's own stack
| System | What it is | Limitation vs. this PS |
|---|---|---|
| **Digital Ocean** (do.incois.gov.in, 2020) | Web data-management/fusion suite; advertised 3D/4D viewing of in-situ + satellite + model data | No published architecture; no documented volumetric rendering (isosurface/ray-cast), no model-skill scoring, no public API/embed story. A data portal with globe viewing, not an analysis-grade volumetric renderer |
| **Live Access Server** (las.incois.gov.in) | Ferret/LAS server-side plotting of gridded fields | Static 2D PNGs, one field at a time, no in-situ overlay |
| **ERDDAP + THREDDS** | Standards data services (OPeNDAP/CF/WMS) | Data access layers with rudimentary graphs — these are our **backend**, not competitors |
| **SARAT** | Search-and-rescue drift predictor (ROMS currents + Monte-Carlo leeway) | Single-purpose 2D probability map |
| **OSF / PFZ / ITEWC** | Ocean State Forecasts; Potential Fishing Zone advisories; Tsunami Early Warning Centre (UNESCO-IOC recognized Tsunami Service Provider) with CAP alerts, SAMUDRA app, SMS, GAGAN/NavIC dissemination | World-class *dissemination* pipeline with text/2D-map front ends — the science-visualization layer is the gap |

### Global platforms
- **EU Digital Twin of the Ocean (EDITO / EDITO-Model Lab; EDITO2 2025–28, €14M)** — cloud infra fusing Copernicus Marine + EMODnet (STAC/Zarr), in-browser model lab, game-engine 3D scenes. *Infrastructure-first, notebook-centric, Europe-scoped; no coherent volumetric globe, no Indian Ocean/INCOIS integration.*
- **Copernicus MyOcean Pro viewer** — best-in-class web 2.5D: depth-*level* selection, vertical profiles, Hovmöller, particle animation, in-situ layers. *A flat map with a depth dropdown — you never see the column's 3D shape. Copernicus's own roadmap schedules its 3D globe viewer for **January 2027** (re-verify near submission; one source said Nov 2026) — we target what their roadmap says is still months away.*
- **Argovis** (JTECH 2020; JTECH 2025) — the strongest **co-location engine** (Argo × gridded products, versioned REST API). *2D Leaflet + 2D plots; no 3D, no volumetrics. Our methodological ancestor for model-vs-obs pairing — mirror its API semantics.*
- **earth.nullschool.net / Windy** — beautiful particle-advection globes. *Ocean = surface only (nullschool's multi-level data is atmospheric); no in-situ, no bathymetry, no analysis, no skill.*
- **NASA Worldview / Sea Level Portal, NOAA nowCOAST / Science On a Sphere, Euro-Argo Fleet Monitoring, OceanOPS** — all 2D web maps, surface rasters, ops dashboards, or museum hardware.

### The "desktop-bound" tools (the PS's own complaint)
- **Ocean Data View (ODV)** — de-facto standard for in-situ sections/profiles (~10k users). Desktop; weak on gridded model data. **Note: webODV exists** (2D plots in browser) — be precise: say "webODV is 2D-plot-based," not "ODV has no web version."
- **pyParaOcean (IISc Bangalore; EnvirVis 2023 + Computer Graphics Forum 2025)** — **our most serious technical prior art**: ParaView plugin with volume rendering, eddy identification, salinity tracking, demonstrated on *Bay of Bengal* data. But: ParaView/HPC install, expert-only, no browser client; its scaling answer (Cinema pre-rendered image DBs) trades away interactivity. Cite respectfully as methodological reference.
- **Unidata IDV / McIDAS-V** — genuine interactive 3D (isosurfaces, probes) in desktop Java; dated UX, no web.
- **Panoply** — desktop 2D slice viewer. **HoloViz stack** — 2D dashboards, library not platform.

### AI prior art (exists separately — never combined)
- **FloatChat (SIH 2025, INCOIS/MoES PS!)** — RAG + NL-to-SQL over Argo tables → charts. Ministry has already seen chat-over-Argo; a chatbot alone will not impress.
- **cesium-mcp (GitHub)** — generic LLM camera/entity/layer control of a Cesium globe.
- **FathomGPT (ACM UIST 2024)** — NL exploration of ocean imagery/measurements; **OceanAI (arXiv 2025)** — LLM + parameterized NOAA API calls with verifiably sourced numeric answers.
- **Nobody wires an LLM to volumetric scene state + live skill metrics.** That intersection is ours.

## B. Academic literature (must-cite ★ for Slide 6)

| # | Work | Method | We borrow / differ |
|---|---|---|---|
| ★1 | Qin et al. 2021, *Env. Modelling & Software* 135:104908 — web 3D framework for time-varying ocean forecast data (Cesium + volume rendering) | Cesium globe + NetCDF volume viz in browser | Closest ancestor. We swap in deck.gl/WebGPU custom layers, add in-situ fusion + agent control |
| ★2 | Yu, Qin, Xu 2025, *Applied Sciences* 15(5):2782 — WebGPU volume rendering of ocean scalars | GPU ray-casting with **early ray termination + adaptive sampling** | Adopt both optimizations; keep WebGL2 fallback (judge laptops may lack WebGPU) |
| ★3 | Liu, Silver, Bemis 2019, *IEEE Access* 7 — 3D ocean eddies in browsers | Extract features server-side, ship light geometry, not grids | Adopt for eddies/fronts; we keep a true volumetric layer alongside |
| 4 | Resch et al. 2014, *CaGIS* 41(3) — web 4D marine geo-data via WebGL | Early 4D concept + interaction metaphors | "Proposed a decade ago; GPU + cloud formats now make it operational" framing (re-verify author list before printing) |
| ★5 | Blower et al. 2013, *EMS* 47 — ncWMS | WMS on CF-NetCDF with vertical-section/time extensions | The 2D-tile status quo we supersede; reuse CF handling + section idea |
| ★6 | Signell & Pothina 2019, *JMSE* 7(4):110 — coastal model analysis in the cloud | Xarray + Dask + **Zarr** on object storage | Our storage decision: NetCDF→Zarr chunks over HTTP range requests |
| 7 | deck.gl, arXiv:1910.08865 | Layered WebGL, 64-bit geo accuracy | Argo points/tracks/particles layer base |
| 8 | OGC 3D Tiles 1.1 (22-025r4) | LOD tileset streaming | Reuse pattern for depth-sliced volume bricks keyed on time |
| ★9 | Tzachor et al. 2023, *npj Ocean Sustainability* 2:16 — digital twins of the ocean | DTO review; interoperability/cost barriers | Problem framing: India lacks a DTO front-end; we answer with open standards |
| 10 | Wickberg & Lidström 2025, *New Media & Society* | DTO as governance/media project | One line: a twin is only useful if humans can interrogate it → motivates voice/LLM layer |
| 11 | EDITO-Infra / Model Lab / EDITO2 reports | data lake → process → focused-app architecture | Template; we differ: browser-native 3D for non-programmers |
| ★12 | Ryan et al. 2015, *J. Operational Oceanography* 8 — **GODAE OceanView Class 4** | Verify forecasts in **observation space**: co-locate model to Argo T/S profiles; bias/RMSE metrics | **The backbone of our scorecard.** Implement Class-4-style co-location, per-depth-bin bias/RMSE; label it "Class-4-style" in the UI |
| ★13 | Tucker et al. 2020, *JTECH* 37(3) — Argovis | 3-tier app + API for 4D Argo queries | Copy API contract (bbox+depth+time → profiles); render profiles inside the 3D volume |
| ★14 | Wong et al. 2020, *Frontiers Marine Sci* 7:700 — Argo 2M profiles | Array + QC-flag structure | Provenance; scorecard uses QC flags 1/2 only |
| ★15 | Khanal et al. 2024, *ACM UIST* — FathomGPT | NL interface over ocean data; latency ablations | Agent pattern: intent → structured tool call → scene mutation. Lesson: pre-register tools; **never let the LLM write code on stage** |

**LLM-agent block (cite 2):** ★ *GeoJSON Agents* (arXiv:2509.08863) — function-calling vs code-generation compared head-to-head (our architecture decision, function-calling wins for reliability); *OceanAI* (arXiv:2511.01019) — every spoken number carries a data reference (we adopt: dataset, timestamp, float WMO ID in agent answers). **Indian context:** ★ Balakrishnan Nair et al. 2013, *Current Science* 105(2) — INCOIS Ocean State Forecast validation (incl. cyclone Thane) — the domestic validation precedent.

## C. The gap — what NOBODY does (our 4 defensible claims)

| Capability | Who's closest | Why they miss |
|---|---|---|
| 1. **Volumetric water-column rendering in a browser, co-registered with in-situ profiles** | pyParaOcean/IDV (volumetrics, desktop) · MyOcean/Argovis (web, 2D) | No system occupies both cells |
| 2. **Live model-skill scorecard (Class-4 RMSE/bias) inside the viewer** | GODAE/CMEMS quality reports | Computed offline, published as PDFs; no operational viewer shows skill next to the field |
| 3. **Voice/NL control of a *scientific* scene graph** (isosurface threshold, depth slab, colocate, recompute RMSE) | FloatChat (tables→charts) · cesium-mcp (generic camera) | Neither knows the other's domain; our tool schema spans volumetrics + validation |
| 4. **Indian Ocean / INCOIS-native** (ROMS/HYCOM + Indian Argo/glider/CTD holdings) | EDITO/Copernicus | Structurally Europe-scoped |

**Match, don't reinvent:** Argovis colocation API semantics · nullschool-style particle advection · MyOcean depth-profile/Hovmöller ergonomics · Cesium World Bathymetry + GEBCO · INCOIS ERDDAP/THREDDS as backend (zero data duplication — a deployment argument, not just a shortcut).

## D. Judge-ready answers ("how are you different from X?")

1. **"INCOIS already has Digital Ocean — it says 3D/4D."** Correct — and we build *with* it. Digital Ocean is a data-management portal whose 3D is a georeferenced globe with draped layers and time animation. SagarDrishti adds what it doesn't do: true volumetrics (ray-cast slabs, isosurfaces), a quantitative Class-4-style skill panel, and natural-language control — while consuming INCOIS's own ERDDAP/THREDDS, so zero data duplication.
2. **"MyOcean Pro already views 4D."** Its depth axis is a *selector* — one level at a time; you never see the 3D shape of a thermocline or an eddy's vertical extent. Copernicus's own roadmap puts their 3D globe at Jan 2027, without volumetrics or in-situ integration. We're targeting what the world's best viewer says is still out of reach.
3. **"pyParaOcean already does volumetric Indian-Ocean viz."** Yes — it's our cited methodological reference, and it's exactly what the PS means by "desktop-bound": a ParaView/HPC plugin an INCOIS forecast-desk officer cannot use. We deliver a defensible subset of that power at a URL, zero install, plus observation-comparison and language layers it has no scope for.
4. **"Isn't this earth.nullschool/Windy for the ocean?"** Those are surface-only particle animations (nullschool's levels are *atmospheric*). 90% of ocean state — the physics behind cyclone intensification, fisheries, SAR — lives below the pixel they render. No in-situ, no export, no skill, no column.
5. **"SIH 2025 had FloatChat; LLM-Cesium repos exist."** Both true and cited. FloatChat does RAG over Argo *tables*; cesium-mcp does generic camera moves. Our agent's tool surface is the scientific scene graph + validation state — a spoken request produces a reproducible scene plus a number with its data citation, not a chat paragraph.

## E. Methodology adoptions (decided by this review)

1. NetCDF → **Zarr** chunked (time, depth, y, x), HTTP range requests (Signell & Pothina).
2. Volume ray-casting with **early ray termination + adaptive sampling**; WebGL2 fallback; coarse-pyramid-first LOD, refine on idle (Yu et al.; 3D Tiles pattern).
3. **Two-tier rendering:** raw volume only for the actively inspected scalar; server-extracted feature geometry (eddies/fronts) otherwise (Liu et al.).
4. **Class-4 observation-space verification** for the scorecard; QC flags 1/2 only (Ryan et al.; Wong et al.).
5. Agent = **function-calling over a small typed tool schema**; no code generation on stage; every spoken number carries dataset + timestamp + WMO ID (GeoJSON Agents; FathomGPT; OceanAI).
6. Vertical exaggeration + arbitrary vertical sections are *expected* oceanographer affordances (ncWMS lineage) — P0, not polish.

## F. Sources

**INCOIS:** PIB Digital Ocean launch (pib.gov.in PRID=1684418) · las.incois.gov.in · incois ERDDAP · sarat.incois.gov.in · services.incois.gov.in/portal/services.jsp · tsunami.incois.gov.in (ITEWC + TSP-Userguide.pdf) · UNESCO recognition article (unesco.org) · MHA Lok Sabha reply on CAP/GAGAN/NavIC (mha.gov.in par2025 LS11032025/1852.pdf)
**Global:** edito.eu · edito-infra.eu · edito-modellab.eu · Mercator EDITO2 press release · help.marine.copernicus.eu (MyOcean features, v13) · **marine.copernicus.eu/user-corner/product-roadmap/transition-information** (3D viewer date) · sos.noaa.gov · sealevel.nasa.gov · earth.nullschool.net/about · journals.ametsoc.org JTECH-D-19-0041.1 + JTECH-D-24-0160.1 (Argovis) · fleetmonitoring.euro-argo.eu · ocean-ops.org
**Desktop/vis research:** odv.awi.de · emodnet-chemistry.webodv.awi.de · docs.unidata.ucar.edu/idv · arxiv.org/abs/2309.14328 + arxiv.org/abs/2501.05009 (pyParaOcean) · sciencedirect S1364815220309658 (Qin 2021) · mdpi.com/2076-3417/15/5/2782 (Yu 2025) · ieeexplore 8682055 (Liu 2019) · tandfonline 15230406.2014.901901 (Resch) · sciencedirect S1364815213000947 (ncWMS) · mdpi.com/2077-1312/7/4/110 (Signell) · arxiv 1910.08865 (deck.gl) · docs.ogc.org/cs/22-025r4 (3D Tiles) · cesium.com (bathymetry, voxels roadmap, undersea)
**Validation/DTO/AI:** tandfonline 1755876X.2015.1022330 (Class 4) · frontiersin fmars.2020.00700 (Wong) · os.copernicus.org/articles/15/997/2019 (BGC-Argo metrics) · nature.com s44183-023-00023-9 (Tzachor) · UIST 2024 FathomGPT · arxiv 2511.01019 (OceanAI) · arxiv 2509.08863 (GeoJSON Agents) · researchgate FloatChat SIH 2025 + rjwave.org IJEDR2601908 · github.com/gaopengbin/cesium-mcp · Balakrishnan Nair 2013 Current Science 105(2)
**Hardware & alerts (for SagarNode/HazardWatch):** robocraze.com (ESP32 ₹831, DS18B20 ₹63, turbidity ₹489, DFRobot TDS ₹1,435) · robu.in (clones ~₹250–600; re-check manually — blocked automated fetch) · pmc PMC3444120 (Albaladejo 2012 low-cost buoy, *Sensors*) · mdpi 2077-1312/13/9/1629 (2025 multi-functional buoy) · sciencedirect S0029801824028592 (LoRaWAN buoys) · nature s41598-026-37287-3 (2026 sub-$80 ESP32 water rig + TinyML) · sachet.ndma.gov.in (NDMA CAP backbone) · undrr.org CAP + case study · sciencedirect S2212420923006751 (tsunami last-mile review)

**Open verification flags:** (1) screenshot do.incois.gov.in's real rendering pre-pitch; (2) re-verify Copernicus 3D-viewer date near submission; (3) re-verify Resch 2014 + deck.gl author lists before printing; (4) re-check Robu.in clone prices manually.
