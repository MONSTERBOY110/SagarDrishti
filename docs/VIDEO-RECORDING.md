# Recording the portal demo video

**The video is a replay, not a performance.** The tour
`storyboards/00-the-whole-story.tour.json` drives the whole demo hands-free:
twelve steps, 150 seconds, every P0 requirement in the order a reviewer meets
them. You start it and then keep your hands off the keyboard. If a take goes
wrong, you run it again and get an identical take, which is the entire point of
building it this way.

A test pins that: `test_the_submission_tour_drives_every_p0_claim_in_one_run`
fails if a future edit drops the isosurface step, stops opening a float, stops
showing the derived density field, or turns the hazard layer on before it is
announced.

---

## Before you press record

| Thing | State |
|---|---|
| WiFi | **Off.** Say so on camera. Everything is served from the laptop and a test fails the build if any request leaves it |
| Services | `./tasks.ps1 api`, `./tasks.ps1 agent`, then `./tasks.ps1 demo` (production build, not `web`) |
| Browser | Full screen, 1920x1080, zoom at 100 per cent, no bookmarks bar, no notifications |
| Second monitor | Disable, or move everything to the recording display. A tooltip from another screen ends a take |
| The scene | Let it finish loading before recording. The slice stack builds asynchronously; start early and you record a half-built column |
| Capture | 1920x1080 at 30 fps is enough. The scene runs at 51 fps median, so 30 fps capture will not stutter |

Open the tour picker (**GUIDED TOURS** at the foot of the scene), choose
**"The whole story, in two minutes"**, and let it run. It advances itself.

---

## What the eleven steps show, and what you say over them

The narration is on screen under each step, and the evidence line beneath it is
the on-screen fact that sentence rests on. You can read the narration aloud
verbatim: it was written to be spoken and it carries no number that the tool
cannot show.

| # | Hold | The beat | The requirement it answers |
|---|---:|---|---|
| 1 | 12 s | The Bay of Bengal, temperature, the whole column in a browser | F1, F5 |
| 2 | 11 s | Travel down to 2000 m: 29 degC at the surface, under 3 at depth | F1, F4 |
| 3 | 12 s | The 26 degC isosurface: how much fuel a cyclone has | F1 |
| 4 | 12 s | Current vectors at the cursor, from a second agency, land blocks refused | F1 |
| 5 | 13 s | The instrument marks, four classes told apart by shape | F2 |
| 6 | 14 s | **The glider.** Real, dated 2018, ringed as archive, and refused by the verification | F2 |
| 7 | 13 s | Open a BGC float: measured profile against the model, plus biogeochemistry | F2 |
| 8 | 13 s | **The verification card.** How wrong the model is, as a number | F9 |
| 9 | 14 s | **The caveat, in red.** Analysis fit, not forecast skill | F9 |
| 10 | 12 s | Density: computed by a plugin through TEOS-10, never measured | F6 |
| 11 | 13 s | HazardWatch appears on cue. CAP v1.2, everything stamped Exercise | F13 |
| 12 | 11 s | Open standards, own data, network off | F7, F11 |

**Steps 8 and 9 are the ones that win it.** If you trim anything, do not trim
those two. Every ocean viewer draws the model; printing how wrong it is, and
then printing the sentence that limits your own number, is the claim no other
team at the nodal centre will be making.

---

## Two things to say out loud that the tour cannot show

**The WiFi is off.** Show it. It takes three seconds and it converts the whole
"deployable on INCOIS infrastructure" argument from a promise into a
demonstration.

**The glider is eight years old, and say so before anyone asks.** Step 6 shows
it, the ring around the mark says it and the panel prints the reason, but
saying it out loud turns a thing a reviewer might catch you on into a thing you
volunteered. The line is short: the problem statement asks for gliders, there
is no glider in the Bay of Bengal today, this is a real one from 2018, and the
verification refuses all 13,622 of its levels rather than scoring them against
a 2026 field.

**The assistant has no language model in it yet.** If you show Samudra Sahayak
at all, say that it is a rule-based router over real tools and that it prints
`planner: rules` under every answer. Being found out is worse than being
modest, and the honest version is still impressive: it physically cannot state
a number no tool produced.

---

## If something goes wrong mid-take

| Symptom | What it is | Do this |
|---|---|---|
| Globe is black, panels fine | Stale `.next` build | Stop, `rm -rf apps/web/.next`, `./tasks.ps1 demo`, start again |
| A panel is missing entirely | Its service is not running. The ask box disappears when the agent is down, by design | Start it, or carry on: every P0 feature still works without it |
| A tour step seems to do nothing | It cannot silently no-op; the validator refuses unknown keys | Check the API is up; the tour patches through the same store your clicks use |
| Frame rate visibly drops | Another application is using the GPU | Close it. The measured figure is 51 fps median on the integrated chip |

**Do not restart a take because a number looks unfamiliar.** Every figure on
screen is computed from the local cube; if it differs from a slide, the slide
is the thing that is stale, not the tool.

---

## After recording

- [ ] Watch it once at full size and check the narration panel is legible
- [ ] Check the verification caveat in step 8 is readable, not clipped
- [ ] Confirm nothing personal is on screen: no file paths with a name in them,
      no other browser tabs, no notifications
- [ ] Keep the raw take. A re-export is cheaper than a re-record
