"""The tools Samudra Sahayak is allowed to use (TRD M4).

A TOOL IS THE ONLY WAY A NUMBER ENTERS AN ANSWER. That is the hard rule in
CONTRIBUTING.md and it is the whole architecture of this module: every tool returns
a `ToolResult` carrying its `values` and its `citations`, and app/guard.py
refuses to let an answer through that states a figure no tool produced.

Two properties follow from that and both are deliberate.

**The agent has no private data path.** Every tool here calls the same public
HTTP API the browser calls. It cannot read a zarr store, a parquet table or a
CAP file directly, so there is no route by which it could know something the
user cannot check by opening the same endpoint. TRD section 6.5 puts it as
"kill the agent and every P0 still passes"; this is the other half of that,
which is that the agent knows nothing the tool plane does not tell it.

**A tool cannot draw.** `set_scene` returns a validated PATCH, and the browser
applies it through the same store a person's clicks go through. The agent can
request a view it is allowed to express and nothing else, which is the same
channel the guided tours use and is already tested there.

WHAT THIS MODULE IS NOT
-----------------------
It is not a language model, and it does not pretend one is present. There is no
Ollama on this machine and no cloud call is permitted in an air-gapped demo, so
the planner in app/planner.py is a deterministic router over these tools rather
than a model choosing between them. PRD section 10 already answers a judge on
this point: offline mode "uses a local model or disables narration gracefully".
The tool schemas below are the ones an LLM would be handed the day one is
available, and the guard would apply to it unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

#: Where the data plane lives. The agent is a SEPARATE service (TRD section 8)
#: precisely so it can be detached without touching a P0 requirement, so it
#: reaches the API over HTTP like any other client.
API_BASE = os.environ.get("SAGAR_API_BASE", "http://127.0.0.1:8000")

#: A tool call that hangs is worse than one that fails: the demo stalls with no
#: explanation. Short, because every endpoint here reads from local disk.
TIMEOUT = 15.0

#: TRD M4's cap. A planner that can call tools without limit can spend a demo
#: slot thinking, and an LLM in a loop is the usual way that happens.
MAX_TOOL_CALLS = 8


class ToolError(RuntimeError):
    """A tool could not answer. Reported to the user, never swallowed."""


@dataclass
class ToolResult:
    """What a tool returns, and the only place a number may come from.

    `values` is the machine-readable answer. `facts` is the same information as
    short phrases the planner may put in a sentence. `citations` is what the
    data plane said about where it came from, copied rather than composed.
    """

    tool: str
    ok: bool
    #: Structured result, for a caller that wants to act on it.
    values: dict[str, Any] = field(default_factory=dict)
    #: Phrases safe to speak. Every numeral in an answer must appear in one of
    #: these or in `values` (see app/guard.py).
    facts: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    #: A validated scene patch, when the tool asks for the view to change.
    patch: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "values": self.values,
            "facts": self.facts,
            "citations": self.citations,
            "patch": self.patch,
            "error": self.error,
        }


def _get(path: str, **params) -> Any:
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params or None, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise ToolError(f"the data plane at {API_BASE} did not answer: {exc}") from None
    if r.status_code >= 400:
        detail = r.text[:200]
        try:
            detail = r.json().get("detail", detail)
        except ValueError:
            pass
        raise ToolError(f"{path} refused: {detail}")
    return r.json()


def _round(x: float | None, dp: int = 2) -> float | None:
    return None if x is None else round(float(x), dp)


def units_label(units: str, variable: str = "") -> str:
    """What to SAY for a unit the API served.

    The INCOIS analysis declares salinity as CF's dimensionless "1", which is
    correct and unspeakable: an agent that says "35.03 one" has produced a
    sentence nobody can act on. The number is untouched and only the spoken
    label changes, the same translation the web client makes
    (apps/web/lib/api.ts:displayUnits) and for the same reason.
    """
    if units and units != "1":
        return units
    if variable.upper() in {"SAL", "PSAL"} or "salin" in variable.lower():
        return "PSU"
    return ""


def _article(word: str) -> str:
    """"an extreme tsunami", not "a extreme tsunami"."""
    return "an" if word[:1].lower() in "aeiou" else "a"


# --------------------------------------------------------------------------
# The tools
# --------------------------------------------------------------------------


def search_catalog(query: str = "") -> ToolResult:
    """Datasets that are materialized locally, optionally filtered by name."""
    body = _get("/catalog")
    hits = []
    for d in body["datasets"]:
        text = f"{d['id']} {d['title']} {' '.join(v['name'] for v in d['variables'])}".lower()
        if not query or query.lower() in text:
            hits.append(
                {
                    "id": d["id"],
                    "title": d["title"],
                    "variables": [v["name"] for v in d["variables"]],
                    "times": d["times"],
                    "depths": [d["depths"][0], d["depths"][-1]] if d["depths"] else [],
                }
            )
    return ToolResult(
        tool="search_catalog",
        ok=True,
        values={"datasets": hits},
        facts=[
            f"{len(hits)} dataset is available locally" if len(hits) == 1
            else f"{len(hits)} datasets are available locally"
        ]
        + [f"{h['id']} carries {', '.join(h['variables'])}" for h in hits],
        citations=[d["citation"] for d in body["datasets"] if d.get("citation")],
    )


def get_field_summary(
    source_id: str, variable: str, time: str, depth: float | None = None
) -> ToolResult:
    """Min, max and mean of one variable over the demo box, at one depth.

    The statistics are computed HERE, over values the API served, rather than
    asked of a model. That is the point: an agent that says "about 22 degrees at
    a hundred metres" has to have arithmetic behind it that a reader can repeat.
    """
    cat = _get("/catalog")
    entry = next((d for d in cat["datasets"] if d["id"] == source_id), None)
    if entry is None:
        raise ToolError(f"no dataset {source_id!r} is materialized locally")

    bbox = ",".join(str(v) for v in entry["bbox"])
    body = _get(
        f"/field/{source_id}/{variable}",
        bbox=bbox,
        time=time,
        **({"depth": depth} if depth is not None else {"all_depths": "true"}),
    )
    finite = [v for v in body["values"] if v is not None]
    if not finite:
        return ToolResult(
            tool="get_field_summary",
            ok=False,
            error=f"{variable} has no valid cells in this box at {body['time']}",
            citations=[body.get("citation", "")],
        )

    lo, hi = min(finite), max(finite)
    mean = sum(finite) / len(finite)
    at = body.get("depths")
    level = body.get("depth") if at is None else None
    units = body.get("units", "")

    where = f"at {level:g} m" if level is not None else "over the whole column"
    spoken = units_label(units, variable)
    suffix = f" {spoken}" if spoken else ""
    return ToolResult(
        tool="get_field_summary",
        ok=True,
        values={
            "source_id": source_id,
            "variable": variable,
            "time": body["time"],
            "depth": level,
            "units": units,
            "min": _round(lo),
            "max": _round(hi),
            "mean": _round(mean),
            "n_cells": len(finite),
            "n_missing": len(body["values"]) - len(finite),
        },
        facts=[
            f"{variable} {where} on {body['time'][:10]} runs from "
            f"{lo:.2f} to {hi:.2f}{suffix}",
            f"the mean over {len(finite):,} valid cells is {mean:.2f}{suffix}",
            f"{len(body['values']) - len(finite):,} cells have no value and are not counted",
        ],
        citations=[body.get("citation", "")],
    )


def find_profiles(bbox: str | None = None) -> ToolResult:
    """The in-situ instruments on the globe, counted by class."""
    body = _get("/profiles", **({"bbox": bbox} if bbox else {}))
    counts: dict[str, int] = {}
    platforms: set[str] = set()
    for p in body["profiles"]:
        counts[p["platform_kind"]] = counts.get(p["platform_kind"], 0) + 1
        platforms.add(p["wmo"])

    nouns = {
        "gdac_geo": "Argo float",
        "gdac_bgc": "biogeochemical float",
        "mooring": "moored buoy",
        "file": "ship cast or glider",
    }
    said = ", ".join(
        f"{n} from {nouns.get(k, k)}s" for k, n in sorted(counts.items(), key=lambda x: -x[1])
    )
    return ToolResult(
        tool="find_profiles",
        ok=True,
        values={
            "count": body["count"],
            "by_kind": counts,
            "n_platforms": len(platforms),
            "profiles": [
                {"id": p["profile_id"], "wmo": p["wmo"], "kind": p["platform_kind"],
                 "lat": p["lat"], "lon": p["lon"]}
                for p in body["profiles"]
            ],
        },
        facts=[
            f"{body['count']} profiles from {len(platforms)} platforms are in the box",
            f"they are {said}" if said else "no instruments are in the box",
        ],
        citations=[body.get("citation", "")],
    )


def get_profile(profile_id: str) -> ToolResult:
    """One instrument's own measurements, with its QC policy and citation."""
    body = _get(f"/profiles/{profile_id}")
    params = ", ".join(p["label"] for p in body["parameters"])
    return ToolResult(
        tool="get_profile",
        ok=True,
        values={
            "profile_id": body["profile_id"],
            "wmo": body["wmo"],
            "kind": body["platform_kind"],
            "time": body["time"],
            "lat": body["lat"],
            "lon": body["lon"],
            "n_levels": body["n_levels"],
            "parameters": [p["name"] for p in body["parameters"]],
        },
        facts=[
            f"platform {body['wmo']} reported {body['n_levels']} levels on {body['time'][:10]}",
            f"at {body['lat']:.3f} N {body['lon']:.3f} E",
            f"it measures {params}",
            body["qc_policy"],
        ],
        citations=[body.get("citation", "")],
        patch={"selection": body["profile_id"]},
    )


def compare_model_obs(source_id: str, variable: str, observed: str = "temp") -> ToolResult:
    """The Class-4-style verification card (TRD M5).

    The caveat travels with the numbers as a FACT rather than as a footnote, so
    an answer built from this tool cannot quote the RMSE without also being
    able to say what it is and is not.
    """
    body = _get(f"/scorecard/{source_id}/{variable}", observed=observed)
    o = body["overall"]
    worst = max(
        (b for b in body["by_depth"] if b["n"] >= 20 and b["rmse"] is not None),
        key=lambda b: b["rmse"],
        default=None,
    )
    spoken = units_label(body["units"], variable)
    suffix = f" {spoken}" if spoken else ""
    facts = [
        f"across {o['n']:,} matched observation pairs the model runs "
        f"{o['bias']:+.3f}{suffix}",
        f"its RMSE is {o['rmse']:.3f}{suffix}",
        f"the pairs come from {body['n_profiles']} casts on {body['n_platforms']} platforms",
        f"{body['refused']['total']:,} levels could not be paired, each counted by reason",
    ]
    if worst:
        facts.append(
            f"the largest residual is {worst['rmse']:.2f}{suffix} between "
            f"{worst['depth_min']:.0f} and {worst['depth_max']:.0f} m"
        )
    facts.append(body["caveat"])

    return ToolResult(
        tool="compare_model_obs",
        ok=True,
        values={
            "variable": variable,
            "units": body["units"],
            "bias": o["bias"],
            "rmse": o["rmse"],
            "n_pairs": o["n"],
            "n_profiles": body["n_profiles"],
            "worst_band": worst,
            "refused": body["refused"],
            "caveat": body["caveat"],
        },
        facts=facts,
        citations=[body.get("citation", "")] + body.get("observation_citations", []),
    )


def get_warnings(at: str, rehearsal: bool = True, bbox: str | None = None) -> ToolResult:
    """Active CAP warnings at an instant (TRD M8).

    A drill is named as one in the fact itself, in the first clause, not as a
    trailing qualifier. An agent that says "a tsunami warning is in force" and
    only afterwards "this is an exercise" has already caused the wrong reaction.
    """
    body = _get(
        "/warnings", at=at, rehearsal=str(rehearsal).lower(), **({"bbox": bbox} if bbox else {})
    )
    facts = []
    if body["count"] == 0:
        facts.append(f"no warning is valid over this water at {at}")
        if body["refused"]["total"]:
            facts.append(
                f"{body['refused']['total']} alerts on file did not apply at that time"
            )
    for a in body["alerts"]:
        sev = a["severity"].lower()
        lead = (
            f"{_article(sev)} {sev} {a['event'].lower()} warning is in force"
            if a["status"] == "Actual"
            else f"a REHEARSAL bulletin, not a real warning, describes "
            f"{_article(sev)} {sev} {a['event'].lower()}"
        )
        facts.append(f"{lead} for {a['area_desc']}" if a["area_desc"] else lead)

    return ToolResult(
        tool="get_warnings",
        ok=True,
        values={
            "at": body["at"],
            "count": body["count"],
            "exercise_count": body["exercise_count"],
            "alerts": [
                {"id": a["identifier"], "event": a["event"], "severity": a["severity"],
                 "status": a["status"], "urgency": a["urgency"], "area": a["area_desc"]}
                for a in body["alerts"]
            ],
            "refused": body["refused"],
        },
        facts=facts,
        citations=list(body.get("citations", {}).values()),
        patch={"rehearsal": rehearsal},
    )


def list_storyboards() -> ToolResult:
    """The guided tours available (TRD M4's run_storyboard, PRD F12)."""
    body = _get("/storyboards")
    return ToolResult(
        tool="list_storyboards",
        ok=True,
        values={"tours": [{"id": t["id"], "title": t["title"], "seconds": t["seconds"],
                           "n_steps": t["n_steps"]} for t in body["tours"]]},
        facts=[f"{body['count']} guided tours are available"]
        + [f"{t['title']} runs {t['seconds']:.0f} seconds" for t in body["tours"]],
        citations=[],
    )


def set_scene(**patch: Any) -> ToolResult:
    """Ask the browser to move to a view. The ONLY way the agent affects it.

    Validated against the same key list the storyboard loader uses, so the
    agent cannot request a state the client has no way to express, and a key
    the scene does not have is refused here rather than silently dropped in the
    browser. The patch travels to the client, which applies it through the same
    store a person's clicks go through: the agent cannot draw.
    """
    from .scene_keys import PATCHABLE

    unknown = sorted(set(patch) - PATCHABLE)
    if unknown:
        raise ToolError(
            f"the scene has no {', '.join(unknown)}. It has: {', '.join(sorted(PATCHABLE))}"
        )
    return ToolResult(
        tool="set_scene",
        ok=True,
        values={"patch": patch},
        facts=[],
        citations=[],
        patch=dict(patch),
    )


#: The tool schemas, in the shape an LLM would be handed. Kept beside the
#: implementations rather than in a separate file, because a schema that drifts
#: from its function is how a model gets told a tool takes an argument it does
#: not take.
TOOLS: dict[str, dict[str, Any]] = {
    "search_catalog": {
        "fn": search_catalog,
        "description": "List the datasets materialized locally, with their variables and times.",
        "parameters": {"query": {"type": "string", "required": False}},
    },
    "get_field_summary": {
        "fn": get_field_summary,
        "description": "Min, max and mean of a model variable over the demo box at one depth.",
        "parameters": {
            "source_id": {"type": "string", "required": True},
            "variable": {"type": "string", "required": True},
            "time": {"type": "string", "required": True},
            "depth": {"type": "number", "required": False},
        },
    },
    "find_profiles": {
        "fn": find_profiles,
        "description": "Count the in-situ instruments on the globe by class.",
        "parameters": {"bbox": {"type": "string", "required": False}},
    },
    "get_profile": {
        "fn": get_profile,
        "description": "One instrument's measurements, QC policy and citation.",
        "parameters": {"profile_id": {"type": "string", "required": True}},
    },
    "compare_model_obs": {
        "fn": compare_model_obs,
        "description": "Class-4-style bias and RMSE of the model against the in-situ profiles.",
        "parameters": {
            "source_id": {"type": "string", "required": True},
            "variable": {"type": "string", "required": True},
            "observed": {"type": "string", "required": False},
        },
    },
    "get_warnings": {
        "fn": get_warnings,
        "description": "Active CAP warnings at an instant, with drills named as drills.",
        "parameters": {
            "at": {"type": "string", "required": True},
            "rehearsal": {"type": "boolean", "required": False},
            "bbox": {"type": "string", "required": False},
        },
    },
    "list_storyboards": {
        "fn": list_storyboards,
        "description": "The guided tours available to play.",
        "parameters": {},
    },
    "set_scene": {
        "fn": set_scene,
        "description": "Move the 3D view. The only way the agent can affect what is drawn.",
        "parameters": {"patch": {"type": "object", "required": True}},
    },
}


def describe_tools() -> list[dict]:
    """The schemas, without the function objects, for serving over HTTP."""
    return [
        {"name": name, "description": t["description"], "parameters": t["parameters"]}
        for name, t in TOOLS.items()
    ]


def call(name: str, **kwargs: Any) -> ToolResult:
    """Run one tool by name, turning any failure into a reported one."""
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(f"no tool named {name!r}. Available: {', '.join(sorted(TOOLS))}")
    fn: Callable[..., ToolResult] = spec["fn"]
    try:
        return fn(**kwargs)
    except ToolError as exc:
        return ToolResult(tool=name, ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        # A tool that raises something unexpected must still produce a result
        # the planner can report, rather than taking the request down with a
        # stack trace in front of an audience.
        return ToolResult(tool=name, ok=False, error=f"{type(exc).__name__}: {exc}")
