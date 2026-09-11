# firmware/sagarnode/

ESP32 firmware for **SagarNode**, the live sensor station (TRD M9 / PRD F6).

An ESP32 with three probes in a tank of water, posting one reading a second to
the SagarDrishti API, where it appears on the globe beside twenty-five real
ocean casts. The problem statement asks for an extensible design that can take
"future integration of additional sensors"; this is that clause answered with
hardware a judge can put a hand in.

## Status

| Part | State |
|---|---|
| Server side (`POST /ingest/sagarnode`, `GET /sagarnode`) | **Built and tested.** 27 tests. Works today with `curl`, no hardware needed |
| Globe mark and live panel | **Built and tested.** A hollow station mark, a three-reading panel with a temperature trend, and an end-to-end test that drives the whole beat through the API |
| `sagarnode.ino` | **Written, never run on a board.** The parts were not bought when it was written |
| MQTT bridge | **Not built.** See below |

**The screen half needs no hardware either.** Post to the route with `curl` and
a panel appears beside the globe with the three readings and a trend, and a
mark appears on the water. Post nothing and there is no panel and no mark:
absence is the normal state and the interface shows it by having nothing there,
rather than by an empty box reading "no data".

**The sketch has never driven a real pin.** It compiles against the libraries
it names and it implements the contract the server already enforces, but treat
it as a starting point that saves an evening rather than as working firmware.
Before believing it, run the 20-minute acceptance test in
[`docs/SAGARNODE-BOM.md`](../../docs/SAGARNODE-BOM.md).

The earlier version of this file said the sketch would be written once the
hardware was in hand, on the grounds that flashing untested code onto an
unbought board is theatre. That is still true of *flashing* it. What changed is
the calendar: with the internal round close, having the sketch ready turns the
day the parts arrive from a day of writing into an hour of testing. It is
marked untested in the file itself, in this table, and in its header.

## You can demo the whole path with no hardware at all

The server does not care what posts to it:

```bash
curl -X POST http://127.0.0.1:8000/ingest/sagarnode \
  -H "Content-Type: application/json" \
  -d '{"station_id":"sagarnode-01","temp_c":27.4,"tds_ppm":310,"turbidity_ntu":4.2}'

curl http://127.0.0.1:8000/sagarnode
```

Post twenty quiet readings then one seven degrees warmer and the threshold
trips, exactly as a jug of warm water would.

## Wiring

Fixed in [`docs/SAGARNODE-BOM.md`](../../docs/SAGARNODE-BOM.md). Do not change
one without the other.

| Probe | Pin | Note |
|---|---|---|
| DS18B20 data | GPIO4 | 4.7 kOhm pull-up to 3V3 |
| TDS analog out | GPIO36 (ADC1_CH0) | **through a divider** |
| Turbidity out | GPIO39 (ADC1_CH3) | **through a divider** |

**Two things that destroy boards or data.**

The TDS and turbidity boards output **0 to 5 V** when powered at 5 V, and an
ESP32 pin tolerates **3.3 V**. They must go through the resistor dividers
(10k + 20k, or two 10k). Without them you can damage the board on first
power-up. `DIVIDER_RATIO` in the sketch undoes the division in software and
must match the resistors actually fitted: 1.5 for 10k + 20k, 2.0 for two 10k.

**ADC2 is unusable while WiFi is on.** Both analog probes are therefore on ADC1
(GPIO32 to GPIO39). Move one to GPIO25 and it will work on the bench and stop
the moment WiFi associates, which is the worst possible way to find out.

## The telemetry contract

```json
{"station_id": "sagarnode-01", "temp_c": 27.4, "tds_ppm": 310.0, "turbidity_ntu": 4.2}
```

**There is deliberately no `ts`.** An ESP32 has no battery-backed clock and
learns the time from NTP, and PRD F11 promises the demo runs with the network
off, so in the hall the board will never reach a time server. It therefore
sends no timestamp and the server stamps the reading on arrival, recording
`ts_source: "server"` so a receipt time is never mistaken for an observation
time. A board that *does* have a synced clock may send `ts` and it is kept.

What the server refuses is a timestamp that is **present and unreadable**: a
board reporting 1970 has a clock it believes and has wrong, which is worse than
having none, because it sorts to the front of the trend and drags the axis.

## What the server refuses, and why that helps you

Every value is range-checked against what a probe in a tank can physically
produce, and a refusal comes back as a sentence naming the field and the range.
That is the entire debugging loop for a headless board: open the serial
monitor and it tells you which lead is loose.

```
400 temp_c is -127.0, outside the -5.0 to 100.0 a probe in a tank can produce.
    That is what a disconnected pin or a mis-wired divider reads like, so it is
    refused rather than drawn.
```

`-127` is what a DS18B20 library reports when it cannot find the device, so
that exact message is the one you will see first if the 1-Wire pull-up is
missing.

## Calibration, stated rather than assumed

The TDS and turbidity conversions in the sketch are the **vendor nominal
curves** and neither is calibrated against a known solution. Conductivity
probes also drift as the electrodes foul. Until somebody calibrates them with a
known-concentration standard, both figures are indications rather than
measurements, and nothing in the demo should quote either as a number to be
relied on. The temperature probe is different: a DS18B20 is factory-calibrated
to about 0.5 degrees and can be quoted.

## MQTT

TRD M9 specifies MQTT as the primary transport with HTTP POST as the fallback,
because campus WiFi commonly blocks 8883. **Only the HTTP path is built**, and
that is a deliberate ordering rather than an omission: the fallback is the one
that works on a network nobody controls, and a demo that depends on an open
broker port has a single point of failure it does not need.
`mosquitto.conf` is here for when the bridge is written; the registry entry is
already `kind: mqtt` so it will not have to change.

## Safety

USB low voltage only. **Probes in the water, electronics outside it.** Nothing
in this rig should be near mains.

## Wording

The TDS probe is a **conductivity-derived salinity proxy**, never a "salinity
sensor" (CLAUDE.md). It infers total dissolved solids from conductivity, and an
INCOIS oceanographer is exactly the person who would notice the difference. A
test checks the labels the API serves.
