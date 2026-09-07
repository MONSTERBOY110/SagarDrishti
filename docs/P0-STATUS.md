# P0 status: the problem statement's own requirement list

**Date of this measurement: 2026-09-07.** Every number below was read off the
running service on the build laptop today, not copied from an earlier run. The
commands that produced them are in each row so anyone can re-run them and
disagree with me.

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
| F1 | 3D volumetric rendering | **Partly met** | All three named TECHNIQUES are built. Depth-resolved current vectors are blocked on a Copernicus account; chlorophyll has an INCOIS source, not yet registered because it is a surface field and every source today is 4D. |
| F2 | Instrument data overlay | **Partly met** | Argo floats and BGC floats both work end to end and are drawn as different marks. Glider and CTD parsers are built and tested, but no such cast is loaded, so those two classes do not yet appear. |
| F3 | Multi-format data ingestion | **Met** | None. |
| F4 | Customizable colorbar and variable controls | **Met** | None. |
| F5 | Web-based, scalable architecture | **Partly met** | The Docker path is authored and never executed, because Docker is not installed here. |
| F6 | Extensible design | **Partly met** | The registry works, carries a live product, and that product is now served through WMS and WCS. No source reader is registered yet, so one half of the interface has tests but no running example. |
| F7 | Open standards (OGC WMS/WCS, CF) | **Met** | None. Stored variables and plugin-derived products are both served. |

Four of seven have no gap. Three have a named gap: one blocked on the team
lead (Docker), one blocked on data availability (a glider or CTD file), and one
mine to close (isosurface extraction). The order is at the bottom of this file.

## Test and check counts behind these verdicts

```
services/api      281 tests   (argo 20, cf 13, colormap 10, field 24,
                               isosurface 27, offline 3, ogc 58, plugins 60,
                               text profiles 66)
e2e                 4 tests   production build, real browser, off-origin guard
```

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

**No source: current vectors at depth.** INCOIS ERDDAP publishes surface
geostrophic currents only, so there is nothing subsurface to render. The
depth-resolved source is Copernicus GLORYS12, which is free but needs an
account. `data/sources.yaml` already carries the `glorys12` entry shipped
`enabled: false`; it becomes `true` the day credentials exist. This is item 2
on the team lead's list in START-HERE.md.

**Chlorophyll: a source exists, and it is INCOIS's own.** An earlier draft of
this file said there was none. That was wrong, and checking the ERDDAP catalogue
rather than assuming corrected it. INCOIS publish two ocean-colour products on
the same open server we already use:

| Dataset | Variables | Grid | Span |
|---|---|---|---|
| `incois_oceansat2_datasets` | CHL, KD490, TSM | about 0.04 deg, 717 x 1317 | 2011-02-05 to 2020-05-01, daily |
| `IRS_chlorophyll_datasets` | CHLOROPHYLL | about 0.01 deg, 2556 x 4315 | 2003 to 2006 |

Oceansat-2 is the better of the two: finer time resolution, three variables,
and it declares `_FillValue = -1.0E34`, the second fill convention our CF tests
already pin. Two things have to be said plainly when it is wired up. It is a
SURFACE product, because ocean colour is measured from a satellite and has no
profile, so it renders as a surface layer over the volume and not as part of
it. And its latest date is 2020, so it cannot be shown under a 2026 time
scrubber as though contemporaneous; it is a separate layer with its own date.

Registering it is not yet done. It is a change of shape rather than a change of
scale: every source in the cube today is 4D `(time, depth, lat, lon)` and this
one has no vertical axis at all, so the registry, the preprocessor and the
renderer each need to accept a source with no depth dimension. That is a real
piece of work and it is on the list below rather than claimed here.

Chlorophyll DOES already reach the screen from a different direction: the BGC
floats under F2 carry measured chlorophyll profiles, which is a profile
quantity rather than a field.

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

**Gap: no glider or CTD cast is loaded.** This one is worth being precise
about, because the parsing half is done and the ingestion half is not:

- The delimited-text parser is built and is the most heavily tested module in
  the repo (66 tests), covering Sea-Bird CTD ASCII, ODV spreadsheet exports,
  footer blocks, ragged lines, and the station-boundary cases where a blank
  station cell would otherwise attribute one cast's levels to another.
- `data/sources.yaml` registers `ctd_text_ascii` and `odv_spreadsheet`.
- Provenance is now RECORDED per row rather than inferred. Every profile row
  carries the `source_id` it was ingested from, because the previous scheme
  guessed from the shape of the platform id: that works for a text cast
  (prefixed "CTD-...") but cannot tell a BGC float from a core float, since
  both have a plain 7-digit WMO. A BGC float's chlorophyll cited to the core
  daily files, which contain no chlorophyll at all, would have been exactly the
  misattribution the routing existed to prevent.
- The marker glyphs now exist and are wired: a square is a core float, a
  diamond a BGC float, a triangle a ship or glider cast, a circle a fixed
  station. The legend lists only the classes actually present, so it cannot
  advertise a glider we have no glider data for.
- What is missing is a real glider or CTD file to ingest. No such dataset is on
  INCOIS's own ERDDAP; its 17 datasets are gridded satellite and analysis
  products plus one tabular Argo dataset. So this needs either an outside
  archive or a file from the team, and it is the one remaining P0 clause whose
  blocker is data availability rather than code.

Today `profiles.parquet` holds 22 profiles across 16 platforms: 13 core Argo
floats and 3 BGC floats. Two of the four instrument classes the PS names are
therefore live, and the two that are not are one ingest away rather than one
feature away.

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

**Gap: the Docker path has never been executed.** `docker-compose.yml` and
`docker-compose.offline.yml` are written per TRD §8 and both say so in their own
header. Docker is not installed on this machine (ADR-0004), so the files are
unproven. A reviewer reading a compose file that has never run is a risk we
should not carry into screening. This is item 4 on the team lead's list.

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

**Remaining gap: no source reader is registered.** The slot is built,
contract-checked and documented, but `source_readers` is empty, so that half of
the interface is demonstrated by tests rather than by a running example. The
HF-radar or ADCP reader in PRD's P2 list is what fills it.

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

## What I am building next, in this order

Ordered by how much PS text each closes per unit of work, which is also the
order they matter to a screening reviewer.

1. **F1: chlorophyll as a surface layer** from `incois_oceansat2_datasets`.
   Needs the registry, the preprocessor and the renderer to accept a source
   with no depth axis, which is also the shape every future satellite product
   will have. The OGC side already handles a depth-less layer, since that is
   what a derived surface product is.
2. **F6: one source reader**, so both halves of the plugin contract have a
   running example rather than one half having only tests.

Done since this file was first written: F2's BGC clause, F6's
derived-products-through-OGC gap, and F1's isosurface clause.

**F2's remaining clause needs data, not code.** A glider or CTD cast would
finish it, the parser and the marks are already there, and no such dataset is
published on INCOIS's own ERDDAP. If the team can obtain one Indian Ocean
glider or cruise CTD file in any delimited text format, that clause closes the
day it lands.

## What needs the team lead, not me

| # | Item | Which requirement it unblocks |
|---|---|---|
| 1 | Free Copernicus Marine account | F1 current vectors at depth, and the 1/12 degree upgrade |
| 2 | Docker Desktop installed, or an explicit decision to skip it | F5 deployability, the last unproven claim in it |

Both are already items 2 and 4 in START-HERE.md §4, restated here so this file
stands alone.
