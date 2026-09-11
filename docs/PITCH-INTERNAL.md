# The three-minute pitch, internal round (Wed 16 September 2026)

Written to be **spoken**, not read. Every figure in it is on the screen behind
you while you say it, and every one can be re-derived from
[`docs/P0-STATUS.md`](P0-STATUS.md) if a judge asks where it came from. Nothing
here is a number we made up to sound good, and that is worth more in this room
than any adjective.

**Rehearse it five times with a timer.** Three minutes is shorter than it
sounds: the demo eats a third of it and a stall eats the rest.

---

## Before you start

| Thing | State it must be in |
|---|---|
| WiFi | **Off, visibly.** Turn it off in front of them. It is the strongest thing you can do in the first ten seconds and it costs nothing. |
| Services | `./tasks.ps1 api`, `./tasks.ps1 agent`, `./tasks.ps1 demo` all running and checked once |
| Browser | Full screen, on the Bay of Bengal opening view, zoom 100 per cent |
| The rig | Powered, probes in the tank, its panel already on screen; a jug of warm water within reach and NOT on the laptop side of the table |
| Backup | The recorded video open in a second tab. If anything hangs for more than five seconds, switch to it and keep talking. |

If the parts never arrived, the rig beat still works: post readings with
`curl` from a second terminal. Say what you are doing. "This is a stand-in for
the board, and the board is the only part that is missing" is a fine sentence
in front of judges and a much better one than pretending.

---

## The script

### 0:00 to 0:25 &nbsp; The problem, in INCOIS's own words

> *Speaker: Content and Scenarios (Beginner 2). Slide: the PS quote, nothing else.*

"India's ocean forecasting agency, INCOIS, wrote this problem statement
themselves. Their words: forecasters are **forced to toggle between disparate
software packages**, and that **impedes timely hazard assessment,
search-and-rescue support, fishery advisories**.

They produce a 3D ocean every day. They have no single place to look at it.
We built that place, and it is running on this laptop with the WiFi off."

*Hand over. Do not explain the architecture. They will see it.*

---

### 0:25 to 1:35 &nbsp; The demo

> *Driver: the Lead. Talk while you drag; never narrate a still screen.*

**(0:25) The water column.** Drag the depth cursor down the rack from 5 m to
2000 m.

"This is the Bay of Bengal on the 30th of July, from INCOIS's own public
ERDDAP server. Twenty-four levels, five metres to two thousand. Not a stack of
maps: you are inside it, and you can fly through it."

*If it is running well, tilt the camera under the surface for one second. It
is the shot people remember.*

**(0:45) The instruments.** Click an Argo float.

"Twenty-five real casts are in this box, taken by seventeen instruments:
thirteen Argo floats, three biogeochemical floats that reported three times
each, and one moored buoy on the ninety-east line that India helps run. This
one is a real float with a real WMO number, and that is the water it actually
measured, against the model, at the same place and the same time."

> **Say casts, not floats.** A float drifts and reports repeatedly, so
> twenty-five marks were made by seventeen instruments and the screen says
> both. Calling the marks floats would put **eight instruments in the Bay of
> Bengal that are not there**, in front of the people who run the array. For
> the BGC floats alone it would be nine where there are three.

**(1:05) The number nobody else prints.** Point at the verification card, top
right.

"And this is the part I would ask you to remember. Every ocean viewer in the
world draws the model. This one also prints **how wrong the model is**.

Bias two hundredths of a degree, root-mean-square error **0.60 degrees**, over
**eleven thousand seven hundred and eighteen** matched measurements from
twenty-three real casts. And underneath it, in red, our own caveat: this
analysis has already seen these floats, so that is how well it fits its own
data and it is **not** forecast skill. We print the thing that weakens our own
number, because a forecaster who cannot see that cannot use the tool."

**(1:25) The danger.** Point at HazardWatch.

"The theme of this problem statement is Disaster Management. This panel is
real CAP, the format India's national alert backbone actually publishes.
Everything you see marked EXERCISE is a drill, and it says so four separate
ways, because the one thing this layer must never do is announce a tsunami
that is not happening."

---

### 1:35 to 2:05 &nbsp; The rig on the table

> *Driver: the Lead. Speaker: QA and Ops (Beginner 3) pours.*

"The problem statement asks for a design that takes future sensors. Most
answers to that are a paragraph. Here is ours."

*Point at the tank. Point at its mark on the globe.*

"An ESP32 in a bucket, posting to the same API the Argo floats and the moored
buoys come through. It appeared on that globe without one line of the data
model changing.

Watch what happens when I warm it."

*Pour. Wait for it. Do not fill the silence.*

"There. It tripped its own threshold and raised an alert, and the alert is
stamped EXERCISE, because a bucket in a college hall is not a coastal hazard
and we will not let it look like one on a screen full of real ocean."

---

### 2:05 to 2:35 &nbsp; Why this one wins

> *Speaker: Data Engineer or Analytics Dev. Slide: four lines, large type.*

"Four things, quickly.

**It is their own problem, in their own words.** The Ministry of Earth
Sciences posted this. It is an internal INCOIS tooling request, so the
deployment story is not something we invented for a slide.

**It runs air-gapped.** No internet, no licences, no client install. That was
in the problem statement and it has been true since the first week.

**It is checkable.** Five hundred and nineteen automated tests, and ten of
them drive a real browser through the demo you just watched. The demo path
itself is a test, so it cannot rot quietly between now and December.

**And almost nobody is attempting it.** This problem statement has no AI
buzzword in the title and it needs NetCDF and WebGL, which most teams do not
have. When we checked on the seventh of September it had zero ideas against a
cap of five hundred, while the crowded ones were already at their cap."

> **Re-check the counter on 15 September and say the number you actually
> see**, not the one written here. sih.gov.in/sih2026PS, PS SIH26067. Quoting
> a stale figure to judges who can open the page on a phone is a bad trade for
> a sentence that works either way.

---

### 2:35 to 3:00 &nbsp; The team, and the close

> *Speaker: the Lead. Every member says their own line. Nine words each, no more.*

Each member, in one breath: name, and the one thing they own.

"Six of us, and every one of us owns something on that screen you can ask
about."

Then close on one sentence and stop:

"INCOIS makes a three-dimensional ocean every day, and their forecasters still
have to change software to put it beside the instruments in the water. This
puts them on one screen, on INCOIS's own data, with a number saying how far
apart they are, and it works with the internet off."

*Stop. Do not add anything. Let them ask.*

> **Say it exactly as written.** An earlier draft closed with "and has nowhere
> to look at it", which is the one claim CLAUDE.md forbids: INCOIS's Digital
> Ocean portal advertises 3D and 4D visualisation, and one informed judge
> sinks the whole pitch with that sentence. The gap the PS itself describes is
> that forecasters are "forced to toggle between disparate software packages",
> which is a different and defensible thing. Never upgrade it back.

---

## If you are running long, cut in this order

1. The tilt under the surface (five seconds).
2. HazardWatch (fifteen seconds). Painful, and it is still the right cut: the
   verification card is the harder claim to copy.
3. The agent. It is not in the script above for exactly this reason: it is the
   most impressive thing in the room and the easiest to overrun on. Bring it
   out in questions instead, where it earns more.

**Never cut the verification card or the tank.** One is the claim no other
team can make and the other is the thing they will remember in the corridor.

---

## The five questions to expect, with the answers

**"Doesn't INCOIS already have a 3D portal?"**
Yes, and never say otherwise. Their Digital Ocean portal claims 3D and 4D
visualisation, and it is a data-management and fusion portal whose 3D is a
globe with draped layers and time animation. We consume their own ERDDAP, so
there is no data duplication, and we add what it does not do: true
volumetrics, a skill number beside the field, and natural-language control.
The long version is in `docs/PRIOR-ART.md` section D.

**"Is this just Windy or earth.nullschool?"**
Those are surface animations. Ninety per cent of the ocean state that matters
for cyclone intensification, fisheries and search-and-rescue is below the
pixel they draw. We render the whole column, fuse the instruments into it, and
quantify how far the model is from them.

**"Is the AI making the numbers up?"**
It cannot. Every figure in every answer has to come from a tool call against
the real data, and there is code that reads the finished sentence and
**withholds** it if a number appears that no tool produced. Click the tool
trace under any answer and you see exactly what ran. And be straight about
this: there is no language model in it yet, it prints `planner: rules` under
every answer, and being caught pretending would cost far more than saying so.

**"How fast is it really?"**
Fifty-one frames a second, median, at 1920 by 1080, measured on the integrated
Intel chip rather than the good GPU, because the weaker one is what a nodal
centre will have. Worst single frame in five seconds was twenty-seven. Those
numbers and the method are written down in `docs/P0-STATUS.md`.

**"What is missing?"**
Answer it straight, it is a strength. A glider or CTD file, which needs data
and not code; chlorophyll, which INCOIS publishes only up to 2020 so it cannot
share a time axis with a 2026 field and we refuse to fake it; and the Docker
path, which is written and has never been run because Docker is not installed
on this laptop. All three are in `docs/P0-STATUS.md` with the same wording.

---

## What NOT to say

- Never "no 3D exists at INCOIS". It is wrong and one informed judge sinks the
  pitch with it. (CLAUDE.md, `docs/PRIOR-ART.md`.)
- Never "salinity sensor" for the tank probe. It is a **conductivity-derived
  salinity proxy**, and the person most likely to notice is the person most
  worth impressing.
- Never quote the RMSE without the caveat that follows it. If you have time
  for the number you have time for the sentence.
- Never call the drill bulletins real warnings, even as shorthand.
- Never say "AI-powered" about the assistant while it is a rule-based router.
- Never call the twenty-five marks twenty-five floats. They are twenty-five
  casts from seventeen instruments, and the screen says so.
