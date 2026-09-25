# Demo video and voiceover script, 2026-09-25

Video: `docs/submission/video/SagarDrishti-demo-2026-09-25.mp4` (1920x1080, 30 fps, H.264, 231 s).
Its only sound is the app's own voice (1 utterance), so the
voiceover fits everywhere else. The same take with no sound at all:
`docs/submission/video/SagarDrishti-demo-2026-09-25.video-only.mp4`.

Recorded by `node tools/record_demo.mjs` from the running build. Every number
on a card was read from the data plane at recording time: RMSE 0.602 degC,
bias +0.026 degC, 11,718 matched pairs, 23 casts from 15
platforms, 18,294 levels refused.

**How to read it:** start each line at its time. Each is written to fit its
segment at about 2.5 words a second; if a line runs long, drop its last clause
rather than speeding up. Do not speak over the agent's own voice.

| t (s) | Segment | On screen | Voiceover |
|---|---|---|---|
| 0.0 | 01  The problem | Three dimensional ocean models, read through flat tools | INCOIS runs its ocean models in three dimensions, but forecasters read them by toggling between separate tools, one file and one depth at a time. The core challenge: the model is a volume, the instruments are points, and what a forecaster needs is how far apart they are. |
| 18.0 | 02  Why it changes the job | One page. The whole column. A number for the gap. | SagarDrishti puts the model and every instrument in the water on one page, the whole column in 3D, with a number for the gap. Nothing to install, and it runs with the network switched off. |
| 35.1 | 03  The core innovation | Class-4 verification, in observation space | The core innovation is Class 4 verification in observation space, the method operational centres use. The model is interpolated to each cast's own position and depth. R M S E 0.602 degrees over 11,718 pairs, and 18,294 levels refused, each with a printed reason, rather than guessed. |
| 54.3 | 04  The prototype, opening frame | The whole globe, the Bay of Bengal box | Here is the prototype, running on this laptop. It opens on the whole globe, with the Bay of Bengal in the box. |
| 63.0 | Walkthrough, tour step 1 | The whole water column, in a browser | This is the Bay of Bengal from INCOIS's own ERDDAP server: the whole water column, twenty four levels from five metres to two kilometres. |
| 73.0 | Walkthrough, tour step 2 | Travel down the column | Move the depth cursor and you travel down it. About twenty nine degrees at the surface, under three at two kilometres. |
| 83.1 | Walkthrough, tour step 3 | The 26 degC surface: cyclone fuel | This sheet is the twenty six degree surface, the depth of cyclone fuel, extracted from the grid itself. |
| 94.1 | Walkthrough, tour step 4 (additional) | Currents at depth, second agency | Currents at depth, from a second agency, and labelled as one. |
| 99.1 | Walkthrough, tour step 5 | Every mark is a real instrument | Every mark is a real instrument: Argo floats, BGC floats, a RAMA buoy, a glider and ship casts. |
| 109.1 | Walkthrough, tour step 6 (additional) | A 2018 glider, dated, not scored | The glider flew in 2018, so it is dated, and never scored. |
| 114.2 | Walkthrough, tour step 7 | What it measured, against the model | Click one and you see what it measured, against the model at the same place and time, and the gap between them. |
| 126.2 | Walkthrough, tour step 8 | The ray-marched volume, beside the cast | The same cast in the volume studio: the model ray marched on the GPU, cut away by depth, with the measured profile beside it. |
| 139.2 | Walkthrough, tour step 9 | Class-4: RMSE 0.602 degC over 11,718 pairs | And this is the core. Every cast scored where it was taken, Class 4 style. R M S E 0.602 degrees over 11,718 pairs. |
| 150.2 | Walkthrough, tour step 10 | The caveat travels with the number | With its caveat attached: this analysis has already seen these floats, so it is analysis fit, not forecast skill. |
| 159.3 | Walkthrough, tour step 11 (additional) | Density, derived by a plugin (TEOS-10) | Density, derived by a plugin with TEOS-10. |
| 164.3 | Walkthrough, tour step 12 | CAP warnings from NDMA SACHET, drills marked | Warnings drawn over the water, parsed from India's national CAP feed, NDMA SACHET. A drill can never pass for a real alert. |
| 175.3 | Walkthrough, tour step 13 | Served over OGC WMS and WCS | All of it served through OGC WMS and WCS, so the tools INCOIS already runs can read it. |
| 186.0 | Walkthrough, the agent (additional) | Ask: How warm is it at 100 m? | Ask Samudra Sahayak a question, and it answers only from the data plane's own tools, cites the source, and reads the answer aloud. |
| 212.9 | 05  Long-term impact | Deployable on INCOIS infrastructure as it stands | It deploys on INCOIS infrastructure as it stands: three containers, open standards, no licences. A new model or instrument is a configuration entry, not a rewrite. Next, the full Indian Ocean, cyclone season operations, and voice in the coastal languages through Bhashini. |
| 228.9 | End |  |  |
