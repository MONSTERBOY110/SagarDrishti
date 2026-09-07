"""Samudra Sahayak agent plane (TRD M4) -- Phase 2.

Deliberately empty in Phase 1. The agent is a SEPARATE service so that it can
be detached wholesale if a judge dislikes it (TRD §6.5) without touching a
single P0 requirement.

Contract when implemented:
  * The agent calls the same public API the browser calls. It has no database
    access and no private data path.
  * Numbers enter answers ONLY as tool results, each carrying dataset id,
    timestamp and (for Argo) float WMO id -- CLAUDE.md hard rule.
  * Scene control is a validated SceneState patch (packages/scene) pushed over
    WebSocket. The agent cannot draw; it can only request a state it is allowed
    to express.
"""
