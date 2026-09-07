# SagarNode - Bill of Materials & Shop Sheet

**What this is:** the parts list for **SagarNode**, our tabletop live-sensor station (TRD M9 / PRD "SagarNode"). It streams real water readings into the SagarDrishti globe as a live "virtual mooring," which is how we demonstrate the PS's own **Extensible Design** requirement - *"future integration of additional sensors (CTDs, moorings…)"* - with physical hardware on the table.

**Who this is for:** the person walking into a local electronics shop. Print it or open it on your phone. Prices are Indian retail, cross-checked against PRIOR-ART.md §F (Robocraze/Robu, verified Sep 2026); a local shop will usually be within ±30%.

> **Wording rule (non-negotiable, from CLAUDE.md):** the TDS probe is a **"conductivity-derived salinity proxy."** Never call it a salinity sensor - in a room with INCOIS oceanographers that single word costs us credibility.

---

## 1. Buy this (core rig - everything needed for a working demo)

| # | Ask the shop for | Qty | Expected ₹ | Why we need it | Acceptable substitute |
|---|---|---|---|---|---|
| 1 | **ESP32 DevKit V1** (ESP32-WROOM-32, 30-pin or 38-pin dev board) | 1 | 250-850 | The brain: WiFi + ADC + 1-Wire, all on USB power | ESP32-WROOM-32D/32U, NodeMCU-32S, ESP32-DevKitC. **Not** an ESP8266 (too few ADC pins) |
| 2 | **DS18B20 waterproof temperature probe** (stainless steel tip, ~1 m lead, 3 wires) | 1 | 60-150 | Water temperature - the one measurement that is scientifically real | Any waterproof DS18B20; avoid the bare TO-92 chip version (not submersible) |
| 3 | **4.7 kΩ resistor** (¼ W) | 1 (buy a strip of 5-10) | 5-20 | **Mandatory** 1-Wire pull-up. Without it the DS18B20 returns −127 °C or nothing | 4.7 kΩ only; 10 kΩ works but is less reliable on long leads |
| 4 | **Analog TDS sensor module** (with its own probe) | 1 | 350-1,450 | Conductivity → our **salinity proxy** | DFRobot Gravity SEN0244 (branded, ~₹1,435) or any "analog TDS sensor module Arduino" clone (~₹350-600) |
| 5 | **Turbidity sensor module** (with probe) | 1 | 489-700 | Third variable; makes "pour something into the tank" visibly change the globe | DFRobot SEN0189 or clone. **Optional - see §3** |
| 6 | **10 kΩ resistors** (¼ W) | 4 | 10-20 | **Voltage dividers** for items 4 and 5 - see §2. Skipping these can kill the ESP32 | 2×10 kΩ per sensor, or one 10 kΩ + one 20 kΩ per sensor |
| 7 | **Breadboard** (half-size 400-point or full 830-point) | 1 | 40-80 | No soldering needed for the whole build | Any solderless breadboard |
| 8 | **Jumper wires - male-to-male**, 40-pin ribbon | 1 set | 40-80 | Breadboard runs | - |
| 9 | **Jumper wires - male-to-female**, 40-pin ribbon | 1 set | 40-80 | Sensor modules have female headers; the breadboard needs male pins | - |
| 10 | **USB data cable matching the board** (micro-USB on most ESP32 DevKits; some newer ones are USB-C) | 1 | 80-150 | Power **and** programming | **Must be a DATA cable.** See §2 |
| 11 | Transparent container, ~1-2 L (small aquarium, glass jar, plastic box) | 1 | 0-200 | The "ocean" for the demo | A kitchen jar is fine |

**Core total: ≈ ₹1,400 (clone parts) - ₹2,900 (branded)** - inside PRD's ₹1,650-3,000 envelope.

### Nice to have (₹100-200, buy if the shop has them)

- Small flat-head screwdriver (TDS/turbidity modules often have screw terminals)
- Electrical tape or heat-shrink (tidy the probe leads)
- A second ESP32 board as a spare - **strongly recommended** if budget allows. A dead board 12 h before the internal round is our worst hardware failure mode, and ESP32s die from exactly the mistake described in §2(a).

---

## 2. Three things that go wrong - read before you pay

**(a) The 5 V analog trap - this is why item 6 is on the list.**
The TDS and turbidity modules are designed for the Arduino Uno: powered at 5 V, they output **0-5 V** on their analog pin. The ESP32's ADC pins tolerate **3.3 V maximum**. Feeding 5 V into an ESP32 GPIO can permanently damage it. Two fixes, and we use both:

- Power the modules from the ESP32's **5 V (VIN)** pin, then drop each analog output through a **2:1 resistor divider** (two 10 kΩ resistors: signal → 10 kΩ → ADC pin → 10 kΩ → GND). 5 V becomes 2.5 V - safe - and we scale it back up in firmware.
- Some clone modules run acceptably at 3.3 V with reduced range. We still use the divider; it costs ₹5 and removes the risk entirely.

**(b) ADC2 does not work while WiFi is on.**
The ESP32 has two ADC blocks, and **ADC2 is unavailable whenever WiFi is active** - which, for us, is always. So both analog sensors must land on **ADC1 pins only: GPIO32-GPIO39**. The pinout below uses GPIO36 and GPIO39, matching TRD M9. If a tutorial tells you to use GPIO25/26/27, ignore it.

**(c) Charge-only USB cables.**
A large fraction of cheap micro-USB cables carry power but no data lines. The board will light up and still be completely invisible to your computer. **Ask for a data cable**, and test it in the shop if you can.

---

## 3. If the shop doesn't have everything

Buy in this priority order - the demo degrades gracefully:

1. **Items 1, 2, 3, 7, 8, 9, 10** → a working temperature-only station. This alone satisfies the "live sensor on the globe" beat and the PS's extensibility requirement.
2. **+ item 4 (TDS) + item 6** → adds the conductivity-derived salinity proxy. This is the pairing that most resembles a real CTD and is worth a second trip.
3. **+ item 5 (turbidity)** → the third variable. Genuinely optional; drop it without hesitation if unavailable or overpriced.

Do **not** substitute a pH sensor, water-level sensor, or flow meter for any of these - they measure nothing INCOIS reports, so they add no narrative value.

---

## 4. Wiring (no soldering; ~15 minutes)

```
                    ESP32 DevKit V1
                  +-----------------+
   DS18B20 DATA --| GPIO4      3V3  |-- 3.3 V rail (DS18B20 VCC + 4.7k pull-up)
                  |                 |
   TDS  Ao -------| GPIO36      VIN |-- 5 V rail (TDS VCC, Turbidity VCC)
   (via divider)  |   (ADC1_CH0)    |
                  |                 |
   TURB Ao -------| GPIO39      GND |-- common ground (ALL grounds tie here)
   (via divider)  |   (ADC1_CH3)    |
                  +-----------------+
                          |
                         USB  ->  laptop / power bank (5 V only, nothing else)

   4.7 kOhm pull-up:   GPIO4 ----[4.7k]---- 3.3 V      (required for 1-Wire)

   Voltage divider, one per analog sensor:

       sensor Ao ----[10k]----+---- ESP32 ADC pin
                              |
                            [10k]
                              |
                             GND
```

### Pin table

| Signal | ESP32 pin | Notes |
|---|---|---|
| DS18B20 data | **GPIO4** | 1-Wire; needs the 4.7 kΩ pull-up to 3.3 V |
| DS18B20 VCC | 3V3 | |
| TDS analog out | **GPIO36** (ADC1_CH0) | through the 2:1 divider |
| TDS VCC | VIN (5 V) | |
| Turbidity analog out | **GPIO39** (ADC1_CH3) | through the 2:1 divider |
| Turbidity VCC | VIN (5 V) | |
| All grounds | GND | one common ground - sensors *and* dividers |

---

## 5. Safety

- **USB 5 V only.** Never connect mains, a wall adapter's bare leads, or a battery pack above 5 V.
- **Probes in the water; the ESP32, breadboard and modules stay outside and dry.** Only the stainless DS18B20 tip and the TDS/turbidity probe heads are submersible - the modules themselves are not.
- Use plain tap water plus table salt and warm water for the demo. No chemicals, no acids.
- Keep the tank off the laptop's table surface, or stand it on a tray.

---

## 6. On arrival - 20-minute acceptance test

Run this the day the parts land, before any project firmware is written, so a bad part is discovered immediately and not at 2 a.m.:

1. Plug the board in. A power LED lights and the board appears as a COM port in Device Manager. *(Fails → charge-only cable, or the CP210x/CH340 USB driver is missing.)*
2. Flash the Arduino IDE `Blink` example. LED blinks. *(Proves toolchain + board.)*
3. Wire only the DS18B20 + pull-up. Run the DallasTemperature library example: it should read ≈ room temperature, and rise when the probe goes into warm water. *(Reads −127 °C → pull-up missing or wrong data pin.)*
4. Add the TDS module through its divider. Raw ADC sits low in plain water and rises clearly when you stir in a spoon of salt. *(Absolute ppm accuracy does not matter to us - only that the trend is real and repeatable.)*
5. Same for turbidity: clear water vs. a pinch of flour.
6. Report the four numbers (room temp, warm temp, plain-water TDS raw, salty TDS raw). Those become the threshold calibration constants in the firmware.

Firmware (`firmware/sagarnode/`), the MQTT topic and the `/ingest/sagarnode` HTTP fallback are **Phase 2** deliverables per TRD M9 - written once these parts are confirmed in hand.

---

## 7. Honesty rule for the pitch

When the tank trips a threshold and HazardWatch fires an alert, we say out loud: **this sensor alert is a pedagogical stand-in for INCOIS's real hazard products**, flagged in the system as `source: demo-sensor`. We are demonstrating the ingestion path and the alert bus - not claiming to detect a cyclone in a bucket. Judges reward that distinction and punish its absence.

*Prices & hardware references: PRIOR-ART.md §F. Module specs: TRD M9. Demo beat: PRD §11 step 8.*
