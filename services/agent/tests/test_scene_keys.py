"""The three copies of "what the agent may change about the view" agree.

There are three, on purpose, and none of them can be an import of another:

  * `services/agent/app/scene_keys.py` -- the agent is a SEPARATE service whose
    whole point is that it can be detached and deployed alone, so it may not
    take a Python dependency on services/api.
  * `services/api/app/storyboards.py:PATCHABLE` -- validates tour files at load.
  * `apps/web/lib/scene.ts:INITIAL_SCENE` -- the live store, and the authority.
    The browser derives its whitelist from this at runtime, so it is right by
    construction and refuses an unknown key out loud.

Duplication kept honest by a test rather than by coupling. This is the test.
It fails at build time, which is the only place a divergence is cheap: the
alternative is a tour step or an agent answer that silently changes nothing on
stage and looks exactly like one that worked.
"""

from __future__ import annotations

import pathlib
import re

from app.scene_keys import PATCHABLE

REPO = pathlib.Path(__file__).resolve().parents[3]


def _api_patchable() -> set[str]:
    src = (REPO / "services" / "api" / "app" / "storyboards.py").read_text(encoding="utf-8")
    block = re.search(r"PATCHABLE = frozenset\(\s*\{(.*?)\}\s*\)", src, re.S)
    assert block, "services/api storyboards.py no longer declares PATCHABLE as a frozenset"
    return set(re.findall(r'"([A-Za-z_]+)"', block.group(1)))


def _store_keys() -> set[str]:
    src = (REPO / "apps" / "web" / "lib" / "scene.ts").read_text(encoding="utf-8")
    block = re.search(r"INITIAL_SCENE: SceneState = \{(.*?)\n\};", src, re.S)
    assert block, "apps/web/lib/scene.ts no longer declares INITIAL_SCENE"
    # Keys at the top level of the object literal, ignoring commented lines.
    return {
        m.group(1)
        for line in block.group(1).splitlines()
        if not line.strip().startswith("//")
        for m in [re.match(r"\s{2}([A-Za-z_][A-Za-z0-9_]*):", line)]
        if m
    }


def test_the_agent_and_the_tour_loader_allow_the_same_keys():
    assert PATCHABLE == _api_patchable(), (
        "services/agent/app/scene_keys.py has drifted from "
        "services/api/app/storyboards.py:PATCHABLE"
    )


def test_both_match_the_live_scene_store():
    """The browser store is the authority: it is what a patch is applied to."""
    store = _store_keys()
    assert store, "could not read the scene store keys"
    assert PATCHABLE == store, (
        "the agent may patch "
        f"{sorted(PATCHABLE ^ store)} which the scene store does not agree about. "
        "A key the store does not have is a patch that silently does nothing."
    )
