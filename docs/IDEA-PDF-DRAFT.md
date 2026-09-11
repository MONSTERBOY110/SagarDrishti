# The six-slide idea PDF: content draft

**Deadline: 20 September 2026, via the college SPOC. Reviewers: MoES / INCOIS.**

This file is the **words**, written to the structure
[`SUBMISSION-GUIDE.md`](SUBMISSION-GUIDE.md) prescribes. Design and Story owns
turning it into the SIH template and exporting the PDF. Nothing here is a
layout instruction; where a visual is needed it is named and sourced.

## The one rule this draft follows

**Every claim is marked BUILT or PLANNED, and the built ones carry a number.**

An idea PDF is allowed to propose. What loses a reviewer is a proposal that
reads like a description of something finished. Ours is unusual in that most
of it is already running, so saying which half is which is not modesty, it is
the strongest thing on the page: a screening reviewer who sees "0.602 degC,
measured, 11,718 matched pairs" beside "planned: voice" believes both.

Figures below were read off the running services on 10 September 2026 and can
be re-derived from [`P0-STATUS.md`](P0-STATUS.md). **Re-run them the day the
PDF is exported** and correct any that have moved. A stale number in a
submitted PDF cannot be withdrawn.

---

## Slide 1. Problem statement details

**On the slide:**

> **PS ID:** SIH26067
> **Title:** (paste the exact title from sih.gov.in/sih2026PS, character for character)
> **Organisation:** Ministry of Earth Sciences, INCOIS
> **Category:** Software &nbsp;|&nbsp; **Theme:** Disaster Management
> **Team:** (name and ID)
>
> **SagarDrishti**: a browser-native 3D digital twin of India's ocean that
> renders INCOIS model fields and in-situ instrument profiles in one
> interactive scene, quantifies how far the model is from the instruments,
> and runs with the network off.

*Visual:* the Bay of Bengal volumetric view, full bleed behind the text block.
Screenshot from the running alpha, not a mockup.

*Note to the designer:* paste the PS title from the portal rather than
retyping it. A reviewer sees their own words first, and a paraphrase there
reads as carelessness before anything else is read.

---

## Slide 2. Proposed solution: innovation and uniqueness

**On the slide, three bullets against the PS's own phrases:**

> - INCOIS's fields and the instruments in one **"single interactive
>   environment"**: the water column as 24 depth levels from 5 m to 2000 m,
>   with isosurfaces and time animation, and 25 real Argo, BGC and moored-buoy
>   casts on the same globe. **Built.**
> - **"Depth-resolved volumetric views"** in a browser, with no client
>   install, at 51 frames a second on integrated graphics. **Built.**
> - A new data source is a registry entry, not a rewrite: **"without
>   significant re-engineering"**. A moored-buoy reader and a live sensor
>   station were both added this way. **Built.**

**Uniqueness block:**

> 1. **A skill number beside the field.** Class-4-style verification in
>    observation space: bias **+0.026 degC**, RMSE **0.602 degC** over
>    **11,718** matched model-observation pairs, with the caveat printed on
>    screen that the analysis assimilates these profiles, so this bounds the
>    analysis fit and is not forecast skill. Operational viewers publish this
>    in offline reports, if at all. **Built.**
> 2. **HazardWatch**: real CAP v1.2 warnings, the protocol behind NDMA's
>    SACHET, drawn over the water they concern. The theme is Disaster
>    Management. **Built.**
> 3. **SagarNode**: a physical sensor station that posts to the API and
>    appears on the globe with no code change, which is the PS's "future
>    sensor integration" clause demonstrated rather than described. **Built;
>    hardware on order.**
> 4. **Samudra Sahayak**, an assistant that operates the 3D scene and cannot
>    state a number no tool produced. **Built as a deterministic tool router;
>    the language model and multilingual voice via Bhashini are planned.**
> 5. **Air-gapped by construction**: the demo makes no off-origin request, and
>    a test fails the build if one appears. **Built.**

**Positioning line:**

> Desktop tools have volumetrics without the web. Web viewers have the web
> without volumetrics. Copernicus's own roadmap puts their 3D globe at January
> 2027. SagarDrishti occupies the empty intersection, for the Indian Ocean.

*Verify before printing:* PRIOR-ART.md's open flag list includes re-checking
that Copernicus 3D-viewer date near submission. If it has moved or shipped,
the sentence still works without it; if it has shipped and we print it anyway,
the whole positioning paragraph is worth nothing.

*Visual:* the hero shot again is a waste. Use the **verification card beside
the water column**, cropped tight, so the RMSE and its caveat are legible at
100 per cent. That picture is the argument.

---

## Slide 3. Technical approach

**On the slide:**

> **Flow:** NetCDF and delimited text &rarr; source registry
> (`data/sources.yaml`) &rarr; zarr cube &rarr; REST + OGC WMS 1.3.0 / WCS
> 1.0.0 &rarr; 3D scene, with the agent driving the same scene state a click
> drives.
>
> **Stack:** Next.js 15 and CesiumJS over WebGL2 · FastAPI with xarray and
> zarr · CF Conventions, OGC WMS/WCS, CAP v1.2 · ESP32 over HTTP · Docker.
>
> The PS suggests "WebGL / Three.js or Cesium.js". We took Cesium, for
> geodetic accuracy at basin scale.

*Visual:* **the architecture diagram, and it is the slide.** Redraw TRD
section 1 clean. One box per service, arrows labelled with the actual formats
(NetCDF, zarr, JSON, PNG, CAP XML). The guide is right that this slide wins or
loses screening; give it two thirds of the area and cut words to fit.

*Note:* name the registry file on the diagram. "A new source is a YAML entry"
is a claim; showing the file in the data path is evidence.

*Two things deliberately NOT on the stack line, and they must not be added
back from the submission guide or the TRD.*

**deck.gl.** ADR-0001 planned it as a camera-synced overlay and the guide's
stack line still says "CesiumJS/deck.gl". It is in `package.json` and it is
imported by nothing: every mark and every slice is a Cesium primitive or
entity. Naming a library we do not call is the cheapest possible thing for a
reviewer to catch and one of the worst to be caught at.

**Docker as a verified deployment.** The compose files are authored and have
never been executed, because Docker is not installed on the build machine
(ADR-0004). It is legitimate on a proposal slide as the intended deployment
path, which is how the line above reads. It must not become "Dockerised" or
"deployed on INCOIS infrastructure" until somebody has run it.

---

## Slide 4. Feasibility and viability

**On the slide:**

> **The data is live and open.** INCOIS ERDDAP (`incois_argo_10d_VAM`, the
> variational analysis, 24 levels), the Argo GDAC at Ifremer, RAMA moored
> buoys, and Copernicus Marine GLORYS for depth-resolved currents at one
> twelfth of a degree. Every one verified, no licence, no paywall.
>
> **It is not a proposal on paper.** The alpha runs today: 519 automated
> tests, ten of which drive a real browser through the demo path, and a frame
> rate measured on integrated graphics rather than a gaming GPU.
>
> **Three risks, three answers.** Render cost: depth-space level of detail,
> with a slices-only floor that is what the renderer already is. Data outage:
> the whole demo runs from a local cube with the network off. Scope: P0 is the
> PS's own requirement list and nothing else is built before it.

*Visual:* a QR code to the 60-second demo video. **Test it from a phone on
mobile data**, not on the college WiFi.

*Note:* the guide says "by submission date we will have the Phase-2 alpha".
That is now understated. Say it runs today and give the test count; a reviewer
can check the claim's shape even if they cannot run it.

---

## Slide 5. Impact and benefits

**On the slide, disaster management first, because it is the theme:**

> **Hazard assessment.** INCOIS's own words are that toggling between separate
> packages "impedes timely hazard assessment, search-and-rescue support,
> fishery advisories". A forecaster asking "can I trust today's field" gets a
> per-depth answer on the same screen as the field: in our current cube the
> model is within 0.12 degC below 500 m and 2.07 degC across the thermocline
> at 50 to 100 m, which is exactly where cyclone heat potential is read.
>
> **Warnings in context.** CAP bulletins stop being text and become a shape on
> the water, beside the temperature field that explains them.
>
> **Operational reach.** One deployment serves every INCOIS mandate the PS
> names: hazard, search and rescue, fishery advisories, climate monitoring.
>
> **Outreach, which the PS asks for by name.** Guided tours narrate the scene
> for schools and exhibitions; Indian-language voice is planned and widens
> that further.
>
> **Cost.** Zero licences, entirely open source, one commodity GPU server.

*Visual:* the per-depth error table, cropped. Numbers, not icons.

---

## Slide 6. Research and references

**On the slide, grouped so a reviewer can see the reasoning, not just a list:**

> **The problem and the prior art.** SIH26067 (sih.gov.in/sih2026PS) ·
> INCOIS Digital Ocean portal, which we extend rather than duplicate ·
> pyParaOcean, IISc, CGF 2025, desktop volumetrics we bring to the browser.
>
> **Web 3D ocean visualisation.** Qin et al. 2021, Environmental Modelling and
> Software · Yu et al. 2025, Applied Sciences, WebGPU ocean volume rendering ·
> Tucker et al. 2020, JTECH, Argovis.
>
> **Verification method, which our scorecard implements.** Ryan et al. 2015,
> Journal of Operational Oceanography, GODAE OceanView Class 4 ·
> Balakrishnan Nair et al. 2013, Current Science, INCOIS OSF validation, the
> Indian precedent.
>
> **Data quality.** Wong et al. 2020, Frontiers in Marine Science, Argo QC:
> our profiles keep flags 1 and 2 only.
>
> **Standards.** CF Conventions · OGC WMS 1.3.0 and WCS 1.0.0 · OASIS CAP v1.2.
>
> **The rest.** Tzachor et al. 2023, npj Ocean Sustainability, digital twins ·
> FathomGPT, UIST 2024 · Bhashini / AI4Bharat · Albaladejo et al. 2012,
> Sensors, the low-cost buoy that grounds SagarNode.

*Note:* the annotated bibliography in [`PRIOR-ART.md`](PRIOR-ART.md) is the
depth behind this slide if a reviewer asks.

---

## Before this is exported

From the guide's own checklist, plus what this draft adds:

- [ ] **Re-run every number** against the running service and correct this
      file first. Commands are in `P0-STATUS.md`.
- [ ] Every slide at or under roughly 80 words with one visual.
- [ ] PS phrases quoted verbatim at least three times across slides 2 to 4.
      This draft quotes four; keep them in quotation marks.
- [ ] The architecture diagram legible at 100 per cent on a second machine.
- [ ] Demo-video QR tested from a phone on mobile data.
- [ ] The idea counter for SIH26067 checked and screenshotted for the decision
      log (re-checks due 15 and 19 September).
- [ ] Decide deliberately about the second idea slot and backup PS SIH26176.
- [ ] Roster: six members, at least one female, names exactly as in college
      records.
- [ ] **No BUILT label survives that is not still true**, and no PLANNED item
      is written as though it exists. Voice and the language model are the two
      to watch: they are the most impressive things on the page and the two we
      have not built.
