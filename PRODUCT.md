# Product

<!-- impeccable:product-schema 1 -->

Derived from the repository's own product record (`docs/PRD.md`, `docs/TRD.md`,
`docs/PRIOR-ART.md`, `docs/TEAM-ROLES.md`, `CLAUDE.md`) rather than a fresh
interview, because those documents already are the confirmed product truth for
this project. Facts inferred rather than stated there are marked *(inferred)*.

## Platform

web

## Users

1. **INCOIS operational forecasters** - the primary users and the authors of the
   problem statement. At a forecast desk, on deadline, correlating a numerical
   model run against in-situ observations before issuing an advisory. Today they
   "toggle between disparate software packages" to do it.
2. **Disaster managers** consuming cyclone / high-wave / tsunami advisories
   (INCOIS runs India's Tsunami Early Warning Centre).
3. **Search-and-rescue coordinators** (Coast Guard, Navy) who need currents *at
   depth*, not just at the surface.
4. **Fishery advisory services** issuing Potential Fishing Zone advisories to
   roughly 9 lakh fisherfolk households.
5. **Ocean researchers, students, and exhibition visitors** - the PS explicitly
   names outreach, education and e-learning.
6. **Competition judges** - MoES/INCOIS oceanographers at screening and at the
   grand finale. A real, non-negotiable audience for this build. *(inferred from
   docs/HANDOFF.md)*

## Product Purpose

Render INCOIS's numerical ocean model fields and its in-situ observations in one
interactive 3D scene in a browser, so a forecaster can answer "can I trust
today's model run, here, at this depth?" in seconds rather than minutes.

Success: time-to-insight for a model-vs-float check drops from multi-tool
minutes to under 30 seconds; the scene holds 60 FPS at 1080p (30 floor); first
render of a preloaded region under 3 seconds; the whole demo runs air-gapped.

## Positioning

Four capabilities no existing system combines (`docs/PRIOR-ART.md` §C):

1. Volumetric water-column rendering **in a browser**, co-registered with in-situ
   profiles. pyParaOcean and Unidata IDV have volumetrics but are desktop;
   Copernicus MyOcean and Argovis are web but 2D. Nothing occupies both cells.
2. A **live Class-4-style model-skill scorecard inside the viewer**. GODAE and
   CMEMS compute skill offline and publish PDFs; no operational viewer shows
   RMSE and bias next to the field they describe.
3. **Natural-language and voice control of a scientific scene graph** - isosurface
   threshold, depth slab, co-location, recomputed RMSE.
4. **Indian-Ocean and INCOIS-native**: consumes INCOIS's own ERDDAP/THREDDS, so
   zero data duplication. EDITO and Copernicus are structurally Europe-scoped.

**Framing constraint (hard rule):** INCOIS's own Digital Ocean portal publicly
claims 3D/4D visualization. Never claim "no 3D exists at INCOIS." The defensible
position is that SagarDrishti is the analysis front-end built *with* INCOIS's
services, adding true volumetrics, a skill panel, and language control.

## Operating Context

- A forecast desk and, at the grand finale, a stage. The demo laptop is the
  performance target, and it runs **with WiFi off**.
- Source data is CF-convention NetCDF from ERDDAP/OPeNDAP and Argo GDAC, plus
  ASCII/CSV for some glider and CTD formats. Real government NetCDF is not
  CF-clean; the source registry exists to absorb that.
- Deployment target is INCOIS infrastructure via Docker, with no client-side
  installs.
- The oceanographic conventions users already expect: depth increasing downward,
  vertical exaggeration (the ocean is ~4 km deep over ~1000 km, so 1× is
  unreadable), perceptually-uniform palettes, arbitrary vertical sections.

## Capabilities and Constraints

**Confirmed capabilities (P0, each traced to a PS requirement):** volumetric
rendering of model fields over the water column with depth slices, isosurfaces
and time animation; clickable Argo/glider/CTD/BGC overlays with depth-vs-variable
profiles; multi-format ingestion driven by a config registry; colorbar editor,
variable selector, layer opacity, vertical exaggeration, depth navigation, time
scrubber; REST + OGC WMS/WCS endpoints; a documented plugin interface.

**Constraints:**
- `OFFLINE=1` is the default posture, not a mode. Network access exists in one
  file (`tools/fetch_sample.py`).
- The agent plane never computes or invents a number. Numbers enter answers only
  as tool results carrying dataset, timestamp and float WMO id.
- The agent plane is detachable: every P0 requirement must pass with it removed.
- Python 3.11, Next.js 15, CesiumJS 1.145, deck.gl 9.4, ECharts 5.6, zarr 2.18.
- Docker is not installed on the build machine; compose files are authored but
  unverified (`docs/adr/0004`).
- **Undecided:** Copernicus Marine credentials do not exist yet, so GLORYS12 is
  registered but disabled - which means depth-resolved current vectors are
  blocked. Grand-finale date unannounced. Internal-hackathon date unconfirmed.

**Terminology (binding):** the TDS probe is a "conductivity-derived salinity
proxy", never a "salinity sensor". The skill panel is labelled
"Class-4-style verification".

## Brand Commitments

- Name **SagarDrishti** (सागर दृष्टि, "Ocean Vision"), deliberately echoing the
  SAGAR doctrine and MoES's Deep Ocean Mission. Agent persona: **Samudra
  Sahayak**.
- Languages: Hindi, Telugu, Tamil, English, via the Government of India's own
  Bhashini / AI4Bharat stack.
- Every displayed number carries its dataset and timestamp. Sensor-derived demo
  alerts are labelled `source: demo-sensor` and described out loud as a
  pedagogical stand-in.

## Evidence on Hand

- **Real data, verified live 2026-09-07:** INCOIS ERDDAP griddap
  `incois_argo_10d_VAM` (24 levels, 5-2000 m, latest 2026-07-30) in
  `data/cube/incois_vam_bob.zarr`; 13 real Argo floats in the Bay of Bengal box
  in `data/cube/profiles.parquet` with genuine WMO ids (1902681, 2902765,
  2902768, 2902770, 2902772, 2902775, 4903793, 4903794, 5907086, 5907152,
  7902069, 7902073, 7902190), 4191 accepted levels from 10 days of Argo GDAC
  files.
- 36 passing data-plane tests, including an offline guard that blocks
  non-loopback sockets and DNS and still serves the whole demo path.
- 15 cited academic works and a full prior-art landscape in `docs/PRIOR-ART.md`.
- **Do not fabricate:** INCOIS endorsement, stakeholder quotes, deployment
  claims, RMSE figures, or any performance number not measured on the machine.
  No stakeholder outreach has happened yet.

## Product Principles

1. **Every P0 requirement before any P1 polish.** Screening reviewers grade
   against their own problem-statement text.
2. **Offline is the default path, not a fallback.** If it needs the network to
   look good, it is not built yet.
3. **A number without provenance is not shippable.** Dataset, timestamp, WMO id.
4. **The instrument must never lie about missing data.** Land, fill values and
   rejected QC levels are visibly absent, never coloured.
5. **Every part is swappable under pressure.** Mid-finale requirement changes
   are expected; a new variable or source is a config edit.

## Accessibility & Inclusion

- Keyboard operation and contrast are an explicit pre-finale pass (TRD §7).
- Multilingual voice and narration serve the outreach mandate, and are an
  inclusion feature the competition scores.
- Colour must never be the sole carrier of meaning: numeric readouts accompany
  every colour-mapped field, since a colorbar is being read as a measurement.
