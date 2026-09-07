# firmware/sagarnode/

ESP32 firmware for **SagarNode**, the live sensor station (TRD M9 / PRD).

**Phase 1 status: parts list only.** The sketch is written once the hardware is
in hand - flashing untested code onto an unbought board is theatre.

- **Buy the parts:** [`docs/SAGARNODE-BOM.md`](../../docs/SAGARNODE-BOM.md) - shop sheet, wiring diagram, pin table, safety rules, and a 20-minute
  acceptance test to run the day the parts arrive.
- **Pinout (fixed, do not change without updating the BOM):** DS18B20 on GPIO4
  with a 4.7 kΩ pull-up; TDS on GPIO36 (ADC1_CH0); turbidity on GPIO39
  (ADC1_CH3). ADC1 only - ADC2 is unusable while WiFi is active.
- **Telemetry contract (Phase 2):** 1 Hz sampling, 10-sample median filter, JSON
  `{station_id, ts, temp_c, tds_ppm, turbidity_ntu}` published to MQTT topic
  `sagardrishti/station/{id}/telemetry` (QoS 1), with an HTTP POST fallback to
  `/ingest/sagarnode` because campus WiFi commonly blocks port 8883.

**Wording rule:** the TDS probe is a *conductivity-derived salinity proxy*,
never a "salinity sensor" (CLAUDE.md).
