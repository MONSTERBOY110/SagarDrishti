"""JSON-scripted guided tours (PRD F12, TRD M7).

A tour is a list of steps. Each step is a patch to the scene, a line of
narration, and the evidence that line rests on. Replaying one drives the same
controls a person drives, so a tour can do nothing a user could not do by hand,
and it needs no LLM: it replays identically with the network off.

WHY THIS IS A DATA-PLANE MODULE AND NOT A PILE OF JSON IN THE CLIENT
--------------------------------------------------------------------
Because narration is the one place in this whole project where a number can
reach a judge without passing through a tool result. Everything else on screen
is a value the API computed and cited. A sentence in a tour is prose somebody
typed, and prose that says "the model is within half a degree" is a claim with
no provenance and no test behind it.

So every numeral in a tour's narration must be BACKED: it must appear either in
the patch that step applies, or in that step's own `evidence` list, which is
where the author records the on-screen fact and where it comes from. That rule
is enforced by `validate_tour` and by a test over every shipped tour, and it is
the narration equivalent of the citation discipline CLAUDE.md imposes on the
agent.

It also catches the thing that will actually happen: a number in a tour going
stale when the data is refetched. A tour that says "eleven thousand pairs"
after the cube is rebuilt is wrong on stage, and the evidence line beside it is
what makes that findable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Every key a step may patch.
#:
#: This is the scene state the WEB CLIENT holds (apps/web/lib/scene.ts), not
#: the aspirational SceneState in packages/scene/scene.schema.json, which is
#: the wider shape the agent plane will patch in Phase 4 and which the live
#: store does not implement yet. Listing the live keys here is deliberate: a
#: tour that patches something the client cannot apply is a tour that silently
#: does nothing on stage.
#:
#: The client checks the same thing against its own store at runtime and
#: refuses an unknown key out loud, so the two cannot quietly disagree: if this
#: list goes stale the player says so on screen rather than skipping the step.
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
    }
)

#: A tour step may not sit on screen for less than this, or a reader cannot
#: finish the sentence, and not for more than this, or a demo stalls.
MIN_HOLD = 4.0
MAX_HOLD = 20.0

#: Numerals that carry no claim and would only add noise to the guard: a date
#: inside a patched timestamp, an ordinal in "the tenth of July", a spelled
#: number. Digits are what the rule is about.
_NUMERAL = re.compile(r"\d+(?:\.\d+)?")


class TourError(ValueError):
    """A tour file this module will not serve."""


@dataclass
class Tour:
    id: str
    title: str
    subtitle: str
    audience: str
    source_id: str
    steps: list[dict]
    path: str = ""

    @property
    def seconds(self) -> float:
        return round(sum(float(s.get("hold", 0)) for s in self.steps), 1)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "audience": self.audience,
            "source_id": self.source_id,
            "steps": self.steps,
            "n_steps": len(self.steps),
            "seconds": self.seconds,
        }


def _backed(narration: str, patch: dict, evidence: list[str]) -> list[str]:
    """Numerals in the narration that nothing on the step accounts for.

    A numeral counts as backed if it appears in a patched VALUE or anywhere in
    the evidence text. Substring matching is used on purpose and is the lenient
    direction: "26" is backed by evidence mentioning 26.5, and "0.6" by
    evidence mentioning 0.602. The guard exists to catch a sentence with no
    supporting fact beside it at all, which is the failure that matters, not to
    audit rounding.
    """
    haystack = " ".join(str(v) for v in patch.values()) + " " + " ".join(evidence)
    return [n for n in _NUMERAL.findall(narration) if n not in haystack]


def validate_tour(raw: dict, *, where: str = "") -> Tour:
    """A tour document, or TourError naming what is wrong with it."""
    prefix = f"{where}: " if where else ""

    for field in ("id", "title", "steps"):
        if field not in raw:
            raise TourError(f"{prefix}missing required field {field!r}")
    if not isinstance(raw["steps"], list) or not raw["steps"]:
        raise TourError(f"{prefix}steps must be a non-empty list")

    for i, step in enumerate(raw["steps"], start=1):
        at = f"{prefix}step {i}"
        if not isinstance(step, dict):
            raise TourError(f"{at}: not an object")

        narration = step.get("narration", "")
        if not isinstance(narration, str) or not narration.strip():
            raise TourError(f"{at}: narration is empty; a step with nothing to say is a pause")

        hold = step.get("hold")
        if not isinstance(hold, (int, float)):
            raise TourError(f"{at}: hold must be a number of seconds")
        if not MIN_HOLD <= float(hold) <= MAX_HOLD:
            raise TourError(
                f"{at}: hold {hold} is outside {MIN_HOLD} to {MAX_HOLD} seconds. "
                "Shorter and a reader cannot finish the sentence; longer and a "
                "demo stalls in front of a judge."
            )

        patch = step.get("patch", {})
        if not isinstance(patch, dict):
            raise TourError(f"{at}: patch must be an object")
        unknown = sorted(set(patch) - PATCHABLE)
        if unknown:
            raise TourError(
                f"{at}: patch sets {', '.join(unknown)}, which the scene does not "
                f"have. A tour that patches a key the client cannot apply does "
                f"nothing at all, silently, on stage. Known keys: "
                f"{', '.join(sorted(PATCHABLE))}"
            )

        evidence = step.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(e, str) for e in evidence):
            raise TourError(f"{at}: evidence must be a list of strings")

        loose = _backed(narration, patch, evidence)
        if loose:
            raise TourError(
                f"{at}: the narration says {', '.join(loose)} and nothing on this "
                f"step accounts for it. Every number spoken to a judge has to be "
                f"one the tool can show; put the on-screen fact and where it comes "
                f"from in this step's `evidence`, or take the number out of the "
                f"sentence."
            )

    return Tour(
        id=str(raw["id"]),
        title=str(raw["title"]),
        subtitle=str(raw.get("subtitle", "")),
        audience=str(raw.get("audience", "judge")),
        source_id=str(raw.get("source_id", "")),
        steps=list(raw["steps"]),
        path=where,
    )


def load_tours(root: Path) -> tuple[list[Tour], list[dict]]:
    """Every `*.tour.json` under `root`, in filename order, plus the refusals.

    Filename order rather than an index file, so adding a tour is dropping in a
    file. The numeric prefixes are the running order.

    A malformed tour does NOT take the others down: it is refused by name with
    the reason, and the caller serves the rest. One broken file should not cost
    a demo every tour it has.
    """
    tours: list[Tour] = []
    refused: list[dict] = []
    if not root.is_dir():
        return tours, refused

    seen: dict[str, str] = {}
    for path in sorted(root.glob("*.tour.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            refused.append({"file": path.name, "reason": f"unreadable: {exc}"})
            continue
        try:
            tour = validate_tour(raw, where=path.name)
        except TourError as exc:
            refused.append({"file": path.name, "reason": str(exc)})
            continue
        if tour.id in seen:
            # Two tours with one id means a deep link or an agent call would
            # get whichever happened to load second.
            refused.append(
                {"file": path.name, "reason": f"id {tour.id!r} already used by {seen[tour.id]}"}
            )
            continue
        seen[tour.id] = path.name
        tours.append(tour)

    return tours, refused
