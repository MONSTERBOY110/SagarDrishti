# Ocean-hazard bulletins, CAP v1.2 (REHEARSAL SET)

**Every file in this directory is a drill. None of them is a real warning and
none of them describes anything that happened.**

## Why they exist

The problem statement's portal theme is Disaster Management and it names three
ocean hazards: **tsunami, high wave, swell surge**. Those come from INCOIS's
Indian Tsunami Early Warning Centre and its Ocean State Forecast service.

India *does* have a live, public, machine-readable CAP feed: NDMA SACHET, the
national CAP backbone. HazardWatch reads it, and the parser in
`services/api/app/cap.py` is proven against real alerts retrieved from it. But
on 2026-09-09 that feed carried 99 alerts from CWC, IMD and the state disaster
authorities and **not one ocean hazard**, and no public machine-readable CAP or
RSS endpoint for ITEWC itself could be found (`tsunami.incois.gov.in` answers;
its `ITEWS/cap.jsp` and `ITEWS/rss.jsp` do not).

So the three hazards the PS names by name are authored here, in the real
format, over the real demo box, and marked as drills.

## How they are marked, and why it is not a workaround

Every file carries `<status>Exercise</status>`.

That is CAP's own field for this. The vocabulary is Actual, **Exercise**,
System, Test, Draft, and `Exercise` means precisely "this is a drill, handle it
as though it were real". It is what a genuine tsunami exercise uses. Four
consequences follow, and they are mechanical rather than promised:

1. **Any conforming CAP reader** in the world, not only ours, will treat these
   as drills. The marking travels with the file.
2. `app/cap.py:active()` refuses a non-`Actual` alert and counts it under
   `not_actual`. Showing one requires a caller to pass `allow_exercise=True`
   explicitly, and even then the alert keeps its `Exercise` status all the way
   to the client.
3. `allow_exercise` admits `Exercise` **only**. `Test`, `Draft` and `System`
   stay refused even in rehearsal, and a test pins that: `Draft` is content an
   issuing agency has not approved for release, so a flag meaning "let me
   rehearse" must never be the thing that publishes it.
4. Each headline begins `EXERCISE EXERCISE EXERCISE`, which is the convention
   real emergency-management drills use, so the marking is legible to a human
   who reads the text rather than the XML.

## What is modelled on what

The structure follows ITEWC bulletin practice as described in the UNESCO-IOC
Tsunami Service Provider user guide: an event, a threat level, an area, and an
instruction. The wording is ours. The geometry is placed inside the Bay of
Bengal demo box (6 to 26 N, 81 to 96 E) so the polygons sit over the model
field the rest of the tool is drawing.

| File | Hazard | Severity | Exercises |
|---|---|---|---|
| `itewc-tsunami-andaman.cap.xml` | Tsunami | Extreme | a circle around an epicentre plus a coastal polygon, and three languages |
| `osf-high-wave-north-andhra.cap.xml` | High wave | Severe | the ordinary polygon path |
| `osf-swell-surge-andaman-nicobar.cap.xml` | Swell surge | Moderate | a hazard whose severity ranks below the others, so the banner ordering is visible |

## The day a real feed appears

Nothing in the code special-cases this directory. It is a `kind: cap` source in
`data/sources.yaml` exactly like the SACHET one, so pointing that entry at a
real ITEWC endpoint is a config edit, and the files here can then be deleted
without touching a line of Python.
