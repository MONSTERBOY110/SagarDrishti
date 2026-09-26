"""SagarNode: a real sensor in a bucket, and what it is not (TRD M9, PRD F6).

The PS asks for an extensible design that can take "future integration of
additional sensors". SagarNode is that clause demonstrated with hardware
instead of a paragraph: an ESP32 in a tank on the demo table, posting readings
that appear on the globe beside twenty-five Argo floats.

Which is exactly why this module needs the most careful refusals in the
project. A bucket in a college hall is about to be drawn on the same map as the
Bay of Bengal, and three different things could go wrong in a way that matters:

  * A WIRING FAULT reads as a measurement. An analog pin with nothing on it
    floats, and a floating pin is a plausible-looking number. Every reading is
    range-checked and an implausible one is REFUSED and counted, never stored.
  * A TANK BECOMES AN OCEAN. The station is drawn as its own instrument class
    with its own mark, and the API says in words that it is a demonstration
    rig, so nobody reads it as an INCOIS observation.
  * A THRESHOLD TRIP BECOMES A PUBLIC WARNING. Pouring warm water into a
    bucket trips the alert, and the alert is CAP-shaped so it can ride the same
    HazardWatch bus as everything else. It is emitted with CAP status Exercise,
    which means every guard already written for the rehearsal bulletins applies
    to it unchanged: the server refuses it unless asked, the globe draws it
    dashed, the panel stamps itself.

And the wording rule from CONTRIBUTING.md, which has a test of its own: the TDS probe
is a "conductivity-derived salinity proxy", NEVER a salinity sensor. It infers
dissolved solids from conductivity and calling it a salinity sensor overstates
what a two-electrode probe in a bucket can know.
"""

from __future__ import annotations

import json

import pytest

from app import sagarnode


def reading(**over) -> dict:
    base = {
        "station_id": "sagarnode-01",
        "ts": "2026-09-10T18:30:00+05:30",
        "temp_c": 27.4,
        "tds_ppm": 310.0,
        "turbidity_ntu": 4.2,
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------
# A floating pin is not a measurement
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("temp_c", -40.0),
        ("temp_c", 150.0),
        ("tds_ppm", -5.0),
        ("tds_ppm", 90000.0),
        ("turbidity_ntu", -1.0),
        ("turbidity_ntu", 50000.0),
    ],
)
def test_a_reading_outside_what_the_probe_can_mean_is_refused(field, value):
    """An unconnected analog pin floats, and a floating pin produces a number
    that looks exactly like a measurement. These are the ranges a DS18B20 in a
    bucket and a TDS probe in tap water can physically produce."""
    ok, why = sagarnode.validate(reading(**{field: value}))

    assert not ok
    assert field in why
    # The message says the range, so somebody holding a multimeter can act on
    # it rather than guessing which probe is loose.
    assert any(ch.isdigit() for ch in why)


def test_a_plausible_reading_is_accepted():
    ok, why = sagarnode.validate(reading())
    assert ok, why


def test_a_missing_field_is_refused_rather_than_defaulted():
    """Defaulting an absent temperature to zero would put a reading of zero
    degrees on the globe, which is a measurement nobody took."""
    r = reading()
    del r["temp_c"]
    ok, why = sagarnode.validate(r)
    assert not ok and "temp_c" in why


def test_a_reading_with_no_station_is_refused():
    ok, why = sagarnode.validate(reading(station_id=""))
    assert not ok and "station_id" in why


def test_a_non_numeric_reading_is_refused_rather_than_coerced():
    ok, why = sagarnode.validate(reading(temp_c="warm"))
    assert not ok and "temp_c" in why


def test_a_timestamp_that_is_present_and_wrong_is_refused():
    """A board that reports a time it believes and has wrong is worse than a
    board with no clock: it sorts to the front of the trend and drags the
    axis with it."""
    ok, why = sagarnode.validate(reading(ts="not-a-time"))
    assert not ok and "ts" in why


def test_a_reading_with_NO_timestamp_is_accepted_because_of_the_air_gap():
    """This is the air-gapped demo showing up in the data contract.

    An ESP32 has no battery-backed clock and learns the time from NTP, and
    PRD F11 promises the demo runs with the network off. In that hall the
    board never gets a clock, so refusing an unstamped reading would refuse
    every reading of the actual demo. The server stamps it instead.
    """
    r = reading()
    del r["ts"]
    ok, why = sagarnode.validate(r)
    assert ok, why

    ok, why = sagarnode.validate(reading(ts=""))
    assert ok, why


# --------------------------------------------------------------------------
# The threshold, and what it is allowed to become
# --------------------------------------------------------------------------


def test_a_quiet_tank_trips_nothing():
    history = [reading(temp_c=27.0 + i * 0.01) for i in range(20)]
    assert sagarnode.threshold_alert(history) is None


def test_pouring_warm_water_in_trips_the_alert():
    """The demo beat: a jug of warm water into the tank, and the globe reacts.

    A jump against the recent spread, not an absolute number, because a tank
    in an air-conditioned hall and a tank in September Kolkata sit at
    different temperatures and neither is a fault.
    """
    history = [reading(temp_c=27.0 + (i % 2) * 0.05) for i in range(20)]
    history.append(reading(temp_c=34.0))

    alert = sagarnode.threshold_alert(history)

    assert alert is not None
    assert "temp" in alert["event"].lower() or "warm" in alert["event"].lower()


def test_the_trip_is_marked_as_an_exercise_and_as_a_demonstration_rig():
    """The most important test in this file.

    A bucket in a college hall is not a coastal hazard. This alert rides the
    same CAP bus as the tsunami and high-wave bulletins, so if it could arrive
    as `status: Actual` the tool would be capable of drawing a live warning
    because somebody poured a kettle into a tank.

    Marking it Exercise means every guard already written for the rehearsal
    bulletins applies to it unchanged, with no new code and no new promises.
    """
    history = [reading(temp_c=27.0) for _ in range(20)] + [reading(temp_c=34.0)]
    alert = sagarnode.threshold_alert(history)

    assert alert["status"] == "Exercise"
    assert "demo-sensor" in alert["source"]
    said = (alert["headline"] + " " + alert["description"]).lower()
    assert "demonstration" in said or "tank" in said
    # It must not describe itself as an ocean hazard.
    assert "tsunami" not in said and "coast" not in said


def test_the_trip_carries_the_reading_that_caused_it():
    """An alert that cannot be traced to a number is an alert nobody can check."""
    history = [reading(temp_c=27.0) for _ in range(20)] + [reading(temp_c=34.0)]
    alert = sagarnode.threshold_alert(history)

    assert "34" in alert["headline"] or "34" in alert["description"]
    assert alert["reading"]["temp_c"] == 34.0


def test_too_little_history_trips_nothing():
    """A spread needs samples. The first reading after power-on must not look
    like a spike against a history of one."""
    assert sagarnode.threshold_alert([reading(temp_c=34.0)]) is None
    assert sagarnode.threshold_alert([]) is None


def test_a_tank_that_is_simply_warm_does_not_trip_forever():
    """Once the water has settled at its new temperature it is the new normal,
    and an alert that never clears is an alert nobody reads."""
    history = [reading(temp_c=34.0 + (i % 2) * 0.05) for i in range(25)]
    assert sagarnode.threshold_alert(history) is None


# --------------------------------------------------------------------------
# The wording rule (CONTRIBUTING.md)
# --------------------------------------------------------------------------


def test_the_tds_probe_is_never_called_a_salinity_sensor():
    """It infers dissolved solids from conductivity. Calling it a salinity
    sensor overstates what two electrodes in a bucket can know, and an INCOIS
    oceanographer is exactly the person who would notice.

    Tests the LABELS, not the source text. The first version grepped whole
    files for the phrase and failed on the docstring that states the rule,
    which is the rule being kept rather than broken. What matters is what
    reaches a reader.
    """
    from app.registry import load_registry

    labels = [sagarnode.TEMP_LABEL, sagarnode.TDS_LABEL, sagarnode.TURBIDITY_LABEL]

    spec = load_registry().get("sagarnode_demo")
    labels += [v.label or "" for v in spec.variables]
    labels.append(spec.title)
    labels.append(spec.citation)

    for label in labels:
        assert "salinity sensor" not in label.lower(), f"{label!r} calls it one"

    # And the right phrase is actually used, not merely the wrong one avoided.
    assert "conductivity" in sagarnode.TDS_LABEL.lower()
    assert "proxy" in sagarnode.TDS_LABEL.lower()
    assert "conductivity" in spec.citation.lower()


# --------------------------------------------------------------------------
# Over the API
# --------------------------------------------------------------------------


@pytest.fixture
def node_client(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    root = tmp_path / "cube"
    root.mkdir()
    monkeypatch.setenv("SAGAR_CUBE", str(root))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    clear_caches()


def test_an_unstamped_reading_is_stamped_on_arrival_and_says_so(node_client):
    """A receipt time must never be quietly passed off as an observation time."""
    r = reading()
    del r["ts"]
    assert node_client.post("/ingest/sagarnode", json=r).status_code == 200

    latest = node_client.get("/sagarnode").json()["latest"]
    assert latest["ts_source"] == "server"
    assert latest["ts"] == latest["received_at"]


def test_a_stamped_reading_keeps_the_board_s_own_time(node_client):
    assert node_client.post("/ingest/sagarnode", json=reading()).status_code == 200

    latest = node_client.get("/sagarnode").json()["latest"]
    assert latest["ts_source"] == "device"
    assert latest["ts"].startswith("2026-09-10T18:30")
    # And the arrival time is kept beside it, which is how a wrong board clock
    # gets noticed at all.
    assert latest["received_at"] != latest["ts"]


def test_a_posted_reading_comes_back_out(node_client):
    r = node_client.post("/ingest/sagarnode", json=reading())
    assert r.status_code == 200
    assert r.json()["stored"] is True

    body = node_client.get("/sagarnode").json()
    assert body["count"] == 1
    assert body["latest"]["temp_c"] == 27.4
    assert body["station"]["id"] == "sagarnode-01"
    # Position comes from the registry, not from the board: a device that could
    # tell the server where it is could put a bucket in the Bay of Bengal.
    assert -90 <= body["station"]["lat"] <= 90


def test_a_bad_reading_is_refused_with_a_reason_and_not_stored(node_client):
    r = node_client.post("/ingest/sagarnode", json=reading(temp_c=150.0))
    assert r.status_code == 400
    assert "temp_c" in r.json()["detail"]

    assert node_client.get("/sagarnode").json()["count"] == 0


def test_the_station_says_what_it_is(node_client):
    """Twenty-five real Argo floats are on the same globe. The one thing this
    must never be mistaken for is an ocean observation."""
    node_client.post("/ingest/sagarnode", json=reading())
    body = node_client.get("/sagarnode").json()

    said = (body["station"]["note"] + body["station"]["title"]).lower()
    assert "demonstration" in said or "demo" in said
    assert "salinity sensor" not in said
    assert "conductivity" in body["parameters"]["tds_ppm"]["label"].lower()


def test_the_endpoint_serves_an_empty_station_rather_than_failing(node_client):
    """No rig plugged in is the normal state, including on the judges' laptop."""
    body = node_client.get("/sagarnode").json()
    assert body["count"] == 0
    assert body["latest"] is None
    assert body["alert"] is None
    assert body["station"]["id"]


def test_a_trip_is_served_beside_the_readings(node_client):
    for i in range(20):
        node_client.post("/ingest/sagarnode", json=reading(temp_c=27.0 + (i % 2) * 0.05))
    node_client.post("/ingest/sagarnode", json=reading(temp_c=34.0))

    body = node_client.get("/sagarnode").json()
    assert body["alert"] is not None
    assert body["alert"]["status"] == "Exercise"


def test_the_readings_survive_a_restart(node_client, tmp_path):
    """A demo that loses its trend because somebody restarted the API is a
    demo that cannot be restarted."""
    node_client.post("/ingest/sagarnode", json=reading())
    path = tmp_path / "cube" / "sagarnode.jsonl"
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["temp_c"] == 27.4
