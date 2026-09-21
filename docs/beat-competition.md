# Beat the competition: a four day plan to 25 September

**Written 21 September 2026.** Record on the 25th, submit to the SIH portal
straight after. Internals are not the target: the college has already
nominated us, so this plan optimises for the portal submission and the roughly
30 teams who will reach the finale on SIH26067.

Working days available: **21, 22, 23, 24.** The 25th is the recording day and
must be a build freeze.

---

## 1. What we actually know about the field

One competitor sample, watched frame by frame on 20 September.

**Team NULL Pointers**, same problem statement, video uploaded 11 September,
five minutes, no narration captions. Product name "INCOIS 3D Ocean Platform,
Indian Ocean Digital Twin and In-Situ Observations".

**They have:** a Cesium globe with camera presets; a layer catalog with
3D volumetric slab, temperature and salinity as 3D voxels, chlorophyll,
current vectors, Argo floats, gliders, moored buoys and an India EEZ
boundary; palette, log and linear, min and max bounds, opacity, vertical
exaggeration at 250 per cent; a depth slice slider and a 14 day time scrubber;
a click-through Argo depth profile; an Operational and Outreach mode toggle
with chaptered stories; and a full screen **3D Volumetric Ocean Block Studio**
with an orbitable water column, a laser depth slice, per depth readouts
including sound velocity, and labelled water mass bands.

**They do not have, in five minutes of video:** any model versus observation
comparison, any bias or RMSE, any warning layer, any agent, any isosurface,
any offline claim, any hardware, and any provenance on screen. Their data is a
fixed 14 day window in June 2024. Their "EXPORT AND GIS INTEROPERABILITY,
CF-1.8 / OGC" panel is never opened.

**Confidence note:** the video had no captions and no transcript was
obtainable, so this is a read of the pixels. They may narrate claims that the
interface does not show.

---

## 2. The field model: what the other thirty will look like

The PS title contains no AI buzzword and demands NetCDF plus WebGL, which
filters the field but does not empty it. Expect roughly this distribution.

| Archetype | Share | What it looks like | What beats it |
|---|---|---|---|
| **A. 2D dashboard wearing a globe** | ~40% | Leaflet or a Cesium globe with a draped raster, a depth dropdown, Chart.js profiles, one hand-downloaded NetCDF file | Actual volume through depth, and more than one real source |
| **B. The polished 3D viewer** | ~25% | NULL Pointers. Real-looking volumetrics, dense attractive UI, synthetic or single-snapshot data, no verification | Verification, provenance, standards proven live, offline |
| **C. The chatbot bolt-on** | ~20% | Retrieval or natural-language-to-SQL over Argo tables, charts in a chat window | FloatChat already did this on an INCOIS PS in 2025. Say so. Then show an agent that cannot fabricate, attached to a real scene |
| **D. The ML prediction pitch** | ~10% | "We forecast SST and cyclone tracks with an LSTM" | Off-brief. The PS asks to visualise model output, not to compete with INCOIS's models. Our refusal to train one is a documented decision, not a gap |
| **E. The genuine engineering team** | ~5% | Real CF handling, real Argo, real standards, honest scope | Only depth beats them. This is who the rest of this document is aimed at |

**The insight that decides this competition:** almost every team will show a
picture of the ocean. Almost nobody will show **whether the picture is
right**. And the portal files this problem under **Disaster Management**,
which most teams will never notice because the title does not say so.

Two of our features answer exactly those two blind spots, and they are already
built. The work over the next four days is to stop burying them.

---

## 3. What to take from NULL Pointers, and what not to

### 3.1 Take the information architecture

Their real advantage is not that their UI is prettier. It is that **their
interface advertises its own capability on first frame** and ours does not.
Their left rail says "8 Active, 3/3, 3/3, 1/1, 1/1" before a word is spoken.
A judge scanning a thumbnail counts features. We have more features and show
fewer of them.

### 3.2 Do not take the skin

`apps/web/app/layout.tsx` carries a written design thesis that rejects this
aesthetic on purpose:

> refuses the category default, the dark-navy dashboard with floating
> translucent panels and glowing cyan accents, because a translucent panel
> over a moving 3D scene is unreadable exactly when a forecaster needs it, and
> because glow spends hue that belongs to the measurement

That is a defensible professional argument, it is ours, and every other team
in archetype B will look like each other. A reskin four days before recording
would throw away the one thing that makes our screenshots recognisable, risk
the 11 browser tests, and gain nothing a judge scores. **Keep the Station
Logsheet world. Raise its density.**

If asked on the day why we do not look like a dark ops dashboard, the answer
is the thesis above, in one sentence: opaque stock stays readable over moving
water, and colour is reserved for the data.

---

## 4. The build list, ranked by judge impact over risk

Four days. Ordered so that stopping at any point still leaves a coherent
product.

### Tier 1: do these

**T1. Layer catalog rail with live counts.** Highest ratio in the list.
Everything it would show already exists; it is presentation only.
Group as Model volumes, Circulation, In-situ platforms, Hazards, Jurisdiction.
Each row gets a badge carrying a real fact taken from the API, not a label:
`24 levels`, `TEOS-10 derived`, `149 casts`, `CAP v1.2`, `WMS + WCS`.
Header shows active count. Footer states the plugin surface in one line, which
is the F6 answer.
Files: new `apps/web/components/LayerCatalog.tsx`, mounted in `app/page.tsx`.
**Estimate: half a day. Risk: low.**

**T2. Water Column Studio.** Our answer to their cube, and the one place we
should out-execute rather than match. A full screen orbitable column for a
selected cast, drawn from data we already serve: 24 depth levels, temperature,
salinity, SIG0 density, D26.
The thing theirs cannot do, and the reason ours is worth building:
**draw the model curve and the measured curve in the same column, with the
residual shaded between them, and print the Class-4 number for that cast on
the panel.** Their cube shows a column. Ours shows a column being checked.
Files: new `apps/web/components/ColumnStudio.tsx`, reusing `lib/colormap.ts`
and the existing `/profiles/{id}` and `/scorecard` routes.
**Estimate: one to one and a half days. Risk: medium. This is the only item
that can overrun, so it starts first on day 2 and is cut on day 4 if it is not
working.**

**T3. Water mass stratification bands.** Label the column: Euphotic mixed
layer, thermocline, intermediate oxygen minimum, deep water. We already
compute the D26 isotherm depth, so the thermocline band is derived from our
own plugin rather than hardcoded. Domain literate, cheap, and it makes the
Studio read as oceanography rather than graphics.
**Estimate: three hours including tests. Risk: low.**

**T4. Sound speed as a derived field.** They show it and we do not, it is
genuinely useful for search and rescue and naval users, and we already depend
on `gsw`. A fifth plugin alongside `d26_isotherm` and `density_sigma0`, using
`gsw.sound_speed` after the standard `SA_from_SP` and `CT_from_t` conversions.
It also strengthens F6: three derived products instead of two, all served
through WMS and WCS.
Files: new `services/api/plugins/sound_speed.py` plus tests mirroring
`tests/test_density.py`.
**Estimate: three hours. Risk: low. TDD, this is data plane.**

**T5. Operational and Outreach mode toggle.** We have six tours already. A top
level switch makes the dual mandate legible in one glance, and the PS asks for
outreach explicitly. Operational shows the full instrument; Outreach hides the
dense panels and runs the tours with the narration cards.
**Estimate: two to three hours. Risk: low.**

**T6. India EEZ boundary.** A jurisdiction layer is a cheap signal that a
ministry audience reads immediately.
**Estimate: two hours. Risk: low.**

### Tier 2: only if Tier 1 lands early

**T7. Export button.** Wire a visible Download to the existing `/wcs`
GetCoverage and a CSV of the current profile. They advertise export and never
open it. Opening it is the whole point.

**T8. A cursor readout line.** Variable, value, units, depth, latitude and
longitude under the pointer. They have this; it costs us little.

### Tier 3: explicitly not doing, and why

- **Full dark reskin.** Section 3.2.
- **A language model planner.** A week of work with a live failure mode, and
  the guard, tools and citations are already real. `planner: rules` stays, and
  stays labelled.
- **Voice and Bhashini.** Not built, not startable in four days, and honestly
  marked as not built in every document we ship.
- **Any ML model.** Off-brief by design.

---

## 5. Day by day

| Day | Build | Ends with |
|---|---|---|
| **Mon 21** | T1 layer catalog, T6 EEZ, T4 sound speed plugin with tests | Capability visible on first frame; a fifth plugin and a third derived product |
| **Tue 22** | T2 Column Studio, geometry and orbit, model and observed curves | A column you can spin, with two curves in it |
| **Wed 23** | T2 finish: residual shading, Class-4 number on the panel. T3 stratification bands | The Studio is demo ready |
| **Thu 24** | T5 mode toggle, Tier 2 if free. Then **freeze**: full test run, re-capture all screenshots, rehearse the script twice with a timer | Frozen build, fresh evidence, rehearsed |
| **Fri 25** | Record. No code changes | Video, then portal submission |

**Freeze rule:** nothing merges after Thursday evening except content and
copy. Every winning team documented in `PRIOR-ART.md` froze early; every
disaster story is a team that shipped a feature on recording day.

---

## 6. The recording script, which is where the cheap wins are

Order matters more than any single feature. Most teams open on a spinning
globe, which is the one shot every judge will have seen twenty times that day.

1. **Open on the verification card, not the globe.** First sentence:
   "this is how wrong today's model is, and here is how we know." Bias +0.026,
   RMSE 0.602, 11,718 matched pairs, worst band 50 to 100 metres at 2.07
   degrees. **No other team will open this way**, and archetype B cannot open
   this way at all.
2. **Then the water, with the instruments in it.** Pull back to the globe;
   the numbers you just saw came from the marks now on screen.
3. **Water Column Studio.** One cast, spun, with the model curve beside the
   measured one and the residual shaded between them.
4. **HazardWatch.** State the theme out loud: the portal files this problem
   under Disaster Management. Show the CAP areas. Say plainly which three are
   rehearsals and why they are stamped EXERCISE. **Honesty here is a scoring
   move, not a confession**, because the alternative is being caught.
5. **The standards proof.** Open a desktop GIS client against `/wms` live.
   Competitors will claim CF and OGC on a slide. Fifteen seconds of a
   different program reading our server converts a shared bullet into a sole
   differentiator.
6. **Extensibility, live.** Add a source in `sources.yaml` and show it appear.
   Mention the fifth plugin shipped this week.
7. **The agent**, with the tag visible, and say the sentence: it cannot invent
   a number, every figure is a tool result with a citation.
8. **The WiFi is off.** Three seconds. It converts "deployable on INCOIS
   infrastructure" from a promise into something the viewer watched happen.

Close on the three numbers that are hard to fake: 13 sources across 9 kinds,
30,012 quality-controlled levels, 567 tests.

---

## 7. What we say when a reviewer names a competitor

Rehearse these. They are all defensible and none of them attacks anyone.

- **"Another team showed a nicer 3D cube."** Good, volumetrics are the right
  answer to this problem statement. Ours also tells you whether the column is
  correct, because the model curve and the measured curve are in the same box
  with the residual between them. A picture of the ocean and a checked picture
  of the ocean are different products.
- **"Everyone claims OGC."** We opened a third-party GIS client against ours
  on camera.
- **"Everyone has a chatbot."** FloatChat did this on an INCOIS problem
  statement in 2025 and the ministry has seen it. Ours is a small typed tool
  surface over a scientific scene, with a guard that runs on every answer, and
  it is labelled honestly as a rules planner today.
- **"Your data is a small box."** Thirteen sources across nine kinds, with the
  dataset and timestamp printed on screen at all times, quality flags enforced,
  and archive observations marked as archive rather than passed off as
  current. Ask the other teams what date their data is from.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Column Studio overruns and eats the freeze | It starts first on day 2 and is **cut on Thursday morning** if the two curves are not drawing. Everything else in Tier 1 is independent of it |
| The reskin temptation returns | Section 3.2. If it comes up again, the decision is the lead's, but it is a day of work for zero scored points and it breaks the e2e suite |
| Screenshots go stale | Re-capture all 20 on Thursday, after freeze, before rehearsal |
| A competitor turns out to have verification too | Then we still have CAP, OGC proven live, offline, hardware and 567 tests. Depth is the only defence against archetype E, and it is the one we have |
| Adding features breaks the data plane | TDD on everything under `services/`, per CLAUDE.md. Sound speed ships with tests or does not ship |

---

## 9. What this does not change

P0 before P1 still holds: nothing in Tier 1 touches a requirement that is
already met, and the two known gaps stay honest. Chlorophyll remains disabled
as a gridded field because the INCOIS series ends in 2020. Docker remains
authored and unexecuted until someone installs Docker. The agent planner
remains labelled `planner: rules`. We win by being the team whose claims all
survive checking, and that only works if we keep not making the ones that do
not.
