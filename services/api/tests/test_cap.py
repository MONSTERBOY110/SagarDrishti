"""CAP v1.2 warning parsing, and above all what it refuses to call active.

This is the disaster-management half of the problem statement (PRD F13, TRD M8)
and it is the one module in the project where a bug is not an embarrassment but
a FALSE ALARM. Every other surface here can be wrong and merely misinform. A
warning layer that draws a cancelled tsunami alert, or that draws a drill as
though it were real, is the failure mode that would end a demo and deserve to.

So the tests below are weighted accordingly. Most of them assert that something
is NOT shown:

  * a `Cancel` message removes the alert it references
  * an `Update` supersedes the alert it references
  * `status: Exercise`, `Test`, `Draft` and `System` never pass as live
  * an expired alert is not active, evaluated in its own timezone
  * an alert that has not reached its effective time is not active yet

and two of them assert the coordinate convention, which is the single most
likely silent error in the whole feature: **CAP writes latitude first and
GeoJSON writes longitude first**, so a parser that forgets lands a warning for
the Bay of Bengal somewhere in Somalia and still draws a perfectly convincing
polygon.

The two golden files under tests/fixtures/ are REAL government CAP retrieved
from NDMA SACHET, India's national CAP backbone, on 2026-09-09. See the
PROVENANCE.md beside them.
"""

from __future__ import annotations

import pathlib

import pytest

from app import cap

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

NOW = cap.parse_time("2026-09-09T17:00:00+05:30")


def alert_xml(
    *,
    identifier: str = "IN-TEST-1",
    sender: str = "INCOIS-ITEWC",
    sent: str = "2026-09-09T16:00:00+05:30",
    status: str = "Actual",
    msg_type: str = "Alert",
    references: str = "",
    event: str = "High Wave",
    severity: str = "Severe",
    urgency: str = "Expected",
    certainty: str = "Likely",
    effective: str = "2026-09-09T16:00:00+05:30",
    expires: str = "2026-09-09T22:00:00+05:30",
    area: str = "<cap:polygon>15.0,80.0 15.0,82.0 13.0,82.0 13.0,80.0 15.0,80.0</cap:polygon>",
    extra_info: str = "",
) -> bytes:
    """A CAP 1.2 alert in the real namespace, with one knob per test."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>{identifier}</cap:identifier>
  <cap:sender>{sender}</cap:sender>
  <cap:sent>{sent}</cap:sent>
  <cap:status>{status}</cap:status>
  <cap:msgType>{msg_type}</cap:msgType>
  <cap:scope>Public</cap:scope>
  <cap:references>{references}</cap:references>
  <cap:info>
    <cap:language>en-IN</cap:language>
    <cap:category>Met</cap:category>
    <cap:event>{event}</cap:event>
    <cap:urgency>{urgency}</cap:urgency>
    <cap:severity>{severity}</cap:severity>
    <cap:certainty>{certainty}</cap:certainty>
    <cap:effective>{effective}</cap:effective>
    <cap:expires>{expires}</cap:expires>
    <cap:headline>{event} warning</cap:headline>
    <cap:instruction>Do not venture into the sea.</cap:instruction>
    <cap:area>
      <cap:areaDesc>Off the Andhra Pradesh coast</cap:areaDesc>
      {area}
    </cap:area>
  </cap:info>{extra_info}
</cap:alert>
""".encode()


# --------------------------------------------------------------------------
# The coordinate convention, which is where a warning silently lands in the
# wrong ocean
# --------------------------------------------------------------------------


def test_cap_writes_latitude_first_and_we_store_longitude_first():
    """CAP is lat,lon. GeoJSON, Cesium and every renderer here are lon,lat.

    "15.0,80.0" is 15 N 80 E, in the Bay of Bengal. Read the other way round it
    is 80 N 15 E, in the Arctic Ocean north of Norway, and it would still draw
    a perfectly convincing polygon.
    """
    alert = cap.parse_alert(alert_xml())
    ring = alert.infos[0].areas[0].polygons[0]

    assert ring[0] == (80.0, 15.0), "stored lon first"
    assert all(80.0 <= lon <= 82.0 for lon, _ in ring)
    assert all(13.0 <= lat <= 15.0 for _, lat in ring)


def test_a_coordinate_outside_the_earth_is_refused_rather_than_drawn():
    """A transposed or corrupt pair usually shows up as an impossible latitude."""
    bad = "<cap:polygon>95.0,80.0 15.0,82.0 13.0,82.0 95.0,80.0</cap:polygon>"
    alert = cap.parse_alert(alert_xml(area=bad))

    assert alert.infos[0].areas[0].polygons == []
    assert "latitude" in " ".join(alert.notes).lower()


def test_a_ring_that_does_not_close_is_closed_and_the_fact_is_recorded():
    """CAP requires a closed ring. Dropping a live warning over a missing
    repeated coordinate would be absurd, so it is closed and SAID."""
    unclosed = "<cap:polygon>15.0,80.0 15.0,82.0 13.0,82.0</cap:polygon>"
    alert = cap.parse_alert(alert_xml(area=unclosed))
    ring = alert.infos[0].areas[0].polygons[0]

    assert ring[0] == ring[-1]
    assert len(ring) == 4
    assert any("closed" in n.lower() for n in alert.notes)


def test_a_ring_with_too_few_points_is_not_an_area():
    """Two points is a line. Closing it would produce a zero-area polygon that
    renders as nothing and counts as a warning, which is the worst of both."""
    alert = cap.parse_alert(alert_xml(area="<cap:polygon>15.0,80.0 13.0,82.0</cap:polygon>"))
    assert alert.infos[0].areas[0].polygons == []


def test_a_circle_is_kept_as_a_circle_with_its_radius_in_kilometres():
    """Tsunami alerts are often circular. CAP's radius is km, not metres or
    degrees, and treating it as either would size the hazard wrongly by orders
    of magnitude."""
    alert = cap.parse_alert(alert_xml(area="<cap:circle>13.5,80.5 150.0</cap:circle>"))
    circles = alert.infos[0].areas[0].circles

    assert circles == [(80.5, 13.5, 150.0)]
    assert alert.infos[0].areas[0].polygons == []


def test_an_area_named_but_not_drawn_is_reported_rather_than_dropped():
    """A geocoded area is a real warning that this tool cannot place on a
    globe. Silently discarding it would under-report the hazard."""
    geo = (
        "<cap:geocode><cap:valueName>district</cap:valueName>"
        "<cap:value>Nellore</cap:value></cap:geocode>"
    )
    alert = cap.parse_alert(alert_xml(area=geo))
    area = alert.infos[0].areas[0]

    assert area.polygons == [] and area.circles == []
    assert area.geocodes == {"district": "Nellore"}
    assert not area.drawable
    assert area.desc == "Off the Andhra Pradesh coast"


# --------------------------------------------------------------------------
# What is live, and what only looks live
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["Exercise", "Test", "Draft", "System"])
def test_a_drill_is_never_served_as_a_live_warning(status):
    """CAP has a field for exactly this and it is load-bearing.

    An exercise alert is written to be indistinguishable from a real one in
    every respect except this word. If it can reach the globe unmarked, the
    tool is capable of announcing a tsunami that is not happening.
    """
    alert = cap.parse_alert(alert_xml(status=status))
    assert not alert.is_live(NOW)
    assert alert.status == status

    live, refused = cap.active([alert], now=NOW)
    assert live == []
    assert refused.not_actual == 1


def test_only_an_exercise_may_be_opted_into_and_it_stays_labelled():
    """A rehearsal needs a drill on the globe. The other three statuses do not
    become showable just because the operator asked for a drill.

    The distinction is the whole point and it is not pedantry. `Draft` is
    content the issuing agency has NOT approved for release, so a flag called
    "let me rehearse" must never be the thing that publishes it. `Test` is a
    message about the channel rather than about the sea, and `System` is about
    the alerting system itself.
    """
    exercise = cap.parse_alert(alert_xml(status="Exercise"))
    shown, _ = cap.active([exercise], now=NOW, allow_exercise=True)
    assert len(shown) == 1
    # Never laundered into a real one: the caller still has to say what it is.
    assert shown[0].status == "Exercise"

    for status in ("Test", "Draft", "System"):
        blocked = cap.parse_alert(alert_xml(status=status))
        shown, refused = cap.active([blocked], now=NOW, allow_exercise=True)
        assert shown == [], f"{status} must not be showable even in rehearsal"
        assert refused.not_actual == 1


def test_a_cancel_removes_the_alert_it_references():
    """The false-alarm case. A cancelled warning still on screen is the single
    worst thing this layer could do."""
    original = cap.parse_alert(alert_xml(identifier="IN-1", event="Tsunami"))
    cancel = cap.parse_alert(
        alert_xml(
            identifier="IN-2",
            msg_type="Cancel",
            references="INCOIS-ITEWC,IN-1,2026-09-09T16:00:00+05:30",
        )
    )

    live, refused = cap.active([original, cancel], now=NOW)

    assert [a.identifier for a in live] == []
    assert refused.cancelled == 1
    # The Cancel itself is not a warning either; it is bookkeeping.
    assert refused.not_a_warning == 1


def test_an_update_supersedes_the_alert_it_references():
    """Otherwise the same hazard is drawn twice, once with stale numbers."""
    first = cap.parse_alert(alert_xml(identifier="IN-1", severity="Moderate"))
    update = cap.parse_alert(
        alert_xml(
            identifier="IN-2",
            msg_type="Update",
            severity="Extreme",
            references="INCOIS-ITEWC,IN-1,2026-09-09T16:00:00+05:30",
        )
    )

    live, refused = cap.active([first, update], now=NOW)

    assert [a.identifier for a in live] == ["IN-2"]
    assert live[0].severity == "Extreme"
    assert refused.superseded == 1


def test_references_may_carry_several_triples_separated_by_whitespace():
    """CAP allows a Cancel to withdraw a whole batch at once."""
    a = cap.parse_alert(alert_xml(identifier="IN-1"))
    b = cap.parse_alert(alert_xml(identifier="IN-2"))
    cancel = cap.parse_alert(
        alert_xml(
            identifier="IN-3",
            msg_type="Cancel",
            references=(
                "INCOIS-ITEWC,IN-1,2026-09-09T16:00:00+05:30 "
                "INCOIS-ITEWC,IN-2,2026-09-09T16:00:00+05:30"
            ),
        )
    )

    live, refused = cap.active([a, b, cancel], now=NOW)
    assert live == []
    assert refused.cancelled == 2


def test_an_expired_alert_is_not_active_and_the_timezone_is_respected():
    """The real feed stamps +05:30. Comparing that against a naive clock is a
    five and a half hour error in both directions."""
    alert = cap.parse_alert(alert_xml(expires="2026-09-09T16:30:00+05:30"))

    assert alert.is_live(cap.parse_time("2026-09-09T16:29:00+05:30"))
    assert not alert.is_live(cap.parse_time("2026-09-09T16:31:00+05:30"))
    # The same instant written in UTC must give the same answer.
    assert not alert.is_live(cap.parse_time("2026-09-09T11:01:00Z"))
    assert alert.is_live(cap.parse_time("2026-09-09T10:59:00Z"))

    _, refused = cap.active([alert], now=NOW)
    assert refused.expired == 1


def test_an_alert_that_has_not_started_is_not_active_yet():
    alert = cap.parse_alert(
        alert_xml(
            effective="2026-09-09T20:00:00+05:30",
            expires="2026-09-10T02:00:00+05:30",
        )
    )
    live, refused = cap.active([alert], now=NOW)

    assert live == []
    assert refused.not_yet_effective == 1


def test_an_alert_with_no_expiry_stays_active():
    """CAP makes `expires` optional. Absent means open-ended, not expired."""
    alert = cap.parse_alert(alert_xml(expires=""))
    live, _ = cap.active([alert], now=NOW)
    assert len(live) == 1
    assert alert.expires is None


def test_every_alert_is_either_live_or_counted_as_refused():
    """The ledger discipline used everywhere else in this project."""
    alerts = [
        cap.parse_alert(alert_xml(identifier="IN-1")),
        cap.parse_alert(alert_xml(identifier="IN-2", status="Exercise")),
        cap.parse_alert(alert_xml(identifier="IN-3", expires="2026-09-09T16:00:00+05:30")),
        cap.parse_alert(alert_xml(identifier="IN-4", effective="2026-09-09T23:00:00+05:30")),
        cap.parse_alert(
            alert_xml(
                identifier="IN-5",
                msg_type="Cancel",
                references="INCOIS-ITEWC,IN-1,2026-09-09T16:00:00+05:30",
            )
        ),
    ]
    live, refused = cap.active(alerts, now=NOW)

    assert len(live) + refused.total == len(alerts)
    assert live == []
    assert refused.cancelled == 1
    assert refused.not_actual == 1
    assert refused.expired == 1
    assert refused.not_yet_effective == 1
    assert refused.not_a_warning == 1


# --------------------------------------------------------------------------
# CAP's own vocabulary
# --------------------------------------------------------------------------


def test_an_unknown_severity_becomes_Unknown_rather_than_being_believed():
    """CAP's severity vocabulary is closed. A value outside it cannot be
    ordered against the others, and guessing where it sits would rank a hazard
    this parser does not understand."""
    alert = cap.parse_alert(alert_xml(severity="Catastrophic"))
    assert alert.severity == "Unknown"
    assert any("Catastrophic" in n for n in alert.notes)


def test_severity_ranks_so_the_worst_warning_can_be_found():
    order = [cap.severity_rank(s) for s in ("Extreme", "Severe", "Moderate", "Minor", "Unknown")]
    assert order == sorted(order, reverse=True)
    assert cap.severity_rank("Extreme") > cap.severity_rank("Minor")


def test_the_headline_and_instruction_come_from_the_chosen_language():
    """CAP carries one info block per language and they are not translations of
    a single canonical block: each is authored. Picking the wrong one hands a
    Telugu instruction to an English reader."""
    telugu = """
  <cap:info>
    <cap:language>te-IN</cap:language>
    <cap:category>Met</cap:category>
    <cap:event>High Wave</cap:event>
    <cap:urgency>Expected</cap:urgency>
    <cap:severity>Severe</cap:severity>
    <cap:certainty>Likely</cap:certainty>
    <cap:headline>Telugu headline</cap:headline>
    <cap:area><cap:areaDesc>coast</cap:areaDesc></cap:area>
  </cap:info>"""
    alert = cap.parse_alert(alert_xml(extra_info=telugu))

    assert alert.languages == ["en-IN", "te-IN"]
    assert alert.info("en").headline == "High Wave warning"
    assert alert.info("te").headline == "Telugu headline"
    # An unavailable language falls back to the first block rather than to
    # nothing, and the caller can see which language it actually got.
    assert alert.info("fr").language == "en-IN"


def test_geometry_is_taken_from_whichever_info_block_carries_it():
    """Only the English block in the real SACHET file carries the area, and a
    reader who asked for Telugu must still get the polygon."""
    telugu = """
  <cap:info>
    <cap:language>te-IN</cap:language>
    <cap:event>High Wave</cap:event>
    <cap:severity>Severe</cap:severity>
    <cap:urgency>Expected</cap:urgency>
    <cap:certainty>Likely</cap:certainty>
    <cap:headline>Telugu headline</cap:headline>
  </cap:info>"""
    alert = cap.parse_alert(alert_xml(extra_info=telugu))

    assert alert.info("te").areas == []
    assert len(alert.geometry()) == 1, "the alert as a whole is placed"


# --------------------------------------------------------------------------
# Real government CAP, not our idea of it
# --------------------------------------------------------------------------


def test_the_real_sachet_alert_parses_with_both_of_its_languages():
    raw = (FIXTURES / "sachet_ap_sdma_thunderstorm.cap.xml").read_bytes()
    alert = cap.parse_alert(raw, source="sachet_ndma")

    assert alert.identifier == "IN-1788952195339008_8"
    assert alert.sender == "Andhra-Pradesh-SDMA"
    assert alert.status == "Actual"
    assert alert.msg_type == "Update"
    assert alert.severity == "Severe"
    assert alert.urgency == "Expected"
    assert alert.certainty == "Likely"
    assert alert.languages == ["en-IN", "TL"]
    assert "Thunderstorms" in alert.event
    assert "Eluru" in alert.info("en").areas[0].desc

    # It supersedes the IMD bulletin it was raised from.
    assert alert.references == ["IN-1788952195339008_68"]

    # It has expired, which is exactly why it is safe to keep in a repository.
    assert not alert.is_live(cap.parse_time("2026-09-10T00:00:00+05:30"))

    # And it carries NO inline geometry: SACHET puts it in a separate file.
    assert alert.geometry() == []
    assert alert.polygon_url and "FetchPolygonXMLFile" in alert.polygon_url


def test_the_real_polygon_sidecar_parses_despite_having_no_namespace():
    """Two real quirks in one file: it is not in the CAP namespace, and it
    repeats the identical ring twice."""
    raw = (FIXTURES / "sachet_ap_sdma_thunderstorm.polygon.xml").read_bytes()
    rings = cap.parse_polygon_sidecar(raw)

    assert len(rings) == 1, "the duplicate ring must not become two polygons"
    ring = rings[0]
    assert ring[0] == ring[-1]
    assert len(ring) == 9
    # Coastal Andhra Pradesh, lon first. If this ever reads 17,81 the
    # convention has been lost somewhere between here and the globe.
    assert 80.8 < ring[0][0] < 82.0
    assert 16.4 < ring[0][1] < 17.2


def test_attaching_the_sidecar_places_an_alert_that_had_no_geometry():
    alert = cap.parse_alert(
        (FIXTURES / "sachet_ap_sdma_thunderstorm.cap.xml").read_bytes()
    )
    assert alert.geometry() == []

    rings = cap.parse_polygon_sidecar(
        (FIXTURES / "sachet_ap_sdma_thunderstorm.polygon.xml").read_bytes()
    )
    alert.attach_geometry(rings)

    assert len(alert.geometry()) == 1
    assert any("sidecar" in n.lower() for n in alert.notes)


# --------------------------------------------------------------------------
# Malformed input is refused, never guessed at
# --------------------------------------------------------------------------


def test_input_that_is_not_xml_at_all_is_refused_by_name():
    with pytest.raises(cap.CapError) as e:
        cap.parse_alert(b"<html><body>404 Not Found</body></html>")
    assert "alert" in str(e.value).lower()


def test_broken_xml_is_refused_rather_than_partly_parsed():
    with pytest.raises(cap.CapError):
        cap.parse_alert(b"<cap:alert><cap:identifier>truncated")


def test_an_alert_with_no_info_block_is_refused():
    """CAP allows it for a Cancel, but it carries no hazard, and treating the
    empty case as a Minor warning would put an unexplained polygon on a globe."""
    with pytest.raises(cap.CapError):
        cap.parse_alert(
            b'<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">'
            b"<cap:identifier>X</cap:identifier><cap:sender>S</cap:sender>"
            b"<cap:sent>2026-09-09T16:00:00+05:30</cap:sent>"
            b"<cap:status>Actual</cap:status><cap:msgType>Alert</cap:msgType>"
            b"</cap:alert>"
        )


def test_cap_1_1_and_a_namespaceless_alert_both_parse():
    """Producers in the wild use 1.1, and some omit the namespace entirely.
    Refusing those would refuse real warnings over a detail of serialisation."""
    v11 = (
        alert_xml()
        .decode()
        .replace("emergency:cap:1.2", "emergency:cap:1.1")
        .encode()
    )
    assert cap.parse_alert(v11).identifier == "IN-TEST-1"

    bare = b"""<alert>
      <identifier>IN-TEST-1</identifier>
      <sender>INCOIS-ITEWC</sender>
      <sent>2026-09-09T16:00:00+05:30</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <language>en-IN</language>
        <event>High Wave</event>
        <urgency>Immediate</urgency>
        <severity>Extreme</severity>
        <certainty>Observed</certainty>
        <area>
          <areaDesc>Off the Andhra Pradesh coast</areaDesc>
          <polygon>15.0,80.0 15.0,82.0 13.0,82.0 13.0,80.0 15.0,80.0</polygon>
        </area>
      </info>
    </alert>"""
    parsed = cap.parse_alert(bare)
    assert parsed.identifier == "IN-TEST-1"
    assert parsed.severity == "Extreme"
    # And the coordinate convention survives the missing namespace.
    assert parsed.geometry()[0].polygons[0][0] == (80.0, 15.0)


def test_a_time_that_cannot_be_read_is_None_rather_than_now():
    """Defaulting a missing expiry to the current time would silently expire
    every alert; defaulting it to now plus something would invent a duration."""
    assert cap.parse_time("") is None
    assert cap.parse_time("not a timestamp") is None
    assert cap.parse_time("2026-09-09T16:00:00+05:30") is not None


# --------------------------------------------------------------------------
# Geometry small enough to draw, without pretending it is what was issued
# --------------------------------------------------------------------------


def test_a_straight_run_of_points_collapses_to_its_endpoints():
    """The property Douglas-Peucker is chosen for: points that lie on a line
    between their neighbours carry no shape and can go."""
    ring = [(80.0, 10.0)] + [(80.0 + i * 0.001, 10.0) for i in range(1, 400)]
    ring += [(80.4, 12.0), (80.0, 12.0), (80.0, 10.0)]

    out = cap.simplify_ring(ring, tolerance=0.01)

    assert len(out) < 10
    assert out[0] == out[-1], "still closed"
    assert (80.0, 12.0) in out, "a real corner survives"


def test_a_corner_further_than_the_tolerance_is_never_removed():
    """Decimation would drop this depending on where the stride landed. That
    is the reason this is not decimation."""
    ring = [(80.0, 10.0)]
    ring += [(80.0 + i * 0.001, 10.0) for i in range(1, 100)]
    ring += [(80.05, 10.5)]  # a spike, half a degree off the line
    ring += [(80.0 + i * 0.001, 10.0) for i in range(100, 200)]
    ring += [(80.2, 12.0), (80.0, 12.0), (80.0, 10.0)]

    out = cap.simplify_ring(ring, tolerance=0.01)
    assert (80.05, 10.5) in out


def test_a_small_ring_is_left_exactly_as_the_agency_issued_it():
    """Most warning polygons are a few dozen points. Rounding those is damage
    for no gain, so nothing under the threshold is touched at all."""
    ring = [(80.0, 15.0), (82.0, 15.0), (82.0, 13.0), (80.0, 13.0), (80.0, 15.0)]
    assert cap.simplify_ring(ring, tolerance=0.01) == ring

    alert = cap.parse_alert(alert_xml())
    original = [list(r) for r in alert.infos[0].areas[0].polygons]
    alert.simplify()
    assert [list(r) for r in alert.infos[0].areas[0].polygons] == original
    assert not any("simplified" in n for n in alert.notes)


def test_simplifying_is_disclosed_on_the_alert_that_was_simplified():
    """A thinned boundary must never be presented as the one the agency drew."""
    # A dense run along one parallel, then two real corners. Deliberately NOT
    # collinear with the closing segment: a ring whose every point lies on one
    # line has no area, and simplify_ring correctly returns such a ring
    # untouched rather than collapsing it to two points.
    dense = " ".join(f"10.0000,{80.0 + i * 0.0001:.4f}" for i in range(500))
    dense += " 12.0,82.0 10.0,80.0"
    alert = cap.parse_alert(alert_xml(area=f"<cap:polygon>{dense}</cap:polygon>"))
    assert len(alert.infos[0].areas[0].polygons[0]) > 200

    alert.simplify()

    assert len(alert.infos[0].areas[0].polygons[0]) < 20
    note = next(n for n in alert.notes if "simplified" in n)
    assert "502 points to 4" in note, "says how many points went in and came out"
    assert "0.01 degree tolerance" in note, "and the tolerance a reader can argue with"
    assert "finer than this" in note, "and that the issued boundary was not this"


def test_simplifying_never_returns_something_that_is_not_an_area():
    """A tolerance far larger than the shape must not collapse it to a line."""
    ring = [(80.0, 10.0)] + [(80.0 + i * 0.001, 10.001) for i in range(1, 300)]
    ring += [(80.0, 10.0)]
    out = cap.simplify_ring(ring, tolerance=50.0)
    assert len(out) >= 4
    assert out[0] == out[-1]


def test_the_real_feed_is_reduced_to_something_a_globe_can_draw():
    """Measured on real SACHET geometry, which is the reason this exists.

    A single Gujarat alert fetched on 2026-09-09 carried a ring of 93,478
    points. Twelve alerts came to 114,412 between them, which would blow the
    frame budget in TRD section 5 before a single volumetric slice was drawn.
    """
    import pathlib

    raw = pathlib.Path(__file__).resolve().parents[3] / "data" / "raw" / "cap" / "sachet"
    files = sorted(raw.glob("*.polygon.xml")) if raw.is_dir() else []
    if not files:
        pytest.skip("no fetched CAP geometry; run tools/fetch_sample.py")

    before = after = 0
    for f in files:
        if f.stat().st_size == 0:
            continue
        for ring in cap.parse_polygon_sidecar(f.read_bytes()):
            before += len(ring)
            after += len(
                cap.simplify_ring(ring) if len(ring) > cap.SIMPLIFY_ABOVE else ring
            )

    assert before > 0
    assert after < before / 10, f"{before} points reduced only to {after}"


# --------------------------------------------------------------------------
# Over the API
# --------------------------------------------------------------------------


@pytest.fixture
def warned_client(tmp_path, monkeypatch):
    """A cube directory holding only a warnings.json, wired to the real app.

    Deliberately no zarr and no profiles: the hazard layer must stand up on a
    deployment that has warnings and nothing else, because a disaster-response
    office might well be exactly that.
    """
    import json

    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    def record(alert, source="cap_incois_ocean"):
        alert.source = source
        return alert.as_dict()

    live = cap.parse_alert(alert_xml(identifier="LIVE-1", event="High Wave"))
    drill = cap.parse_alert(alert_xml(identifier="DRILL-1", status="Exercise", event="Tsunami"))
    gone = cap.parse_alert(
        alert_xml(identifier="OLD-1", expires="2026-09-09T16:00:00+05:30")
    )
    killed = cap.parse_alert(alert_xml(identifier="DEAD-1", event="Swell Surge"))
    canceller = cap.parse_alert(
        alert_xml(
            identifier="CANCEL-1",
            msg_type="Cancel",
            references="INCOIS-ITEWC,DEAD-1,2026-09-09T16:00:00+05:30",
        )
    )
    # A real, live warning that is simply somewhere else in India. Given its
    # own severity so the ordering assertions below rest on the sort rather
    # than on it happening to be stable.
    faraway = cap.parse_alert(
        alert_xml(
            identifier="FAR-1",
            event="Flood",
            severity="Minor",
            area="<cap:polygon>26.0,72.0 26.0,74.0 24.0,74.0 24.0,72.0 26.0,72.0</cap:polygon>",
        )
    )

    root = tmp_path / "cube"
    root.mkdir()
    (root / "warnings.json").write_text(
        json.dumps(
            {
                "generated_from": ["cap_incois_ocean"],
                "citations": {"cap_incois_ocean": "test fixture, not real bulletins"},
                "method": cap.METHOD,
                "simplify_tolerance_deg": cap.SIMPLIFY_TOLERANCE_DEG,
                "count": 6,
                "unreadable": [],
                "alerts": [
                    record(a) for a in (live, drill, gone, killed, canceller, faraway)
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SAGAR_CUBE", str(root))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    clear_caches()


AT = {"at": "2026-09-09T17:00:00+05:30"}


def test_the_warnings_route_serves_the_live_one_and_counts_the_rest(warned_client):
    r = warned_client.get("/warnings", params=AT)
    assert r.status_code == 200
    body = r.json()

    # Both genuinely live warnings, worst first. FAR-1 is over Rajasthan, which
    # is not a reason to withhold it when no bounding box was asked for.
    assert [a["identifier"] for a in body["alerts"]] == ["LIVE-1", "FAR-1"]
    assert body["count"] == 2
    assert body["exercise_count"] == 0
    assert body["rehearsal"] is False

    # The ledger, which is the point: one shown, five withheld, each explained.
    assert body["refused"]["not_actual"] == 1      # the drill
    assert body["refused"]["expired"] == 1
    assert body["refused"]["cancelled"] == 1
    assert body["refused"]["not_a_warning"] == 1   # the Cancel message itself
    assert body["citations"]


def test_a_drill_reaches_the_globe_only_when_asked_for_and_stays_labelled(warned_client):
    off = warned_client.get("/warnings", params=AT).json()
    assert all(a["status"] == "Actual" for a in off["alerts"])

    on = warned_client.get("/warnings", params={**AT, "rehearsal": "true"}).json()
    drills = [a for a in on["alerts"] if a["status"] == "Exercise"]

    assert len(drills) == 1
    assert drills[0]["identifier"] == "DRILL-1"
    # The client cannot forget to check: the count is computed server-side.
    assert on["exercise_count"] == 1
    assert on["rehearsal"] is True


def test_a_cancelled_warning_is_never_served(warned_client):
    """The false-alarm case, asserted at the boundary as well as in the parser.

    Two implementations of the cancel rule is exactly how one of them ends up
    wrong, so this checks that the route really does defer to app/cap.py.
    """
    for params in (AT, {**AT, "rehearsal": "true"}):
        body = warned_client.get("/warnings", params=params).json()
        assert "DEAD-1" not in [a["identifier"] for a in body["alerts"]]


def test_the_worst_warning_is_first(warned_client):
    """A banner shows the top of this list, so the order is part of the answer."""
    body = warned_client.get("/warnings", params={**AT, "rehearsal": "true"}).json()
    ranks = [a["severity_rank"] for a in body["alerts"]]
    assert ranks == sorted(ranks, reverse=True)


def test_a_warning_elsewhere_in_india_is_filtered_by_the_bounding_box(warned_client):
    """FAR-1 is over Rajasthan. It is a real warning and it is not in our box."""
    everywhere = warned_client.get("/warnings", params=AT).json()
    assert everywhere["count"] == 2

    boxed = warned_client.get("/warnings", params={**AT, "bbox": "80,5,95,25"}).json()
    assert [a["identifier"] for a in boxed["alerts"]] == ["LIVE-1"]

    rajasthan = warned_client.get("/warnings", params={**AT, "bbox": "70,22,76,28"}).json()
    assert [a["identifier"] for a in rajasthan["alerts"]] == ["FAR-1"]
    assert rajasthan["refused"]["outside_bbox"] == 1


def test_the_layer_moves_with_the_time_the_client_asks_for(warned_client):
    """The hazard layer shares the field's time axis, so scrubbing moves both."""
    before = warned_client.get(
        "/warnings", params={"at": "2026-09-09T10:00:00+05:30"}
    ).json()
    assert before["count"] == 0
    assert before["refused"]["not_yet_effective"] >= 1

    during = warned_client.get("/warnings", params=AT).json()
    assert during["count"] == 2

    after = warned_client.get(
        "/warnings", params={"at": "2026-09-10T10:00:00+05:30"}
    ).json()
    assert after["count"] == 0
    assert after["refused"]["expired"] >= 1


def test_a_naive_instant_is_read_as_utc_rather_than_as_local_time(warned_client):
    """Five and a half hours against a feed that stamps +05:30."""
    body = warned_client.get("/warnings", params={"at": "2026-09-09T11:30:00"}).json()
    assert body["at"].endswith("+00:00")
    assert body["count"] == 2, "11:30 UTC is 17:00 IST, inside the window"


def test_an_unusable_instant_is_refused_rather_than_treated_as_now(warned_client):
    r = warned_client.get("/warnings", params={"at": "not-a-time"})
    assert r.status_code == 400
    assert "at" in r.json()["detail"]

    r = warned_client.get("/warnings", params={**AT, "bbox": "not,a,box"})
    assert r.status_code == 400


def test_the_text_comes_from_one_language_block_and_the_response_says_which(warned_client):
    body = warned_client.get("/warnings", params={**AT, "lang": "en"}).json()
    alert = next(a for a in body["alerts"] if a["identifier"] == "LIVE-1")
    assert alert["language"] == "en-IN"
    assert body["language"] == "en"
    assert "High Wave" in alert["headline"]
    assert alert["instruction"]
    assert "infos" not in alert, "one language is served, not all of them"


def test_a_deployment_with_no_warning_feed_reports_an_empty_layer(tmp_path, monkeypatch):
    """Absent is not broken. An office with no feed configured has no hazards,
    and that must read as a true statement rather than as a 500."""
    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    empty = tmp_path / "cube"
    empty.mkdir()
    monkeypatch.setenv("SAGAR_CUBE", str(empty))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        r = c.get("/warnings")
    get_settings.cache_clear()
    clear_caches()

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["alerts"] == []
    assert body["refused"]["total"] == 0


def test_the_shipped_rehearsal_bulletins_are_all_marked_as_drills():
    """A guard on the repository itself, not on the parser.

    data/warnings/incois holds bulletins we authored. If one of them ever
    acquires status Actual, this project starts publishing a warning for an
    event that did not happen, and no amount of care in app/cap.py would stop
    it. This is the test that would fail.
    """
    root = pathlib.Path(__file__).resolve().parents[3] / "data" / "warnings" / "incois"
    files = sorted(root.glob("*.cap.xml"))
    assert files, "the rehearsal set has gone missing"

    for f in files:
        alert = cap.parse_alert(f.read_bytes())
        assert alert.status == "Exercise", f"{f.name} is not marked as a drill"
        assert not alert.is_live(cap.parse_time("2026-07-30T05:30:00+05:30"))
        # Legible to a human reading the text, not only to a CAP parser.
        assert "EXERCISE" in alert.info("en").headline.upper()
