"""SagarNode: the live sensor station (TRD M9, PRD F6).

An ESP32 in a tank on the demo table, posting readings that appear on the same
globe as twenty-five real ocean casts. The problem statement asks for an
extensible design that can take "future integration of additional sensors";
this is that clause demonstrated with hardware rather than with a paragraph,
and a judge can put a hand in the water.

WHICH IS WHY THIS MODULE IS MOSTLY REFUSALS
-------------------------------------------
A bucket in a college hall is about to be drawn on a map of the Bay of Bengal.
Three things could go wrong and each has code against it.

**A wiring fault reading as a measurement.** An ESP32 analog pin with nothing
attached floats, and a floating pin produces a number that looks exactly like a
reading. Every value is range-checked against what the probe can physically
mean in a tank of water, and an implausible one is refused with the range in
the message, so somebody holding a multimeter knows which lead is loose.

**A tank being mistaken for the ocean.** The station carries its own note
saying it is a demonstration rig, it is drawn with its own mark, and its
position comes from the registry rather than from the device: a board that
could tell the server where it is could put a bucket in the Bay of Bengal.

**A threshold trip becoming a public warning.** Pouring warm water in trips the
alert, and the alert is CAP-shaped so it can ride the same HazardWatch bus as
everything else. It is emitted with CAP `status: Exercise`, which means every
guard already written for the rehearsal bulletins applies to it unchanged: the
server refuses it unless a caller asks for rehearsals, the globe draws it
dashed and lighter, and the panel stamps itself. No new promises, no new code.

THE WORDING RULE
----------------
CLAUDE.md: the TDS probe is a "conductivity-derived salinity proxy", never a
salinity sensor. It infers total dissolved solids from conductivity, and
calling that a salinity sensor overstates what two electrodes in a bucket can
know. An INCOIS oceanographer is precisely the person who would notice.

A test checks the LABELS this module and the registry expose, not the source
text. Grepping whole files for the phrase failed on the sentence above, which
is the rule being kept rather than broken; what matters is what reaches a
reader.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

#: What each field is called on screen, and what it honestly measures.
TEMP_LABEL = "Water temperature (DS18B20, immersed)"
TDS_LABEL = "Conductivity-derived salinity proxy (total dissolved solids)"
TURBIDITY_LABEL = "Turbidity (optical scatter)"

#: Ranges a probe in a tank of water can physically produce. Deliberately WIDE:
#: the job is to catch a disconnected pin and a mis-wired divider, not to
#: second-guess an unusual but real reading. A floating ADC pin on an ESP32
#: reads anywhere across its range, so anything outside these is hardware.
LIMITS: dict[str, tuple[float, float]] = {
    # Ice water to just under boiling. A DS18B20 spans -55 to 125 and a reading
    # outside this band in a demo tank is a broken 1-Wire bus, which reports
    # -127 when it cannot find the device.
    "temp_c": (-5.0, 100.0),
    # Distilled water to well past seawater. Seawater is roughly 35,000 ppm, so
    # this leaves room for somebody stirring in salt on purpose.
    "tds_ppm": (0.0, 60000.0),
    # Clear water to opaque. A 0 to 5 V turbidity board maps to about this.
    "turbidity_ntu": (0.0, 4000.0),
}

#: `ts` is NOT here, and that is the air-gapped demo showing up in the data
#: contract. An ESP32 has no battery-backed clock, so it learns the time from
#: NTP, and PRD F11 promises the demo runs with the network off. In that hall
#: the board never gets a clock.
#:
#: So a reading may OMIT its timestamp and the server stamps it on arrival,
#: recording `ts_source: "server"` so nobody later mistakes a receipt time for
#: an observation time. What is still refused is a timestamp that is PRESENT
#: and wrong, because a board reporting 1970 has a clock it believes and that
#: is worse than a board with none: it would sort to the front of the trend
#: and drag the axis with it.
REQUIRED = ("station_id", "temp_c", "tds_ppm", "turbidity_ntu")

#: How many readings the trend keeps. At 1 Hz this is about eight minutes,
#: which outlasts any demo beat and keeps the served payload small.
MAX_READINGS = 500

#: A trip needs this many standard deviations above the recent mean, and this
#: many samples to compute a mean from.
TRIP_SIGMA = 6.0
TRIP_MIN_HISTORY = 12
#: An absolute floor as well, so a very still tank (tiny standard deviation)
#: does not trip on a rounding wobble. Half a degree is more than the sensor's
#: own noise and less than a jug of warm water.
TRIP_MIN_DELTA_C = 1.5


def parse_time(value) -> datetime | None:
    """A board's timestamp, or None. Never a guess.

    An ESP32's clock comes up unset if NTP has not answered, which in an
    air-gapped hall it will not. Returning None rather than inventing
    something lets the caller decide: `validate` allows a reading with NO
    timestamp, and the route stamps it on arrival and records
    `ts_source: "server"`. What is refused is a stamp that is present and
    unreadable, because a board with a clock it believes and has wrong is
    worse than a board with none.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def validate(reading: dict) -> tuple[bool, str]:
    """Is this a reading, or is it a wiring fault? Returns (ok, why-not)."""
    if not isinstance(reading, dict):
        return False, "the body is not a JSON object"

    for field in REQUIRED:
        if field not in reading:
            return False, f"{field} is missing; a reading needs {', '.join(REQUIRED)}"

    if not str(reading["station_id"]).strip():
        return False, "station_id is empty; a reading has to say which rig it came from"

    # Absent is fine and is stamped on arrival; present and wrong is not.
    ts = reading.get("ts")
    if ts not in (None, "") and parse_time(ts) is None:
        return False, (
            f"ts {ts!r} is not an ISO-8601 timestamp. Send no ts at all and the "
            "server stamps the reading on arrival, which is the right answer "
            "for a board with no clock. A board that reports a time it "
            "believes and has wrong is worse: it sorts to the front of the "
            "trend and drags the axis with it."
        )

    for field, (lo, hi) in LIMITS.items():
        value = reading[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False, f"{field} is {value!r}, which is not a number"
        if not math.isfinite(float(value)):
            return False, f"{field} is not finite"
        if not lo <= float(value) <= hi:
            return False, (
                f"{field} is {value}, outside the {lo} to {hi} a probe in a tank "
                "can produce. That is what a disconnected pin or a mis-wired "
                "divider reads like, so it is refused rather than drawn."
            )

    return True, ""


def threshold_alert(history: list[dict]) -> dict | None:
    """A CAP-shaped alert if the tank just changed, or None.

    Against the RECENT SPREAD rather than an absolute temperature, because a
    tank in an air-conditioned hall and a tank in September Kolkata sit at
    different temperatures and neither is a fault. What is a fault, or rather
    what is the demo beat, is a sudden jump: somebody pouring a jug of warm
    water in.

    Once the water has settled at its new temperature that becomes the new
    normal and the alert clears, because an alert that never clears is an
    alert nobody reads.
    """
    if len(history) < TRIP_MIN_HISTORY + 1:
        return None

    latest = history[-1]
    prior = [float(r["temp_c"]) for r in history[:-1][-MAX_READINGS:]]
    mean = sum(prior) / len(prior)
    var = sum((x - mean) ** 2 for x in prior) / len(prior)
    sigma = math.sqrt(var)
    now = float(latest["temp_c"])
    delta = now - mean

    if delta < TRIP_MIN_DELTA_C:
        return None
    if sigma > 0 and delta < TRIP_SIGMA * sigma:
        return None

    return {
        # CAP's own word for a drill, and the reason this is safe. A bucket in
        # a college hall is not a coastal hazard, and marking it Exercise means
        # every guard written for the rehearsal bulletins applies unchanged.
        "status": "Exercise",
        "source": "demo-sensor",
        "event": "Rapid warming in the demonstration tank",
        "severity": "Moderate",
        "urgency": "Immediate",
        "certainty": "Observed",
        "headline": (
            f"DEMONSTRATION RIG. The SagarNode tank warmed to {now:.1f} degC, "
            f"{delta:.1f} above its recent average of {mean:.1f}."
        ),
        "description": (
            "This is the tabletop sensor station on the demo table, not an "
            "ocean observation. It is here to show that the tool takes a new "
            "instrument without a code change (PS requirement F6). The "
            "threshold is a jump against the tank's own recent spread rather "
            "than a fixed temperature, because a tank in an air-conditioned "
            "hall and one in a warm room are both normal."
        ),
        "instruction": "None. Nothing about this reading concerns anybody at sea.",
        "reading": dict(latest),
        "mean_before": round(mean, 2),
        "delta_c": round(delta, 2),
    }


# --------------------------------------------------------------------------
# Storage: a JSON-lines file, appended
# --------------------------------------------------------------------------


def append(path: Path, reading: dict) -> None:
    """One reading, one line. Survives a restart, which a demo needs.

    JSON lines rather than a database or a parquet: readings arrive one at a
    time at 1 Hz, an append is the whole write pattern, and a file a person can
    `tail` is worth more during a live demo than a format that needs a reader.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reading, separators=(",", ":")) + "\n")


def load(path: Path, limit: int = MAX_READINGS) -> list[dict]:
    """The most recent readings, oldest first.

    A corrupt line is SKIPPED rather than taken down the whole trend: this file
    is appended to by a microcontroller over WiFi, and a half-written line at
    the end after a power cut is a normal thing to find, not a reason to lose
    the eight minutes before it.
    """
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out
