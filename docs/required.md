# What I need from you

**Internal college hackathon: Wednesday 16 September 2026. Seven days from
today (9 September).**

Everything in this file needs your account, your money, your college or your
decision. I cannot do any of it. Everything else, I am building.

Ordered by **when you have to start**, not by importance. Items 1 and 2 have
delivery or scheduling lead time, so they decay if left until the weekend.

---

## Start today

### 1. Buy the SagarNode parts

**Why it is first:** your mentor asked for a physical rig, and an internal round
is exactly where one pays off. Judges walking a room remember the team whose
project they could put a hand in. It also demonstrates PS requirement F6
(extensible design, "future integration of additional sensors") with hardware
rather than with a paragraph, and the software side of that requirement is
already finished and running.

**What to do:** take `docs/SAGARNODE-BOM.md` to a local electronics shop. It is
written as a shopping sheet, with substitutes and expected prices. Roughly
Rs 1,400 to 2,900.

**Two things in that sheet that people get wrong, so do not let the shop talk
you out of them:**

- The **resistor dividers** (10 k plus 20 k, or two 10 k). The TDS and turbidity
  boards output 0 to 5 V and the ESP32 pin tolerates 3.3 V. Without the divider
  you can damage the board on first power-up.
- A **data** USB cable, not a charge-only one. Many cheap cables cannot carry
  data and the symptom is a board that appears dead.

**If it cannot arrive by Sunday 13 September, tell me and I will stop planning
around it.** A rig that shows up on the 15th is a risk, not a feature: it needs
a day of wiring and a rehearsal.

**What is already ready for it, as of 10 September: everything except the
tank.** The ingest endpoint, the mark on the globe, the panel with the three
readings and a temperature trend, and the warm-water alert are built and
tested. The firmware sketch is written too, and marked in the file as never
having run on a board, so the day the parts arrive is an hour of testing
rather than an evening of writing.

You can see the whole thing today without buying anything, because the server
does not care what posts to it. With `./tasks.ps1 api` running:

```
curl -X POST http://127.0.0.1:8000/ingest/sagarnode -H "Content-Type: application/json" ^
  -d "{\"station_id\":\"sagarnode-01\",\"temp_c\":27.4,\"tds_ppm\":310,\"turbidity_ntu\":4.2}"
```

Post that twenty times and the panel appears beside the globe. Post one more
at 34.2 and it stamps itself as a drill and says the tank warmed 7 degrees
above its own recent average. That is the beat the rig performs on the table,
and the only thing the hardware adds is that a judge can cause it by hand.

### 2. Confirm the demo logistics with the SPOC

Four questions, one message. Each of them changes what I build this week.

- **How long is our slot?** A 5 minute demo and a 15 minute demo are different
  products. I will script the run to fit.
- **Is there internet in the room?** It does not matter for correctness, we run
  air-gapped by design, but if there IS Wi-Fi I will not spend time on the
  offline story in the pitch, and if there is not, that becomes a talking point.
- **Do we present on our own laptop or a provided machine?** This is the one
  that can actually break the demo. If it is a provided machine I need to know
  now, because the 3D scene needs a working GPU and a browser we can install
  nothing on.
- **Is there a slide deck as well as a live demo, and what is the format?**

### 3. Confirm the team

Six members and two mentors, and **at least one female member is an SIH hard
rule**. If registration is not done, it is worth doing before the round rather
than after.

---

## This week, whenever you have ten minutes

### 4. A free Copernicus Marine account: DONE, and it paid off the same evening

You sent the credentials on 9 September. They are in `.env`, which is
gitignored, and the source went live that night.

**What it bought.** Depth-resolved currents, the one part of the problem
statement's F1 that no INCOIS source can answer, because their free server
publishes surface currents only. 40 levels from half a metre to 1942 m, at
1/12 degree, which is 128 times the cells per level of the INCOIS analysis.
Real values: eastward currents from -1.24 to +1.46 m/s over the box.

**It also caught a mistake we could not have found without it.** The dataset we
had configured was the GLORYS multi-year reanalysis, and logging in showed it
stops on 23 June 2026. All three of our dates are in July. It would have been
configured, enabled, and quietly incapable of producing one usable field. The
right product (analysis and forecast) covers us, and a test now fails the build
if anyone puts the reanalysis back.

**Two things on the account itself, then I will stop.** Change that password
when you get a minute: it came through a chat window, and it is worth treating
as exposed even though nothing bad has happened. And it never enters the
repository: it lives only in `.env`, which git is configured to ignore, and I
checked that it does.

**Done since:** the arrows are on the globe. Switch CURRENTS on in the left
panel and move the depth cursor: at the surface the fastest flow is about
1.3 metres per second, at a kilometre down it is a fifth of that. Nothing more
is needed from you for this one.

### 5. Docker Desktop, or tell me to drop it

**Why:** the problem statement says the tool must be deployable on INCOIS's own
servers. The Docker files are written and have **never been run**, because
Docker is not on this machine. That is the last unproven claim in requirement
F5, and a judge who works in IT may ask.

**Either** install Docker Desktop and tell me, and I will run the compose stack
and turn "authored" into "verified", **or** tell me to skip it and I will say
plainly in the docs that it is unverified rather than leave it ambiguous.

### 6. One glider or ship CTD file for the Indian Ocean: NO LONGER BLOCKING

**This is done, and you did not have to do anything.** Leaving the item here
because it was the last P0 gap and because how it closed is worth two minutes
of your time if a judge asks.

On 15 September I found a real glider and real CTD casts, and both are now in
the product. All four instrument classes the problem statement names are live:
149 casts from 19 instruments, up from 25 casts from 17.

**Where they came from, and why we did not have them before.** The problem
statement's own "Dataset Link" field on sih.gov.in lists four archives, and I
had never read that field. The third link is an Ifremer glider FTP. Its index
file turned out to be 248 MB of whitespace, a broken build on their side, but
the same data sits in the Copernicus archive we already have an account for.
The reason three weeks of searching missed it: I had been querying that
archive's live thirty-day window, and concluding that no glider had reported in
thirty days meant no glider existed. The historical part of the same dataset
indexes 89,115 files.

**What is in the demo now:** glider ru29, a Rutgers robot that flew off
southern Sri Lanka in 2018, 109 dives inside our box, down to 955 m. Plus
fifteen CTD casts taken from the research vessel SHINYO MARU in the Bay of
Bengal in 1990 and 1991.

**The one thing to know before a judge asks: they are old.** 2018 and 1990
against a July 2026 model. That is not hidden and it is not an accident:

- there is no glider in the Bay of Bengal today, and I checked. On
  1 September the entire live feed held one Indian Ocean glider and it was in
  the Mozambique Channel, 4,000 km away;
- so every one of those marks is drawn inside a ring, clicking one prints the
  date and the reason, and the verification REFUSES all 13,622 of their
  measurement levels rather than scoring an old dive against a new field, and
  prints that refusal count on screen.

**If a judge presses you:** the problem statement asks for gliders to be
CO-DISPLAYED, not verified. The choice was a real glider with its date
declared, or no glider at all. We took the first and made the system say so.

**Still genuinely useful, if it ever appears:** a cast in delimited text, CSV or
an ODV export, from a mentor, NIOT, NIO Goa, or anyone who has been on a
research cruise. That reader is still built and still empty, and a file handed
over on a USB stick is the form a cast from INCOIS would actually arrive in.
It is no longer blocking anything.

---

## Two calendar reminders

### 7. Check the idea counter on 15 and 19 September

**15 September: DONE. SIH26067 stands at 4 of 500.** Nowhere near the ~150
threshold, so the backup problem statement stays on the shelf. Submission
deadline on the portal reads 30 September 2026.

Three other things came out of that check, all now handled:

- **The theme is Disaster Management**, confirmed on sih.gov.in itself. Two
  third-party mirrors disagree with each other about this and one of them says
  Smart Automation. Ours was right. It is printed on slide 1, so it mattered.
- **The exact problem statement title was wrong in our deck** and is now
  verbatim from the source: "Develop a web-based interactive 3D visualization
  platform that integrates numerical ocean model outputs and in-situ
  observations."
- **The Dataset Link field** is what closed item 6 above.

**Still to do on 19 September:** re-check the counter at sih.gov.in/sih2026PS.
Same threshold, same escalation.

### 8. The idea PDF goes to the SPOC by 20 September

Four days after the internal round. **The words are now drafted**, all six
slides, in [`IDEA-PDF-DRAFT.md`](IDEA-PDF-DRAFT.md), written from what
actually exists rather than from what we hoped to build: every claim is marked
BUILT or PLANNED and every built one carries a measured number.

Three things are still yours and the team's:

1. **Design and Story sets it in the SIH template and exports the PDF.** The
   draft is words and visual choices, not a layout.
2. **Somebody redraws the TRD section 1 architecture diagram clean.** The
   submission guide is right that slide 3 wins or loses screening, and a
   diagram is the one thing I cannot produce for you.
3. **Re-run the numbers the day it is exported.** They were read off the
   running service on 10 September. A stale figure in a submitted PDF cannot
   be withdrawn.

### 8b. Rehearse the three-minute pitch, five times, with a timer

[`PITCH-INTERNAL.md`](PITCH-INTERNAL.md) is written and timed to the second:
the problem in INCOIS's own words, a four-beat demo, the tank, the competition
math, and a line each for six people. It also carries the five questions to
expect with answers, what to cut if the clock runs out, and the five things
nobody may say on stage.

A script nobody has said out loud is not a pitch. Three minutes is shorter
than it reads, and the only way to find that out safely is in a room with a
timer rather than in front of judges.

---

## Ongoing

### 9. Commit and push

You said you would handle git and I have not committed anything.

**You committed on 10 September as `9ea32ee`, 33 files and about 3,900 lines,
and that cleared the backlog this section used to describe.** Everything up to
the live sensor station, the internal pitch script and the widened typography
guard is in that commit. Thank you; it is a much safer place to be.

The same request stands for whatever lands after it: push before the round, so
there is a recoverable copy that is not this laptop.

---

## What you do NOT need to do

So you are not carrying phantom work:

- Nothing about the data. Real INCOIS model fields, real Argo floats, real
  biogeochemical floats and a real moored buoy are all downloaded, processed and
  serving.
- Nothing about the demo running offline. It already does, and a test fails the
  build if anything reaches the internet.
- Nothing about the 3D scene, the isosurface, the standards endpoints or the
  plugin system. Those are done and tested.
- Nothing about the demo script. There are four guided tours built into the
  tool: press GUIDED TOURS at the bottom of the screen and it drives itself
  while you talk over it, arrow keys to go at your own pace. That is your
  safety net if the click order goes out of your head on the day.
- Nothing about the warning layer. HazardWatch is built and reading India's
  real national CAP alert feed. The three ocean hazards the problem statement
  names are rehearsal bulletins, marked as drills in the file itself, and there
  is a tickbox on screen to hide them. `docs/START-HERE.md` section 2 has the
  30 seconds of pitch that goes with it.
- Nothing about the accuracy scorecard. It is built and on screen as of today:
  the model is **0.60 degrees** from the real floats overall, worst across the
  thermocline at 2.07, from 11,718 matched pairs, with the 4,672 unusable
  levels counted and the reason for each printed beside them. See section 2 of
  `docs/START-HERE.md` for what to say about it, including the one caveat you
  must not be caught without.

---

## If you can only do two things

**Buy the parts, and answer the four logistics questions.** Everything else on
this list improves the project. Those two decide what the demo IS.

---

## Added 20 September: eleven icon PNGs for slide 3

Slide 3 of `docs/submission/PixelPaws_SIH2026.pptx` is now a real architecture
diagram, built on the pattern the four winning decks you sent all share. Every
icon slot in it is drawn as a **dotted placeholder box labelled `icon`**, so
the slide is complete and presentable exactly as it stands. If you drop PNGs
in, it gets better. If you run out of time, nothing looks broken.

**All eleven are transparent PNGs. Square unless noted. One colour or two,
simple enough to read at 0.2 inches, which is about 20 pixels on a projector.**

| Where | What it should show | Size on the slide | Export at |
|---|---|---|---|
| Zone 1 header | a database or a cloud, "external sources" | 0.20 in | 256 px |
| Zone 2 header | a funnel or gears, "processing" | 0.20 in | 256 px |
| Zone 3 header | a server or an API bracket | 0.20 in | 256 px |
| Zone 4 header | a person at a screen, "the forecaster" | 0.20 in | 256 px |
| the 7 component boxes | optional, one line glyph each | 0.18 in | 256 px |

**Where to get them free, with a licence we can name if asked:** Lucide
(lucide.dev), Tabler Icons, or Google Material Symbols. All three are MIT or
Apache, so we can use them in a competition deck without attribution trouble.
Download as PNG at 256 px with a transparent background.

**How to place them:** open the deck in PowerPoint or Slides, click a dotted
`icon` box, and paste the PNG over it. Do not resize the dotted box first,
match the image to it.

**The zone 4 slot is labelled `user`, not `icon`.** That one is the human
in the system, the INCOIS forecaster, and it is the only place a person
appears in the diagram. If you only do one, do that one.
