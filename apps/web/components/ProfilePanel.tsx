"use client";

/** Spike C: a clicked float becomes its own depth profile (PS requirement F2).
 *
 * Two curves, and the difference between them is stated in the grammar of the
 * sheet rather than in a legend nobody reads:
 *
 *   - the OBSERVED profile is drawn solid and coloured along its own length by
 *     the same colorbar the slices use, because it is a measurement;
 *   - the MODEL column is drawn as a dashed ink line, because it is a
 *     computation. Dash carries state on this surface; hue belongs to data.
 *
 * The header prints the WMO id, the profile timestamp and the QC policy, and
 * the footer prints the dataset citation. That is the citation discipline the
 * agent inherits in Phase 2 - it starts here, on a chart a human reads.
 *
 * Deliberately NOT here: any RMSE or bias number. The model curve is taken
 * from the nearest grid cell, and a skill figure computed that way would be
 * indefensible in front of an INCOIS oceanographer. The verified comparison
 * lives in ScorecardPanel, which interpolates the model to each cast's own
 * position and depth (TRD M5, Ryan et al. 2015). This panel says so on screen
 * and points at it, rather than leaving a reader to assume the dashed line is
 * the verification.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { modelProfileAt, type FieldColumn, type ProfileDetail } from "@/lib/api";
import { rampCss, rgbFor, type Palette, type Scale } from "@/lib/colormap";

/**
 * Which profile parameter the gridded model can be compared against.
 *
 * The INCOIS analysis carries temperature and salinity, and nothing else. A
 * BGC float's chlorophyll, oxygen, nitrate and pH have NO model counterpart,
 * so for those the dashed model curve is not drawn and the panel says why.
 * Drawing an empty dashed line, or worse borrowing the temperature column,
 * would imply a comparison that does not exist.
 */
const MODEL_COUNTERPART: Record<string, string> = { temp: "TEMP", psal: "SAL" };

/** The scene variable a profile parameter corresponds to, for colour parity. */
const SCENE_VARIABLE: Record<string, string> = { temp: "TEMP", psal: "SAL" };

/**
 * Below this many samples a parameter is drawn WITH its sample points showing.
 *
 * A BGC sensor samples far more sparsely than the CTD beside it: on float
 * 2903831 the CTD returns 1012 levels while nitrate returns 76. Joining 76
 * points into a smooth curve without showing where they are invites reading
 * the line between two samples as measured. Showing the marks is the ordinary
 * oceanographic presentation and it is honest at a glance.
 */
const SPARSE_SAMPLE_LIMIT = 200;

/**
 * What to call the instrument, from its registry kind.
 *
 * The header said "Argo float" for everything, which is wrong the moment a
 * ship cast or a BGC float is clicked. Naming the class is not decoration: a
 * reader has to know whether the chlorophyll in front of them came off a float
 * or out of a cruise file before they can judge it.
 */
function platformNoun(kind: string): string {
  switch (kind) {
    case "gdac_bgc":
      return "BGC float";
    case "file":
      return "Cast";
    case "mooring":
      return "Mooring";
    case "hf_radar":
      return "HF radar";
    case "adcp":
      return "ADCP";
    default:
      return "Argo float";
  }
}

interface Props {
  detail: ProfileDetail | null;
  column: FieldColumn | null;
  variable: string;
  units: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  focusDepth: number;
  /** Marks on the globe: one per CAST, not one per instrument. */
  stationCount: number;
  /** Distinct instruments behind those casts. */
  platformCount: number;
  loading: boolean;
  onFocusDepth: (d: number) => void;
  onClose: () => void;
}

const PLATE = "#c4b89a";
const INK = "#16130d";
const INK_SOFT = "#4a4335";
const RULE = "rgba(43,106,134,.34)";
const MONO = '"Courier Prime", ui-monospace, monospace';
const SANS = '"Archivo Narrow", system-ui, sans-serif';

export default function ProfilePanel(p: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // Which of the clicked instrument's parameters is plotted. Panel-local,
  // because it is a property of the profile in front of you and not of the
  // scene: the globe keeps showing the field the scene variable selects.
  const [chosen, setChosen] = useState<string | null>(null);

  const available = p.detail?.parameters ?? [];

  // Default to the parameter matching the scene variable, so clicking a float
  // while looking at salinity opens salinity. A BGC float that does not carry
  // it falls back to its first served parameter rather than an empty chart.
  const param = useMemo(() => {
    if (!available.length) return null;
    if (chosen && available.some((a) => a.name === chosen)) return chosen;
    const wanted = Object.keys(SCENE_VARIABLE).find(
      (k) => SCENE_VARIABLE[k] === p.variable,
    );
    if (wanted && available.some((a) => a.name === wanted)) return wanted;
    return available[0].name;
  }, [available, chosen, p.variable]);

  // A new profile clears the choice, so the selector cannot keep pointing at a
  // parameter the newly clicked instrument does not measure.
  useEffect(() => setChosen(null), [p.detail?.profile_id]);

  const active = available.find((a) => a.name === param) ?? null;
  const obs = p.detail && param ? (p.detail.levels[param] ?? null) : null;
  // Never borrow the scene variable's unit for a different quantity: that put
  // "Chlorophyll-a . degC" on the axis. An unknown unit is left blank, which is
  // merely incomplete rather than wrong.
  const obsUnits =
    active?.units || (param && SCENE_VARIABLE[param] === p.variable ? p.units : "");
  const obsLabel = active?.label || p.variable;
  const modelVariable = param ? MODEL_COUNTERPART[param] : undefined;
  // Colour the observed line from the colorbar only when it is measuring the
  // same quantity the colorbar is scaled to. Colouring chlorophyll with a
  // temperature ramp would state a scale that does not apply to it.
  const colourMatchesScale = Boolean(param && SCENE_VARIABLE[param] === p.variable);

  useEffect(() => {
    let disposed = false;

    (async () => {
      const echarts = await import("echarts");
      if (disposed || !hostRef.current || !p.detail || !obs) return;

      const chart = chartRef.current ?? echarts.init(hostRef.current, undefined, { renderer: "canvas" });
      chartRef.current = chart;

      const depths = p.detail.levels.depth;
      const obsPairs: [number, number][] = [];
      for (let i = 0; i < depths.length; i++) {
        const v = obs[i];
        if (v !== null && Number.isFinite(v)) obsPairs.push([v, depths[i]]);
      }

      // The model curve exists only for a parameter the model actually
      // carries, AND only when the scene is showing that same variable, since
      // `p.column` holds one variable at a time.
      const comparable = modelVariable !== undefined && modelVariable === p.variable;
      const model = comparable && p.column
        ? modelProfileAt(p.column, p.detail.lat, p.detail.lon)
        : null;
      const modelPairs: [number, number][] = [];
      if (model) {
        model.depths.forEach((d, i) => {
          const v = model.values[i];
          if (v !== null && Number.isFinite(v)) modelPairs.push([v, d]);
        });
      }

      // Colour the observed line along its own length with the field's
      // colorbar, so the chart and the globe speak one colour language. Only
      // when the two are measuring the same quantity: see colourMatchesScale.
      const gradientStops = colourMatchesScale
        ? obsPairs.map((_, i) => {
            const t = obsPairs.length === 1 ? 0 : i / (obsPairs.length - 1);
            const [r, g, b] = rgbFor(obsPairs[i][0], p.vmin, p.vmax, p.palette, p.scale, p.reverse);
            return { offset: t, color: `rgb(${r},${g},${b})` };
          })
        : [];
      const sparse = obsPairs.length > 0 && obsPairs.length < SPARSE_SAMPLE_LIMIT;

      const maxDepth = Math.max(
        obsPairs.length ? obsPairs[obsPairs.length - 1][1] : 0,
        modelPairs.length ? modelPairs[modelPairs.length - 1][1] : 0,
      );

      chart.setOption(
        {
          backgroundColor: "transparent",
          animation: false, // the sheet's motion grammar is a stamp, not a tween
          grid: { left: 48, right: 16, top: 34, bottom: 36 },
          textStyle: { fontFamily: MONO, color: INK_SOFT, fontSize: 10 },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: "cross", label: { show: false } },
            backgroundColor: PLATE,
            borderColor: INK,
            borderWidth: 1,
            textStyle: { color: INK, fontFamily: MONO, fontSize: 11 },
            formatter: (items: any[]) =>
              items
                .map(
                  (it) =>
                    `${it.seriesName}: ${Number(it.value[0]).toFixed(3)} ${obsUnits} @ ${Number(
                      it.value[1],
                    ).toFixed(0)} m`,
                )
                .join("<br/>"),
          },
          xAxis: {
            type: "value",
            name: obsUnits ? `${obsLabel} · ${obsUnits}` : obsLabel,
            nameLocation: "middle",
            nameGap: 20,
            nameTextStyle: {
              fontFamily: SANS,
              color: INK_SOFT,
              fontSize: 10,
              fontWeight: 700,
            },
            scale: true,
            axisLine: { lineStyle: { color: INK } },
            axisTick: { lineStyle: { color: INK } },
            splitLine: { lineStyle: { color: RULE, type: "solid", width: 1 } },
          },
          yAxis: {
            type: "value",
            // Depth increases downward. Any other orientation is wrong to an
            // oceanographer, and this is the audience that would notice.
            inverse: true,
            name: "DEPTH · M",
            // On an inverted axis "start" is the zero end, i.e. the top. Placing
            // it at "end" drops it into the x-axis title.
            nameLocation: "start",
            nameGap: 12,
            nameTextStyle: {
              fontFamily: SANS,
              color: INK_SOFT,
              fontSize: 10,
              fontWeight: 700,
              align: "left",
            },
            min: 0,
            max: Math.ceil(maxDepth / 100) * 100,
            axisLine: { lineStyle: { color: INK } },
            axisTick: { lineStyle: { color: INK } },
            splitLine: { lineStyle: { color: RULE, width: 1 } },
          },
          series: [
            {
              name: "MODEL",
              type: "line",
              data: modelPairs,
              showSymbol: false,
              lineStyle: { color: INK, width: 1.4, type: "dashed" },
              z: 2,
            },
            {
              name: "OBSERVED",
              type: "line",
              data: obsPairs,
              // Sparse parameters show their sample points: see
              // SPARSE_SAMPLE_LIMIT. The line between two BGC samples is
              // drafting, not data, and the marks say which is which.
              showSymbol: sparse,
              symbol: "circle",
              symbolSize: 3.5,
              itemStyle: { color: INK },
              lineStyle: {
                width: 2.4,
                color: gradientStops.length
                  ? {
                      type: "linear",
                      x: 0,
                      y: 0,
                      x2: 0,
                      y2: 1,
                      colorStops: gradientStops,
                    }
                  : INK,
              },
              z: 3,
              // The depth cursor, shared with the rack and the slice stack:
              // one axis, three synchronized readouts.
              markLine: {
                silent: true,
                symbol: "none",
                label: {
                  formatter: `${Math.round(p.focusDepth)} m`,
                  position: "insideEndTop",
                  color: INK,
                  fontFamily: MONO,
                  fontSize: 10,
                },
                lineStyle: { color: INK, width: 1, type: [4, 3] },
                data: [{ yAxis: p.focusDepth }],
              },
            },
          ],
        },
        { notMerge: true },
      );

      // Clicking the chart at a depth drives the same cursor the rack does.
      chart.getZr().off("click");
      chart.getZr().on("click", (e: any) => {
        const pt = [e.offsetX, e.offsetY];
        if (!chart.containPixel({ gridIndex: 0 }, pt)) return;
        const [, depth] = chart.convertFromPixel({ gridIndex: 0 }, pt);
        if (Number.isFinite(depth)) p.onFocusDepth(Math.max(0, depth));
      });

      chart.resize();
    })();

    return () => {
      disposed = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.detail, p.column, p.variable, p.units, p.palette, p.scale, p.vmin, p.vmax,
      p.reverse, p.focusDepth, param, obsUnits, obsLabel, colourMatchesScale, modelVariable]);

  // Dispose only on unmount; re-creating the chart per update would throw away
  // the canvas every time the depth cursor moves.
  useEffect(
    () => () => {
      chartRef.current?.dispose?.();
      chartRef.current = null;
    },
    [],
  );

  useEffect(() => {
    const onResize = () => chartRef.current?.resize?.();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <section
      className="sheet"
      style={{ width: "25rem", display: "flex", flexDirection: "column" }}
      aria-label="Instrument profile"
    >
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "0.5rem",
          padding: "0.625rem 0.75rem 0.5rem",
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h2
            style={{
              margin: 0,
              fontSize: "0.8125rem",
              fontWeight: 700,
              letterSpacing: "0.11em",
              textTransform: "uppercase",
              color: "var(--ink)",
            }}
          >
            {p.detail ? `${platformNoun(p.detail.platform_kind)} ${p.detail.wmo}` : "Instrument profile"}
          </h2>
          {p.detail ? (
            <p
              className="num"
              style={{ margin: "0.125rem 0 0", fontSize: "0.6875rem", color: "var(--ink-soft)" }}
            >
              {p.detail.time.replace("T", " ").replace("Z", "")} · {p.detail.lat.toFixed(3)}°N{" "}
              {p.detail.lon.toFixed(3)}°E · {p.detail.n_levels} lv
            </p>
          ) : (
            <p
              className="num"
              style={{ margin: "0.125rem 0 0", fontSize: "0.6875rem", color: "var(--ink-soft)" }}
            >
              {/* CASTS and the instruments that took them, not one number
                  called "stations". A float drifts and reports repeatedly, so
                  the two differ, and printing only the larger overstates how
                  much of the Indian Ocean observing system is in this box. */}
              {p.stationCount} cast{p.stationCount === 1 ? "" : "s"} from{" "}
              {p.platformCount} instrument{p.platformCount === 1 ? "" : "s"}
            </p>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flexShrink: 0 }}>
          {/* The Argo QC filter belongs on the observation panel, not on the
              model sheet: this is the data it actually describes. */}
          {p.detail && (
            <span className="overprint" title={p.detail.qc_policy}>
              {p.detail.platform_kind.startsWith("gdac") ? "ARGO QC 1-2" : "QC 1-2"}
            </span>
          )}
          {p.detail && (
            <button type="button" className="tick stamp" onClick={p.onClose} title="Clear selection">
              Clear
            </button>
          )}
        </div>
      </header>

      {p.detail ? (
        <>
          {/* The parameters THIS instrument served. A core float shows two and
              a BGC float up to seven, and one whose pH was entirely rejected
              shows no pH: offering a variable that draws nothing reads as a
              broken chart, so the API reports what it actually has. */}
          {available.length > 1 && (
            <div
              role="group"
              aria-label="Profile parameter"
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.25rem",
                padding: "0.4375rem 0.75rem 0",
              }}
            >
              {available.map((a) => (
                <button
                  key={a.name}
                  type="button"
                  className="tick"
                  aria-pressed={a.name === param}
                  onClick={() => setChosen(a.name)}
                  title={`${a.label}${a.units ? ` · ${a.units}` : ""} · ${a.n_values} accepted levels`}
                  /* No inline colour. `.tick[aria-pressed="true"]` already
                     inverts to ink-on-plate; overriding the colour here put
                     dark text on a dark ground and the label vanished. */
                >
                  {a.label}
                </button>
              ))}
            </div>
          )}
          <div ref={hostRef} style={{ height: "19rem", width: "100%" }} />
          <div
            style={{
              display: "flex",
              gap: "0.875rem",
              padding: "0 0.75rem 0.375rem",
              fontSize: "0.625rem",
              color: "var(--ink-soft)",
            }}
          >
            {/* The legend states the grammar: solid coloured = measured,
                dashed ink = computed. */}
            <span style={{ display: "flex", alignItems: "center", gap: "0.3125rem" }}>
              <span
                aria-hidden
                style={{
                  width: "1.25rem",
                  height: "0.1875rem",
                  // The real ramp, not an approximation of it: a legend that
                  // does not match the line it describes is a wrong legend.
                  // Ink when the line is ink, for the same reason.
                  background: colourMatchesScale
                    ? rampCss(p.palette, 24, p.reverse)
                    : "var(--ink)",
                }}
              />
              OBSERVED
            </span>
            {/* Only claimed when it is actually drawn. The INCOIS analysis has
                no chlorophyll, oxygen, nitrate or pH, so for those parameters
                there is nothing to compare against and saying so is the whole
                point. */}
            {modelVariable === p.variable ? (
              <span style={{ display: "flex", alignItems: "center", gap: "0.3125rem" }}>
                <span
                  aria-hidden
                  style={{ width: "1.25rem", borderTop: "1.4px dashed var(--ink)" }}
                />
                MODEL · nearest cell
              </span>
            ) : (
              <span style={{ color: "var(--ink-faint)" }}>
                {modelVariable
                  ? `MODEL · switch the scene to ${modelVariable} to compare`
                  : "MODEL · this analysis carries no " + (obsLabel || "").toLowerCase()}
              </span>
            )}
          </div>
          <footer
            style={{
              padding: "0.4375rem 0.75rem 0.625rem",
              borderTop: "1px solid var(--rule-soft)",
              color: "var(--ink-soft)",
            }}
          >
            {/* Printed matter in the form's face; only entered values stay
                in the typewriter. */}
            <p style={{ margin: 0, fontSize: "0.6875rem", lineHeight: 1.45 }}>
              {p.detail.qc_policy}
            </p>
            <p style={{ margin: "0.125rem 0 0", fontSize: "0.6875rem", lineHeight: 1.45 }}>
              {p.detail.citation}
            </p>
            <p
              style={{
                margin: "0.3125rem 0 0",
                fontSize: "0.625rem",
                lineHeight: 1.45,
                color: "var(--caution-ink)",
              }}
            >
              Model curve is the nearest grid cell, so no skill figure is
              claimed on this chart. The verification certificate above is the
              Class-4-style comparison, interpolated to each cast's own
              position and depth.
            </p>
          </footer>
        </>
      ) : (
        <div style={{ padding: "1rem 0.75rem 1.125rem" }}>
          {p.loading ? (
            <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--ink-soft)" }}>
              Reading cast…
            </p>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: "0.8125rem", lineHeight: 1.5, color: "var(--ink)" }}>
                Click a station mark on the globe to read its water column
                against the model.
              </p>
              {/* Prose in the form's own face. The typewriter is reserved
                  for entered values, per the rule in globals.css. */}
              <p
                style={{
                  margin: "0.5rem 0 0",
                  fontSize: "0.75rem",
                  lineHeight: 1.5,
                  color: "var(--ink-soft)",
                }}
              >
                Every mark is a real profile inside the Bay of Bengal box,
                contemporaneous with the model field, filtered to QC flags 1
                and 2. Square marks are Argo floats; a diamond is a float
                carrying biogeochemical sensors, so it also reads oxygen,
                chlorophyll, nitrate and pH.
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
