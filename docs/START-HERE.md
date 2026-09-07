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
handled and covered by 36 automated tests, so it stays handled.

**The 3D scene.** The Bay of Bengal as a stack of 24 coloured layers, one per
depth, from 5 m down to 2000 m. You can see the warm surface, the sharp
temperature drop between 50 and 200 m (the thermocline, which is what feeds
cyclones), and the cold deep water. It runs at **44 frames per second** on the
weaker of this laptop's two graphics chips, which is the number that matters
because it is the harder case.

**The float click-through.** 13 real Argo floats are on the globe. Click one and
you get its actual temperature profile, 524 measurements in the case of float
1902681, drawn as a coloured line against a dashed line showing the model. Where
the two lines separate is where the model disagrees with reality. That is the
whole point of the product, visible in one glance.

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
| 4 | **Install Docker Desktop** (or tell me to skip it) | The problem statement says the tool must be deployable on INCOIS's servers. The config files for that are written but have never been run, because Docker is not on this machine. A judge may ask | Medium |
| 5 | **Commit and push the code** | You said you would handle git. Nothing has been committed. About 90 files are staged and waiting | Medium |
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
- **Cyclone warning polygons**, the **sensor rig**, **guided tours**, and the
  standards endpoints (OGC WMS/WCS). Phases 2 and 4.

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

*Deeper detail, if you ever want it: `docs/PRD.md` for features, `docs/TRD.md`
for architecture, `docs/ROADMAP.md` for dates and open items, `docs/adr/` for
why specific technical choices were made, `README.md` for developer setup.*
