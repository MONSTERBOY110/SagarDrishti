"""Samudra Sahayak's planner: what to do about a question (TRD M4).

THIS IS A DETERMINISTIC ROUTER, NOT A LANGUAGE MODEL, AND IT SAYS SO
--------------------------------------------------------------------
Every answer this module produces carries `planner: "rules"`, and the UI prints
it. That is not modesty, it is the same discipline as everything else here: a
demo that lets an audience believe a language model is reasoning when a regular
expression is matching has misled them, and a judge who works this out
unprompted has found us out rather than been told.

The reason it is rules today is concrete rather than philosophical. PRD F11
promises an air-gapped demo, so a cloud model is not available on stage; there
is no Ollama on the build machine; and a small local model doing reliable
tool-calling is a week of work with a real chance of failing in front of an
audience. The ROADMAP's own Phase 2 line asks for exactly this, a "first agent
trick (scripted)".

What matters is that the SHAPE is the real one. The tools in app/tools.py are
the tools a model would be handed, with the schemas it would be handed. The
guard in app/guard.py is applied to the finished answer regardless of what
produced it. The tool trace is recorded the same way. When a model lands it
replaces `plan()` and nothing else: the day the agent can hallucinate is the
day the guard that stops it has already been running for weeks.

WHAT IT REFUSES
---------------
A question outside the tool set gets a refusal that lists what the tool set
CAN do, and calls no tools at all. TRD M4 names this as something judges test,
and it is also the honest behaviour: an ocean viewer asked about the weather in
Delhi should say it cannot, not produce a sentence shaped like an answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import guard, tools

#: The dataset the demo is built on. Named here rather than discovered per
#: question so a slow catalog call cannot delay every answer; `search_catalog`
#: is still a tool, for when a question is actually about what exists.
DEFAULT_SOURCE = "incois_vam_argo"


def _sentence(clause: str) -> str:
    """One clause as a sentence. Never alters a digit.

    A trailing comma or semicolon is a clause that was written to be continued,
    and appending a full stop to it produced ",." on screen. Stripped rather
    than special-cased at the call site, so the next author who writes a
    lead-in with a comma does not meet the same thing.
    """
    s = clause.strip().rstrip(",;")
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    return s if s[-1] in ".!?:" else s + "."


@dataclass
class Answer:
    """What the agent says, and everything needed to check it."""

    question: str
    text: str
    #: Every tool call made, in order. TRD M4: the trace streams to the UI so
    #: judges can watch it think, and so a wrong answer is diagnosable rather
    #: than mysterious.
    trace: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    #: A scene patch for the browser to apply, if the answer moved the view.
    patch: dict[str, Any] = field(default_factory=dict)
    #: "rules" today. The UI prints it, because an audience must not be left to
    #: assume a language model is in the loop when one is not.
    planner: str = "rules"
    refused: bool = False

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.text,
            "trace": self.trace,
            "citations": [c for c in dict.fromkeys(self.citations) if c],
            "patch": self.patch,
            "planner": self.planner,
            "refused": self.refused,
            "n_tool_calls": len(self.trace),
        }


CAPABILITIES = [
    "how warm or salty the water is, at a depth you name",
    "how deep the 26 degree isotherm is, and draw it",
    "how far the model is from the floats, with its caveat",
    "what instruments are in the water, and open one",
    "what warnings are in force, and when",
    "which guided tours exist, and play one",
]


def _refusal(question: str) -> Answer:
    return Answer(
        question=question,
        text=(
            "I cannot answer that from the data this tool holds. I can tell you: "
            + "; ".join(CAPABILITIES)
            + ". Everything I say comes from a tool call against the local "
            "datasets, which is why the list is short."
        ),
        refused=True,
    )


#: A question about the FUTURE. Checked before every topical route, because
#: "what will the temperature be next Tuesday" matches the temperature route
#: perfectly and would have been answered from a July 2026 analysis of the
#: past. That is the worst answer this agent could give: confident, cited,
#: precise, and about the wrong thing entirely. Found by a test.
_FORECAST = re.compile(
    r"\b(tomorrow|forecast|predict|prediction|will\s+(it|the|there)\b|"
    r"next\s+(week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"going to be|in future|in the future)\b",
    re.I,
)

#: Depth in a question: "at 100 m", "100 metres down", "at 1000m".
_DEPTH = re.compile(r"(\d+(?:\.\d+)?)\s*(?:m\b|metre|meter)", re.I)
#: A profile id or a bare WMO number.
_PLATFORM = re.compile(r"\b(\d{7}(?:_\d{8}T\d{6})?)\b")


def _latest_time() -> tuple[str, tools.ToolResult]:
    """The newest analysis step, from the catalog rather than from a constant."""
    r = tools.call("search_catalog")
    times = r.values.get("datasets", [{}])[0].get("times", []) if r.ok else []
    return (times[-1] if times else ""), r


def plan(question: str) -> Answer:
    """Route one question to tools, then answer only from what they returned."""
    q = (question or "").strip()
    if not q:
        return _refusal(question)
    low = q.lower()

    trace: list[tools.ToolResult] = []

    def run(name: str, **kw) -> tools.ToolResult:
        if len(trace) >= tools.MAX_TOOL_CALLS:
            raise tools.ToolError(f"tool-call cap of {tools.MAX_TOOL_CALLS} reached")
        r = tools.call(name, **kw)
        trace.append(r)
        return r

    def finish(sentences: list[str], patch: dict | None = None) -> Answer:
        # Tools emit facts as clauses, because a clause composes and a finished
        # sentence does not. Punctuating here rather than in each tool is what
        # keeps "runs from 17.98 to 25.45 degC the mean over 208 valid cells is
        # 22.45" from reaching a reader as one breathless line, which is how it
        # first came out. Capitalisation and full stops only: nothing here may
        # touch a digit, or the guard below would be checking different text
        # from the text a user sees.
        text = " ".join(_sentence(s) for s in sentences if s and s.strip())
        # THE LAST THING EVERY ANSWER PASSES THROUGH.
        guard.enforce(text, trace, q)
        merged: dict[str, Any] = {}
        for r in trace:
            merged.update(r.patch)
        if patch:
            merged.update(patch)
        return Answer(
            question=q,
            text=text,
            trace=[r.as_dict() for r in trace],
            citations=[c for r in trace for c in r.citations],
            patch=merged,
        )

    try:
        # --- the future, which nothing here holds ----------------------------
        if _FORECAST.search(low):
            return Answer(
                question=q,
                text=(
                    "I cannot answer that: nothing here forecasts. The datasets on "
                    "this machine are past analysis steps and past instrument casts, "
                    "so any answer I gave about the future would be a statement about "
                    "history with the wrong date on it. I can tell you: "
                    + "; ".join(CAPABILITIES)
                    + "."
                ),
                refused=True,
            )

        # --- warnings -------------------------------------------------------
        if re.search(r"warn|hazard|alert|cyclone warning|tsunami", low):
            when, cat = _latest_time()
            trace.append(cat)
            if not when:
                return _refusal(q)
            r = run("get_warnings", at=when, rehearsal=True)
            if not r.ok:
                return finish([f"I could not read the warning layer: {r.error}"])
            head = (
                "Nothing is in force over this water at the step on screen."
                if r.values["count"] == 0
                else f"There are {r.values['count']} in force at the step on screen."
            )
            tail = (
                "Every one of them is a rehearsal bulletin: India's live national feed "
                "carried no ocean warning when this was ingested, and INCOIS publishes "
                "no public machine feed for its own."
                if r.values["exercise_count"] == r.values["count"] and r.values["count"]
                else ""
            )
            return finish([head] + r.facts + [tail])

        # --- model skill ----------------------------------------------------
        if re.search(r"\brmse\b|skill|how (good|accurate|wrong)|bias|verif|trust", low):
            variable = "SAL" if "salin" in low else "TEMP"
            observed = "psal" if variable == "SAL" else "temp"
            r = run(
                "compare_model_obs",
                source_id=DEFAULT_SOURCE,
                variable=variable,
                observed=observed,
            )
            if not r.ok:
                return finish([f"I could not read the verification card: {r.error}"])
            return finish(
                ["Here is how far the model sits from the instruments themselves"] + r.facts
            )

        # --- one named instrument -------------------------------------------
        hit = _PLATFORM.search(q)
        if hit and re.search(r"float|platform|profile|buoy|show|open|instrument", low):
            wanted = hit.group(1)
            listed = run("find_profiles")
            if not listed.ok:
                return finish([f"I could not list the instruments: {listed.error}"])
            # The newest profile for that platform, not whichever the list
            # happened to yield first: a float reports repeatedly and "show me
            # 2903831" means its latest cast unless a full profile id was given.
            candidates = [
                p for p in listed.values["profiles"]
                if p["id"] == wanted or p["wmo"] == wanted
            ]
            match = max(candidates, key=lambda p: p["id"], default=None)
            if match is None:
                return finish(
                    [f"No platform {wanted} is in the box."] + listed.facts[:1]
                )
            r = run("get_profile", profile_id=match["id"])
            if not r.ok:
                return finish([f"I could not open that profile: {r.error}"])
            return finish(["Opened on the globe."] + r.facts)

        # --- the instruments in general --------------------------------------
        if re.search(r"float|instrument|profile|buoy|argo|how many", low):
            r = run("find_profiles")
            if not r.ok:
                return finish([f"I could not list the instruments: {r.error}"])
            return finish(r.facts)

        # --- the 26 degree isotherm ------------------------------------------
        if re.search(r"isotherm|26\s*deg|isosurface|cyclone (fuel|heat)|d26", low):
            when, cat = _latest_time()
            trace.append(cat)
            if not when:
                return _refusal(q)
            r = run(
                "get_field_summary", source_id=DEFAULT_SOURCE, variable="D26", time=when
            )
            if not r.ok:
                return finish([f"I could not read the isotherm depth: {r.error}"])
            return finish(
                ["The depth of the 26 degree isotherm, which is the heat a cyclone can use:"]
                + r.facts
                + ["I have drawn the surface on the globe."],
                patch={"isosurfaceOn": True, "isovalue": 26, "variable": "TEMP"},
            )

        # --- a field value at a depth -----------------------------------------
        if re.search(
            r"temperat|warm|cold|salin|salt|degree|how (hot|deep)|dens|sigma|stratif",
            low,
        ):
            when, cat = _latest_time()
            trace.append(cat)
            if not when:
                return _refusal(q)
            # Density BEFORE salinity, because "how dense is the water" and
            # "how salty is the water" are different questions and density is
            # computed FROM salinity: a salinity-first test would answer the
            # denser question with the saltier one. SIG0 is a derived product
            # (a plugin), so this route also proves the agent reaches anything
            # the registry advertises rather than a list hardcoded here.
            if re.search(r"dens|sigma|stratif|isopycnal", low):
                variable = "SIG0"
            elif re.search(r"salin|salt", low):
                variable = "SAL"
            else:
                variable = "TEMP"
            depth_hit = _DEPTH.search(q)
            depth = float(depth_hit.group(1)) if depth_hit else None
            r = run(
                "get_field_summary",
                source_id=DEFAULT_SOURCE,
                variable=variable,
                time=when,
                **({"depth": depth} if depth is not None else {}),
            )
            if not r.ok:
                return finish([f"I could not read that field: {r.error}"])
            patch: dict[str, Any] = {"variable": variable}
            if depth is not None:
                patch["focusDepth"] = depth
            return finish(r.facts, patch=patch)

        # --- the tours ---------------------------------------------------------
        if re.search(r"tour|storyboard|walk me|explain|show me around|demo", low):
            r = run("list_storyboards")
            if not r.ok:
                return finish([f"I could not list the tours: {r.error}"])
            return finish(
                r.facts + ["Pick one from the tours control at the foot of the scene."]
            )

        # --- what have you got -------------------------------------------------
        if re.search(r"catalog|dataset|what data|what have you|source", low):
            r = run("search_catalog")
            if not r.ok:
                return finish([f"I could not read the catalog: {r.error}"])
            return finish(r.facts)

        return _refusal(q)

    except tools.ToolError as exc:
        return Answer(
            question=q,
            text=f"I could not complete that: {exc}",
            trace=[r.as_dict() for r in trace],
            refused=True,
        )
    except guard.Fabrication as exc:
        # The guard firing is a BUG in this module, not a user-facing outcome,
        # so it is reported as one rather than dressed up as an answer. If this
        # ever reaches a user, a sentence was built from something no tool said.
        return Answer(
            question=q,
            text=(
                "I withheld that answer: it contained a figure no tool produced, "
                "which this agent is not allowed to say. Please report it."
            ),
            trace=[r.as_dict() for r in trace],
            refused=True,
            planner="rules (answer withheld by the no-fabrication guard: " f"{exc})",
        )
