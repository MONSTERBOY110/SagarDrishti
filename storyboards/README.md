# storyboards/

JSON-scripted guided tours (TRD M7 / PRD F12). Each tour is a sequence of
`SceneCommand` patches (see `packages/scene/scene.schema.json`) plus narration
text and optional pre-rendered TTS audio, so a tour replays identically offline
and needs no LLM.

Owner: Content & Scenarios (Beginner 2), per TEAM-ROLES.md.

Planned tours (Phase 4):
1. `cyclone-cold-wake.json` - a cyclone's cold wake in the Bay of Bengal
2. `monsoon-upwelling-kerala.json` - monsoon-onset upwelling off Kerala
3. `eddy-seen-by-glider.json` - an eddy carrying a glider
4. `what-is-an-argo-float.json` - the outreach/education explainer

Phase 1 ships this README and the schema reference only; no tour content yet.
