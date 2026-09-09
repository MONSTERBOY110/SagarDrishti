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
handled and covered by **466 automated tests**, so it stays handled. Eight more
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

**Three kinds of instrument, told apart by shape.** 13 marks are ordinary Argo
floats, drawn as squares, measuring temperature and salinity. 9 are profiles
from 3 **biogeochemical floats**, drawn as diamonds, which also measure
dissolved oxygen, chlorophyll, nitrate and pH. Click a diamond and the panel
offers all of them. One of those floats reads **1.7 micromole of oxygen per
kilogram at 141 metres** while the surface above it is 28.5 degrees: that is the
Bay of Bengal oxygen minimum zone, water with effectively no oxygen in it, and
it is the kind of thing an INCOIS scientist will recognise immediately.

The last 3 marks are a **moored buoy**, drawn as a circle: a fixed instrument
anchored to the seabed at 15 N 90 E that measures the water column every day.
It belongs to RAMA, the Indian Ocean moored array that India's Ministry of
Earth Sciences and INCOIS help run, so it is literally one of our own
instruments. Worth knowing if a judge asks: RAMA has three buoys in the Bay of
Bengal and **only one is still in the water**. The other two stopped reporting
in March 2026 and September 2025. The tool says so rather than quietly showing
one buoy as though that were the whole array.

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

**The verification certificate.** This is the one I would lead with in front of
an INCOIS reviewer, because it is the thing their own public portal does not do.

Every ocean viewer in the world draws the model. Ours also prints, on the same
screen, **how wrong the model is**, as a number, checked against the real
instruments in the water. Top right of the page, under "Model verification":

> Bias **+0.026** degrees. RMSE **0.602** degrees. From **11,718** matched
> measurement pairs across 23 casts.

Expand it and you get the error broken down by depth. That breakdown is the part
an oceanographer will actually look at, and it says something true about the Bay
of Bengal: the model is nearly perfect in the deep water below a kilometre
(0.12 degrees), and worst between **50 and 100 metres** (2.07 degrees), which
is the thermocline, the layer that feeds cyclones. That is not a flaw we are
hiding. It is the expected place for a model to struggle, and being able to
point at it and say why is what a reviewer is testing for.

Two things about it that you should know before anyone asks you.

**It counts what it could not use.** 11,718 pairs were matched and **4,672
levels were refused**, each with the reason printed: 3,506 were never measured
by that instrument, 566 sit next to a coast where the model has a hole, 493 are
outside our downloaded box. A skill number without that ledger is a selected
number, and a reviewer who works with data will look for the ledger first.

**It is deliberately NOT called forecast skill, and the panel says so in red.**
The INCOIS model we are scoring already used these same Argo floats when it was
built. So the number measures how closely it fits data it has already seen,
which is a real and useful quantity, and it is not the same thing as predicting
tomorrow. If a judge tries to catch us on that, the answer is already printed on
the screen, in the reserved warning ink, above our own number. That is the whole
posture of this project in one panel.

**HazardWatch, the warning layer.** The problem statement's theme is Disaster
Management, and until today the tool showed the ocean and said nothing about
danger. Now, top of the middle of the screen, there is a HazardWatch panel and
red warning areas drawn on the water.

Three things to know about it, in order of how likely a judge is to ask.

**The feed is real.** India has a national disaster-alert system called SACHET,
run by the NDMA, and it publishes its alerts publicly in a format called CAP,
which is the international standard INCOIS themselves use. We read it. When I
checked on 9 September it carried **99 live alerts** from the Central Water
Commission, the weather department and six state disaster authorities, and the
tool parses them. Two real ones are saved into the project as permanent test
cases, so the code can never quietly stop understanding the real thing.

**The three ocean hazards are drills, and they say so.** The problem statement
names tsunami, high wave and swell surge. Those come from INCOIS's own tsunami
centre, which does not publish a public machine-readable feed (I looked). So
those three bulletins are written by us, in the real format, and every one is
marked with the CAP status **Exercise**, which is the standard's own word for a
drill. That marking is not decoration: any CAP reader in the world will treat
them as drills, our own server refuses to show them unless asked, the globe
draws them dashed rather than solid, and the panel stamps itself EXERCISE.
There is a tickbox on the panel: **untick it during the demo** and the three
drills vanish, leaving only whatever is genuinely live in India. That is a good
30 seconds of the pitch.

**It moves with the time slider.** The warnings are not pinned to today's
clock; they are shown for whatever date the scene is showing. Scrub to 10 July
and there is nothing. Scrub to 20 July and a swell surge appears off the
Nicobars. Scrub to 30 July, the date it opens on, and a tsunami warning and a
high wave warning are both in force. A judge scrubbing the timeline will see
the hazard picture change with the ocean underneath it.

One number worth having ready if someone asks whether it is really reading real
government data: one alert in that live feed had a boundary made of **93,478
points**. Drawing that as-is would have wrecked the frame rate, so the tool
simplifies it to about a kilometre of precision, and then it says on screen
that it did, because the boundary being drawn is no longer exactly the one the
agency published.

**Currents at depth, which your Copernicus account unlocked.** Until 9
September the tool could show temperature and salinity through the water column
but not which way the water was MOVING, because INCOIS's free server publishes
surface currents only and the problem statement asks for current vectors by
name. Your account fixed that the same evening: we now have the eastward and
northward current on 40 levels from half a metre down to nearly 2 km, at twelve
times the horizontal detail of the INCOIS field.

Worth knowing, because it is a good answer to "how careful are you": the
dataset we had configured for this turned out to be the wrong one, and only
logging in revealed it. It was the multi-year reanalysis, which stops on 23
June 2026, and all three of our dates are in July. It would have sat there
enabled and quietly unable to produce a single usable field. We switched to the
forecast product and added a test that fails the build if anyone puts the old
one back.

The currents are ingested and served, including through the two international
standards endpoints. They are not yet drawn as arrows on the globe; that is my
next job.

**Samudra Sahayak, the assistant.** Bottom of the screen there is a box marked
SAMUDRA SAHAYAK. Type a question, or click one of the four suggestions, and it
answers from the data and moves the scene to match. Ask "how good is the
model?" and it gives you the RMSE with its caveat. Ask "how warm is it at 500
m?" and it tells you and moves the depth cursor there. Ask about the cricket
and it politely says it cannot, and lists what it can.

**Three things to say about it if a judge asks, in this order.**

First: **it cannot make up a number.** Every figure in every answer has to come
from a tool call against the real data, and there is code that checks the
finished sentence and refuses to show it if a number appears that no tool
produced. Not corrects it, refuses it. Thirteen tests cover that one rule.

Second: **it shows its working.** Click the "1 tool call" button under any
answer and you see exactly which tool ran and what it returned. Nothing is
taken on trust.

Third, and be straightforward about this: **there is no AI language model in it
yet.** It is a rule-based router over the tools, it prints "planner: rules"
under every answer, and that is deliberate rather than embarrassing. A language
model needs either the internet, which we promise not to use on stage, or a
local model that would take a week and might fall over in front of the judges.
The tools, the safety check and the whole shape are the real ones; the model
slots in behind them later. If you are asked, say that. Being caught pretending
would cost far more than admitting it.

**Guided tours, which is the one I would actually use on the day.** At the
bottom of the screen there is a button marked GUIDED TOURS. Four of them, each
under 80 seconds:

1. **Reading a water column**, for a non-specialist audience
2. **The heat a cyclone feeds on**, the 26 degree surface
3. **The instruments, and whether the model agrees with them**
4. **When there is a warning**, HazardWatch

Press play and the tool drives itself: it moves the depth cursor, switches the
isosurface on, opens the right float, scrubs the date. The narration appears in
large type at the bottom for you to read aloud, and under each sentence it
prints the fact on screen that the sentence rests on. Space bar pauses, arrow
keys step, Escape gets out.

**This is your safety net.** If you are nervous about remembering the order of
clicks under stage lights, you do not have to. Start a tour and talk over it.
Arrow keys let you go at your own pace instead of the timer's.

One rule I built into it that is worth mentioning if a judge asks: **a tour is
not allowed to say a number unless the number is on screen or the step records
where it comes from.** The build fails otherwise. Narration is the only place
in this whole project where a figure could reach an audience without the tool
having computed it, so it is the one place that needed a rule.

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
- The **sensor rig**, which is waiting on the parts. (The standards endpoints,
  the accuracy scorecard, the cyclone warning layer and the guided tours all
  used to be on this list and are now built, see above.)
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
