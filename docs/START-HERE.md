# START HERE

Plain-English map of what exists, how to look at it, and what only you can do.
No jargon. If you read one file, read this one.

---

## 1. What this thing actually is

INCOIS produce two kinds of ocean data every day:

1. **Model output.** A computer's estimate of temperature, salinity and currents
   for every point in the ocean, at many depths. Think of it as a weather
   forecast, but for the sea, and in 3D.
2. **Real measurements.** Floating robots called **Argo floats** drift around the
   ocean, sink to 2 km, and come back up measuring temperature and salinity all
   the way. Roughly 4000 of them worldwide.

The problem in their own words: there is no single web tool that shows both at
once. A forecaster has to open one program for the model, another for the floats,
and mentally stitch them together. That is slow, and it slows down cyclone and
high-wave warnings.

**SagarDrishti is that single tool.** One web page where you see the model as a
3D block of coloured water, the real floats sitting inside it as clickable
marks, and, when you click one, the float's own measurements drawn against what
the model predicted at the same place.

## 2. What is built and working right now

Three things, all running on **real INCOIS and Argo data downloaded today**, not
mock-ups:

**The data pipeline.** Downloads real ocean files from INCOIS's own public
server and from the international Argo archive, cleans them up, and serves them
to the web page. Government science files are messy in specific ways (a missing
value stored as -9999, temperature labelled "degs" instead of Celsius, a depth
axis that does not say whether depth counts upward or downward). All of that is
handled and covered by **281 automated tests**, so it stays handled. Four more
tests drive a real browser through the whole demo and fail the build if
anything reaches the internet.

**The 3D scene.** The Bay of Bengal as a stack of 24 coloured layers, one per
depth, from 5 m down to 2000 m. You can see the warm surface, the sharp
temperature drop between 50 and 200 m (the thermocline, which is what feeds
cyclones), and the cold deep water. It runs at **44 frames per second** on the
weaker of this laptop's two graphics chips, which is the number that matters
because it is the harder case.

**The float click-through.** 22 real instruments are on the globe. Click one and
you get its actual temperature profile, 524 measurements in the case of float
1902681, drawn as a coloured line against a dashed line showing the model. Where
the two lines separate is where the model disagrees with reality. That is the
whole point of the product, visible in one glance.

**Two kinds of instrument, told apart.** 13 of those marks are ordinary Argo
floats, drawn as squares, measuring temperature and salinity. The other 9 are
profiles from 3 **biogeochemical floats**, drawn as diamonds, which also
measure dissolved oxygen, chlorophyll, nitrate and pH. Click a diamond and the
panel offers all of them. One of those floats reads **1.7 micromole of oxygen
per kilogram at 141 metres** while the surface above it is 28.5 degrees: that is
the Bay of Bengal oxygen minimum zone, water with effectively no oxygen in it,
and it is the kind of thing an INCOIS scientist will recognise immediately.

**The isosurface.** Switch on "Isosurface" in the left panel and the tool draws
the single curved surface in the ocean where the temperature is exactly 26
degrees, as real 3D geometry threading through the flat layers. That is the
shape a cyclone forecaster actually reads: the deeper that surface, the more
heat there is to fuel a storm. Drag the slider to pick a different value.

Three things about it are worth knowing, because a judge may ask.

It **agrees exactly** with the separate calculation we already had for the same
quantity, to the last decimal place, in every water column where both apply.
That is checked automatically on every run.

It **stops short of the coast, on purpose**, and draws an orange line where it
stops. Near the shore some of the surrounding measurements are missing, and
rather than guess them we leave a hole and say how many cells we left out. The
alternative is inventing data, which is the one thing this project never does.

On the 10th of July it comes back as **two separate pieces**. That is real: a
layer of warmer water sits trapped under cooler water in the Bay of Bengal, a
known effect of monsoon and river freshwater. Nothing in our code knows that
happens; the surface simply came out that way, which is a good sign.

**Standards endpoints.** The tool also speaks the two international standards
INCOIS use, so their existing software can read our data without knowing
anything about us: a **WMS** map service (open it in QGIS and our temperature
field appears as a layer) and a **WCS** coverage service (ask it for a region
and it hands back a proper CF-convention NetCDF file). Plus a **plugin system**,
with one plugin already running that computes the depth of the 26 degree
isotherm, the number cyclone forecasters actually use.

Everything works with **the WiFi switched off.** That is deliberate and it is a
scoring criterion: no map service, no font service, no cloud anything. It all
comes off the laptop.

## 3. How to look at it

Two things need to be running. Open two terminals in `D:\Projects\SagarDrishti`.

**Terminal 1, the data server:**

```
.\tasks.ps1 api
```

**Terminal 2, the web page:**

```
.\tasks.ps1 web
```

Then open **http://localhost:3000** in Chrome or Edge.

If PowerShell complains about running scripts, run this once:

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### What to try, in order

1. **Drag the globe** with the mouse. Scroll to zoom. You are looking at the Bay
   of Bengal from the side, which is why the water column looks like a slab.
2. **Click any of the small square marks** on the water. That is an Argo float.
   Its profile opens on the right, with its ID number, the exact time it
   surfaced, and where the data came from.
3. **Click any row in the left-hand list** (the 24 depth levels). The scene
   brings that depth forward and the chart marks it. Arrow keys work too.
4. **Drag "Vertical exaggeration."** The ocean is 2 km deep but 1600 km wide, so
   at true scale it is a thin film. This stretches it so you can see inside it.
   The bar at bottom-right tells you honestly how much it has been stretched.
5. **Press RUN** under the time strip to step through the three dates.

## 4. Things only you can do

I cannot do these. They need your account, your money, or your college.

| # | What | Why it matters | Urgency |
|---|---|---|---|
| 1 | **Get the internal hackathon date from the SPOC** | Everything is currently planned against a guess (Sep 12). If it is sooner, I need to cut scope deliberately rather than discover it late | **Highest.** One message |
| 2 | **Make a free Copernicus Marine account** at data.marine.copernicus.eu, then give me the username and password | This is the only source of **ocean currents at depth.** The problem statement asks for current vectors and I cannot build them without it. INCOIS's free server has temperature and salinity but no deep currents | **High.** 5 minutes, free |
| 3 | **Buy the SagarNode sensor parts** | The physical tank demo for the internal round. Full shop list, wiring diagram and the two mistakes that kill the board are in `docs/SAGARNODE-BOM.md`. Roughly Rs 1400 to 2900 | **High**, because delivery takes time |
| 3b | **Find one glider or ship CTD file** for the Indian Ocean, in any text format (CSV, tab separated, an ODV export) | The problem statement names gliders and CTDs as instruments we must display. The reader for them is built and is the most heavily tested part of the codebase, but INCOIS do not publish such a file on their open server, so I have nothing to feed it. Any real one closes that requirement the day it arrives. A mentor or a college contact at a marine institute is the likeliest route | Medium |
| 4 | **Install Docker Desktop** (or tell me to skip it) | The problem statement says the tool must be deployable on INCOIS's servers. The config files for that are written but have never been run, because Docker is not on this machine. A judge may ask | Medium |
| 5 | **Commit and push the code** | You said you would handle git. Nothing has been committed. Roughly 100 files are staged and waiting | Medium |
| 6 | **Confirm the 6-member team** (at least one female member is an SIH hard rule) and 2 mentors | Registration requirement | Medium |
| 7 | **Re-check the idea counter** on sih.gov.in for SIH26067 on **Sep 15 and Sep 19** | If it goes above ~150 ideas our odds drop and we should consider the backup problem statement | Two calendar reminders |

## 5. What is deliberately not built yet

So you are not surprised by gaps. These are all planned, in order, and none of
them is a P0 requirement that is missing:

- The **talking assistant** (Samudra Sahayak) that flies the camera on voice
  command. Phase 2. The scene was built so the assistant can only move it
  through the same controls you use, which is what keeps it honest.
- The **accuracy scorecard** (RMSE numbers proving how far the model is from
  reality). Phase 4. The two curves are drawn today, but no number is claimed,
  and the panel says so on screen, because a number computed the quick way would
  not survive an INCOIS oceanographer's question.
- **Cyclone warning polygons**, the **sensor rig** and **guided tours**.
  Phases 2 and 4. (The standards endpoints used to be on this list and are now
  built, see above.)
- **Depth-resolved currents** and a **chlorophyll layer**, both waiting on
  items in your list above.

## 6. Honest weak points today

- The data is on a **1 degree grid**, updated every 10 days. That is INCOIS's own
  analysis product, so it is defensible, but it looks coarse. The finer data
  (1/12 degree) is item 2 in your list above.
- **Deep currents are missing entirely** until that account exists.
- The occasional frame still stutters (1 frame in 100 drops to about 27 per
  second). Fine, not yet excellent.
- The Docker deployment path is written but unproven.
- Nobody from INCOIS has been contacted yet. Past winners did this and said so on
  stage. Worth doing in October.

---

*Deeper detail, if you ever want it: `docs/P0-STATUS.md` for exactly where each
of the problem statement's seven requirements stands and what proves it,
`docs/PRD.md` for features, `docs/TRD.md` for architecture, `docs/ROADMAP.md`
for dates and open items, `docs/PLUGINS.md` for the plugin interface,
`docs/adr/` for why specific technical choices were made, `README.md` for
developer setup.*
