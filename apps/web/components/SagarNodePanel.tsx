"use client";

/** SagarNode: the tabletop sensor station, live (PS requirement F6, TRD M9).
 *
 * The problem statement asks for "an extensible design ... future integration
 * of additional sensors". This panel is that clause with a wire in it: a
 * device nobody had heard of when the cube was built posts to /ingest and
 * appears here and on the globe, with no change to the data model and no
 * redeploy. A judge can put a hand in the water and watch the trend move.
 *
 * IT IS ABSENT WHEN NOTHING IS PLUGGED IN. No rig is the normal state: on the
 * judges' laptop, on CI, and on this machine most of the time. The server
 * answers an empty station rather than a 404 for that reason, and this panel
 * renders nothing at all until a reading exists, the way AskPanel renders
 * nothing when the agent service is not running. An empty instrument box
 * reading "no data" is a broken control; no box is a feature that is not
 * currently in use.
 *
 * IT NEVER LETS THE BUCKET PASS FOR THE OCEAN. Three separate guards, because
 * this is the one layer on the surface whose data is not an ocean
 * observation:
 *
 *   1. the mark on the globe is a circle with a BROKEN rim, in the same dash
 *      grammar that draws a rehearsal warning;
 *   2. the station's own note is printed under the readings, unabbreviated;
 *   3. a threshold trip arrives as CAP status Exercise and is stamped
 *      Exercise here, exactly as HazardWatch stamps a drill.
 *
 * IT SAYS WHICH NUMBERS CAN BE QUOTED. The DS18B20 is factory-calibrated and
 * its degrees are a measurement. The conductivity and turbidity probes run on
 * the vendors' nominal curves against no standard solution, so they are
 * indications, and the footer says so rather than leaving an oceanographer to
 * assume we did not know.
 */

import { useEffect, useState } from "react";

import { api, type SagarNodeReading, type SagarNodeStation } from "@/lib/api";

/** How often the rig is asked for its state.
 *
 * The board posts at 1 Hz (TRD M9). Polling at 2 Hz means a new reading shows
 * up within about half a second of arriving, which is fast enough that
 * pouring warm water in feels connected to the trend moving, and the document
 * is a couple of kilobytes so the cost is nil. Polling rather than a socket
 * keeps the data plane a plain request-response service with nothing to
 * reconnect on stage. */
const POLL_MS = 500;

/** How often the rig is asked for its state when there is no rig.
 *
 * No rig is the normal state, and asking twice a second forever on a judge's
 * laptop for a feature nobody has plugged in is a cost with no return. Three
 * seconds still means a board switched on mid-demo appears while the hand is
 * still moving. */
const IDLE_POLL_MS = 3000;

/** Readings drawn in the trend. At 1 Hz this is the last two minutes, which
 *  covers the whole demo beat and keeps the path short enough to redraw at
 *  poll rate without thinking about it. */
const TREND_POINTS = 120;

/** Which reading field each row reads. */
const FIELD = {
  temp_c: (r: SagarNodeReading) => r.temp_c,
  tds_ppm: (r: SagarNodeReading) => r.tds_ppm,
  turbidity_ntu: (r: SagarNodeReading) => r.turbidity_ntu,
};

/** The rows, in the order a reader wants them: the one that can be quoted
 *  first, then the two that are indications. Keyed to what /sagarnode serves
 *  under `parameters`, so the LABELS come from the server rather than from a
 *  table here that could drift out of step with it. */
const ROWS: { key: keyof typeof FIELD; digits: number }[] = [
  { key: "temp_c", digits: 1 },
  { key: "tds_ppm", digits: 0 },
  { key: "turbidity_ntu", digits: 1 },
];

export default function SagarNodePanel({
  onStation,
}: {
  /** Lifted so the globe draws the same station this panel lists. One fetch,
   *  one source of truth: a panel and a globe each polling their own could
   *  disagree about whether the threshold has tripped, and the trip is the
   *  beat the whole rig exists to perform. */
  onStation: (station: SagarNodeStation | null) => void;
}) {
  const [node, setNode] = useState<SagarNodeStation | null>(null);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      let delay = IDLE_POLL_MS;
      try {
        const s = await api.sagarnode();
        if (!live) return;
        // count === 0 is an EMPTY station, not a station with nothing to say.
        // Both this panel and the globe treat it as absent.
        const present = s.count > 0 ? s : null;
        if (present) delay = POLL_MS;
        setNode(present);
        onStation(present);
      } catch {
        // Absent, not broken. The route 404s when no rig is registered and
        // the whole request fails when the API is down, and the page already
        // reports a dead data plane in one place. A second red box saying the
        // same thing about a feature nobody is using is noise.
        if (!live) return;
        setNode(null);
        onStation(null);
      } finally {
        if (live) timer = setTimeout(tick, delay);
      }
    };

    tick();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!node || !node.latest) return null;

  const latest = node.latest;
  const trend = node.readings.slice(-TREND_POINTS);
  const alert = node.alert;

  return (
    <section className="node" aria-label="SagarNode sensor station">
      <header className="node__head">
        <span className="node__title">SagarNode</span>
        {alert && (
          <span
            className="node__drill"
            title="CAP status Exercise. A demonstration rig, handled as though it were real, and never a live warning."
          >
            Exercise
          </span>
        )}
      </header>

      <dl className="node__rows">
        {ROWS.map(({ key, digits }) => {
          const meta = node.parameters[key];
          if (!meta) return null;
          return (
            <div className="node__row" key={key}>
              {/* The label the SERVER serves, verbatim. The conductivity probe
                  is a salinity PROXY (CLAUDE.md) and the one place that must
                  never be shortened into "salinity" is the line a reader
                  actually looks at. */}
              <dt className="node__name">{meta.label}</dt>
              <dd className="node__value num">
                {FIELD[key](latest).toFixed(digits)}
                <span className="node__units"> {meta.units}</span>
              </dd>
            </div>
          );
        })}
      </dl>

      <Trend readings={trend} meanBefore={alert ? alert.mean_before : null} />

      {alert && (
        <p className="node__headline" role="status">
          {alert.headline}
        </p>
      )}

      <footer className="node__foot">
        {/* The station's own words, unabbreviated. It is the sentence that
            stops a bucket being read as an ocean observation. */}
        <p className="node__note">{node.station.note}</p>
        {/* Kept to one line each. Four paragraphs of small grey caveat under
            three numbers is wallpaper; two are read. */}
        <p className="node__note">
          The DS18B20 is factory calibrated and can be quoted. The other two
          probes run on nominal vendor curves against no standard, so both are
          indications rather than measurements.
        </p>
        {latest.ts_source === "server" && (
          <p className="node__note">
            Timestamped by the API on arrival: the board has no clock and the
            demo runs offline. A receipt time, not an observation time.
          </p>
        )}
        <p className="node__cite">{node.citation}</p>
      </footer>
    </section>
  );
}

/**
 * The temperature trend, as a sparkline.
 *
 * TEMPERATURE ONLY, and that is the honest choice rather than the lazy one.
 * It is the one channel on this rig that is calibrated, it is the channel the
 * threshold watches, and three lines sharing one axis in three unrelated
 * units would be a chart that cannot be read.
 *
 * The vertical extent is LABELLED. An unlabelled sparkline auto-scales to its
 * own data, so a tank sitting perfectly still draws a dramatic mountain range
 * out of the last two hundredths of a degree. The numbers at the ends are
 * what stop that reading as a story.
 */
function Trend({
  readings,
  meanBefore,
}: {
  readings: SagarNodeReading[];
  /** The average the threshold tripped against, ruled across the chart so the
   *  jump is visible rather than asserted. Null when nothing has tripped. */
  meanBefore: number | null;
}) {
  if (readings.length < 2) {
    return (
      <p className="node__note">
        <span className="num">{readings.length}</span> reading on file. The
        trend needs a second one.
      </p>
    );
  }

  const values = readings.map((r) => r.temp_c);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (meanBefore !== null) {
    lo = Math.min(lo, meanBefore);
    hi = Math.max(hi, meanBefore);
  }
  // A dead-flat trace would divide by zero and, worse, would be drawn as a
  // line through the middle of nowhere. Given a floor of a fifth of a degree,
  // a still tank draws a flat line near the middle, which is the truth.
  if (hi - lo < 0.2) {
    const mid = (hi + lo) / 2;
    lo = mid - 0.1;
    hi = mid + 0.1;
  }

  const W = 300;
  const H = 40;
  // A margin top and bottom. Without it the extremes are drawn ON the frame
  // edge, where half the stroke width falls outside the box and the highest
  // reading of the demo, the one being pointed at, is the one drawn thinnest.
  const PAD = 4;
  const x = (i: number) => (i / (readings.length - 1)) * W;
  const y = (v: number) => H - PAD - ((v - lo) / (hi - lo)) * (H - 2 * PAD);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const seconds = elapsed(readings);

  return (
    <figure className="node__trend">
      <svg
        className="node__spark"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={
          `Water temperature over the last ${readings.length} readings, ` +
          `from ${lo.toFixed(1)} to ${hi.toFixed(1)} degrees Celsius.`
        }
      >
        <path d={path} className="node__spark-line" vectorEffect="non-scaling-stroke" />
        {meanBefore !== null && (
          /* The average the trip was measured against. Ruled, dashed, in the
             reserved caution ink: the jump is then something a reader sees
             rather than something the headline claims.
             Drawn AFTER the trace, not before. A still tank sits exactly on
             its own mean, so the rule lands under the flat part of the trace
             and the one stroke that explains the chart was the one hidden. */
          <line
            x1={0}
            x2={W}
            y1={y(meanBefore)}
            y2={y(meanBefore)}
            className="node__spark-mean"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      <figcaption className="node__scale">
        <span className="num">{lo.toFixed(1)}</span>
        {/* The span is printed only when there IS one. Twenty-one readings
            posted by a script in the same second are honestly "over 0 s", and
            printing that reads as a broken clock rather than as a fast
            sender. */}
        <span>
          {readings.length} readings
          {seconds !== null && seconds > 0 && (
            <>
              {" "}
              over <span className="num">{seconds}</span> s
            </>
          )}
        </span>
        <span className="num">{hi.toFixed(1)} degC</span>
      </figcaption>
    </figure>
  );
}

/** Wall-clock span of the drawn readings, in whole seconds, or null if the
 *  stamps cannot be read. Printed so the sparkline's width means something:
 *  120 points is two minutes at 1 Hz and twenty seconds at 6 Hz, and the
 *  chart looks identical either way. */
function elapsed(readings: SagarNodeReading[]): number | null {
  const first = Date.parse(readings[0]?.ts ?? "");
  const last = Date.parse(readings[readings.length - 1]?.ts ?? "");
  if (!Number.isFinite(first) || !Number.isFinite(last)) return null;
  return Math.max(0, Math.round((last - first) / 1000));
}
