"""The no-fabrication guard: an answer may not state a number no tool produced.

CONTRIBUTING.md's hard rule is that the agent never computes or invents numbers, and
that numbers enter answers only via tool results with dataset, timestamp and
float WMO id citations. This module is that rule made mechanical, because a
rule enforced by good intentions is a rule that survives until the demo.

WHY IT IS A SEPARATE MODULE AND NOT A PROMPT
--------------------------------------------
Today the planner is deterministic, so it could in principle be trusted not to
invent a figure. That is exactly why the guard is worth writing NOW: the day a
language model is plugged in behind the same interface, the guard is already
there, already tested, and already the last thing an answer passes through. A
guardrail added after the model is a guardrail added after the first
hallucination.

WHAT IT CHECKS
--------------
Every numeral in the answer text must appear in a tool result: in a `fact` the
tool produced, or in one of its `values`. Not "a plausible number", not "close
to one of them" -- the same digits.

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
Whether the number is the RIGHT one for the question. A guard cannot know that
"the RMSE is 0.602" was the answer to a question about bias. What it can
guarantee is that 0.602 came out of the data plane rather than out of a model,
which is the difference between an answer that is wrong and an answer that is
made up. The first is a bug; the second is the thing a judge will never forgive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Digit runs, with decimals and thousands separators. Sign is excluded on
#: purpose: "+0.026" and "0.026" are the same claim about the data.
_NUMERAL = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Fabrication(AssertionError):
    """An answer stated a figure no tool produced. Never shown to a user."""


def _digits(text: str) -> set[str]:
    """Every numeral in a string, normalised so 11,718 matches 11718."""
    return {m.group(0).replace(",", "") for m in _NUMERAL.finditer(text)}


def _flatten(value) -> str:
    """Everything a tool result carries, as one searchable string."""
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    if isinstance(value, float):
        # A float reaches the answer text rounded, so the source has to be
        # searchable at several precisions or every rounded figure would look
        # fabricated. Two through four decimals covers what the tools print.
        return " ".join([repr(value)] + [f"{value:.{n}f}" for n in (0, 1, 2, 3, 4)])
    return str(value)


@dataclass
class Verdict:
    ok: bool
    unbacked: list[str]

    def __bool__(self) -> bool:
        return self.ok


def check(answer: str, results: list, question: str = "") -> Verdict:
    """Is every numeral in `answer` backed by a tool result or by the question?

    `results` is a list of ToolResult (duck-typed: anything with `facts` and
    `values`), so this module has no import back into the tool layer and can be
    tested on plain objects.

    THE QUESTION COUNTS AS GROUNDING, and that took a failing test to notice.
    Asked "show me float 1111111" when no such float exists, the honest answer
    is "no platform 1111111 is in the box", and the first version of this guard
    refused to let that through: 1111111 appears in no tool result, so it read
    as invented. It was not invented, it was QUOTED. A number the user supplied
    and the agent repeats back is the opposite of a fabrication, and a guard
    that blocks it teaches the planner to drop the one detail that makes the
    refusal useful.
    """
    grounded: set[str] = _digits(question)
    for r in results:
        grounded |= _digits(" ".join(getattr(r, "facts", []) or []))
        grounded |= _digits(_flatten(getattr(r, "values", {}) or {}))
        grounded |= _digits(_flatten(getattr(r, "patch", {}) or {}))
        # Citations carry dataset years and version numbers, which an answer is
        # allowed to repeat when it names its source.
        grounded |= _digits(" ".join(getattr(r, "citations", []) or []))
        # A tool that FAILED still said something, and an answer is allowed to
        # repeat it. "the data plane at 127.0.0.1:8000 did not answer" is a
        # report of a failure, not a claim about the ocean.
        grounded |= _digits(str(getattr(r, "error", "") or ""))

    unbacked = sorted(d for d in _digits(answer) if d not in grounded)
    return Verdict(ok=not unbacked, unbacked=unbacked)


def enforce(answer: str, results: list, question: str = "") -> str:
    """Return the answer, or raise. The last thing every answer passes through.

    Raising rather than scrubbing is deliberate. A silently corrected answer is
    an answer nobody knows was wrong, and the failure it hides is the one that
    matters most in this project.
    """
    verdict = check(answer, results, question)
    if not verdict.ok:
        raise Fabrication(
            "the answer states "
            + ", ".join(verdict.unbacked)
            + " and no tool result contains those figures. Numbers may only "
            "enter an answer through a tool (CONTRIBUTING.md)."
        )
    return answer
