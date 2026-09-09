"""What the agent does with a question, and what it refuses to do (TRD M4).

Every test here runs against a STUBBED data plane rather than a live API. Not
for speed: because the point of these tests is the planner's behaviour, and a
test that also depends on today's cube would start failing for reasons that
have nothing to do with the planner the moment the data is refetched. The real
endpoints are tested in services/api.

The three properties being pinned:

  * a question outside the tool set is refused, by name, with no tool called
  * an answer's numbers all come from tool results, checked by the guard that
    every answer already passes through
  * the tool trace is complete, because TRD M4 asks for a panel where a judge
    can watch it think and a trace that omits a call is worse than none
"""

from __future__ import annotations

import pytest

from app import planner, tools

CATALOG = {
    "datasets": [
        {
            "id": "incois_vam_argo",
            "title": "INCOIS Argo 10-day gridded analysis",
            "citation": "INCOIS ERDDAP, incois_argo_10d_VAM",
            "variables": [{"name": "TEMP"}, {"name": "SAL"}, {"name": "D26"}],
            "times": ["2026-07-10T00:00:00Z", "2026-07-30T00:00:00Z"],
            "depths": [5.0, 2000.0],
            "bbox": [81.0, 6.0, 96.0, 26.0],
        }
    ]
}

FIELD = {
    "time": "2026-07-30T00:00:00Z",
    "units": "degC",
    "citation": "INCOIS ERDDAP, incois_argo_10d_VAM",
    "depth": 100.0,
    "values": [22.0, 23.0, None, 24.0],
}

PROFILES = {
    "count": 2,
    "citation": "Argo GDAC (Ifremer)",
    "profiles": [
        {"profile_id": "2903831_20260708T043743", "wmo": "2903831", "time": "2026-07-08",
         "lat": 18.2, "lon": 90.2, "platform_kind": "gdac_bgc", "n_levels": 100,
         "max_depth": 2000, "source_id": "argo_bgc_indian", "parameters": ["temp"]},
        {"profile_id": "2903831_20260728T141348", "wmo": "2903831", "time": "2026-07-28",
         "lat": 18.0, "lon": 89.8, "platform_kind": "gdac_bgc", "n_levels": 144,
         "max_depth": 2000, "source_id": "argo_bgc_indian", "parameters": ["temp"]},
    ],
}

PROFILE = {
    "profile_id": "2903831_20260728T141348",
    "wmo": "2903831",
    "platform_kind": "gdac_bgc",
    "time": "2026-07-28T14:13:48",
    "lat": 18.093,
    "lon": 89.843,
    "n_levels": 1444,
    "citation": "Argo GDAC (Ifremer), BGC synthetic profiles",
    "qc_policy": "QC flags [1, 2] only (Wong et al. 2020)",
    "parameters": [{"name": "temp", "label": "Temperature", "units": "degC",
                    "canonical": "sea_water_temperature", "n_values": 1444}],
    "levels": {"depth": [], "pres": []},
}

SCORECARD = {
    "units": "degC",
    "citation": "INCOIS ERDDAP, incois_argo_10d_VAM",
    "observation_citations": ["Argo GDAC (Ifremer)"],
    "overall": {"n": 11718, "bias": 0.0262, "rmse": 0.6017, "mae": 0.2378, "std": 0.6012},
    "by_depth": [
        {"depth_min": 50.0, "depth_max": 100.0, "n": 407, "bias": -0.06, "rmse": 2.0745},
        {"depth_min": 1000.0, "depth_max": 2000.0, "n": 5125, "bias": -0.04, "rmse": 0.1179},
    ],
    "n_profiles": 23,
    "n_platforms": 15,
    "refused": {"total": 4672},
    "caveat": "The INCOIS VAM analysis assimilates these same Argo profiles.",
}

WARNINGS = {
    "at": "2026-07-30T00:00:00Z",
    "count": 1,
    "exercise_count": 1,
    "citations": {"cap_incois_ocean": "ITEWC-style rehearsal bulletins"},
    "refused": {"total": 13},
    "alerts": [
        {"identifier": "EX-1", "event": "Tsunami", "severity": "Extreme", "status": "Exercise",
         "urgency": "Immediate", "area_desc": "Andaman Sea"}
    ],
}

TOURS = {
    "count": 2,
    "tours": [
        {"id": "water-column", "title": "Reading a water column", "seconds": 50.0, "n_steps": 6},
        {"id": "hazardwatch", "title": "When there is a warning", "seconds": 75.0, "n_steps": 7},
    ],
}


@pytest.fixture
def api(monkeypatch):
    """Stub the one function every tool reaches the data plane through."""
    calls: list[str] = []

    def fake_get(path: str, **params):
        calls.append(path)
        if path == "/catalog":
            return CATALOG
        if path.startswith("/field/"):
            return FIELD
        if path == "/profiles":
            return PROFILES
        if path.startswith("/profiles/"):
            return PROFILE
        if path.startswith("/scorecard/"):
            return SCORECARD
        if path == "/warnings":
            return WARNINGS
        if path == "/storyboards":
            return TOURS
        raise tools.ToolError(f"unstubbed path {path}")

    monkeypatch.setattr(tools, "_get", fake_get)
    return calls


# --------------------------------------------------------------------------
# Refusal, which TRD M4 names as something judges test
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "who won the cricket",
        "what is the capital of France",
        "write me a poem about the sea",
        "what will the temperature be next Tuesday",
        "",
    ],
)
def test_a_question_outside_the_tools_is_refused_and_calls_nothing(api, question):
    """An ocean viewer asked about the weather in Delhi should say it cannot,
    not produce a sentence shaped like an answer."""
    a = planner.plan(question)

    assert a.refused
    assert a.trace == [], "a refusal must not spend tool calls"
    assert api == [], "and must not touch the data plane"
    # It says what it CAN do, so the refusal is useful rather than a dead end.
    assert "I can tell you" in a.text


def test_a_forecast_question_is_refused_because_nothing_here_forecasts():
    """The analysis on disk is three past dates. An agent that answered a
    question about next week would be inventing the only thing it cannot have."""
    a = planner.plan("what will the temperature be next Tuesday")
    assert a.refused


# --------------------------------------------------------------------------
# The questions it does answer
# --------------------------------------------------------------------------


def test_a_field_question_reads_the_field_and_moves_the_cursor(api):
    a = planner.plan("how warm is it at 100 m?")

    assert not a.refused
    assert [t["tool"] for t in a.trace] == ["search_catalog", "get_field_summary"]
    assert "22.00" in a.text or "22.0" in a.text
    # It also drives the view to the depth it just described, so the answer and
    # the picture agree.
    assert a.patch["focusDepth"] == 100.0
    assert a.patch["variable"] == "TEMP"
    assert any("incois_argo_10d_VAM" in c for c in a.citations)


def test_a_salinity_question_picks_the_salinity_variable(api):
    a = planner.plan("what is the salinity at 500 metres")
    assert a.patch["variable"] == "SAL"
    assert a.patch["focusDepth"] == 500.0


def test_a_skill_question_returns_the_card_AND_its_caveat(api):
    """The caveat is not optional. An answer that quotes the RMSE without it is
    the one wrong thing this feature could say."""
    a = planner.plan("how good is the model?")

    assert "0.602" in a.text
    assert "11,718" in a.text or "11718" in a.text
    assert "assimilates" in a.text, "the caveat must travel with the number"
    assert "2.07" in a.text, "and the depth band where it is worst"


def test_asking_for_a_named_float_opens_its_LATEST_cast(api):
    """A float reports repeatedly, and "show me 2903831" means its most recent
    cast unless a full profile id was given."""
    a = planner.plan("show me float 2903831")

    assert a.patch["selection"] == "2903831_20260728T141348"
    assert "2903831" in a.text
    assert "Wong et al. 2020" in a.text, "the QC policy travels with the profile"


def test_asking_for_a_float_that_is_not_there_says_so(api):
    a = planner.plan("show me float 1111111")
    assert "1111111" in a.text
    assert a.patch.get("selection") is None


def test_an_instrument_question_counts_them_by_class(api):
    a = planner.plan("how many floats are there?")
    assert "2 profiles" in a.text
    assert "biogeochemical" in a.text


def test_a_warning_question_names_a_drill_as_a_drill(api):
    """And in the FIRST clause. A listener who hears "a tsunami warning is in
    force" and only afterwards "this is an exercise" has already reacted."""
    a = planner.plan("are there any warnings?")

    said = a.text.lower()
    assert "rehearsal" in said
    assert said.index("rehearsal") < said.index("tsunami")


def test_an_isotherm_question_draws_the_surface(api):
    a = planner.plan("how deep is the 26 degree isotherm?")
    assert a.patch["isosurfaceOn"] is True
    assert a.patch["isovalue"] == 26


def test_a_tour_question_lists_the_tours(api):
    a = planner.plan("what tours are there")
    assert "Reading a water column" in a.text


# --------------------------------------------------------------------------
# Properties that hold for every answer
# --------------------------------------------------------------------------


ANSWERABLE = [
    "how warm is it at 100 m?",
    "what is the salinity at 500 metres",
    "how good is the model?",
    "show me float 2903831",
    "how many floats are there?",
    "are there any warnings?",
    "how deep is the 26 degree isotherm?",
    "what tours are there",
    "what data have you got",
]


@pytest.mark.parametrize("question", ANSWERABLE)
def test_every_answer_survives_the_no_fabrication_guard(api, question):
    """The planner already runs the guard on the way out, so reaching an answer
    at all proves it. Asserted anyway, because a future refactor that routes
    around `finish` would lose the check silently."""
    from app import guard

    a = planner.plan(question)
    assert not a.refused, a.text

    class R:
        def __init__(self, d):
            self.facts = d["facts"]
            self.values = d["values"]
            self.citations = d["citations"]
            self.patch = d["patch"]

    assert guard.check(a.text, [R(t) for t in a.trace]).ok


@pytest.mark.parametrize("question", ANSWERABLE)
def test_every_answer_stays_inside_the_tool_call_cap(api, question):
    assert len(a_trace := planner.plan(question).trace) <= tools.MAX_TOOL_CALLS, a_trace


@pytest.mark.parametrize("question", ANSWERABLE)
def test_every_answer_says_which_planner_produced_it(api, question):
    """An audience must not be left to assume a language model is in the loop."""
    assert planner.plan(question).as_dict()["planner"].startswith("rules")


@pytest.mark.parametrize("question", ANSWERABLE)
def test_every_answer_that_quotes_data_cites_it(api, question):
    a = planner.plan(question)
    if any(ch.isdigit() for ch in a.text) and a.trace:
        # A tour list is the one answer built from no dataset.
        if a.trace[0]["tool"] != "list_storyboards":
            assert a.citations, f"{question} quotes figures with no citation"


def test_a_patch_may_only_set_keys_the_scene_has():
    from app.scene_keys import PATCHABLE

    r = tools.call("set_scene", focusDepth=100)
    assert r.ok and r.patch == {"focusDepth": 100}

    bad = tools.call("set_scene", cameraTilt=30)
    assert not bad.ok
    assert "cameraTilt" in bad.error
    assert "focusDepth" in bad.error
    assert "cameraTilt" not in PATCHABLE


def test_the_data_plane_being_down_is_reported_not_crashed(monkeypatch):
    """The agent is a separate service and the API can be stopped under it.
    That must read as an explanation, not as a stack trace."""
    def boom(path: str, **params):
        raise tools.ToolError("the data plane at http://127.0.0.1:8000 did not answer")

    monkeypatch.setattr(tools, "_get", boom)
    a = planner.plan("how good is the model?")

    assert "did not answer" in a.text
    assert not any(ch.isdigit() for ch in a.text.replace("127.0.0.1", "").replace("8000", ""))
