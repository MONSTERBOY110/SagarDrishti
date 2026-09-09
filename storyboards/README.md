# storyboards/

JSON-scripted guided tours (PRD F12, TRD M7). A tour is a list of steps: a
patch to the scene, a line of narration, and the **evidence** that line rests
on. Playing one drives the same store the controls drive, so a tour can do
nothing a presenter could not do by hand, and it needs no LLM: it replays
identically with the network off.

Served by `GET /storyboards`, validated by `services/api/app/storyboards.py`,
played by `apps/web/components/StoryPlayer.tsx`.

## Why they exist before the agent does

Two reasons, and the second is the better one.

**They are the demo's safety net.** A live demo where somebody has to remember
seven clicks under stage lights is a demo that goes wrong. Press play and it
drives itself, with the narration on screen to read from.

**They are the agent plane's plumbing, a phase early.** TRD M4 gives Samudra
Sahayak exactly one channel to affect the view: `set_scene` with a validated
patch. This is that channel, with a JSON file in front of it instead of a
language model. When the agent lands it inherits a patch path that has already
been driven in front of an audience, and `run_storyboard(id)` calls this same
route.

## The rule about numbers

**Every numeral in a narration line must be backed**, by the patch that step
applies or by the step's own `evidence` list. `validate_tour` refuses a tour
where it is not, and a test checks every shipped file.

This is not bureaucracy. Narration is the one place in the whole project where
a number can reach a judge without passing through a tool result: everything
else on screen is a value the API computed and cited, and a sentence in a tour
is prose somebody typed. It also catches the thing that will actually happen,
which is a figure going stale after the cube is refetched. A tour saying
"eleven thousand seven hundred pairs" after a rebuild is wrong on stage, and
the evidence line beside it is what makes that findable.

Write the evidence line as the on-screen fact and where to see it:

```json
{
  "narration": "The model is on average two hundredths of a degree warm.",
  "hold": 8,
  "patch": { "selection": null },
  "evidence": ["bias +0.026 degC over 11,718 pairs, on the verification certificate"]
}
```

## The format

| Field | Meaning |
|---|---|
| `id` | Unique across all tours. A duplicate is refused, because a deep link or an agent call would otherwise get whichever loaded second |
| `title`, `subtitle` | Shown in the menu |
| `audience` | `judge` or `classroom`. Same product, pitched differently |
| `source_id` | The dataset the tour talks about; must exist in `data/sources.yaml` |
| `steps[].narration` | What to say. Read aloud, so write it to be spoken |
| `steps[].hold` | Seconds on screen, 4 to 20. Shorter and a reader cannot finish the sentence; longer and a demo stalls |
| `steps[].patch` | Keys from the live scene store only. A key the client cannot apply is refused, because a step that no-ops looks exactly like one that worked |
| `steps[].evidence` | The on-screen facts the narration rests on |

Files load in filename order, so the numeric prefixes are the running order and
adding a tour is dropping in a file. One malformed tour does not take the
others down: it is refused by name, with the reason, and the player says so.

## What is here

| File | Audience | Covers |
|---|---|---|
| `01-water-column.tour.json` | classroom | What the picture is: depth levels, exaggeration, the thermocline |
| `02-cyclone-fuel.tour.json` | judge | The 26 degC isosurface, its agreement with D26, its coastal refusals, and the day it splits in two |
| `03-instruments-and-skill.tour.json` | judge | The three instrument classes, the oxygen minimum zone, and the verification certificate with its caveat |
| `04-hazardwatch.tour.json` | judge | CAP warnings, the multilingual bulletin, and the Exercise marking |

## The four TRD M7 named, and why these are not them

TRD M7 lists cyclone cold-wake, monsoon upwelling off Kerala, an eddy seen by a
glider, and an Argo explainer. Three of those cannot be built from the data on
disk, and the honest thing is to say which and why rather than narrate over
data we do not have:

- **Cyclone cold-wake** needs a cyclone. The cube covers three ten-day analysis
  steps in July 2026 and no storm passes through them. It needs a case study
  fetched for its dates.
- **Monsoon upwelling off Kerala** is off the WEST coast, around 75 E. The demo
  box is 81 to 96 E. It needs a second box fetched.
- **An eddy seen by a glider** needs a glider, and there is none: the reader is
  built and tested, and no glider file has been obtained (see
  `docs/required.md`).

The Argo explainer survives, inside `03-instruments-and-skill`. The other three
are written above from what the data actually supports, which is also what the
demo will actually show.

Owner: Content & Scenarios (Beginner 2), per TEAM-ROLES.md. Adding a tour needs
no code: drop in a `NN-name.tour.json` and the menu picks it up.
