/*
 * SagarNode: the tabletop sensor station (TRD M9, PRD F6).
 *
 * An ESP32 with three probes in a tank of water, posting one reading a second
 * to the SagarDrishti API, where it appears on the globe beside twenty-five
 * real Argo floats. The problem statement asks for an extensible design that
 * can take "future integration of additional sensors"; this is that clause
 * answered with hardware a judge can put a hand in.
 *
 * =========================================================================
 * THIS SKETCH HAS NEVER RUN ON A BOARD.
 *
 * The parts were not bought when it was written. It compiles against the
 * libraries named below and it implements the contract the server already
 * enforces and tests, but no line of it has driven a real pin. Treat it as a
 * starting point that saves an evening, not as working firmware.
 *
 * Before it is believed, run the 20-minute acceptance test in
 * docs/SAGARNODE-BOM.md. In particular the two conversions at the bottom of
 * this file (TDS and turbidity) are NOMINAL curves from the vendor
 * datasheets, and neither is calibrated against a known solution. Until they
 * are, the TDS figure is an indication rather than a measurement, and the
 * README says so.
 * =========================================================================
 *
 * WIRING. Fixed in docs/SAGARNODE-BOM.md; do not change one without the
 * other.
 *
 *   DS18B20 data ....... GPIO4,  with a 4.7 kOhm pull-up to 3V3
 *   TDS analog out ..... GPIO36 (ADC1_CH0), THROUGH a divider
 *   Turbidity out ...... GPIO39 (ADC1_CH3), THROUGH a divider
 *
 * TWO THINGS THAT DESTROY BOARDS OR DATA, both of which the BOM repeats:
 *
 *   1. The TDS and turbidity boards output 0 to 5 V when powered at 5 V, and
 *      an ESP32 pin tolerates 3.3 V. They MUST go through the resistor
 *      dividers (10k + 20k, or two 10k). Without them you can damage the
 *      board on first power-up. DIVIDER_RATIO below undoes the division in
 *      software and MUST match the resistors actually fitted.
 *   2. ADC2 is unusable while WiFi is on. Both analog probes are therefore on
 *      ADC1 pins (GPIO32 to GPIO39). Moving one to, say, GPIO25 gives
 *      readings that work on the bench and stop the moment WiFi associates,
 *      which is the worst way to find out.
 *
 * LIBRARIES (Arduino Library Manager):
 *   OneWire            by Paul Stoffregen
 *   DallasTemperature  by Miles Burton
 *   ArduinoJson        by Benoit Blanchon  (v7)
 *
 * WORDING (CLAUDE.md): the TDS probe is a conductivity-derived salinity
 * PROXY. It is never called a salinity sensor, here or anywhere else.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// ---------------------------------------------------------------- config --

static const char *WIFI_SSID = "CHANGE_ME";
static const char *WIFI_PASS = "CHANGE_ME";

// The laptop running ./tasks.ps1 api, on the same network. An IP, not a
// hostname: mDNS resolution is exactly the thing that fails on a locked-down
// campus network, and this has to work on a hall's guest WiFi or a phone
// hotspot with nothing else configured.
static const char *API_HOST = "http://192.168.1.100:8000";
static const char *STATION_ID = "sagarnode-01";

// Undoes the potential divider so the figure below is the probe's real output
// voltage. MUST match the resistors actually fitted: 10k + 20k gives 1.5,
// two 10k gives 2.0. Getting this wrong scales every reading silently.
static const float DIVIDER_RATIO = 1.5f;

static const int PIN_ONEWIRE = 4;
static const int PIN_TDS = 36;   // ADC1_CH0
static const int PIN_TURBIDITY = 39;  // ADC1_CH3

// TRD M9: 1 Hz sampling, 10-sample median filter.
static const int MEDIAN_SAMPLES = 10;
static const unsigned long POST_INTERVAL_MS = 1000;

// ------------------------------------------------------------- internals --

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature dallas(&oneWire);

/* Median, not mean. A mean is dragged by a single spike, and an ADC next to a
 * WiFi radio produces spikes; a median of ten throws the outlier away without
 * smearing it across the reading. */
static float medianOf(int *values, int n) {
  for (int i = 1; i < n; i++) {
    int key = values[i], j = i - 1;
    while (j >= 0 && values[j] > key) { values[j + 1] = values[j]; j--; }
    values[j + 1] = key;
  }
  return (n % 2) ? values[n / 2] : 0.5f * (values[n / 2 - 1] + values[n / 2]);
}

/* One analog pin, median-filtered, as the probe's own output voltage. */
static float readVolts(int pin) {
  int raw[MEDIAN_SAMPLES];
  for (int i = 0; i < MEDIAN_SAMPLES; i++) { raw[i] = analogRead(pin); delay(2); }
  float counts = medianOf(raw, MEDIAN_SAMPLES);
  // analogReadMilliVolts would be better (it applies the per-chip calibration
  // burned into eFuse) but is not on every core version; this is the portable
  // form. 12-bit, 0 to 3.3 V at 11 dB attenuation.
  float pinVolts = (counts / 4095.0f) * 3.3f;
  return pinVolts * DIVIDER_RATIO;
}

/* TDS in ppm, from the DFRobot reference curve with temperature compensation.
 *
 * NOMINAL AND UNCALIBRATED. The cubic below is the vendor's, and conductivity
 * probes drift with electrode fouling; without a known-concentration
 * calibration this is an indication of dissolved solids, not a measurement of
 * them. The server labels it a conductivity-derived salinity proxy for
 * exactly this reason. */
static float tdsPpm(float volts, float tempC) {
  // Conductivity roughly doubles per 25 degrees; the standard 2 percent per
  // degree correction back to 25 C.
  float compensated = volts / (1.0f + 0.02f * (tempC - 25.0f));
  return (133.42f * compensated * compensated * compensated
          - 255.86f * compensated * compensated
          + 857.39f * compensated) * 0.5f;
}

/* Turbidity in NTU, from the vendor curve for a 0 to 5 V optical board.
 *
 * ALSO NOMINAL. Above about 4.2 V the board reads clear water and the curve
 * is flat, so the result is clamped at zero rather than allowed to go
 * negative: a negative turbidity is not a cleaner-than-clear reading, it is
 * the curve leaving its valid range. */
static float turbidityNtu(float volts) {
  if (volts > 4.2f) return 0.0f;
  float ntu = -1120.4f * volts * volts + 5742.3f * volts - 4353.8f;
  return ntu < 0.0f ? 0.0f : ntu;
}

// ------------------------------------------------------------------ setup --

void setup() {
  Serial.begin(115200);
  delay(200);

  // 11 dB attenuation gives the full 0 to 3.3 V span on the pin. The default
  // is 0 dB, about 0 to 1.1 V, which silently saturates every reading above a
  // third of scale and looks like a probe stuck at maximum.
  analogSetPinAttenuation(PIN_TDS, ADC_11db);
  analogSetPinAttenuation(PIN_TURBIDITY, ADC_11db);

  dallas.begin();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("wifi");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : " FAILED");

  /* DELIBERATELY NO NTP.
   *
   * An ESP32 has no battery-backed clock, and PRD F11 promises the demo runs
   * with the network off, so in the hall this board will never reach a time
   * server. Rather than send a timestamp it does not have, or worse one it
   * believes and has wrong, it sends NO `ts` field at all: the server stamps
   * the reading on arrival and records ts_source "server" so a receipt time
   * is never mistaken for an observation time.
   *
   * The server REFUSES a timestamp that is present and unreadable, so sending
   * a 1970 stamp here would get every reading rejected. Sending none is the
   * supported path. */
}

// ------------------------------------------------------------------- loop --

void loop() {
  static unsigned long lastPost = 0;
  if (millis() - lastPost < POST_INTERVAL_MS) return;
  lastPost = millis();

  dallas.requestTemperatures();
  float tempC = dallas.getTempCByIndex(0);

  // DEVICE_DISCONNECTED_C is -127, and the server refuses it by range with a
  // message naming the pin. Caught here too so the serial log says which of
  // the two ends is at fault before anybody opens a browser.
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 not found: check the data line on GPIO4 and its 4.7k pull-up to 3V3");
    return;
  }

  float tdsVolts = readVolts(PIN_TDS);
  float turbVolts = readVolts(PIN_TURBIDITY);

  JsonDocument doc;
  doc["station_id"] = STATION_ID;
  doc["temp_c"] = tempC;
  doc["tds_ppm"] = tdsPpm(tdsVolts, tempC);
  doc["turbidity_ntu"] = turbidityNtu(turbVolts);
  // No "ts". See the note in setup().

  String body;
  serializeJson(doc, body);

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("wifi down, reading dropped: " + body);
    return;
  }

  HTTPClient http;
  http.begin(String(API_HOST) + "/ingest/sagarnode");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);

  // The server answers a refusal with a sentence naming the probe and the
  // range it should be in. Printing it is the whole debugging loop for a
  // headless board: plug in the serial monitor and it tells you which lead is
  // loose rather than making you guess.
  Serial.printf("%d %s\n", code, http.getString().c_str());
  http.end();
}
