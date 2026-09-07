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
 * from the nearest grid cell, which is not Class-4 co-location (TRD M5), and a
 * skill figure computed that way would be indefensible in front of an INCOIS
 * oceanographer. The panel says so on screen.
 */

import { useEffect, useRef } from "react";

import { modelProfileAt, type FieldColumn, type ProfileDetail } from "@/lib/api";
import { rampCss, rgbFor, type Palette, type Scale } from "@/lib/colormap";

interface Props {
  detail: ProfileDetail | null;
  column: FieldColumn | null;
  variable: string;
  units: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  focusDepth: number;
  stationCount: number;
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

  const obs = p.detail
    ? p.variable === "SAL"
      ? p.detail.levels.psal
      : p.detail.levels.temp
    : null;

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

      const model = p.column ? modelProfileAt(p.column, p.detail.lat, p.detail.lon) : null;
      const modelPairs: [number, number][] = [];
      if (model) {
        model.depths.forEach((d, i) => {
          const v = model.values[i];
          if (v !== null && Number.isFinite(v)) modelPairs.push([v, d]);
        });
      }

      // Colour the observed line along its own length with the field's
      // colorbar, so the chart and the globe speak one colour language.
      const gradientStops = obsPairs.map((_, i) => {
        const t = obsPairs.length === 1 ? 0 : i / (obsPairs.length - 1);
        const [r, g, b] = rgbFor(obsPairs[i][0], p.vmin, p.vmax, p.palette, p.scale);
        return { offset: t, color: `rgb(${r},${g},${b})` };
      });

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
                    `${it.seriesName}: ${Number(it.value[0]).toFixed(2)} ${p.units} @ ${Number(
                      it.value[1],
                    ).toFixed(0)} m`,
                )
                .join("<br/>"),
          },
          xAxis: {
            type: "value",
            name: `${p.variable} · ${p.units}`,
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
              showSymbol: false,
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
  }, [p.detail, p.column, p.variable, p.units, p.palette, p.scale, p.vmin, p.vmax, p.focusDepth]);

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
            {p.detail ? `Argo float ${p.detail.wmo}` : "Instrument profile"}
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
              {p.stationCount} station{p.stationCount === 1 ? "" : "s"} on the globe
            </p>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flexShrink: 0 }}>
          {/* The Argo QC filter belongs on the observation panel, not on the
              model sheet: this is the data it actually describes. */}
          {p.detail && (
            <span
              className="overprint"
              title="Argo QC flags 1 and 2 only (Wong et al. 2020)"
            >
              Argo QC 1-2
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
                  background: rampCss(p.palette),
                }}
              />
              OBSERVED
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "0.3125rem" }}>
              <span
                aria-hidden
                style={{ width: "1.25rem", borderTop: "1.4px dashed var(--ink)" }}
              />
              MODEL · nearest cell
            </span>
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
              Model curve is the nearest grid cell, not Class-4 co-location. No
              skill figure is claimed here; the verified scorecard is TRD M5.
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
                Every mark is a real Argo profile inside the Bay of Bengal box,
                filtered to QC flags 1 and 2.
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
