# P0 status: the problem statement's own requirement list

**Measured 2026-09-07, extended 2026-09-08 and 2026-09-22.** Every number
below was read off the running service on the build laptop, not copied from an
earlier run. The commands that produced them are in each row so anyone can
re-run them and disagree with me.

**What the 22 September pass changed here.** The test counts, and F1: a GPU
ray-marched volume now renders the box, where before the scene drew the field
as stacked depth slices. The Intel UHD frame-rate measurement below was NOT
re-run and is NOT overwritten, because today's machine offered a discrete GPU
and a number from an RTX 3050 is a different claim about a different computer.
It is quoted separately and labelled.

PRD §5 defines P0 as the PS's explicit requirement list, F1 to F7. CLAUDE.md
says P0 comes before P1 always, so this file exists to make "is a P0 item
missing?" a question with a checkable answer instead of a feeling.

## How to read the verdicts

| Verdict | Means |
|---|---|
| **Met** | Every clause of the PS requirement is built, running, and covered by a test that would fail if it broke. |
| **Partly met** | The requirement is built and demoable, but a clause of it named in the PS text is not there yet. The missing clause is stated, never implied. |
| **Blocked** | Cannot be finished from this machine. The blocker names who can unblock it. |

A "Met" with no missing clause is not a claim that the feature is finished
forever, only that the PS's sentence is satisfied and proven.

## Summary

| # | Requirement | Verdict | The gap, if any |
|---|---|---|---|
| F1 | 3D volumetric rendering | **Partly met** | All three named techniques are built, and since 2026-09-22 so is a fourth that the PS's own words ask for before it names any technique: a GPU ray-marched volume, in Three.js, which the PS explicitly permits. The remaining gap is a field, not a technique. Every field the PS names is now drawn except one: temperature, salinity and depth-resolved CURRENT VECTORS, the last live since the Copernicus account arrived on 2026-09-09. SEVEN gridded fields render in total, three of them plugin-derived: D26, SIG0 (potential density, TEOS-10) and sound speed. Chlorophyll is registered and deliberately disabled as a GRIDDED field: the INCOIS series ends in 2020 and cannot share a 2026 scrubber. It is served as in-situ BGC-float data, which is contemporary. |
| F2 | Instrument data overlay | **Met** | All four instrument classes the PS names are live and drawn as different marks: Argo floats, BGC floats, a glider and shipboard CTD casts, plus a RAMA moored buoy. 149 casts from 19 instruments, 30,012 QC-passed levels. The glider and the CTD casts predate the model field and are marked, dated and refused by the verification rather than left to pass for current. |
| F3 | Multi-format data ingestion | **Met** | None. |
| F4 | Customizable colorbar and variable controls | **Met** | None. |
| F5 | Web-based, scalable architecture | **Met** | Verified 2026-09-25: three containers (`docker compose up --build`), all 12 browser tests passing against them, and the data plane answering the full verification card with its network disabled. `./tasks.ps1 docker` re-runs all of it. |
| F6 | Extensible design | **Met** | Both extension points have running examples: THREE derived products (D26, SIG0 density via TEOS-10, and sound speed, the last added 21 September), all served through WMS and WCS, and a `mooring` source reader on real RAMA buoy data. The PS's "additional sensors" clause also has a live device path: SagarNode posts to `/ingest/sagarnode` and appears on the globe, with `curl` as a sufficient device. |
| F7 | Open standards (OGC WMS/WCS, CF) | **Met** | None. Stored variables and plugin-derived products are both served. |

Six of seven have no gap. The seventh, F1, is short one GRIDDED field, and
that is a deliberate refusal rather than missing work: the INCOIS chlorophyll
series ends in 2020 and cannot share a 2026 time scrubber without the interface
making a false statement. F5 closed on 2026-09-25 when Docker was installed and
the stack was run for the first time; the glider and CTD gap closed earlier.

## Test and check counts behind these verdicts

```
services/api      512 tests   (argo 20, cap 47, cf 20, colormap 10, currents 16,
                               density 19, field 30, in-situ TAC 17,
                               isosurface 27, offline 3, ogc 63, plugins 71,
                               sagarnode 27, scorecard 24, sound speed 16,
                               storyboards 36, text profiles 66)
services/agent     83 tests   (guard 13, planner 56, scene-key drift 2, voice 12)
e2e                12 tests   production build, real browser, off-origin guard
```

Re-collected on 2026-09-23 with `pytest --collect-only -q`, not from memory.
The first version of this block said 506 with storyboards at 30, which was a
true reading taken an hour before the same day's six new storyboard tests
landed: a number can go stale inside a working day, and a block whose whole
claim is that it was measured rather than remembered is the wrong place to
find that out. The growth since 2026-09-08 is the in-situ TAC reader, the
sound-speed plugin, more OGC coverage, the tour `stage` field with its
validation and its client drift check, and two browser tests: one for the
current-vector layer and one, added 23 September, for the panel dock, the tour
restore path and the camera bounds.

The two Python suites are run separately, and must be: both declare a `tests`
package, so pytest resolves the second one's modules against the first one's
rootdir and collection fails. CI runs them as separate jobs for the same
reason.

Reproduce: `./tasks.ps1 test` and `./tasks.ps1 e2e`.

---

## F1. 3D volumetric rendering

> "3D Volumetric Rendering ... WebGL / Three.js or Cesium.js"
>
> Fields named in PRD §5: temperature, salinity, current vectors, chlorophyll.
> Techniques named: depth-slice views, isosurface extraction, time-step
> animation.

**Built.** The Bay of Bengal water column as 24 depth-sliced layers on a
CesiumJS globe, 5 m to 2000 m, blended back to front with a depth-space level
of detail that keeps at most 10 slices alive at once. Time-step animation over
the three available analysis dates, with a RUN control. Temperature and
salinity both render.

**Evidence.**

```
curl "http://127.0.0.1:8000/field/incois_vam_argo/TEMP?bbox=80,5,95,25&time=2026-07-30&all_depths=true"
  -> shape [24, 20, 15]   depths 5.0 .. 2000.0 m   time 2026-07-30T00:00:00Z   units degC
```

**Frame rate, measured today.** Counting actual renders, not animation-frame
ticks, while the camera orbits continuously for 5 seconds:

```
GPU                Intel UHD Graphics via ANGLE D3D11 (the integrated chip)
canvas             1920 x 1080, resolutionScale 1, devicePixelRatio 1
slices drawn       10 of 24 (the depth-space level-of-detail cap)
frames rendered    252 in 5.00 s
median             51 fps
95th percentile    27.6 ms per frame  (36 fps)
worst frame        37.0 ms            (27 fps)
```

TRD §5 sets a 60 fps goal with a 30 fps floor at 1080p. The floor holds at the
95th percentile; the goal is not reached, and the single worst frame in five
seconds dips just under it. That is the honest reading and it is above the
Phase 1 exit gate of 30.

Two things about this measurement are deliberate. It is taken on the Intel
integrated chip rather than the RTX 3050, because the weaker GPU is the one a
nodal-centre machine will resemble. And it counts Cesium `postRender` events
rather than `requestAnimationFrame` callbacks, because an idle globe in
request-render mode fires animation frames while drawing nothing, which would
report a frame rate for a scene that is not being drawn.

**The e2e figure is not this figure.** The Playwright run records a frame-rate
annotation of roughly 7 fps. That is the same scene under trace capture, which
screenshots every action, and it is recorded for trend only with no threshold
asserted. Asserting the TRD floor inside an instrumented run would either fail
a healthy build or get quietly lowered until it passed and then certify
nothing. The annotation says so in its own label.

**Built 2026-09-22: a GPU ray-marched volume.** The PS sentence is "3D
Volumetric Rendering ... WebGL / Three.js or Cesium.js". Until today the scene
answered it with stacked depth-slice rectangles carrying an opacity transfer
function, which TRD 6.4 itself calls the slices-only fallback floor: 3D
positioned, but not a volume render. TRD M3 strategy (c) was specified and
never built. It is built now, in `apps/web/components/VolumeCube.tsx`, and the
statement names both tools, so Cesium keeps the geodesy and Three.js gets the
volumetrics rather than one replacing the other.

```
technique     single-pass ray march in a GLSL3 fragment shader
              ray-box intersection, front-to-back accumulation,
              early ray termination at alpha 0.96, 64 samples per ray
data          THREE.Data3DTexture, RG8: R is the value normalised over
              vmin..vmax, G is validity. Two channels, deliberately: folding
              validity into the value channel made every gap in the analysis
              render as the coldest water in the box
box           24 depth levels by 21 latitudes by 16 longitudes, ~8,000 voxels,
              which is a rounding error for a GPU. The cost is screen pixels
              times steps, not data
colour        the ramp is built by calling rgbFor() from lib/colormap.ts at the
              same vmin and vmax the globe uses, so the cube CANNOT disagree
              with the colorbar about what a colour means
controls      orbit with damping, auto-rotate, and a depth cutaway that
              discards everything below a chosen level to expose the
              thermocline
measured      465 by 411 px in the studio, 60 fps with the volume spinning
              (RTX 3050 laptop GPU via ANGLE D3D11, 1920x1080)
```

It is placed in the Water Column Studio in the same grid row as the residual
plot, so the same cast appears twice: once as a volume and once as the
difference between the model and the instrument that measured it. That is the
part no competitor repository found on 2026-09-22 does.

**Built: isosurface extraction.** `GET /isosurface/{source}/{var}` returns the
surface where a field takes a given value as a triangle mesh, and the scene
draws it as real geometry. All three techniques the PS names for F1 are now
present.

```
curl ".../isosurface/incois_vam_argo/TEMP?value=26&value_units=degC
       &bbox=80,5,95,25&time=2026-07-10"

  -> 200, 26.4 KB of JSON, 8.2 KB on the wire after gzip
     482 vertices, 888 triangles, 2 components, 54.7 to 107.5 m
     n_cells 6118, active 224, skipped for a missing corner 2657,
     straddling but masked 40, ambiguous 0, degenerate culled 0
     extractor marching_cubes 1.0.0
```

**Marching cubes, and the reason is provenance rather than topology.** Three
approaches were argued independently before any code was written: a
depth-per-column height field, marching tetrahedra, and marching cubes.

Every marching-cubes vertex sits on an axis-aligned cell edge, so it is a
one-dimensional statement of the kind this project already makes: linear
interpolation in depth between two bracketing measured levels, or its
horizontal analogue between two adjacent columns at one measured level. An
oceanographer can ask which two measurements produced any vertex and get an
answer.

Marching tetrahedra is far easier to implement correctly, and was rejected on
that same ground: most of its vertices land on decomposition DIAGONALS, joining
75 m at 12.5 N to 100 m at 13.5 N. That is exact arithmetic about nothing
physical, and the answer depends on how the cells were split, so the surface is
not reproducible without also publishing a diagonal convention.

The height field was rejected because it cannot represent a column that crosses
the value twice, and those are real here: on 2026-07-10 seven Bay of Bengal
columns cross 26 degC twice, and the 35 psu isohaline breaks into **6 separate
components**. A height field would have to pick one crossing and call it the
surface.

**It agrees exactly with the science already reviewed.** For every column with
exactly one crossing, the depth the mesh places on the vertical edge equals the
D26 plugin's `isotherm_depth` to **0.000e+00 m**, across 205 to 207 columns on
each of the three timesteps. That is asserted as exact equality rather than
approximate, on purpose: it welds new geometry to reviewed science instead of
letting it become a parallel truth.

**It finds structure nothing in it knows about.** On 2026-07-10 the mesh
separates into two components, the main thermocline sheet plus a closed warm
lens beneath it. That is the Bay of Bengal barrier layer, where monsoon and
river freshwater cap warmer water, and no code in the extractor knows that
inversions exist.

**What it refuses.** A cell is meshed only if all eight corners carry a finite
value, so land, the seabed and the sampled margin are HOLES rather than an
interpolated skin over a corner we invented. The rim of every hole is drawn on
screen in the caution ink the design system uses for a refusal, and the count of
cells that straddled the value but were skipped for a missing corner is served
in the payload and printed in the panel. The surface stops short of the coast
and says so.

**Correctness evidence.** 27 tests, written against the failure modes that
produce a picture rather than an error:

| Check | Result |
|---|---|
| Analytic sphere at n = 12, 20, 32, 48 | Euler characteristic 2, zero boundary edges, zero orientation clashes, positive signed volume converging on the true 1.4368 |
| Sphere surface-area error | 2.20%, 0.72%, 0.27%, 0.12%, monotonically shrinking |
| Torus | Euler characteristic 0 |
| 200 random noise fields, 470,352 triangles, all 256 corner cases | zero non-finite vertices, zero boundary edges, zero orientation clashes, every edge used exactly twice, every signed volume positive |
| Non-uniform depth axis | a crossing halfway between 5 and 10 m gives exactly 7.5 m, and halfway between 1800 and 2000 m gives exactly 1900 m |

The random-noise test is the one that matters most. A winding rule that reads
the local gradient passes every smooth-field test and fails on noise, which is
the worst possible failure schedule for a demo, so the winding here is
structural: each cube face is walked in the order its corners appear from
outside the cell, and two cells sharing a face therefore see opposite cycles and
agree across the shared edge without anything inspecting the data.

**Frame budget, measured rather than assumed.** With ten slices drawn and the
surface on, the scene fell to **28.7 fps median**, under the TRD floor of 30.
The 780 triangles are not the cost: overdraw is, because a translucent fragment
behind an opaque one is still rasterized and blended. The slice budget therefore
drops from 10 to 6 while the surface is on, which is the right way round, since
a forecaster who turns the surface on is reading the surface and the stack is
context. Measured after that change:

```
surface off   10 slices              51.5 fps median, worst frame 34.8 ms
surface on     6 slices + 780 tris   73.0 fps median, worst frame 27.2 ms
```

Turning the surface on is now FASTER than leaving it off, which also confirms
the diagnosis. Four fewer full-domain translucent quads more than pay for the
geometry.

**Currents at depth: the data is now here.** INCOIS ERDDAP publishes surface
geostrophic currents only, so this is the one part of F1 no INCOIS source can
answer. The team lead created a free Copernicus Marine account on 2026-09-09
and the source went live the same evening.

```
python tools/fetch_sample.py     # 42 MB, about 4 minutes
python tools/preprocess.py

glorys12_cur   uo, vo   40 levels 0.49 to 1942 m   3 steps   241 x 181 cells
               valid 64.6%   uo [-1.24, 1.46] m/s   vo [-1.03, 1.12] m/s

curl ".../field/glorys12_cur/uo?bbox=85,12,86,13&time=2026-07-30&depth=100"
  depth 92.33   units m s-1   169 cells   u -0.228 to 0.002
```

Note the `depth: 92.33` in that response. The request asked for 100 m and the
answer says what it actually served: GLORYS has its own 40 levels, none of them
shared with the INCOIS 24, and it is NOT regridded onto them. Regridding would
be an interpolation nobody asked for, applied to make two products look like
one.

**The account also caught a configuration error that would have shipped
quietly.** The registry entry named `cmems_mod_glo_phy_my_0.083deg_P1D-m`, the
GLORYS12V1 multi-year reanalysis. Probed with real credentials, that product
runs to **2026-06-23**. This cube's three steps are 2026-07-10, 07-20 and
07-30, so every one of them is after the reanalysis ends and the configured
source could not have produced a single contemporaneous field. It is the same
trap that keeps the chlorophyll source disabled below, and it was invisible
until somebody could log in. The analysis-and-forecast currents product,
`cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m`, covers 2022-06-01 to 2026-09-18
and is what is configured now. A test asserts the dataset id does not contain
`_my_`, with the dates in the failure message.

Temperature and salinity are deliberately NOT taken from Copernicus even though
the reanalysis carries them: INCOIS's own analysis is the PS-preferred source
and the one the scorecard verifies, and two answers to one question with
nothing to choose between them is worse than one.

**And they are now drawn.** `GET /currents/{source}` serves a decimated vector
field and the globe draws it as arrows at the depth cursor.

```
curl ".../currents/glorys12_cur?bbox=80,5,95,25&time=2026-07-30&depth=100"

asked     5 m -> served     5.08 m |  396 arrows, 171 refused of 567 blocks | fastest 1.27 m/s
asked   100 m -> served    92.33 m |  359 arrows, 208 refused of 567 blocks | fastest 0.63 m/s
asked  1000 m -> served  1062.44 m |  329 arrows, 238 refused of 567 blocks | fastest 0.26 m/s
```

The field weakens with depth and more blocks are refused as the seafloor
rises, both of which are the ocean rather than the code.

**Three decisions in that reduction, each of which could have gone the other
way.** 43,621 cells per level is not a picture, so the field is reduced, and
how it is reduced is the whole design of `app/currents.py`:

- **Blocks are AVERAGED, not sampled.** Taking every Nth cell is cheaper and it
  aliases; on a velocity field aliasing invents eddies that look exactly like
  the real ones.
- **A block less than half water is REFUSED**, not averaged from the two wet
  cells that remain, which is precisely the shelf a forecaster reads. Refused
  blocks are counted and served, so a sparse arrow field is distinguishable
  from a broken one.
- **A cell missing either component contributes nothing.** A velocity needs
  both; averaging u where v is absent points an arrow at nothing measured.

The reduction is disclosed on the response and printed on the sheet: the
stride, the cells behind each arrow, and the blocks dropped.

**Two things the interface refuses to blur.** The sheet names the depth
ACTUALLY served, because GLORYS's 40 levels do not line up with the INCOIS 24
and the arrows sit a few metres from the slice beside them. And the control
says in words that the arrows are Copernicus while the colours are INCOIS, so
nobody leaves thinking one dataset supplied both.

Arrow LENGTH carries speed, not colour. Hue on this surface belongs to the
measurement and the colorbar has already spent it on the scalar field; a second
colour scale would put a fast arrow in competition with warm water and make
neither readable.

**Chlorophyll: the source exists, is registered, and is deliberately OFF.**
INCOIS publish ocean colour on the same open ERDDAP the model field comes from,
and `incois_oceansat2_chl` is now a real entry in `data/sources.yaml` carrying
CHL, KD490 and TSM. It ships `enabled: false` with a `disabled_reason`, and the
three reasons are decisions rather than missing work.

**It is not contemporaneous.** The series ends 2020-05-01; the cube covers July
2026. A scrubber reading 2026-07-30 above a 2020 chlorophyll layer is a false
statement made by the interface itself, made silently, and nothing in the scene
can yet express "this layer has its own epoch".

**It is a surface field.** Ocean colour has no profile, so the source is
(time, lat, lon) with no vertical axis, while every cube in the store is 4D. A
sweep of the codebase for depth-axis assumptions found the client is
single-dataset by construction and would answer "the depth cursor is at NaN
metres", print "0 depth levels from 0 to 0 metres", and unmount the scale bar,
taking the frame-rate readout with it.

**Payload.** At 0.04 degrees this is about 375 x 500 = 187,500 cells for ONE
surface timestep in the demo box, against 300 cells per level and 7,200 for the
ENTIRE 24-level column. A single timestep is roughly 26 times the whole water
column we render today, transported as JSON. The ingest needs a decimation
decision with a scientific cost attached, and nobody has taken it.

Registering it disabled is the honest middle state: the breadth is on the
record, the reason is written down where the next person will find it, and no
2020 frame can reach a projector. Contemporaneous chlorophyll DOES reach the
screen from the other direction, as measured BGC float profiles under F2.

**The sweep paid for itself before the feature.** Half of what it found were
live bugs with no chlorophyll in the tree at all, each of them silent:

| Defect | What it did | Now |
|---|---|---|
| `/field` served `"depth": 0.0` for D26 | A field whose own values run 41 to 96 m was labelled as coming from the surface level. The fabricated number is exactly what CLAUDE.md forbids, and it was shipping. | `depth` is null for a surface product. The one remaining `[0.0]` is a transport placeholder and the response says so in `surface_level_is_a_placeholder`. |
| Canonical axis order keyed on the whole dataset | The target order was built from the union of every variable's dims, so a surface variable sharing a dataset with a volumetric one was left in the file's own order. Reproduced: `CHL` came back as `(lat, lon, time)` while `TEMP` was correct, with no error, under a comment promising the renderer never has to guess an axis. | Ordered per variable. A DECLARED variable carrying an axis outside the canonical set is refused by name; an auxiliary one (CF bounds carry `nv`) is left alone. |
| A `cf_overrides` key naming nothing was ignored | One letter out (`CHLA` for `CHL`) left a -1.0E34 fill unmasked and the served minimum at -9.999999790214768e+33: a colorbar spanning 1e34 with every real value the same colour, a correct-looking legend, and no exception. | Refused at startup, against what the REGISTRY declares rather than what a file contains, so `incois_vam_argo` keeps its legitimate corrections for TERR and SERR which the Bay of Bengal subset does not fetch. |
| The Argo `PRES` overrides did nothing | `cf_overrides` is consumed in exactly one place, `cf.normalize_dataset`, which runs only on gridded sources. Argo files are parsed by `app/argo.py`, which never reads them. | Kept, and labelled in `sources.yaml` as documentation of the file's convention rather than an applied correction. |
| The time scrubber pointed at the wrong step | `Math.max(0, indexOf(current))` meant a time the axis does not contain drew the solid "you are here" tick on the FIRST step, and the play loop's `(-1 + 1 + n) % n` then jumped to step 0 as well, which made it look like it worked. On a projector that is a scrubber pointing confidently at a date the scene is not showing. | Not clamped. Off the axis, no tick is lit and the rule says "off axis". |
| `/profiles` answered 200 for a date years away | A bare day-equality with no range check, so a request outside the observations returned count 0. That reads as a statement about the OCEAN ("no floats in this box") when the true statement is about the REQUEST. `/field` has refused this since the beginning through `store.nearest_time`; the two endpoints disagreed. | Refused with the range it does cover. A quiet day INSIDE the window still returns 200 with count 0, because that one is a real answer. |

Eleven tests pin these, each naming the reproduction.

## F2. Instrument data overlay

> "Instrument Data Overlay"
>
> PRD §5: Argo floats, Gliders, CTD, BGC as geospatially accurate clickable
> markers, leading to a depth-vs-variable profile chart with timestamps.

**Built, for Argo.** 13 real floats from the Argo GDAC Indian Ocean daily
files sit on the globe at their surfacing positions. Clicking one opens its own
measured profile with the float's WMO id, its surfacing timestamp, the QC
policy applied, and the dataset citation.

**Evidence.**

```
curl "http://127.0.0.1:8000/profiles?bbox=30,-30,120,30"   -> 13 profiles
curl "http://127.0.0.1:8000/profiles/1902681_20260730T174500"

  1902681   2026-07-30T17:45:00Z   6.37N 82.13E   524 levels
        3.50 dbar     3.48 m    26.430 degC   psal 34.66
      717.60 dbar   712.38 m     8.914 degC   psal 35.018
     2022.80 dbar  2001.88 m     2.755 degC   psal 34.772
  qc_policy: QC flags [1, 2] only (Wong et al. 2020)
```

Note that pressure and depth differ by 21 m at the bottom of that cast. That
gap is the whole reason `argo.py` converts through TEOS-10 rather than treating
decibars as metres.

**Built, for BGC floats.** Three biogeochemical Argo floats sit inside the
demo box, contributing 9 profiles that are contemporaneous with the model
field, and they carry real dissolved oxygen, chlorophyll-a, nitrate, pH and
particle backscattering. They are drawn as diamonds rather than squares, so an
instrument class is told apart by silhouette rather than by colour, since hue
on this surface belongs to the measurement.

**Evidence.**

```
curl "http://127.0.0.1:8000/profiles?bbox=80,5,95,25"
  -> 22 profiles   kinds: gdac_geo 13, gdac_bgc 9
     source_ids: ['argo_bgc_indian', 'argo_gdac_indian']

curl "http://127.0.0.1:8000/profiles/2903831_20260728T141348"

  BGC float 2903831   2026-07-28T14:13:48Z   18.09N 89.84E   1444 levels
     depth      temp     psal      doxy       pH
       5.0    28.489   31.898         -        -
     200.5         -        -     2.639    7.607
    1499.5     4.671   34.851         -        -
  oxygen minimum 1.71 micromole/kg at 140.9 m
```

Four things in that output are worth reading closely, because each is a
decision rather than an accident.

**The oxygen minimum is real and is the point.** 1.71 micromole/kg at 141 m,
under a 28.5 degC surface, is the Bay of Bengal oxygen minimum zone: water that
is effectively anoxic a hundred and forty metres below a warm tropical surface.
It is the single most scientifically interesting number in the dataset, and a
pipeline that clamped or interpolated near-zero values would have erased it
while looking perfectly healthy.

**The gaps in the table are gaps, not zeroes.** A BGC sensor samples far more
sparsely than the CTD beside it: on this profile the CTD returns 1012 levels
and nitrate returns 76. So a level can carry oxygen and pH but no temperature,
and the API omits a parameter rather than serving a column of nulls. Below 200
samples the chart shows its sample points, because the line between two BGC
measurements is drafting and not data.

**Chlorophyll only exists because the adjusted product is read.** On these
floats the raw `CHLA_QC` is flag 3 on every one of 13,934 measured levels, with
nothing at flag 1 or 2, and only `CHLA_ADJUSTED_QC` reaches flag 2. Our policy
accepts 1 and 2 only. A reader that took the raw values would therefore serve
NO chlorophyll while appearing to work, so `prefer_adjusted` in the registry is
load-bearing rather than a nicety, and there is a test whose whole purpose is
to stop it being switched off. The raw values are also not physical: raw
chlorophyll runs to -0.993 mg/m3 from fluorometer dark-offset drift, and raw pH
spans -381.6 to 157.6 against an ocean range of about 7.4 to 8.2.

**The BGC files were trimmed in time on purpose.** A float's synthetic profile
file carries its whole deployment history: these three hold 132 profiles from
2025-04-15 to 2026-08-30, against a model cube covering three dates in July
2026. Drawing an April 2025 float mark inside a July 2026 field, on one globe,
under one time scrubber, would state a co-location that does not exist. The
ingest keeps only profiles inside the cube's own span widened by half a
timestep, and prints how many it dropped.

**Built, for gliders and CTD casts, on 2026-09-15.** All four instrument
classes the PS names are now live. This section previously read "Gap: no
glider or CTD cast is loaded" and concluded the blocker was data availability
rather than code. That conclusion was wrong, and it is worth recording exactly
how, because it is a mistake worth making only once.

**What the earlier search got wrong.** It looked in three places and came back
empty: INCOIS's own ERDDAP (17 datasets, all gridded products plus one tabular
Argo set), GTSPP's July 2026 best-copy file (5,247 Indian Ocean casts, 211
inside the box, every one of them a single moored buoy at 13.98 N 87.02 E), and
the Copernicus in-situ feed, which on 2026-09-01 carried 42 gliders worldwide
and exactly one in the Indian Ocean, at 12.83 S 45.38 E in the Mozambique
Channel. Each of those findings was correct. The conclusion drawn from them was
not, because the Copernicus dataset was queried through its `latest` part, a
ROLLING THIRTY-DAY WINDOW, and the absence of a glider in the last thirty days
is not the absence of a glider.

**What found it.** The problem statement's own "Dataset Link" field on
sih.gov.in names four archives for SIH26067, and the third is
`ftp://ftp.ifremer.fr/ifremer/glider/v2/`. That archive is real and reachable;
its published index, `glider_prof_index.txt`, is 248 MB of whitespace, checked
at four offsets, which is a broken build on the publisher's side. The same
holdings reach the Copernicus in-situ Thematic Assembly Centre, whose `history`
part indexes 89,115 files. Five gliders and twenty-four CTD collections
intersect the demo box.

**The glider.** `ru29`, a Rutgers Slocum glider, WMO 2801900, flying off
southern Sri Lanka from 12 August to 24 October 2018. 944 half-dives, 472 of
them descending, 109 of those inside the demo box, to 955 m, carrying
temperature, salinity and conductivity. **13,278 levels pass QC.**

The same deployment is ALSO published as `GL_PR_GL_SLU29.nc` by the Australian
Ocean Data Network, with a finer depth axis and a blank WMO field. It is the
same physical glider. Ingesting both would have put two gliders on the globe
where the ocean held one, which is the identical overcount as calling 25 casts
25 instruments, a mistake this project has already made once and corrected.

**The CTD.** `SHINYO MARU`, platform JFCL, fifteen shipboard casts in the Bay
of Bengal between February 1990 and February 1991, 8.5 N to 15.1 N and 85.9 E
to 90.0 E, to 1091 m. **344 levels pass QC.**

**Both are out of epoch, and that is the interesting part.** The model cube
covers July 2026. This repository already refuses to draw INCOIS's own
Oceansat-2 chlorophyll for exactly this reason, in that source's own words: "a
scrubber reading 2026-07-30 above a 2020 chlorophyll layer is a false statement
made by the interface itself, and it would be made silently." The word doing
the work there is SILENTLY. The rule forbids an unstated false claim, not old
data.

So the registry grew an `epoch` marker, which the chlorophyll entry had already
named as the missing capability, and an archive source is refused at load
unless it also carries an `epoch_note` saying why it is one. Four things then
happen that together make showing these casts honest rather than misleading:

1. The mark is drawn inside a ring. The glyph itself is untouched, so it
   still reads as a glider, following the same rule selection and alarm already
   follow on this surface: status is stamped around a mark, never coloured into
   it. The ring is SOLID, and that is the second time this project has learned
   the same lesson: the first attempt dashed it, because dash means "not the
   live thing" everywhere else here, and rendering it showed the dashes landing
   sub-pixel. These marks are drawn at 15 px from a 44 px canvas, so what
   survives is a change to the silhouette, not a texture inside it. The
   SagarNode glyph a few lines away in the same file records the identical
   finding.
2. Clicking it prints ARCHIVE OBSERVATION and the note, above the chart.
3. The scorecard's five-day rule refuses every one of those levels and COUNTS
   the refusal: `refused.no_model_time` is **13,622**, which is 13,278 glider
   levels plus 344 CTD levels exactly. They are displayed against the model and
   never scored against it.
4. The standing copy in the instrument panel, which used to say every mark was
   "contemporaneous with the model field", was true when written and became
   false the moment these arrived. It now names the epoch. A line of prose that
   quietly goes stale is the same defect as a mark that does not say what it is.

**Why show them at all.** Because the alternative is not a contemporaneous
glider; it is no glider. The Bay of Bengal has none in the water now, and the
PS asks for gliders to be CO-DISPLAYED, not verified. A judge who asks "where
are the gliders" gets a real Rutgers deployment, its date, and the reason the
system declines to score it, instead of an apology.

**Evidence.**

```
curl "http://127.0.0.1:8000/profiles?bbox=80,5,95,25"
  -> 149 casts from 19 instruments
     glider 109 (archive) - ctd 15 (archive) - gdac_geo 13 - gdac_bgc 9 - mooring 3

curl "http://127.0.0.1:8000/profiles/2801900_20180812T023601"
  Glider 2801900   2018-08-12T02:36:01Z   8.631N 81.287E
  epoch: archive
  citation: Copernicus Marine in-situ TAC (INSITU_GLO_PHYBGCWAV_DISCRETE_
            MYNRT_013_030, history part). Glider ru29, Rutgers.

curl ".../scorecard/incois_vam_argo/TEMP?bbox=80,5,95,25&time=2026-07-30"
  overall.n              11718   <- contemporaneous pairs, unchanged
  n_profiles                23   <- only the casts that may honestly be scored
  refused.no_model_time  13622   <- every archive level, counted
```

**Five defects in the source files, each handled and each observed.** The
reader is `services/api/plugins/insitu_tac.py` and its tests are
`services/api/tests/test_insitu_tac.py` (18):

1. **Pressure is not depth.** The files measure decibars. Depth depends on
   latitude because gravity does, so the conversion is TEOS-10's
   `gsw.z_from_p`. At 1000 dbar at 5 N the difference from assuming a metre per
   decibar is **7.9 m**, which is wider than the spacing between the model's
   deep levels: an observation placed 7.9 m too deep is interpolated against
   the wrong part of the column and the difference is then reported as model
   error.
2. **Pressure that reverses.** 475 of ru29's 944 half-dives are non-monotonic.
   Most of that is the ascending legs, whose pressure decreases by definition;
   3 descending dives still reverse, because a glider samples continuously and
   wobbles at the apex. The counter reports the 3, not the 475, because the 475
   would count the ascending legs twice, once as dropped and once as disordered.
3. **Gaps in pressure.** 943 of 944 half-dives contain a NaN pressure, and on
   these files the number of gaps INSIDE a dive's sampled span is **0**: the
   file is a rectangle padded out to its longest dive, so all 20,667 NaNs are
   padding. A counter that summed raw NaNs would have reported 20,667 missing
   levels and been believed.
4. **A good measurement at a bad depth.** `PRES_QC` 4 occurs alongside
   `TEMP_QC` 1. Filtering on the temperature flag alone accepts a reading the
   instrument itself could not locate, so the pressure flag is folded into
   every parameter's flag.
5. **Floating-point quality flags.** The flags arrive as floats and a missing
   flag is NaN. Casting NaN to an integer is undefined and in practice yields a
   large negative number that no accepted-flag test matches by accident rather
   than by decision. Missing maps explicitly to 9.

**One profile per dive.** A glider profiles going down and again coming up, and
both legs are in the file tagged 'D' and 'A'. They are minutes apart in nearly
the same water, so keeping both would double the apparent number of independent
observations. The descending leg is kept and the 472 ascending legs are counted
and disclosed.

**This is also the second proof of F6.** The PS's extensibility requirement
names its own worked example: "future integration of additional sensors (e.g.,
CTDs, moorings, HF-radar, ADCP)". Moorings arrived through the plugin
source-reader interface. CTDs and gliders arrived through the SAME interface
with no change to the core: one plugin file and two registry entries. The claim
F6 is graded on is now demonstrated twice by two different instrument classes,
rather than asserted once.

**The text-cast readers are still unused, and still wanted.** `ctd_text_ascii`
and `odv_spreadsheet` read a delimited-text cast handed over on a USB stick,
which is a different thing from an archive holding in NetCDF and is the form a
cast from INCOIS would most likely arrive in. Those two remain built, tested
(66 tests) and waiting for a real file.

Today `profiles.parquet` holds **149 casts from 19 instruments and 30,012
QC-passed levels**, up from 25 casts, 17 instruments and 16,390 levels. All
four instrument classes the PS names are live, plus a moored buoy it names
under F6.

## F3. Multi-format data ingestion

> "Multi-format Data Ingestion"
>
> PRD §5: automated NetCDF (xarray) plus delimited-text parsers, and a modular
> source registry so a new variable or source is a config entry, not a rewrite.

**Verdict: met.**

`data/sources.yaml` carries 6 sources across 5 kinds (`erddap_griddap`,
`gdac_geo`, `file` twice, `copernicus`, `zarr`), of which 5 are enabled. Adding
the two text sources required no new code: both are config entries, including
their column layouts, which is the claim the requirement is actually testing.

The CF normalization handles the defects the real INCOIS files carry, which is
why these tests are not synthetic: `_FillValue` of -9999.0 in one product and
-1.0E34 in another, `units="degs"` for degrees Celsius, `cm/sec` currents, and
a vertical coordinate named `ZAX` with no `positive` attribute, which means
cf-xarray cannot infer which way depth counts. Packing is applied exactly once,
guarded by checking `.attrs` against `.encoding`, because applying
`scale_factor` twice is silent and plausible.

Masking is visible in the served field rather than asserted in a comment:

```
depth    5.0 m   300 cells   86 masked   27.66 .. 30.14 degC
depth  200.0 m   300 cells  108 masked   12.14 .. 16.27 degC
depth 2000.0 m   300 cells  139 masked    2.65 ..  2.65 degC
```

The masked count rising with depth is the shelf and the sea floor entering the
box, which is what a correct land and bottom mask looks like.

## F4. Customizable colorbar and variable controls

> "Customizable Colorbar & Variable Controls"
>
> PRD §5: dynamic colorbar editor (palette, min/max, log/linear), variable
> selector, layer opacity, vertical exaggeration slider, depth navigation, time
> scrubber.

**Verdict: met.** All six named controls exist and are wired to the scene:

| Control | Where |
|---|---|
| Colorbar editor: palette, min/max, log or linear, reverse | `ColorbarEditor.tsx` |
| Variable selector | `StationSheet.tsx`, one button per catalog variable |
| Layer opacity | `StationSheet.tsx` |
| Vertical exaggeration | `StationSheet.tsx`, with an honest readout in `ScaleBar.tsx` |
| Depth navigation, 24 levels | the depth rack, keyboard reachable |
| Time scrubber with RUN | `TimeRule.tsx` |

Two details that are there on purpose. The colorbar refuses a log scale across
a range that straddles zero rather than drawing something meaningless, and it
records that it adjusted the range at the moment it adjusts it, because
checking afterwards can only ever report that the clamped range is legal. And
the vertical exaggeration factor is printed on screen, because a stretched
ocean that does not say it is stretched is a misleading picture.

## F5. Web-based, scalable architecture

> "Web-based, Scalable Architecture"
>
> PRD §5: modern JS frontend plus a lightweight REST/OPeNDAP-compatible API, no
> client-side installs, deployable on INCOIS infra (Docker).

**Built.** Next.js 15 with React 19 on the front, FastAPI behind it. Nine
routes: `/healthz`, `/catalog`, `/field/{source}/{var}`, `/profiles`,
`/profiles/{id}`, `/plugins`, `/plugins/reload`, `/wms`, `/wcs`. No client-side
install of any kind: Cesium and its imagery are served from our own origin, and
an e2e test fails the build if the page requests anything off-origin, which is
also what makes the air-gapped demo true rather than hoped for.

**Verified on 2026-09-25: the Docker path runs, and the full suite passes
against it.**

It was worse than "authored, never executed" when Docker was finally
installed: **there were no Dockerfiles in the repository at all**, so the
compose file failed on its first line. It also declared PostGIS and Mosquitto,
which the app does not use, and put the agent on 8100 where the code listens on
8010. All of that is now fixed rather than described.

```
docker compose up --build
  api     python:3.11-slim, repo layout reproduced under /srv/sagardrishti,
          data/ mounted read-only (only data/cube writable, for the SagarNode
          log), and NO network client in the image: copernicusmarine is
          filtered out of the install because it only serves tools/fetch_sample.py
  agent   python:3.11-slim, reaches the API by service name (http://api:8000)
  web     node:22-slim + pnpm, Cesium vendored at build time, both
          NEXT_PUBLIC_* bases passed as build args because Next inlines them
  -> all three report healthy on their own /healthz checks

SAGAR_E2E_EXTERNAL=1 CI=1 pnpm e2e        (the suite, pointed at the containers)
  -> 12 passed (6.8m)

docker compose -f docker-compose.yml -f docker-compose.offline.yml                --profile airgap up api-airgap          (network_mode: none)
  -> healthz ok, stores [glorys12_cur, incois_vam_argo], 5 plugins loaded
  -> scorecard rmse 0.6017 over 11718 pairs
  -> request to https://example.com: blocked (URLError)
```

`./tasks.ps1 docker` re-runs every line of that and fails if any of it stops
being true.

**What the air-gap check proves, and what it does not.** It proves the data
plane needs nothing outside the machine to answer. It cannot do the same for the
browser's side, because a container on `network_mode: none` cannot publish a
port. The browser's half is proven where it always was: every test in the suite
fails if a single request leaves the machine, and it just passed against the
containers.

On "OPeNDAP-compatible": we serve REST, plus OGC WCS for subsetting, which is
the same job through a standard INCOIS already speaks. We do not implement the
DAP protocol itself, and should say so plainly if asked rather than let the
phrase pass.

## F6. Extensible design

> "Extensible Design"
>
> PS text: "future integration of additional sensors (CTDs, moorings, HF-radar,
> ADCP)" and ML-derived products.

**Built.** A plugin registry that loads Python modules from a directory at
boot, with a validated contract for two extension kinds: source readers, and
derived products. One live product ships with it.

**Evidence.**

```
curl http://127.0.0.1:8000/plugins

  plugins: d26_isotherm   derived_products: [D26]   source_readers: []   failures: 0

curl "http://127.0.0.1:8000/field/incois_vam_argo/D26?bbox=80,5,95,25&time=2026-07-30"

  200 of 300 cells valid, 41.2 to 96.0 m, mean 74.1 m
```

D26, the depth of the 26 degC isotherm, is the right first plugin because it is
the quantity tropical-cyclone forecasters actually use, and because it proves
the interesting half of the contract: a product that is computed from a stored
variable rather than read from disk, and that returns a surface where its input
was a volume. It carries its own method string into the response provenance
("shallowest crossing of 26 degC, linear interpolation in depth between the two
bracketing finite levels; no extrapolation, no interpolation across a missing
level"), so the number on screen can be explained without reading our source.
The registry declares the sensor kinds the PS names (`mooring`, `hf_radar`,
`adcp`) as valid source kinds. `docs/PLUGINS.md` is the documented interface the
requirement asks for.

**Closed: a plugin's product is now offered through WMS and WCS.** It was not.
`ogc.py` built its layer list from the store alone and never asked the plugin
registry, so `GetMap` on D26 answered `LayerNotDefined` while `/catalog` and
`/field` served it happily. A plugin's output was visible to our own client and
invisible to QGIS, which made the obvious judge question ("if I add a plugin,
does it show up in your WMS?") answerable only with "no".

```
curl ".../wms?service=WMS&version=1.3.0&request=GetCapabilities"
  -> incois_vam_argo/D26   dims=time             default style=boxfill/deep
     incois_vam_argo/SAL   dims=time,elevation   default style=boxfill/haline
     incois_vam_argo/TEMP  dims=time,elevation   default style=boxfill/thermal

curl ".../wms?...&request=GetMap&layers=incois_vam_argo/D26&transparent=TRUE&..."
  -> 200 image/png, 129 distinct colours, 16384 of 49152 px transparent
     X-Sagardrishti-Derived: true
     X-Sagardrishti-Derived-From: TEMP
     X-Sagardrishti-Plugin: d26_isotherm
     X-Sagardrishti-Method: shallowest crossing of 26 degC, linear interpolation ...
     X-Sagardrishti-Units: m        (and NO X-Sagardrishti-Elevation)

curl ".../wcs?...&request=GetCoverage&coverage=incois_vam_argo/D26&format=NetCDF3"
  -> 200 application/x-netcdf
     dims {time: 1, lat: 21, lon: 16}, no depth coordinate
     D26: units m, standard_name depth_of_isosurface_of_sea_water_potential_temperature
          derivation_plugin d26_isotherm, derivation_params threshold=26.0
     Conventions CF-1.8, no geospatial_vertical_* attributes
     209 of 336 cells valid, 41.2 to 96.0 m
```

Three decisions in there are the ones worth defending, and each is pinned by a
test.

**A surface product declares no elevation dimension, and refuses one.** D26 is
the depth OF a surface, not a value AT a depth. Advertising an elevation
dimension would be worse than omitting it: a client would offer a depth chooser
for a quantity that has none, and any value it sent would then have to be
either ignored, which answers a different question silently, or refused after
the capabilities document said it was allowed. `ELEVATION=5` returns
`InvalidDimensionValue` and the message says what the values actually are. The
same holds for a `DEPTH` subset in WCS.

**The recipe travels with the pixels and with the file.** A derived layer looks
identical to a stored one over the wire, so the response headers carry the
plugin, what it was derived from, and the method verbatim, and the NetCDF
carries them as variable attributes. A downloaded coverage can therefore still
be explained without the URL that produced it, which is what CLAUDE.md's rule
against a number without provenance means for a computed field.

**A depth in metres is not coloured with the temperature ramp.** This was a real
bug found while wiring it up. D26's CF name is
`depth_of_isosurface_of_sea_water_potential_temperature`, and the palette
chooser matched the word "temperature" first, so a field of METRES got the ramp
the scene uses for DEGREES, on a globe where the two sit side by side. Anyone
reading 60 off that ramp reads it as a temperature. A derived quantity's name
mentions the variable it was derived FROM, so the name alone cannot be trusted;
the unit can. It now resolves to `deep`, and mixed-layer thickness would too.

**A plugin cannot shadow a stored variable.** Two layers of one name would make
the advertisement ambiguous and whichever the dict held last would win
silently. A colliding name is skipped, and a test proves the stored variable
keeps its layer.

**Closed: a source reader is registered and running.** The plugin framework
has offered two extension points from the start. Derived products had a live
example (D26); source readers had a checked contract, error codes D1 to D5,
documentation, and nothing registered against them, so `plugins.open_source`
was called by its own tests and by nothing else.

`services/api/plugins/rama_mooring.py` now serves `kind: mooring`, and
`tools/preprocess.py` routes any source whose kind has a reader through
`open_source` rather than through a parser hardcoded in the core. Adding a
moored buoy took a plugin file, a `sources.yaml` entry, and one branch in the
preprocessor. That is the claim F6 makes, demonstrated rather than described.

```
curl http://127.0.0.1:8000/plugins

  plugins       : ['d26_isotherm', 'rama_mooring']
  derived       : ['D26']
  source reader : kind=mooring plugin=rama_mooring
  failures      : []

curl "http://127.0.0.1:8000/profiles/23009_20260729T120000"

  source_id     : rama_mooring_bob        platform_kind : mooring
  citation      : TAO/TRITON, RAMA and PIRATA moored buoy array, NOAA PMEL ...
     depth      temp
       1.0    29.440
      80.0    26.750
     180.0    16.660
     500.0    10.260
```

**Why RAMA and not a synthetic mooring.** RAMA is the Indian Ocean arm of the
global tropical moored array and INCOIS is one of its partners. Three of its
moorings sit inside the demo box on the 90 E line, and they report daily. A
synthetic mooring would have exercised the plumbing and proved nothing about
the data.

**Three real defects it brought, each handled in the reader.**

*A different QC vocabulary.* TAO/RAMA flags are 0 no sensor, 1 highest quality,
2 default quality, 3 adjusted, 4 lower quality, 5 SENSOR FAILED. Argo's scale
means something different above 2 and has no 5 at all, so the two agree on 1
and 2 by coincidence and diverge beyond. Filtering RAMA with Argo's rules would
compare a failed sensor against a scale it does not belong to. The reader maps
them explicitly, and on the real mooring that catches 46 cells.

*A fourth fill convention.* This source uses 1.0E35. The cube already handles
-9999.0 (INCOIS VAM), -1.0E34 (value-added and ocean colour) and 99999.0 (Argo
BGC). None is a rounding of another.

*A flat table, not a grid.* ERDDAP serves one row per (time, depth) with the
position repeated on every row, 527 rows for one mooring over a month. The
reader pivots it using the depths actually present, because a mooring loses and
regains sensors mid-deployment and assuming a rectangular sampling would either
drop levels or invent them.

**What the array itself said.** Asked which of its 154 stations lie in the demo
box, RAMA answered three: 8n90e, 12n90e and 15n90e. Only **15n90e** is still
reporting. 12n90e stopped on 2026-03-10 and 8n90e on 2025-09-12, so the Bay of
Bengal line is currently one buoy of three. That is a real fact about the
Indian Ocean observing system rather than a fetch failure, and the fetch says
so in those words instead of printing an error.

**One profile per model timestep, and the discard is counted.** A mooring
reports daily from a fixed position, so a month is 36 profiles at one point: on
a globe that is 36 coincident marks and an arbitrary pick when a judge clicks.
It is subsampled to the day nearest each model step, which is the same shape a
float gives, and `n_profiles_reported` and `n_profiles_kept` both ship in the
provenance.

Ten tests pin the reader, including that a failed sensor maps to bad, that the
1.0E35 sentinel never reaches the output as a value, that a WMO id does not
render as "23009.0" into a citation, and that the reader's output passes the
framework's own D1 to D5 contract through `open_source` rather than by direct
call.

### And the clause with a wire in it: SagarNode

The PS words are "future integration of ADDITIONAL SENSORS". The plugin
registry answers that for a file format. SagarNode answers it for a device: a
sensor nobody had heard of when the cube was built posts to `POST
/ingest/sagarnode` and appears on the globe beside twenty-five real ocean
casts, with no change to the data model and no redeploy.

**Both halves are built and the server half needs no hardware.** `curl` is a
sufficient device, which is how the whole beat is tested:

```
POST /ingest/sagarnode  {"station_id":"sagarnode-01","temp_c":27.4,
                         "tds_ppm":310,"turbidity_ntu":4.2}
  -> {"stored":true,"count":1,"alert":null}

POST /ingest/sagarnode  {..., "temp_c":-127}
  -> 400 temp_c is -127.0, outside the -5.0 to 100.0 a probe in a tank can
     produce. That is what a disconnected pin or a mis-wired divider reads
     like, so it is refused rather than drawn.

twenty quiet readings, then one at 34.2
  -> alert "Rapid warming in the demonstration tank", status Exercise
```

`-127` is exactly what a DS18B20 library reports when it cannot find the
device, so a refusal naming the probe and its range is the entire debugging
loop for a headless board.

**A bucket must never pass for the ocean, and four things stop it.** Its mark
on the globe is a HOLLOW circle, not the filled one the moorings use, and it
lives in its own entity layer so the instrument count never includes it. Its
panel prints the station's own note verbatim. Its threshold trip carries CAP
status `Exercise`, so every guard written for the rehearsal bulletins applies
to it unchanged, and the panel stamps itself exactly as HazardWatch does. And
the spoken scene summary names it as a demonstration before it says anything
else about it.

**What it will not claim.** The conductivity probe is a *conductivity-derived
salinity proxy*, never a salinity sensor, and the label the API serves says so
in full. It and the turbidity probe run on their vendors' nominal curves
against no standard solution, so the panel prints both as indications rather
than measurements; only the factory-calibrated DS18B20 is quoted. The board
sends no timestamp at all, because an ESP32 has no battery-backed clock and
PRD F11 promises the demo runs with the network off, so the API stamps arrival
and records `ts_source: "server"` rather than letting a receipt time be
mistaken for an observation time.

27 unit tests, plus an end-to-end test that empties the log, asserts that no
panel and no mark exist with nothing plugged in, then drives the whole beat
through the API and asserts the drill stamp. The firmware
(`firmware/sagarnode/sagarnode.ino`) is written and marked, in the file and in
its README, as never having run on a board: the parts are on the team lead's
list.

**Three departures from TRD M9, each on purpose.**

*A poll, not a WebSocket.* M9 specifies a socket push to the client. The
document is two kilobytes and the board reports at 1 Hz, so a poll costs
nothing measurable and keeps the data plane a plain request-response service
with no connection to re-establish on stage. It also backs off to one request
every three seconds when nothing is plugged in, which is most of the time.

*Its own mark, not the "virtual mooring" glyph M9 names.* Reusing the mooring
circle would have drawn a bucket as the same class of object as the RAMA buoy
on the 90 E line. The rig gets a hollow circle and its own entity layer
instead, so no count, legend total or spoken summary on the page includes it
among the instruments.

*MQTT is not built.* M9 makes it the primary transport with HTTP POST as the
fallback. Only the fallback exists, and that is an ordering rather than an
omission: the fallback is the one that works on a network nobody controls, and
a demo that depends on an open broker port has a single point of failure it
does not need. The registry entry is already `kind: mqtt`, so nothing has to
change when the bridge is written.

## F7. Open standards

> "open standards (OGC WMS/WCS, CF Conventions)"

**Verdict: met for stored variables.**

**WMS 1.3.0.** GetCapabilities and GetMap. Two layers advertised
(`incois_vam_argo/TEMP` and `/SAL`), six boxfill styles each, `time` and
`elevation` dimensions, and both CRS axis orders offered as separate
identifiers: `CRS:84` for lon,lat and `EPSG:4326` for lat,lon. A WMS 1.1.1
request is refused rather than served, because 1.1.1 reads an EPSG:4326 BBOX in
the opposite axis order and quietly serving one for the other relocates the
image.

Transparency behaves as the spec requires, which I checked today rather than
assumed:

```
TRANSPARENT=TRUE   -> alpha in {0, 1},  4737 of 16384 px fully transparent
TRANSPARENT=FALSE  -> alpha uniformly 1, missing cells filled with BGCOLOR
BGCOLOR=0x000000   -> honoured
```

The default is FALSE per the spec even though our own globe wants TRUE, and
missing cells then take the caller's declared background. That does not break
the rule that absent data is never coloured: the caller asked for an opaque
image and chose the colour.

**WCS 1.0.0.** GetCapabilities, DescribeCoverage and GetCoverage, serving
NetCDF3.

```
curl ".../wcs?...&request=GetCoverage&coverage=incois_vam_argo/TEMP
       &crs=EPSG:4326&bbox=80,5,95,25&width=15&height=20&format=NetCDF3&time=2026-07-30T00:00:00Z"

  -> 200, application/x-netcdf, 61976 bytes
     dims {time: 1, depth: 24, lat: 20, lon: 15}
     TEMP: units degC, standard_name sea_water_temperature
     depth: axis Z, positive down, standard_name depth, units m
     Conventions CF-1.8
```

**CF conventions.** The served coverage declares `CF-1.8`, and the vertical
coordinate carries `axis: Z`, `positive: down` and `standard_name: depth`.
Those three attributes are the whole point: the INCOIS source coordinate is
named `ZAX` and declares none of them, so a client reading the original file
cannot know which way depth counts, and a client reading ours can.

One behaviour worth reading as a feature rather than a bug: WCS refuses a
request whose WIDTH and HEIGHT do not match the native grid.

```
WIDTH=8 would require resampling to a grid other than the native 15x20 cells
this subset contains. DescribeCoverage advertises interpolationMethod none, so
this service returns native cells only.
```

A coverage service that silently resamples hands back numbers that were never
measured. Refusing, and citing our own DescribeCoverage while doing it, is the
correct answer for a scientific service.

---

## A bug this exercise found, and why it is in this file

Checking the Argo parser against the ten real daily files, rather than against
its own fixture, turned up a defect that six passing tests could not see.

`parse_profiles` built ONE boolean mask from `TEMP_QC` and `PRES_QC` and then
indexed every parameter with it. So a salinity whose own flag said 3 or 4 was
served as though accepted. Across those ten files that is **60,643 levels**,
carrying salinities including 0.00, 65.53 and **134.12 PSU**, against an ocean
range of roughly 33 to 37. The same mask also DISCARDED good salinity whenever
temperature was rejected, throwing away valid measurements.

Two things made it dangerous rather than merely wrong. The served Bay of Bengal
subset happens to contain none of the bad values, so nothing on screen was ever
incorrect and no test failed; it would have appeared the first time the demo box,
the dates or the float set changed. And the API prints `QC flags [1, 2] only
(Wong et al. 2020)` in every profile response, so the claim on screen was
already stronger than the code behind it.

The fix masks each parameter against its own flag, keeps a level when its
pressure is usable and at least one measurement survives, and reports the flag
alongside so "rejected" stays distinguishable from "never measured". Verified
on the real file that held the 134.12: 4,671 levels there have a good
temperature and a rejected salinity, the salinity served for them is now zero
values, and all 4,671 temperatures are still served. The served table is
byte-identical for today's demo box, which is the point: a latent bug fixed
before it could pick its moment.

Six tests now pin it, including one stated as the invariant that should have
existed from the start: not "the temperature flags are all good" but "no number
is served whose own flag rejects it".

A second guard came out of the same work. `data/sources.yaml` now declares the
unit each variable is expected to carry, and the parser refuses a file that
disagrees. Oxygen is why: micromole/kg and ml/l differ by a factor of about 22,
both appear in the literature, and both look entirely plausible on an axis. The
registry's declaration is what labels the chart, so it may not be allowed to
drift from the data it describes.

## Beyond the PS list: F9, the verification certificate

Not in the summary table above, because that table is the PS's own F1 to F7 and
this is PRD F9. It is recorded here anyway, because it is the claim a screening
reviewer is most likely to test and PRIOR-ART.md §B.12 names it as one of the
four things that make this entry defensible: **no operational ocean viewer
shows model skill next to the field it is drawing.**

**Built.** `GET /scorecard/{source}/{var}` and a certificate panel beside the
globe. Class-4-style verification in observation space (Ryan et al. 2015): the
model is interpolated to each profile's own position, bilinearly from the four
surrounding grid cells, and linearly in depth between the two bracketing model
levels, and the residual is formed there. Per-depth-bin bias, RMSE, mean
absolute error and residual spread.

**Measured on the real cube, 2026-09-09.**

```
curl "http://127.0.0.1:8000/scorecard/incois_vam_argo/TEMP"

overall   n=11,718  bias +0.026  rmse 0.602  mae 0.238   degC
casts     23 profiles from 15 platforms
offset    median 38.6 h from the analysis step, max 107.5 h

     0 to    10 m   n=   80   bias -0.16   rmse 0.32
    10 to    50 m   n=  334   bias -0.13   rmse 1.33
    50 to   100 m   n=  407   bias -0.06   rmse 2.07   <- worst
   100 to   200 m   n=  780   bias +0.57   rmse 1.35
   200 to   500 m   n= 1924   bias +0.13   rmse 0.43
   500 to  1000 m   n= 3068   bias -0.03   rmse 0.12
  1000 to  2000 m   n= 5125   bias -0.04   rmse 0.12

refused   4,672 total: 3,506 not measured, 566 model cell missing,
                       493 outside the box, 107 beyond model depth,
                       0 failed QC, 0 unflagged, 0 without a field in time
```

The shape of that column is the evidence that the method is right, and it is
what the e2e test asserts rather than any single figure: the analysis is nearly
exact below a kilometre, where the water barely changes, and worst across the
thermocline, where a metre of vertical displacement is a degree of temperature.
If that ordering ever inverts, the depth axis has been mishandled.

**What it refuses.** A level whose four surrounding model cells are not all
finite is refused rather than filled from the ones that remain, which is most
of them near a coast. No extrapolation past the model's deepest or shallowest
level. Observations filtered to QC flags 1 and 2. Every refusal is counted and
served, so the pair count is never a selected number.

**The caveat travels with every figure, in the reserved ink, on screen.** The
INCOIS VAM analysis assimilates the very Argo profiles it is scored against, so
this residual bounds how closely the analysis fits data it has already seen. It
is a real and useful quantity. It is **not forecast skill**, the overprint on
the panel says "analysis fit", and an e2e assertion fails the build if that
sentence ever stops being rendered.

One counter in this module was mislabelled during the build and the fix is
worth recording, because it is the same class of error as the QC bug below. The
3,506 levels where an instrument reported nothing were being counted as
`rejected_qc`. Nothing on screen was wrong yet, and the number was correct, but
the label told a reader that three and a half thousand observations had failed
quality control. Verified before splitting it: of 16,390 level rows, 3,506 have
no temperature and **zero** have a finite temperature with a bad flag.

## Beyond the PS list: F13, HazardWatch

Also not in the summary table, and also recorded here, because the problem
statement's portal theme IS **Disaster Management** and "timely hazard
assessment" is its first stated mandate. Until today the tool answered that
with ocean fields and nothing else.

**Built.** `GET /warnings` and a HazardWatch panel with warning areas drawn on
the globe. OASIS Common Alerting Protocol v1.2, which is what INCOIS's own
tsunami service and India's national alert backbone actually speak.

**The feed is real, and better than what was planned.** TRD M8 provided for
curated samples "where a machine feed isn't public". Probing on 2026-09-09
found that one is: **NDMA SACHET**, India's national CAP backbone, publishes a
public RSS index of real CAP documents, and it carried **99 live alerts** that
afternoon from the Central Water Commission, the India Meteorological
Department and the state disaster authorities. The parser is proven against it,
and two of those files are committed as golden fixtures with a provenance
sidecar (`services/api/tests/fixtures/`).

**What that feed did NOT carry is the honest part.** Not one ocean hazard. The
three the PS names by name (tsunami, high wave, swell surge) come from INCOIS's
ITEWC, and the same probe found no public machine-readable CAP or RSS endpoint
for it. So those three are authored in `data/warnings/incois/`, in the real
format, and every one carries CAP's own `status: Exercise`.

That is not a workaround, it is the field the standard provides for a drill,
and four independent guards hang off it:

1. Any conforming CAP reader anywhere treats them as drills. The marking is in
   the file, not in our code.
2. `app/cap.py:active()` refuses a non-`Actual` alert and counts it.
   `allow_exercise` admits `Exercise` **only**: `Test`, `Draft` and `System`
   stay refused even in rehearsal, because `Draft` is content an agency has not
   approved for release and a flag meaning "let me rehearse" must never publish
   it. A test pins that distinction.
3. The globe draws a drill dashed and lighter; the panel stamps itself
   `EXERCISE` whenever one is on screen, and the count comes from the server so
   a client cannot forget to look.
4. A test asserts that every file in `data/warnings/incois/` is still marked
   `Exercise`. If one ever acquires `status: Actual`, that test fails.

**What it refuses to draw, which is the whole design.** This is the one module
here where a bug is not a wrong number but a FALSE ALARM, so most of its 47
tests assert a negative: a `Cancel` withdraws the alerts it references; an
`Update` supersedes them; an expired alert is not active, compared in its own
timezone against a feed that stamps +05:30; one not yet effective is not active
yet. Every refusal is counted and served beside the alerts.

**The coordinate trap, pinned twice.** CAP writes coordinates **latitude
first**. GeoJSON, Cesium and everything downstream write longitude first. A
parser that forgets puts a Bay of Bengal warning in the Arctic and draws it
perfectly convincingly. The transposition happens in exactly one function.

**A real defect the real feed exposed.** One Gujarat alert carried a single
polygon of **93,478 vertices**, and twelve alerts came to 114,412 between them,
enough to blow the frame budget in TRD section 5 before a slice was drawn. The
ingest now applies Ramer-Douglas-Peucker at a 0.01 degree tolerance, about
1.1 km, against a model field on a ONE degree grid. 114,412 vertices become
3,390. The reduction is recorded on each alert it touched and rendered in the
panel, so a thinned boundary is never presented as the one the agency drew.

**Measured, 2026-09-09.**

```
curl "http://127.0.0.1:8000/warnings?rehearsal=true"
  12 live alerts, all status Actual, from 6 state disaster authorities
  and IMD offices. Worst first: 4 Severe, 8 Moderate.

curl "http://127.0.0.1:8000/warnings?at=2026-07-30T00:00:00Z&rehearsal=true&bbox=80,5,95,25"
  Tsunami    Extreme  Immediate  circle r=220 km + coastal polygon, 3 languages
  High Wave  Severe   Expected   polygon off north Andhra and south Odisha
  refused 13: 12 not yet in force, 1 expired
```

The hazard layer shares the field's time axis rather than the wall clock, so
scrubbing the time rule moves the warnings with it: nothing on 2026-07-10, the
swell surge on 07-20, the tsunami and the high wave on 07-30.

## Beyond the PS list: F8, Samudra Sahayak

The agent is a **separate service** on :8010, and that is TRD section 6.5's
"kill the agent and every P0 still passes" built rather than asserted: stop the
process and the client omits the ask box, leaving no broken control behind.

**What is real.** Eight tools over the public API (catalog, field summary,
profiles, one profile, the verification card, warnings, tours, and a validated
scene patch), a tool-call cap, a full trace served with every answer and
printed in the UI, and citations on everything that quotes data. Asked "how
good is the model?" it returns the RMSE, the pair count, the worst depth band
AND the caveat, each traceable to the tool call that produced it.

**The guard is the part worth defending.** CLAUDE.md's hard rule is that the
agent never invents numbers. `services/agent/app/guard.py` makes that
mechanical: every numeral in a finished answer must appear in a tool result,
and an answer that fails is **withheld**, not corrected, because a silently
scrubbed answer is one nobody knows was wrong. Thirteen tests cover it,
including that a rounded figure is still backed by its source, that a thousands
separator does not make a real number look invented, and that the question's
own numerals count as grounding (an agent repeating "no platform 1111111 is in
the box" is quoting, not fabricating; a failing test found that).

Writing it now, while the planner is deterministic and could be trusted, is the
whole point: the day a model is plugged in behind the same interface, the guard
has already been the last step every answer passes through for weeks.

**There is no language model, and it says so everywhere.** `planner: "rules"`
is in every response, in `/healthz`, and printed in the UI. The reasons are
concrete: PRD F11 promises an air-gapped demo so no cloud model is available on
stage, there is no Ollama on this machine, and a small local model doing
reliable tool-calling is a week of work with a real chance of failing in front
of an audience. ROADMAP's own Phase 2 line asks for exactly this, a "first
agent trick (scripted)". The SHAPE is the real one: the tools are the tools a
model would be handed, with the schemas it would be handed, and `plan()` is the
only function a model replaces.

**Two refusals are tested because judges test them.** Out of scope gets a
refusal that lists what the tool set can do and calls no tools at all. And a
question about the FUTURE is refused outright: a test caught that "what will the
temperature be next Tuesday" matched the temperature route perfectly and would
have been answered, confidently and with citations, from a July 2026 analysis of
the past.

## Beyond the PS list: F12, the guided tours

`GET /storyboards` and a player at the foot of the scene. A tour is a list of
steps: a patch to the scene, a line of narration, and the evidence that line
rests on. Playing one drives the SAME store the controls drive, so a tour can
do nothing a presenter could not do by hand, and it needs no LLM at all: it
replays identically with the network off.

Four tours ship, running 50 to 77 seconds each: what a water column is, the
26 degC surface a cyclone feeds on, the instruments and the verification
certificate, and HazardWatch.

**It is also the agent plane's plumbing, built a phase early.** TRD M4 gives
Samudra Sahayak exactly one channel to affect the view, `set_scene` with a
validated patch. This is that channel with a JSON file in front of it instead
of a language model, and `run_storyboard(id)` will call this same route. When
the agent lands it inherits a patch path already driven in front of an
audience.

**The rule that makes it defensible.** Narration is the one place in this whole
project where a number can reach a judge WITHOUT passing through a tool result:
everything else on screen is a value the API computed and cited, and a sentence
in a tour is prose somebody typed. So every numeral in a narration line must be
backed, by the patch that step applies or by the step's own `evidence` list,
which is rendered on screen beside the sentence rather than hidden. A tour that
fails that is refused at load and a test checks every shipped file.

That guard also catches the failure that will actually happen: a figure going
stale after the cube is refetched. A tour saying "eleven thousand seven hundred
pairs" after a rebuild is wrong on stage, and the evidence line is what makes
it findable.

**And a step that cannot be applied says so.** Patch keys are checked against
the live scene store, and an unknown key is reported on screen rather than
skipped, because a step that quietly no-ops is indistinguishable from one that
worked while the tour appears to run correctly.

**Three of TRD M7's four named tours are not here, and the reason is data.**
A cyclone cold-wake needs a cyclone, and no storm crosses the three July
analysis steps on disk. Monsoon upwelling off Kerala is at 75 E and the demo
box starts at 81 E. An eddy seen by a glider needs a glider, and none has been
obtained. Those are written up in `storyboards/README.md` rather than narrated
over data we do not have; the Argo explainer survives inside the instruments
tour.

## The frame rate was never the problem, and the probe was

Worth its own section because I was one step from optimising a scene that is
not slow, and because the number a judge reads off the screen was wrong by a
factor of three.

ROADMAP carried an open item from Phase 1: "p1 frame time (23 FPS), the
1-in-100 frame still stutters". Re-measured on 2026-09-10 against a production
build on the **Intel UHD**, which is the weaker of this laptop's two chips and
the target TRD section 5 names:

```
every layer on: 6 drawn slices, 25 cast marks, 3 CAP hazard shapes,
                337 current arrows, a 780-triangle isosurface, 389 entities

  while the camera is moving   72 FPS median, p1 57
  while the scene is still     27 renders per second
```

**Adding work more than doubled the rate**, which is the tell. Cesium's render
loop is driven by `requestAnimationFrame`, and a browser throttles that on a
window it believes is inactive. So the old probe, which timed the gaps between
renders, was reporting the browser's refresh decision as though it were our
frame cost. There was never a 23 FPS problem; there was a probe measuring the
wrong thing while the scene was sitting still.

**Two fixes, both about honesty rather than speed.** The probe now samples only
while the camera is actually moving, and the readout appends "idle" when it is
showing a held measurement. And "not measured yet" is no longer reported as
"below the floor": with no sample, `fps` was 0, both threshold comparisons were
true, and the readout ruled itself in the reserved caution ink before anybody
had touched the scene. Those are different statements and the second one is an
accusation.

The honest headline is therefore better than the one we had: **the scene beats
TRD's 60 FPS goal on the weaker GPU with every layer switched on**, and no FPS
number goes on a slide without saying it was measured while moving.

## The browser suite could not run on CI, and now can

Found while wiring HazardWatch into the build, and worth its own section
because it was quietly undermining every other claim in this file.

`tools/preprocess.py --fixtures` is what CI runs to get a cube without touching
INCOIS. It built a small INVENTED field. The browser suite in `e2e/` asserts
claims about the real Bay of Bengal on purpose (the surface is warmer than
2000 m, the cartouche cites `incois_argo_10d_VAM`, a BGC float really serves
chlorophyll which proves the adjusted product was read, the 26 degC surface
varies in depth), and not one of those is reachable against an invented field.

Measured rather than assumed. Running the suite against the fixture cube:

```
2 passed, 4 failed
  the water column renders            .cartouche said "SYNTHETIC FIXTURE", not INCOIS
  a BGC float is a different thing    no .legend: the fixture had one instrument class
  the isosurface draws                depth_max == depth_min: the field was flat
  a narrow window is honest           the same cartouche assertion
```

In all four the application was correct and truthfully reporting synthetic
data. The suite therefore only really ran when somebody remembered to run it
locally, which with a week to the round and a lot of building left is the wrong
thing to rely on.

**Fixed by committing the sample.** `data/sample/` now holds 614 KB of real
data: the INCOIS griddap subset exactly as the fetcher downloads it (193 KB)
and the processed in-situ profile table (421 KB), with a README covering
provenance, size reasoning and the attribution each carries. `--fixtures`
builds from those. CI gets the cube the demo runs on and still never reaches a
government server.

The Argo raw files are 6.6 MB each and the BGC synthetic profiles 6 to 7 MB, so
the profile table is committed processed rather than raw. That is a size
decision and it is stated in the sample README rather than left to be inferred.

**Verified 2026-09-09:** `preprocess.py --fixtures` then the full suite,
**6 of 6 browser tests pass**, which is the first time that job has been able
to go green.

## What I am building next, in this order

Ordered by how much PS text each closes per unit of work, which is also the
order they matter to a screening reviewer.

1. **F1: chlorophyll as a drawn surface layer.** Registered and disabled today,
   for the three reasons above. The work is a `vertical: surface` marker and an
   epoch marker in the registry, a depth-tolerant catalog entry, an empty-state
   path through the depth rack and the scale bar, a decimating ingest, and a
   time axis that refuses to join two epochs. It is not on the PS's own P0
   list, so it waits behind the requirements that are.

Done since this file was first written: F2's BGC clause and its mooring class,
F6's derived-products-through-OGC gap AND its source-reader half, F1's
isosurface clause, F9's verification certificate, F13's HazardWatch layer,
F12's guided tours, F8's agent plane, F1's depth-resolved currents, F6's live
sensor station (SagarNode, server and client both), and the six silent defects
above.

**F2's remaining clause needs data, not code.** A glider or CTD cast would
finish it, the parser and the marks are already there, and no such dataset is
published on INCOIS's own ERDDAP. If the team can obtain one Indian Ocean
glider or cruise CTD file in any delimited text format, that clause closes the
day it lands.

### We went and looked, on 2026-09-15, and the ocean is what is missing

"Nobody has given us a file" is a weak answer to give a reviewer, so the two
open archives that could plausibly carry a contemporaneous Bay of Bengal
glider or ship CTD were searched directly. Both were exhausted. The finding is
recorded here because it is a better answer than the absence it explains.

**GTSPP, the Global Temperature and Salinity Profile Programme (NOAA NCEI).**
The Indian Ocean monthly best-copy archive for July 2026,
`gtspp4_in202607.tgz`, holds **5,247 casts**: 3,055 BATHY (XBT, temperature
only) and 2,189 TESAC (temperature and salinity). Filtered to our demo box
(80 to 95 E, 5 to 25 N) and the cube's own time window, **211 casts survive and
every single one is the same moored buoy**, at 13.98 N 87.02 E, reporting
3-hourly on 9 levels to 500 m. Not one ship CTD cast, and not one glider.

**Copernicus Marine in-situ near-real-time, `cmems_obs-ins_glo_phybgcwav_mynrt_na_irr`.**
The glider feed carries 1,333 files, and its rolling window runs
**2026-08-15 to 2026-09-15**, which begins eleven days after our cube's window
closes, so nothing in it can be contemporaneous with the July analysis in the
first place. Setting even that aside: on 2026-09-01 the feed carried **42
gliders worldwide, of which exactly one was anywhere in the Indian Ocean**, at
12.83 S 45.38 E in the Mozambique Channel, roughly 5,000 km from the Bay of
Bengal.

So the honest statement is stronger than the one it replaces. **There was no
glider in the Bay of Bengal to draw.** The parser is written, tested and
waiting; what is absent is the observation, not the software. If a reviewer
asks why two of the four instrument classes are empty, that is the answer, and
it is checkable: both archives are public and both queries are reproducible.

Deliberately NOT done as a substitute: the 211 GTSPP casts are a mooring, a
class already live through RAMA, so ingesting them would raise the instrument
count without answering the clause the PS actually names. Padding a count is
the one thing this file exists to prevent.

## The e2e suite would have failed on CI, and did not fail here

Two problems, both found by running the suite the way CI runs it rather than
the way this machine happens to be set up.

**The built client called the wrong port.** `playwright.config.ts` set
`NEXT_PUBLIC_API_BASE` as an environment variable on `next start`, but Next
inlines `NEXT_PUBLIC_*` at BUILD time, so the setting did nothing: the served
bundle carried the default `127.0.0.1:8000` while the suite booted its API on
8100. It passed locally only because a development API happened to be
listening on 8000. On CI nothing listens there, so every test would have failed
with an empty scene and no clue why, and the off-origin guard would not have
caught it because 127.0.0.1 is local. The build now happens inside the
webServer command, where the variable takes effect. Verified by killing the
port-8000 API and running the suite: 4 passed.

That also retires the stale-build trap, which has cost this project time three
times: the suite can no longer serve a bundle older than the source it tests.

**The timeout assumed a GPU.** Playwright's headless Chromium falls back to
SwiftShader, and CI has no GPU at all, so software rendering is the normal
condition and a hardware GPU is the lucky one. Measured on this machine: the
same four tests take 1.8 minutes on the Intel UHD GPU and 8 to 12 minutes on
SwiftShader, and the longest single test goes from 46 seconds to over 5
minutes. A 120 second timeout passed locally and would have failed every CI
run. The timeout is now sized for software rendering, and the suite annotates
which renderer it actually got, so a slow run is diagnosable instead of looking
like a broken scene. That diagnosis cost real time here before the annotation
existed.

## What needs the team lead, not me

| # | Item | Which requirement it unblocks |
|---|---|---|
| ~~1~~ | ~~Free Copernicus Marine account~~ | **Done 2026-09-09.** The currents are ingested and serving; see F1 above |
| 2 | Docker Desktop installed, or an explicit decision to skip it | F5 deployability, the last unproven claim in it |
| 3 | One glider or ship CTD file, any delimited text format | F2's remaining instrument classes; the reader is built and is the most tested module here |

Restated in `docs/required.md`, which is the working list, so this file stands
alone.
