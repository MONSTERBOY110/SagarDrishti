"""What the agent is allowed to change about the view.

Deliberately a copy of the list in `services/api/app/storyboards.py:PATCHABLE`
rather than an import, and that is worth defending because duplication is
usually the wrong answer.

The agent is a SEPARATE SERVICE (TRD section 8) whose whole point is that it
can be detached without touching a P0 requirement, and that it reaches the data
plane only over the public HTTP API. Importing a Python module out of
`services/api` would make it a code dependency of the thing it is supposed to
be detachable from, and would mean the agent could no longer be deployed on its
own machine.

So the two lists are kept in step by a test rather than by an import:
`services/agent/tests/test_scene_keys.py` reads both and fails if they diverge.
That gives the same protection as sharing the constant without the coupling,
and it fails at build time rather than in front of an audience.

The browser holds the third copy, derived from its own store at runtime, and
refuses an unknown key out loud. Three checks, none of them able to drift
quietly.
"""

from __future__ import annotations

PATCHABLE = frozenset(
    {
        "sourceId",
        "variable",
        "focusDepth",
        "time",
        "palette",
        "scale",
        "vmin",
        "vmax",
        "reverse",
        "colorbarLocked",
        "exaggeration",
        "opacity",
        "playing",
        "selection",
        "isosurfaceOn",
        "isovalue",
        "rehearsal",
        "currentsOn",
    }
)
