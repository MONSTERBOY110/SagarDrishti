"""Guided tours, and the guard that keeps their narration honest (PRD F12).

Narration is the ONE place in this project where a number can reach a judge
without passing through a tool result. Every value on screen is something the
API computed and cited; a sentence in a tour is prose somebody typed. So the
tests below are mostly about the sentences, not the mechanics:

  * every numeral in a narration line must be backed, by the patch that step
    applies or by the evidence the author recorded beside it
  * every shipped tour must pass that guard, so a number going stale after the
    cube is refetched is a failing build rather than a wrong claim on stage
  * a patch may only set scene keys the client can actually apply, because a
    tour that patches a key the client does not have does nothing at all,
    silently, in front of an audience

The last one is the quiet failure this module exists to prevent. A tour is only
useful if it drives the same controls a person drives; a step that no-ops looks
exactly like a step that worked.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app import storyboards

TOURS = pathlib.Path(__file__).resolve().parents[3] / "storyboards"


def step(**over) -> dict:
    base = {
        "narration": "The water is warm at the top and cold at the bottom.",
        "hold": 8,
        "patch": {"variable": "TEMP"},
        "evidence": [],
    }
    base.update(over)
    return base


def tour(**over) -> dict:
    base = {
        "id": "t1",
        "title": "A tour",
        "subtitle": "",
        "audience": "judge",
        "source_id": "incois_vam_argo",
        "steps": [step()],
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------
# The narration guard, which is the reason this module exists
# --------------------------------------------------------------------------


def test_a_number_with_nothing_behind_it_is_refused():
    """The failure this guard exists for: a confident figure nobody can check."""
    bad = tour(
        steps=[step(narration="The model is accurate to within 0.3 degrees.", evidence=[])]
    )
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(bad)

    assert "0.3" in str(e.value)
    # And it says what to do about it, because a guard that only refuses is a
    # guard people route around.
    assert "evidence" in str(e.value)


def test_a_number_the_author_evidenced_is_accepted():
    ok = tour(
        steps=[
            step(
                narration="The model is accurate to within 0.3 degrees.",
                evidence=["RMSE 0.30 degC in the 200 to 500 metre band, on the certificate"],
            )
        ]
    )
    assert storyboards.validate_tour(ok).id == "t1"


def test_a_number_the_step_itself_sets_is_accepted():
    """"Draw the 26 degree surface" needs no separate evidence when the step
    is the thing that sets the isovalue to 26."""
    ok = tour(
        steps=[
            step(
                narration="Draw the surface where the water is exactly 26 degrees.",
                patch={"isosurfaceOn": True, "isovalue": 26},
                evidence=[],
            )
        ]
    )
    assert storyboards.validate_tour(ok)


def test_the_guard_reads_every_numeral_not_just_the_first():
    bad = tour(
        steps=[
            step(
                narration="It runs from 5 to 2000 metres across 24 levels.",
                evidence=["24 levels from 5 metres down"],
            )
        ]
    )
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(bad)
    assert "2000" in str(e.value)


def test_a_sentence_with_no_numbers_needs_no_evidence():
    """Most narration is structural. The guard must not make prose expensive."""
    assert storyboards.validate_tour(
        tour(steps=[step(narration="Watch the colour as the cursor goes down.")])
    )


# --------------------------------------------------------------------------
# A step must actually do something
# --------------------------------------------------------------------------


def test_a_patch_key_the_scene_does_not_have_is_refused_by_name():
    """The silent failure: a step that no-ops looks like a step that worked."""
    bad = tour(steps=[step(patch={"variable": "TEMP", "cameraTilt": 30})])
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(bad)

    assert "cameraTilt" in str(e.value)
    assert "silently" in str(e.value)
    # The refusal lists what IS available, so the author can fix it in one go.
    assert "focusDepth" in str(e.value)


def test_opacity_as_a_percentage_is_refused_because_the_scene_would_show_it():
    """The bug this guard was written for, caught in the act.

    The store holds opacity as a FRACTION and the sheet prints `opacity * 100`,
    so a tour author copying the 72 the slider shows puts "7200%" on the sheet.
    The scene applies a patch verbatim on purpose, so nothing clamps it and
    nothing else on screen looks wrong enough to notice. It reached a recorded
    walkthrough before anybody saw it.
    """
    bad = tour(steps=[step(patch={"opacity": 72})])
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(bad)
    assert "opacity" in str(e.value)
    assert "7200%" in str(e.value), "the refusal should show the author what they would have seen"

    ok = tour(steps=[step(patch={"opacity": 0.72})])
    storyboards.validate_tour(ok)


def test_an_out_of_range_exaggeration_or_depth_is_refused():
    for key, value in (("exaggeration", 20000), ("focusDepth", -5)):
        with pytest.raises(storyboards.TourError) as e:
            storyboards.validate_tour(tour(steps=[step(patch={key: value})]))
        assert key in str(e.value)


def test_a_toggle_patched_with_a_number_is_refused():
    """`isosurfaceOn: 1` would leave the control reading as neither on nor off."""
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(tour(steps=[step(patch={"isosurfaceOn": 1})]))
    assert "isosurfaceOn" in str(e.value)
    storyboards.validate_tour(tour(steps=[step(patch={"isosurfaceOn": True})]))


def test_every_live_scene_key_is_patchable():
    """A tour has to be able to reach every control a presenter would reach.

    Pinned as a list rather than left implicit: when a control is added to the
    scene store and not to PATCHABLE, tours cannot drive it and nothing says so.
    """
    assert "isosurfaceOn" in storyboards.PATCHABLE
    assert "rehearsal" in storyboards.PATCHABLE
    assert "selection" in storyboards.PATCHABLE
    assert "focusDepth" in storyboards.PATCHABLE
    assert "time" in storyboards.PATCHABLE


def test_an_empty_patch_is_allowed_because_a_step_may_be_pure_narration():
    """The last step of a tour is often "and here is why that matters"."""
    assert storyboards.validate_tour(tour(steps=[step(patch={})]))


def test_a_step_with_nothing_to_say_is_refused():
    with pytest.raises(storyboards.TourError):
        storyboards.validate_tour(tour(steps=[step(narration="   ")]))


@pytest.mark.parametrize("hold", [0, 1.5, 45, 300])
def test_a_hold_nobody_can_read_or_sit_through_is_refused(hold):
    with pytest.raises(storyboards.TourError) as e:
        storyboards.validate_tour(tour(steps=[step(hold=hold)]))
    assert "seconds" in str(e.value)


def test_a_missing_hold_is_refused_rather_than_defaulted():
    """Defaulting would put an unreviewed pace in front of an audience."""
    s = step()
    del s["hold"]
    with pytest.raises(storyboards.TourError):
        storyboards.validate_tour(tour(steps=[s]))


def test_a_tour_with_no_steps_is_refused():
    with pytest.raises(storyboards.TourError):
        storyboards.validate_tour(tour(steps=[]))


def test_a_tour_missing_its_identity_is_refused():
    for field in ("id", "title", "steps"):
        raw = tour()
        del raw[field]
        with pytest.raises(storyboards.TourError) as e:
            storyboards.validate_tour(raw)
        assert field in str(e.value)


# --------------------------------------------------------------------------
# Loading a directory of them
# --------------------------------------------------------------------------


def test_one_broken_tour_does_not_cost_the_others(tmp_path):
    """A demo should not lose every tour because one file has a typo."""
    (tmp_path / "01-good.tour.json").write_text(json.dumps(tour(id="good")), encoding="utf-8")
    (tmp_path / "02-broken.tour.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "03-alsogood.tour.json").write_text(
        json.dumps(tour(id="also")), encoding="utf-8"
    )

    tours, refused = storyboards.load_tours(tmp_path)

    assert [t.id for t in tours] == ["good", "also"]
    assert len(refused) == 1
    assert refused[0]["file"] == "02-broken.tour.json"
    assert "unreadable" in refused[0]["reason"]


def test_two_tours_with_one_id_is_refused_rather_than_silently_shadowed(tmp_path):
    """A deep link or an agent call would otherwise get whichever loaded second."""
    (tmp_path / "01-a.tour.json").write_text(json.dumps(tour(id="dup")), encoding="utf-8")
    (tmp_path / "02-b.tour.json").write_text(json.dumps(tour(id="dup")), encoding="utf-8")

    tours, refused = storyboards.load_tours(tmp_path)

    assert len(tours) == 1
    assert "already used by" in refused[0]["reason"]


def test_a_directory_that_is_not_there_is_empty_rather_than_an_error(tmp_path):
    tours, refused = storyboards.load_tours(tmp_path / "nope")
    assert tours == [] and refused == []


def test_tours_load_in_filename_order(tmp_path):
    """The numeric prefixes are the running order, so adding a tour is dropping
    in a file rather than editing an index."""
    for name, tid in [("03-c", "c"), ("01-a", "a"), ("02-b", "b")]:
        (tmp_path / f"{name}.tour.json").write_text(json.dumps(tour(id=tid)), encoding="utf-8")
    tours, _ = storyboards.load_tours(tmp_path)
    assert [t.id for t in tours] == ["a", "b", "c"]


# --------------------------------------------------------------------------
# The tours actually shipped
# --------------------------------------------------------------------------


def test_every_shipped_tour_passes_the_guard():
    """The test that will fail when a figure goes stale after a refetch.

    A tour saying "eleven thousand pairs" after the cube is rebuilt is wrong in
    front of a judge, and the evidence line beside each number is what makes
    that findable rather than mysterious.
    """
    tours, refused = storyboards.load_tours(TOURS)
    assert refused == [], f"shipped tours must all be valid: {refused}"
    assert len(tours) >= 4, "the four demo tours are part of the deliverable"


def test_the_shipped_tours_cover_the_features_they_are_meant_to():
    tours, _ = storyboards.load_tours(TOURS)
    ids = {t.id for t in tours}
    assert {"water-column", "cyclone-fuel", "instruments-and-skill", "hazardwatch"} <= ids


def test_the_submission_tour_drives_every_p0_claim_in_one_run():
    """`the-whole-story` is what the portal demo video is recorded from.

    A video is recorded once and then submitted, so the run behind it has to be
    reproducible rather than performed: this tour exists so that recording is a
    replay, not a live demo that can wander. That makes it a deliverable, and a
    deliverable gets a test.

    What is pinned is COVERAGE, not wording. If a future edit drops the
    isosurface step or stops selecting a float, the video would silently stop
    demonstrating a requirement the PS names, and the only place that would
    show up is in front of a reviewer.
    """
    tours, _ = storyboards.load_tours(TOURS)
    tour = next((t for t in tours if t.id == "the-whole-story"), None)
    assert tour is not None, "the submission walkthrough is part of the deliverable"

    patched: dict[str, set] = {}
    for step in tour.steps:
        for key, value in step.get("patch", {}).items():
            patched.setdefault(key, set()).add(
                value if isinstance(value, (str, int, float, bool, type(None))) else str(value)
            )

    # F1: all three named techniques, and the depth axis actually travelled
    assert True in patched.get("isosurfaceOn", set()), "no isosurface step"
    assert True in patched.get("currentsOn", set()), "no current-vector step"
    assert len(patched.get("focusDepth", set())) >= 3, "the depth cursor barely moves"
    # F2 and F9: an instrument is opened, which is what puts the skill card in view
    assert any(isinstance(v, str) for v in patched.get("selection", set())), \
        "no instrument is ever opened"
    # F2: the GLIDER is opened, not just the floats. The PS names four
    # instrument classes and the glider is the one this project nearly reported
    # as unobtainable; a tour that quietly stops opening it would take the
    # strongest answer to "where are the gliders" out of the submission video
    # without anyone noticing until a reviewer asked.
    glider_dives = [v for v in patched.get("selection", set())
                    if isinstance(v, str) and v.startswith("2801900_")]
    assert glider_dives, "the submission video never opens the glider"
    # F6: the plugin-derived field is shown, not just described
    assert "SIG0" in patched.get("variable", set()), "the derived density field is never shown"
    # F13: the drill layer is REVEALED rather than being on from the start
    rehearsal = [s.get("patch", {}).get("rehearsal") for s in tour.steps
                 if "rehearsal" in s.get("patch", {})]
    assert rehearsal[0] is False and True in rehearsal[1:], (
        "the hazard layer must appear on cue: starting with it already on wastes "
        "the one moment the Disaster Management theme is named out loud"
    )


def test_the_submission_tour_fits_a_portal_video():
    """Long enough to say it, short enough that nobody stops watching."""
    tours, _ = storyboards.load_tours(TOURS)
    tour = next(t for t in tours if t.id == "the-whole-story")
    seconds = sum(float(s["hold"]) for s in tour.steps)
    assert 90 <= seconds <= 200, f"{seconds:.0f}s is outside the usable range for a submission video"


def test_no_shipped_tour_outstays_a_demo_slot():
    """Five minutes is the shortest slot the SPOC might give us, and a tour
    that cannot finish inside one is a tour nobody will run."""
    tours, _ = storyboards.load_tours(TOURS)
    for t in tours:
        assert t.seconds <= 150, f"{t.id} runs {t.seconds}s"


def test_every_shipped_tour_names_a_real_dataset():
    from app.registry import load_registry

    reg = load_registry()
    tours, _ = storyboards.load_tours(TOURS)
    for t in tours:
        assert reg.has(t.source_id), f"{t.id} cites unknown source {t.source_id!r}"


def test_a_tour_that_selects_a_station_selects_one_that_exists():
    """A tour is only convincing if the float it opens is really there.

    Skips when the cube is absent, in the same way the other real-data
    assertions do, rather than passing vacuously.
    """
    from app import store

    frame = store.load_profiles()
    if frame.empty:
        pytest.skip("no local profiles; run tools/fetch_sample.py then tools/preprocess.py")

    known = set(frame["profile_id"].unique())
    tours, _ = storyboards.load_tours(TOURS)
    for t in tours:
        for i, s in enumerate(t.steps, start=1):
            picked = s.get("patch", {}).get("selection")
            if picked:
                assert picked in known, f"{t.id} step {i} selects a profile that is not served"
