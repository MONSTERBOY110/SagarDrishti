"""The no-fabrication guard (CLAUDE.md's hardest rule, made mechanical).

"The agent never computes or invents numbers. Numbers enter answers only via
tool results." Everything here tests that one sentence.

It is worth testing hard NOW, while the planner is deterministic and could in
principle be trusted, because the whole point of writing it early is that the
day a language model is plugged in behind the same interface, the guard is
already the last thing every answer passes through and has been for weeks. A
guardrail added after the model is a guardrail added after the first
hallucination.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app import guard


@dataclass
class FakeResult:
    """Duck-typed ToolResult, so the guard can be tested without the tool layer."""

    facts: list[str] = field(default_factory=list)
    values: dict = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    patch: dict = field(default_factory=dict)


def test_a_figure_no_tool_produced_is_refused():
    """The failure this module exists for."""
    tool = FakeResult(facts=["its RMSE is 0.602 degC"], values={"rmse": 0.602})

    with pytest.raises(guard.Fabrication) as e:
        guard.enforce("The model is accurate to within 0.25 degrees.", [tool])

    assert "0.25" in str(e.value)
    assert "CLAUDE.md" in str(e.value)


def test_a_figure_a_tool_did_produce_is_allowed():
    tool = FakeResult(facts=["its RMSE is 0.602 degC"], values={"rmse": 0.602})
    assert guard.enforce("Its RMSE is 0.602 degC.", [tool])


def test_a_number_from_the_structured_values_counts_even_if_no_fact_said_it():
    """A planner may compose its own sentence around a value the tool returned,
    and should not have to have the tool phrase it first."""
    tool = FakeResult(values={"n_pairs": 11718, "n_profiles": 23})
    assert guard.enforce("There were 11718 pairs from 23 casts.", [tool])


def test_thousands_separators_do_not_make_a_real_number_look_invented():
    """A tool returns 11718 and a readable answer says 11,718. Same claim."""
    tool = FakeResult(values={"n_pairs": 11718})
    assert guard.enforce("Across 11,718 matched pairs.", [tool])


def test_a_rounded_float_is_still_backed_by_its_source():
    """0.6017 in the tool, 0.602 in the sentence. Refusing that would force
    every answer to print full precision, which nobody would read."""
    tool = FakeResult(values={"rmse": 0.6017})
    assert guard.enforce("Its RMSE is 0.602.", [tool])
    assert guard.enforce("Its RMSE is 0.6.", [tool])


def test_a_sign_does_not_change_whether_a_number_is_backed():
    """+0.026 and 0.026 are the same claim about the data."""
    tool = FakeResult(values={"bias": 0.026})
    assert guard.enforce("The bias is +0.026 degC.", [tool])


def test_a_number_inside_a_nested_value_is_found():
    """Tool results are nested; the guard has to look all the way down."""
    tool = FakeResult(
        values={"worst_band": {"depth_min": 50.0, "depth_max": 100.0, "rmse": 2.0745}}
    )
    assert guard.enforce("The worst band is 50 to 100 m, at 2.07.", [tool])


def test_a_number_in_a_citation_is_allowed_because_an_answer_may_name_its_source():
    tool = FakeResult(citations=["INCOIS ERDDAP, incois_argo_10d_VAM (10-day gridded)"])
    assert guard.enforce("From the incois_argo_10d_VAM 10-day analysis.", [tool])


def test_a_number_in_a_scene_patch_is_allowed():
    """"I have set the depth to 100 metres" is a report of what the agent did."""
    tool = FakeResult(patch={"focusDepth": 100})
    assert guard.enforce("I moved the cursor to 100 m.", [tool])


def test_an_answer_with_no_numbers_always_passes():
    """A refusal, or a purely structural sentence, needs no tool at all."""
    assert guard.enforce("I cannot answer that from the data this tool holds.", [])


def test_every_unbacked_figure_is_named_not_just_the_first():
    """An author fixing this should see the whole problem in one go."""
    tool = FakeResult(values={"rmse": 0.602})
    verdict = guard.check("It is 0.25 off across 900 pairs from 12 floats.", [tool])

    assert not verdict.ok
    assert verdict.unbacked == ["0.25", "12", "900"]


def test_the_guard_raises_rather_than_quietly_correcting():
    """A silently scrubbed answer is an answer nobody knows was wrong, and this
    is the one failure in the project that must never be hidden."""
    with pytest.raises(guard.Fabrication):
        guard.enforce("The temperature is 28 degrees.", [FakeResult()])


def test_no_tool_results_at_all_backs_no_number():
    with pytest.raises(guard.Fabrication):
        guard.enforce("There are 25 floats.", [])
