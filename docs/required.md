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

**What I will have ready for it:** the ingest endpoint, the live "virtual
mooring" mark on the globe and the trend chart. The mooring instrument class
already works end to end, on a real RAMA buoy, so SagarNode plugs into a path
that is already proven rather than a new one.

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

**One thing still to build on top of it:** the currents are ingested and served
through the API and the OGC endpoints, but not yet drawn as arrows on the
globe. That is my next piece of work, not yours.

### 5. Docker Desktop, or tell me to drop it

**Why:** the problem statement says the tool must be deployable on INCOIS's own
servers. The Docker files are written and have **never been run**, because
Docker is not on this machine. That is the last unproven claim in requirement
F5, and a judge who works in IT may ask.

**Either** install Docker Desktop and tell me, and I will run the compose stack
and turn "authored" into "verified", **or** tell me to skip it and I will say
plainly in the docs that it is unverified rather than leave it ambiguous.

### 6. One glider or ship CTD file for the Indian Ocean

**Any delimited text format:** CSV, tab separated, or an ODV export.

**Why:** the problem statement names gliders and CTDs among the instruments we
must display. The reader for them is built and is the most heavily tested module
in the whole project, 66 tests. I have nothing to feed it. INCOIS do not publish
such a file on their open server, and I have checked.

**Where to look:** a mentor, a college contact at a marine institute, NIOT, NIO
Goa, or any faculty member who has been on a research cruise. Even one cast from
one station is enough. This is the last piece of a P0 requirement that is
blocked on data rather than on code.

---

## Two calendar reminders

### 7. Check the idea counter on 15 and 19 September

**Where:** sih.gov.in/sih2026PS, find **SIH26067**.

**What to look for:** the number of ideas submitted against it. If it goes above
roughly 150, our odds drop enough that we should talk about the backup problem
statement (SIH26176) before the 20 September PDF deadline.

### 8. The idea PDF goes to the SPOC by 20 September

Four days after the internal round. `docs/SUBMISSION-GUIDE.md` has the six-slide
structure. I will draft it from what actually exists rather than from what we
hoped to build, but you send it.

---

## Ongoing

### 9. Commit and push

You said you would handle git and I have not committed anything. There are
around 35 changed files and 27 new ones waiting, including two new services'
worth of code. Worth pushing before the round: this is a lot to have in one
place. Worth pushing before the
round so there is a recoverable copy that is not this laptop.

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
