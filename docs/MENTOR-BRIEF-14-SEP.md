# Mentor briefing, 14 September 2026

**For:** the mentor review on 14 Sep, and the internal hackathon on 16 Sep.
**Team:** SagarDrishti · **PS:** SIH26067 · **Org:** Ministry of Earth Sciences / INCOIS · **Category:** Software · **Theme:** Disaster Management

Everything in this file was read off the running system on **11 September
2026**. Nothing is estimated and nothing is rounded up. Where a number is
uncertain or a thing is not built, it says so in the same sentence.

**Note it down, but note the caveats too.** Half the credit in a review like
this comes from being the team that says "and here is the part that is weak"
before the judge finds it.

---

# PART 1. The 90 seconds at the start

This is what you say when the judges first arrive. Learn the shape, not the
words.

## 1.1 The problem, in INCOIS's own words

INCOIS produces a three-dimensional ocean every single day: temperature,
salinity, currents and chlorophyll as model output, plus live instruments in
the water (Argo floats, gliders, CTD casts, BGC floats). Their own problem
statement says:

> "No integrated, web-based 3D visualization platform currently exists that can
> simultaneously render model fields and in-situ instrument observations in a
> single interactive environment."

> Existing tools are "desktop-bound, support only 2D plan views, or lack the
> ability to co-visualize model outputs alongside instrument profiles."

> Forecasters are "forced to toggle between disparate software packages,"
> which "impedes timely hazard assessment, search-and-rescue support, fishery
> advisories, climate monitoring."

**Do not ever say "INCOIS has no 3D".** They have a Digital Ocean portal that
advertises 3D and 4D visualisation. One informed judge will sink the whole
pitch on that sentence. The defensible claim is the one the PS itself makes:
the model and the instruments do not live in one place, so a forecaster has to
change software to compare them.

## 1.2 The five things we are solving

The PS names five gap areas. These are your five points. Say them in this
order.

| # | The gap, in the PS's terms | What we build for it |
|---|---|---|
| 1 | No **web-based 3D volumetric** rendering of the water column | The Bay of Bengal as 24 stacked depth levels, 5 m to 2000 m, in a browser, plus isosurfaces and time animation |
| 2 | No **unified display of instruments alongside model fields** | Every Argo, BGC and moored-buoy cast drawn on the same globe, clickable into a depth profile against the model at the same place and time |
| 3 | No **interactive variable / depth / time / colorbar controls** | Variable selector, depth cursor over all 24 levels, time scrubber, editable colour scale (palette, min/max, log or linear), vertical exaggeration |
| 4 | No **ingestion of new data streams without re-engineering** | A YAML registry plus a plugin interface: a new source or a new derived field is a config entry and a file, not a rewrite |
| 5 | No tools for **rapid, intuitive understanding** of 3D ocean phenomena | Guided tours that drive the scene, an assistant that answers from the data and cites it, and a model-versus-instrument skill number on the same screen as the field |

**The honest framing for 16 September.** You are presenting these as what you
set out to solve. They are, in fact, already built. That is not a problem: when
the judges come back after three or four hours you show them working software
instead of a progress bar, and "we were further along than we said" has never
lost anybody a mark. Do not pretend it is unbuilt if they ask directly.

---

# PART 2. Where we actually are

## 2.1 The requirement scoreboard

The PS lists seven explicit requirements, F1 to F7. This is the current
verdict on each. A "partly met" names the missing clause rather than hiding it.

| # | Requirement | Verdict | The gap, if any |
|---|---|---|---|
| F1 | 3D volumetric rendering | **Partly met** | All three named techniques are built (depth slices, isosurface extraction, time animation). Temperature, salinity and depth-resolved currents all render. Chlorophyll renders as instrument data but NOT as a gridded field, for a reason we can defend (see 4.3) |
| F2 | Instrument data overlay | **Partly met** | Argo floats, BGC floats and a moored buoy work end to end and are drawn as different symbols. Glider and CTD parsers are written and tested, but nobody has given us such a file, so those two classes do not appear |
| F3 | Multi-format data ingestion | **Met** | None |
| F4 | Customisable colorbar and variable controls | **Met** | None |
| F5 | Web-based, scalable architecture | **Partly met** | The Docker deployment files are written and have never been run, because Docker is not installed on the build laptop |
| F6 | Extensible design | **Met** | None. Two live proofs: a moored-buoy reader, and two derived fields computed by plugins |
| F7 | Open standards (OGC WMS / WCS, CF) | **Met** | None |

**Four of seven have no gap. Three have a named gap**, and two of those three
need data or a machine rather than code.

## 2.2 What that is built on

| Thing | Count |
|---|---|
| Automated tests, data plane | **462** |
| Automated tests, assistant | **71** |
| Automated tests, real browser through the whole demo | **10** |
| **Total** | **543** |
| Rendering speed | **51 frames per second** median at 1920x1080, measured on the weak integrated Intel graphics chip, not the gaming GPU. Worst single frame in five seconds: 27 fps |
| Requests that leave the machine | **Zero.** Everything is served from this laptop, the demo runs with WiFi off, and a test fails the build if any request goes off-origin |

---

# PART 3. The parameters

This is the section your mentor asked for by name. **We serve 13 ocean
parameters today.** Below, each one: what it physically is, where it comes
from, and why an oceanographer cares. Learn the plain-language column; that is
what you say out loud.

## 3.1 The six gridded fields (the 3D model side)

These are fields over the whole box: every one has a value at every latitude,
longitude and depth.

| # | Name on screen | What it is | Units | Source | Stored or computed |
|---|---|---|---|---|---|
| 1 | **TEMP** | Sea water temperature | degC | INCOIS | stored |
| 2 | **SAL** | Practical salinity | PSU | INCOIS | stored |
| 3 | **SIG0** | Potential density anomaly (sigma-0) | kg/m3 | computed from TEMP + SAL | **plugin** |
| 4 | **D26** | Depth of the 26 degC isotherm | m | computed from TEMP | **plugin** |
| 5 | **uo** | Eastward current velocity | m/s | Copernicus | stored |
| 6 | **vo** | Northward current velocity | m/s | Copernicus | stored |

### What each one MEANS, in words you can say out loud

**Temperature.** How warm the water is, at every depth. In the Bay of Bengal
the surface in July is about 29 degC and the water at 2000 m is about 2.6 degC.
It matters because warm water is the fuel a cyclone runs on, and because
temperature plus salinity together decide density.

**Salinity.** How much dissolved salt is in the water, measured on the
Practical Salinity Scale. Open ocean is about 35. The Bay of Bengal surface is
much fresher, about 32 to 33, because the Ganges, Brahmaputra and Irrawaddy
pour enormous volumes of fresh water into it during the monsoon. It is the
freshest large bay in the world and that single fact explains most of its
behaviour.

> **Say "practical salinity", and know why it has no unit.** Salinity is
> measured by electrical conductivity and expressed on a defined scale, so
> formally it is dimensionless. The data file literally declares its unit as
> "1". We print "PSU" on screen because "34.05 1" looks like a typo, but the
> number we send and store is untouched. If a judge asks why the unit looks
> odd, that is the answer, and it is the kind of answer that gets you taken
> seriously.

**Density (sigma-0).** How heavy a given volume of sea water is. This is the
one that actually controls the ocean: heavy water sinks, light water floats,
and the arrangement of density decides whether a water column mixes or stays
in layers. It sets the mixed-layer depth, it identifies where a body of water
came from, and it decides how hard a storm has to work to stir cold water up
to the surface.

Four things about density you must be able to say:

1. **It is never measured.** There is no density sensor on an Argo float. It is
   *computed* from temperature, salinity and pressure through an equation of
   state. That is why it is one of our plugin-derived fields.
2. **We compute it with TEOS-10**, the international standard since 2009
   (IOC, SCOR and IAPSO, 2010), using the `gsw` Gibbs SeaWater toolbox. The
   older standard, EOS-80, is still common and disagrees slightly. Naming the
   standard is part of quoting the number.
3. **"Sigma-0" means referenced to the surface**, and the value has 1000
   subtracted from it. That is why our numbers read about 20 to 28 rather than
   1020 to 1028. Sigma-0 is the right variable for the upper ocean; below about
   1000 m an oceanographer would switch to sigma-2 or sigma-4, and we say so on
   the field itself.
4. **In our cube it runs from about 19.8 at the surface to 27.8 at 2000 m.**

**D26, the depth of the 26 degC isotherm.** How deep you have to go before the
water drops below 26 degC. This is an operational cyclone variable: 26 degC is
the conventional bottom of the layer warm enough to feed a tropical cyclone, so
the depth of that line is roughly "how much fuel is in the tank". INCOIS
publish it themselves. It is also computed, not measured.

**Currents (uo and vo).** Which way the water is moving and how fast, split
into an eastward and a northward component, at every depth. This is what
search-and-rescue drift prediction runs on. Note for judges: INCOIS's free
ERDDAP publishes only *surface* geostrophic currents, so the depth-resolved
currents come from Copernicus Marine's GLORYS product instead. We say that on
screen rather than letting anyone assume one agency supplied everything.

## 3.2 The seven measured instrument parameters (the in-situ side)

These come from real instruments in the water, one profile at a time, not on a
grid.

| # | Name | What it is | Which instruments carry it | QC-passed levels we hold |
|---|---|---|---|---|
| 7 | **temp** | Temperature at each level of a cast | all | **12,884** |
| 8 | **psal** | Practical salinity at each level | Argo + BGC floats | **12,849** |
| 9 | **doxy** | Dissolved oxygen | BGC floats only | **3,142** |
| 10 | **chla** | Chlorophyll-a, a proxy for phytoplankton | BGC floats only | **2,120** |
| 11 | **nitrate** | Dissolved nitrate, a nutrient | BGC floats only | **327** |
| 12 | **bbp700** | Particle backscatter at 700 nm, a proxy for suspended particles | BGC floats only | **1,955** |
| 13 | **ph_in_situ_total** | Acidity of the sea water | BGC floats only | **1,957** |

Plus two vertical coordinates that every cast carries: **pres** (pressure in
decibars, which is what the instrument actually measures) and **depth** (metres,
which we compute from pressure and latitude using TEOS-10).

> **Why pressure and not depth?** An Argo float does not know how deep it is.
> It measures the weight of water above it, as pressure. Converting that to
> metres requires latitude, because gravity varies with latitude. Treating one
> decibar as one metre is the classic error here: at 2000 m it is wrong by
> about 21 metres. We use the official conversion and we test it.

## 3.3 The count, stated honestly

- **13 ocean parameters served today**: 6 gridded fields and 7 measured
  instrument parameters.
- **2 of the 13 are computed by plugins** rather than stored (SIG0 and D26).
  That is not a weakness, it is the live proof of requirement F6.
- **2 more are vertical coordinates** (pressure, depth).
- **3 more exist but are being deferred**: the tabletop sensor rig
  (temperature, a conductivity-derived salinity proxy, turbidity). See Part 6.

If a judge asks "how many parameters", say **thirteen**, then offer the split.
Do not say twenty.

---

# PART 4. The datasets, and how much data

## 4.1 What we ingest

| Source | What it is | Access | Status |
|---|---|---|---|
| **INCOIS ERDDAP** `incois_argo_10d_VAM` | 10-day gridded Argo analysis, Variational Analysis Method. INCOIS's own product | Open, no login | **Live** |
| **Argo GDAC (Ifremer)** | Daily basin-aggregated Argo profile files, Indian Ocean | Open | **Live** |
| **Argo BGC (Sprof)** | Biogeochemical float synthetic profiles | Open | **Live** |
| **RAMA moored buoys** | The 90 E line in the Bay of Bengal, which India helps run | Open | **Live** |
| **Copernicus Marine GLORYS** | Global ocean physics analysis and forecast, currents at 1/12 degree | Free account | **Live** |
| **NDMA SACHET** | India's national CAP disaster-alert backbone | Open RSS | **Live** |
| INCOIS ocean-hazard bulletins | Tsunami, high wave, swell surge | No public machine feed exists | **Rehearsal bulletins**, marked as drills |
| INCOIS Oceansat-2 ocean colour | Gridded chlorophyll | Open | **Registered and deliberately disabled** (see 4.3) |

## 4.2 How much data

**The INCOIS analysis upstream**, as published on their ERDDAP:

- 813 time steps, 24 depth levels (5 m to 2000 m), 60 latitudes, 90 longitudes
- = **105,321,600 values per variable**

**What we subset into the demo cube** (Bay of Bengal, 3 dates):

| Cube | Shape | Values |
|---|---|---|
| INCOIS temperature | 3 times x 24 depths x 21 lats x 16 lons | **24,192** |
| INCOIS salinity | same | **24,192** |
| Copernicus eastward current | 3 x 40 x 241 x 181 | **5,234,520** |
| Copernicus northward current | same | **5,234,520** |
| | **Total gridded values on disk** | **10,517,424** |

Density and D26 are computed from the above on request, so they add fields
without adding storage. That is worth saying out loud: it is the extensibility
claim in one sentence.

**The instrument side:**

- **25 casts** from **17 distinct instruments** (13 Argo floats, 3 BGC floats
  that each reported 3 times, 1 RAMA moored buoy that reported 3 times)
- **16,390 measurement levels** that passed quality control
- Filtered to **QC flags 1 and 2 only**, following Wong et al. 2020

> **Say casts, not floats.** A float drifts and reports repeatedly. Twenty-five
> marks on the globe were made by seventeen instruments. Calling the marks
> floats would put eight instruments in the Bay of Bengal that are not there,
> in front of the people who run the array. Our screen prints both numbers.

**The warning side:** India's national CAP feed carried **99 live alerts** when
we ingested it. None of them was an ocean hazard, which is itself a finding, so
the three ocean bulletins the PS names are rehearsals and are stamped
EXERCISE four separate ways.

## 4.3 The one dataset we refuse to use, and why

INCOIS publish a gridded chlorophyll product from Oceansat-2. **Its time series
ends in 2020.** Our model field is from July 2026. Putting a 2020 chlorophyll
layer on the same time scrubber as a 2026 temperature field would let a viewer
scrub to one date and see two fields six years apart without being told.

So it is registered in our source list and switched off, with the reason
recorded. If a judge asks "why no chlorophyll layer", that is the answer, and
it is a better answer than having built it.

**Note the distinction carefully:** we DO serve chlorophyll as instrument data,
from BGC floats, 2,120 measured levels, contemporary with the model. What we
refuse is the gridded 2020 field. Do not let these two get mixed up.

---

# PART 5. Where the methods come from (the research answer)

When a judge asks "where did you get this idea / method from", this is the
table. Each row is a decision we made and the paper we took it from.

| What we did | Where it came from |
|---|---|
| **Model-versus-instrument skill scoring in observation space**, with per-depth bias and RMSE. Our verification card. | **Ryan et al. 2015**, *Journal of Operational Oceanography* 8, GODAE OceanView **Class 4** verification framework. We implement it and label it "Class-4-style" on screen. |
| **Keep only QC flags 1 and 2** on every instrument profile | **Wong et al. 2020**, *Frontiers in Marine Science* 7:700, the Argo array and its QC-flag structure |
| **Density from temperature, salinity and pressure** | **TEOS-10**: IOC, SCOR and IAPSO, 2010, *The International Thermodynamic Equation of Seawater 2010*. Implemented through the `gsw` Gibbs SeaWater toolbox |
| **The API shape**: bounding box + depth + time returns profiles | **Tucker et al. 2020**, *JTECH* 37(3), Argovis |
| **3D ocean model fields in a browser on a Cesium globe** | **Qin et al. 2021**, *Environmental Modelling and Software* 135:104908 |
| **Rendering optimisations**: stop drawing a layer once it cannot change the picture; adaptive sampling | **Yu, Qin and Xu 2025**, *Applied Sciences* 15(5):2782, WebGPU ocean volume rendering |
| **Storage as Zarr chunks rather than whole NetCDF files** | **Signell and Pothina 2019**, *Journal of Marine Science and Engineering* 7(4):110 |
| **Serving through OGC WMS on CF-NetCDF** | **Blower et al. 2013**, *Environmental Modelling and Software* 47, ncWMS |
| **Extract features on the server and ship light geometry** rather than whole grids (our isosurfaces) | **Liu, Silver and Bemis 2019**, *IEEE Access* 7 |
| **The assistant calls pre-registered tools and never writes code** | **Khanal et al. 2024**, *ACM UIST*, FathomGPT; and *GeoJSON Agents*, arXiv:2509.08863, which compares function-calling against code-generation head to head |
| **Every number the assistant says carries a data reference** | *OceanAI*, arXiv:2511.01019 |
| **Digital twin of the ocean as a framing** | **Tzachor et al. 2023**, *npj Ocean Sustainability* 2:16 |
| **The Indian validation precedent** | **Balakrishnan Nair et al. 2013**, *Current Science* 105(2), INCOIS Ocean State Forecast validation, including cyclone Thane |
| **The alert format** | OASIS **CAP v1.2**, the same protocol behind NDMA's SACHET |
| **File conventions and vertical axis handling** | **CF Conventions** |

**The two to memorise** are Ryan 2015 (because the verification card is our
strongest claim) and Wong 2020 (because it is why our numbers are trustworthy).
If you only remember two names, remember those.

---

# PART 6. The numbers to quote, with the sentence that must follow each

## 6.1 The verification card: our strongest claim

Every ocean viewer in the world draws the model. Ours also prints **how wrong
the model is**, checked against the real instruments, on the same screen.

| Figure | Value |
|---|---|
| Bias (model minus observation) | **+0.026 degC** |
| RMSE (root mean square error) | **0.602 degC** |
| Mean absolute error | **0.238 degC** |
| Matched model-observation pairs | **11,718** |
| Casts contributing | **23** |
| Instruments contributing | **15** |

**Per depth band**, which is the more interesting table:

| Depth band | Pairs | Bias (degC) | RMSE (degC) |
|---|---|---|---|
| 0 to 10 m | 80 | -0.160 | 0.320 |
| 10 to 50 m | 334 | -0.130 | 1.335 |
| **50 to 100 m** | 407 | -0.061 | **2.074** |
| 100 to 200 m | 780 | +0.568 | 1.345 |
| 200 to 500 m | 1,924 | +0.128 | 0.433 |
| 500 to 1000 m | 3,068 | -0.030 | 0.120 |
| 1000 to 2000 m | 5,125 | -0.041 | 0.118 |

**The story in that table:** the model is superb in the deep ocean (about 0.12
degC) and worst across the thermocline at 50 to 100 m (2.07 degC), which is
exactly where the temperature gradient is steepest and exactly the layer a
cyclone forecaster reads. That is a real, useful, defensible finding.

> **THE CAVEAT THAT MUST TRAVEL WITH EVERY ONE OF THOSE NUMBERS.** The INCOIS
> analysis assimilates these same Argo profiles, so this residual measures how
> closely the analysis fits data it has already seen. **It bounds the analysis
> error and is NOT forecast skill.** It is also a 10-day averaged field being
> compared against instantaneous profiles, which carries a representativeness
> error no interpolation can remove.
>
> This sentence is printed on our own screen, in red, above our own number. If
> you quote the RMSE without it, you have overstated our result. If a judge
> tries to catch you on it, the answer is already on the display.

We also publish what we **refused** to score: 4,672 levels did not become
pairs. 3,506 had no observation at that level, 566 sat next to a missing model
cell, 493 were outside the grid, 107 were outside the model's depth range. A
count with no reasons reads as a bug; the reasons are part of the answer.

## 6.2 A real finding from the density field

Our density field found that **213 of 225 wet columns** in the Bay of Bengal
are statically unstable somewhere: denser water sitting above lighter water,
which in the real ocean would overturn within minutes.

**208 of those 213 inversions are in the top 30 m.** That is the monsoon river
plume: warm fresh water from the Ganges and Brahmaputra sitting as a lid on
saltier water beneath. It is the single most characteristic feature of this
basin, and a smoothed 10-day, 1-degree gridded analysis is under no obligation
to be statically stable.

We report it rather than repairing it. Sorting each column into stable order
would have replaced a real property of INCOIS's product with a number we made
up.

**This is a very good thing to show a judge**, because it demonstrates we
understand the data rather than just drawing it.

## 6.3 Speed

51 frames per second median at 1920x1080, measured on the **integrated Intel
graphics** rather than the laptop's gaming GPU, because the weaker chip is what
a nodal centre machine will resemble. Worst single frame in five seconds: 27
fps. Method and numbers are written down and re-runnable.

---

# PART 7. What we are deliberately NOT doing yet

Being able to list this crisply is worth marks. Every item has a reason.

| Not done | Why |
|---|---|
| **The tabletop sensor rig (SagarNode) hardware** | **Deferred by team decision to after screening.** The entire software path is built and tested: the ingest endpoint, the mark on the globe, the live panel, the trend chart and the threshold alert all work today and can be demonstrated with a single `curl` command and no hardware. What is missing is the physical parts. We would rather show finished software than a half-wired bucket |
| **Glider and CTD instrument classes** | The parsers are written and tested. Nobody has given us a glider or cruise CTD file for the Indian Ocean. This needs **data, not code** |
| **Gridded chlorophyll** | A deliberate refusal. The INCOIS series ends in 2020 and cannot share a time axis with a 2026 field (see 4.3) |
| **A large language model in the assistant** | The assistant is a deterministic rule-based router over real tools, and it **prints "planner: rules" under every answer**. The tools, the safety check and the whole architecture are real; a model slots in behind them later. Being caught implying an AI is reasoning when a regular expression is matching would cost far more than saying this |
| **Multilingual voice (Bhashini)** | Planned, not built |
| **Docker deployment** | The files are written and have never been executed, because Docker is not installed on the build laptop |

---

# PART 8. Questions to expect, and the answers

**"Doesn't INCOIS already have a 3D portal?"**
Yes, and never say otherwise. Their Digital Ocean portal advertises 3D and 4D
visualisation, and it is a data-management and fusion portal whose 3D is a
globe with draped layers and time animation. We consume their own ERDDAP, so
there is no data duplication, and we add what it does not do: true volumetrics,
a skill number beside the field, and natural-language control.

**"How is this different from Windy or earth.nullschool?"**
Those are surface animations. The ocean state that matters for cyclone
intensification, fisheries and search-and-rescue lives below the single pixel
they draw. We render the whole column, fuse the instruments into it, and
quantify how far the model sits from them.

**"Where does your data come from? Is it real?"**
All of it, all open. Name them: INCOIS's own ERDDAP for the analysis, the Argo
Global Data Assembly Centre at Ifremer for the floats, RAMA for the moored
buoy, Copernicus Marine for the currents, NDMA's SACHET for the alerts. Every
panel on screen prints its own dataset name and timestamp.

**"How do you know your numbers are right?"**
Three answers, in this order. The verification card scores us against real
instruments and prints the result. 543 automated tests, ten of which drive a
real browser through the whole demo. And the density calculation reproduces the
published TEOS-10 check values to six decimal places.

**"Is the AI making things up?"**
It cannot. Every figure in every answer has to come from a tool call against
real data, and there is code that reads the finished sentence and **withholds**
it if a number appears that no tool produced. Not corrects it, refuses it. And
be straightforward: there is no language model in it yet, and it says so under
every answer.

**"What is your biggest weakness?"**
Answer it straight, it is a strength to have one ready: we have no glider or
CTD file, so two of the four instrument classes the PS names are built but
empty; and the Docker deployment has never been run. Both are written down.

**"Why should INCOIS adopt this?"**
It reads their own data through their own ERDDAP with zero duplication, it
speaks OGC WMS and WCS so their existing tools can consume it, it needs no
client install, it runs air-gapped, and it costs nothing in licences.

---

# PART 9. What each person should be ready to answer

Judges at SIH routinely pick one member and question them. Every person needs
one area they own completely.

| Area | Must be able to answer |
|---|---|
| **The problem and the five gaps** | Part 1 of this document, without notes |
| **Data sources and ingestion** | Part 4: where every dataset comes from, how much there is, and why chlorophyll is switched off |
| **The parameters** | Part 3: what temperature, salinity and density each physically are, and why density is computed rather than measured |
| **The verification card** | Part 6.1, including the caveat, word for word |
| **The 3D rendering** | How the water column is drawn, the frame rate, and why it is measured on the weak GPU |
| **Extensibility and standards** | Part 2 F6 and F7: the registry, the plugins, and that adding density took one file |

---

# PART 10. The single best thing to show, in order

If the judges only stay for two minutes:

1. **Drag the depth cursor** from 5 m to 2000 m. They see a 3D water column in
   a browser. Ten seconds.
2. **Click an Argo float.** Its real measured profile appears against the model
   at the same place and time. Twenty seconds.
3. **Point at the verification card.** "Every ocean viewer draws the model.
   This one prints how wrong it is: 0.60 degC over 11,718 matched
   measurements. And underneath, in red, our own caveat saying what that number
   is not." Thirty seconds.
4. **Switch the variable to SIG0.** "This is density. Nobody measures it; it is
   computed from temperature and salinity through the international equation of
   state, by a plugin, which is the extensibility requirement working." Twenty
   seconds.

**Number 3 is the one they will remember.** It is the claim no other team at
the nodal centre will be able to make.
