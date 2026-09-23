# Beat the competition: a four day plan to 25 September

**Written 21 September 2026. Rewritten 22 September** after judges reviewed
the prototype and after finding nine competitor codebases on GitHub. Record on
the 25th, submit to the SIH portal straight after.

Working days left: **22, 23, 24.** The 25th is recording and a build freeze.

---

## 1. What the judges said, and what the field actually looks like

### 1.1 The judges, 21 September

They said the prototype **does not look like a 3D model**, and compared it
unfavourably with NULL Pointers. Specifically: it does not read as 3D; the
panels cover so much screen that the globe has no room; the camera gets lost
and does not orbit or zoom well; the colour is off; and we should have the 3D
cube.

**They were right on every point, and the reasons are in the code.**
`OceanGlobe.tsx` draws the field as geodetically placed depth slices with an
opacity transfer function, which its own docblock calls "the slices-only
fallback floor". The ray-marched volume in TRD M3 strategy (c) was never
built, so the scene is 3D-positioned but is not a volume render. The camera
released its reference frame with `lookAtTransform(Matrix4.IDENTITY)`
immediately after the opening shot, handing control to a controller that
orbits the centre of the planet, with collision detection off and no zoom
bounds. Nine panels were mounted on load.

**Do not argue with this feedback.** A judge's first impression IS the product
for the ninety seconds they give it.

### 1.2 Nine competitor codebases, found on GitHub 22 September

YouTube search returns nothing useful for this PS and its result pages cannot
be scraped. GitHub was far better: nine public repositories on SIH26067. Three
were read in full, and the picture is worse than the one this document
described yesterday.

| Team | Stack | Volumetrics | Verification | OGC | Data | Agent |
|---|---|---|---|---|---|---|
| **OceanScope** | Three.js | **GPU ray-marched volume**, marching tetrahedra | bias, MAE, RMSE, **bootstrap 95% intervals** | **WMS + WCS** | Real INCOIS ERDDAP, 10 Argo floats, QC documented | no |
| **incois-3d-ocean-viz** | **Cesium + Three.js + R3F** | isosurface, GPU particles | RMSE, bias, Pearson | CF only | Real GLORYS12V1, NOAA, Argo | no, by choice |
| **OceanTwin 360** | Three.js, OrbitControls | none | R2, RMSE, bias | none | **simulated mock data** | chatbot |
| **NULL Pointers** | Cesium | 3D cube studio | none seen | claimed, never opened | June 2024 snapshot | none |

Also live and unread in detail: `3shits/oceanview`, `Sinchana984/SIH26067`,
`Shravan5566/ATLANTIS`, `Shubham2not/3D-Ocean-Model`,
`oviraraptosarus/incois-3d-ocean-sandbox`, `parassawal/incois-3d-ocean-viz`.

### 1.3 The uncomfortable correction

**OceanScope matches us on most of what this document called our moat.** It has
real INCOIS ERDDAP data, documented QC, TEOS-10 diagnostics, bias and RMSE with
bootstrap confidence intervals, a GPU ray-marched volume, AND it serves OGC WMS
and WCS. It even takes our honesty posture: its README says "OceanScope does
not generate random ocean fields."

So **serving OGC live is no longer a sole differentiator** and the demo must
stop being built around it as though it were. Yesterday's recording script led
with a QGIS proof. That beat is now a tie, not a win.

**What still separates us from every team found:**

- **CAP v1.2 warnings parsed from India's real NDMA SACHET feed.** Nobody else
  speaks CAP. NULL Pointers and OceanScope both have hazard views; neither is
  the national alerting standard, and OceanScope labels its own as
  non-operational.
- **The agent with a refusal guard**, answering only from tool results with
  citations. OceanTwin has a chatbot over mock data; nobody else has one.
- **Air-gapped operation**, enforced by the dependency list rather than claimed.
- **SagarNode**, physical hardware on the globe.
- **The refusal accounting**: 18,294 levels rejected with a reason for each.
  Everyone reports what they scored; we report what we could not.
- **Guided tours** and the outreach mandate.

### 1.4 What this changes about the plan

The visual gap is now the single highest risk we carry, because it is the one
a judge sees in the first ten seconds and two competitors have already closed
it. The build order for the remaining three days is in the plan file, and is:
panel toggles and camera first (done 22 September), then a genuine ray-marched
volumetric cube in Three.js, then colour.

The PS text settles the stack question: **"3D Volumetric Rendering ... WebGL /
Three.js or Cesium.js"**. Both are named, neither is mandated. Using Cesium for
geodesy and Three.js for volumetrics is inside the specification, and is a
better answer to a judge than a defence of why we only have one.

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

### 3.2 The skin: reversed by the judges on 21 September

**This section used to say "do not take the skin", and that was wrong.** The
argument was that `apps/web/app/layout.tsx` carries a design thesis rejecting
the dark dashboard on purpose, that the opaque manila stock stays readable over
moving water, and that every archetype B team would look like each other while
we stayed recognisable.

All of that is still true, and it lost to a simpler fact: judges looked at the
result and said it did not read as a 3D model, and that the colour was off. A
design argument that the audience does not accept is a design argument that
failed, however good its reasoning.

**The decision now is a middle path, not a capitulation.** The panel ground
moves from warm manila to a cool dark slate so the surface reads as a
scientific instrument. The typography, the process-blue rules, the reserved
caution ink and the rule that hue belongs to the measurement all stay. We do
not take the translucent glass, the glow, or the cyan accents, so we still do
not look like OceanScope, OceanTwin or NULL Pointers.

**Shipped 22 September.** The tokens that moved:

| Token | Was | Is | Measured on the new plate |
|---|---|---|---|
| `--plate` | `#c4b89a` manila | `#222B36` slate | 1.40:1 on the water, so the sheet gained a hairline |
| `--plate-shade` | `#b3a686` | `#1A212A` | |
| `--ink` | `#16130d` | `#E3EBF0` | 11.9:1 |
| `--ink-soft` | `#4a4335` | `#A9B8C4` | 7.1:1 |
| `--ink-faint` | `#504935` | `#8493A0` | 4.5:1 |
| `--rule` | `#2b6a86` | `#4A94B6` | 4.2:1, was 2.7:1 unchanged |
| `--caution` | `#b23a22` | `#D4553C` | 3.5:1 |
| `--caution-ink` | `#7e2110` | `#F08A72` | 5.9:1, was **1.6:1** unchanged |

A sweep of the whole surface before the edit found 65 sites, of which two
would have made the change a lie rather than a mistake. The station sheet was
painted with an OPAQUE paper raster whose mean RGB was the old plate, so the
token could have been set to anything at all and every panel would still have
rendered manila. And `--caution-ink`, the ink every honesty surface in this
build is printed in (the DRAFT stamp, the Class-4 caveat, the chlorophyll
disclaimer, the scorecard's error explanation), would have fallen to 1.6:1:
the caveats would have gone invisible while the figures they qualify stayed
bright. Both are fixed. `tools/make_plate_tile.py` now reads `--plate` out of
`globals.css` and refuses to run if the two disagree.

The direction contract in `layout.tsx` is rewritten to match. Leaving a thesis
on disk arguing for a surface we no longer ship is the same class of stale
claim this project refuses everywhere else.

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

- **Full dark reskin to the category default**, meaning translucent glass
  panels, glow and cyan accents. Section 3.2: we change the ground to a
  cool slate and keep everything else.
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

### 5.1 What landed on 22 September, and how it was checked

Each of the judges' five notes has a measurement behind it rather than an
opinion, taken from a headless browser against the production build at both
1920 by 1080 and 1366 by 768.

| Note | What changed | Measured |
|---|---|---|
| "covering the screen too much" | Every overlay is a dock tab, and only the verification card opens on load. The live rig was the last panel still mounted unconditionally and now has its own tab | **0 of 149** station marks on the opening frame sit under a panel. It was 6, and every one of the other eight panels is one labelled click away |
| "does not look like a 3D model" | A real GPU ray-marched volume in Three.js, `Data3DTexture` with early ray termination, beside the residual plot rather than above it | The cube renders at **465 by 411** in the studio, not the 1110 by 336 letterbox the first attempt produced |
| "it gets lost, not in the center" | The camera keeps its `lookAt` frame on the data box instead of releasing it to the globe centre, with zoom bounds and tuned inertia, plus a visible Recentre control | |
| "the colour is a bit off" | Warm manila to cool slate, 65 sites swept, every ratio re-measured (section 3.2) | Every token clears its floor: text at 4.5:1, marks at 3:1 |
| "hidden whenever I want" | One key, `h`, for the pure-globe shot, and a dock control beside it | **0 of 149** marks blocked in water-only mode, and no panel is drawn at all. With all eight open it is 6, which are the six behind the station sheet |

The PS names "**WebGL / Three.js or Cesium.js**", so using Cesium for the
geodesy and Three.js for the volume is inside the specification and is worth
saying out loud to a judge rather than hiding.

### 5.2 Overnight, 22 to 23 September

A pre-freeze review of the day's work found sixteen confirmed defects, of which
six were breaks and two were mine from that same day. All are fixed and the
list is worth keeping, because it is what a reviewer would have found first:

| What | Why it mattered |
|---|---|
| A tour was destroyed by one keystroke | The tour player was unmounted by `h` or by its own dock tab, taking the running tour with it and leaving all eight overlays open with nothing able to close them |
| The clock only ran when its switch was visible | `playing` is scene state the agent and a tour can both set, but the only timer lived inside the station sheet, which is closed on the opening frame. Ask the assistant to run the animation and it reported success while the water stood still |
| The volume's WebGL guard was dead code | `renderer.capabilities.isWebGL2` is hardcoded true in three 0.186, so the real failure escaped as a blank black panel that said nothing |
| Gap edges rendered colder than any cell in the box | Trilinear filtering averages the value channel against missing voxels written as zero. The fix is one divide; the bug is the same lie the two-channel split was built to prevent, at one voxel's width |
| "Cut away below 87 m" for a cut at 10 m | The slider was a fraction of the LEVEL INDEX axis printed as metres on a strongly irregular depth axis. Wrong by up to nine times, printed as a measurement |
| Three overlaps at 1366 by 768 and below 1500 px | The middle column ran under the dock and the cartouche, the dock reached under the profile column, and the recentre control sat on the strip the profile's caveat needs |
| **The scene could still be lost, which is the complaint they actually made** | The 22 September fix held the camera's frame of reference on the data box and set a zoom floor, and it was half a fix. Cesium measures that floor from the `lookAt` origin, and the origin was 190 km underground because a 2000 m column exaggerated 200 times is 400 km tall. Sixty turns of the wheel put the camera 151 km BELOW the sea floor, inside the Earth, with the water behind it. Turning collision detection on got it to 70 km underground and no further. The fix is to aim at the SURFACE and frame the column with pitch and range instead, because a camera at any range and any downward pitch from a surface point is above the ellipsoid, so one bound then holds everywhere |

Fixing it paid twice. Aiming at the surface and framing with pitch and range
put the column in the middle of the frame rather than hanging off the bottom of
it, and the opening range now follows the viewport height so the same framing
holds on a laptop. Measured after: **0 of 149 marks sit under a panel at
1920 by 1080 even with all eight overlays open** (it was 6), and 0 on the
opening frame at 1366 by 768 (3 with everything open, from 18).

That last one was found by a test written to cover the camera, on its first
run, in the code written the day before to fix the same complaint. It is the
clearest argument in this document for writing the test: three people had
looked at that camera and agreed it was fixed.

Two guards were added so the next one is caught by the build rather than by
reading. `tools/check_contrast.py` re-measures every contrast ratio the
stylesheet claims against the ground that token is actually used on, and a CI
job regenerates the station sheet's form stock and fails on any diff, which
also proves the provenance sidecar's byte-for-byte claim. Both are in CI beside
the em-dash guard.

The idea deck was refreshed the same night: every screenshot in it was of the
manila build, slide 2 had no flowchart, and the test count was 567.

---

## 6. The LIVE presentation order, re-ordered 22 September

**This is what you say standing in front of judges, not the portal video.**
The portal video is `docs/VIDEO-RECORDING.md`: one hands-off replay of the
`the-whole-story` tour, thirteen steps, pinned by a test. This section is the
order to lead with when a human is in the room and the first ten seconds decide
whether they keep watching. The two differ on purpose and neither replaces the
other.

Order matters more than any single feature, and the order changed because
OceanScope closed the OGC gap. The old script spent its fifth beat proving a
standard a competitor also serves. That beat drops down.

**The new rule: open on the picture, prove it in the second breath.** Judges
told us the first impression is not 3D enough. Give them the 3D first, then
give them the thing none of them can follow.

1. **Water only.** Press `h`. The globe, the marks and the warning areas, with
   only the provenance cartouche, the scale bar and the dock left on screen.
   Three seconds, no narration. The volume cube is NOT in this shot: it lives
   in the Water Column Studio and it is beat 2. What this shot answers is the
   other half of the review, that the panels left the water no room, and it is
   worth three seconds because every other team opens on a cluttered
   dashboard.
2. **The cube.** Open one cast in the Water Column Studio, spin it. This is the
   feature they asked for, and ours carries the model curve, the measured curve
   and the shaded residual between them. A cube alone is a prettier picture of
   the same thing. A cube beside its own error is an argument.
3. **The verification card.** "This is how wrong today's model is, and here is
   how we know." Bias +0.026, RMSE 0.602, 11,718 matched pairs, worst band 50
   to 100 metres at 2.07 degrees. Then the line nobody else says:
   **18,294 levels were refused, and here is the reason for each.**
4. **HazardWatch.** Say the theme out loud: the portal files this under
   Disaster Management. Show the CAP areas. State plainly that the three ocean
   bulletins are rehearsals stamped EXERCISE and why. **This is now our
   strongest sole differentiator**: nobody else found speaks CAP.
5. **The agent.** Ask it something, show the tool trace and the citations, then
   ask it the weather in Delhi and let it refuse. `planner: rules` stays
   visible.
6. **The WiFi is off.** Three seconds, and it converts "deployable on INCOIS
   infrastructure" from a promise into something the viewer watched happen.
7. **Extensibility, live.** Add a source in `sources.yaml` and show it appear.
   Mention that the sound-speed plugin shipped this week and reached WMS and
   WCS without a line of OGC code changing.
8. **Standards, briefly.** Point QGIS at `/wms`. Keep it short now: it is a
   tie with OceanScope rather than a win, and spending a minute on a tie is a
   minute not spent on CAP or the refusal count.

Close on the three numbers that are hard to fake: 13 sources across 9 kinds,
30,012 quality-controlled levels, 577 tests.

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
