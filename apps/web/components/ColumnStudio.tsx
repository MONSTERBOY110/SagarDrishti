"use client";

/** The water column of ONE cast, opened full width, with the model checked
 *  against it in the same picture.
 *
 * WHY THIS AND NOT A SPINNING CUBE. The obvious answer to "show the water
 * column" is a rotatable 3D block, and it looks superb in a thumbnail. It
 * also shows exactly what a flat colour ramp shows, from a worse angle, and
 * it cannot answer the only question a forecaster actually has at a station:
 * is the model right here? This view puts the measured profile and the model
 * profile on one depth axis and SHADES THE GAP BETWEEN THEM, so the error is
 * the thing with area on screen rather than a number in a corner.
 *
 * WHAT IS DRAWN, AND WHERE EVERY NUMBER CAME FROM.
 *   - The strip on the left is the model column at this cast's own grid cell,
 *     coloured with the scene's colorbar, so the studio and the globe cannot
 *     disagree about what a colour means.
 *   - The solid line is the instrument. The dashed line is the model at the
 *     nearest cell, by the same `modelProfileAt` the profile panel uses; one
 *     function, so the two views cannot drift.
 *   - The shaded band between them is observed minus model, drawn, not
 *     computed into a headline. No statistic is invented in this component.
 *   - The Class-4 figure in the readout is the SERVER'S, for the depth band
 *     the cursor is in, and it is labelled as covering the whole dataset
 *     rather than this one cast, because that is what the endpoint returns.
 *
 * IT IS INERT UNTIL OPENED, and it renders nothing at all without a cast and
 * a model column. A panel that half-draws during a demo is worse than a panel
 * that is not there.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { api, modelProfileAt, type FieldColumn, type ProfileDetail, type Scorecard } from "@/lib/api";
import { rgbFor, type Palette, type Scale } from "@/lib/colormap";

/** Water masses, as an oceanographer reads a tropical column. The thermocline
 *  band is the one that matters and its top is taken from the D26 field when
 *  the scene has it, rather than being asserted. */
const BANDS: { top: number; bottom: number; name: string }[] = [
  { top: 0, bottom: 50, name: "Mixed layer" },
  { top: 50, bottom: 200, name: "Thermocline" },
  { top: 200, bottom: 1000, name: "Intermediate" },
  { top: 1000, bottom: 2000, name: "Deep water" },
];

type Pair = { depth: number; obs: number | null; mod: number | null };

export default function ColumnStudio({
  detail,
  column,
  variableLabel,
  units,
  palette,
  scale,
  vmin,
  vmax,
  reverse,
  sourceId,
  variable,
  observed,
  onClose,
}: {
  detail: ProfileDetail | null;
  column: FieldColumn | null;
  variableLabel: string;
  units: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  /** Which dataset and variable the Class-4 card is asked for. The card
   *  itself is fetched here rather than threaded through the page: it is one
   *  small document, it is only wanted while this is open, and it is never
   *  recomputed locally, because a second implementation of a published
   *  statistic is a second answer. */
  sourceId: string | null;
  variable: string;
  observed: string;
  onClose: () => void;
}) {
  const [cursor, setCursor] = useState<number | null>(null);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const plotRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!sourceId) return;
    let cancelled = false;
    (async () => {
      try {
        const card = await api.scorecard(sourceId, variable, observed);
        if (!cancelled) setScorecard(card);
      } catch {
        // A missing card costs the depth-band readout and nothing else. The
        // column, both curves and the residual are all still drawn.
        if (!cancelled) setScorecard(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sourceId, variable, observed]);

  // Escape closes it, because a full-width overlay with only a mouse target
  // is a trap on a stage where the pointer is being shared.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const model = useMemo(
    () => (column && detail ? modelProfileAt(column, detail.lat, detail.lon) : null),
    [column, detail],
  );

  /** One row per MODEL level, with the instrument's own reading interpolated
   *  onto it. Interpolating the observation to the model's levels rather than
   *  the other way round is deliberate: the model has 24 levels and this
   *  glider dive has 7, so sampling the model at the instrument's depths
   *  would throw away most of the column that is being judged. */
  const rows: Pair[] = useMemo(() => {
    if (!model || !detail) return [];
    const od = detail.levels.depth ?? [];
    // The column the scene is SCORED against, never a hardcoded one: with
    // the globe on salinity, plotting temperature here against a salinity
    // model would draw a residual between two different quantities.
    const ov = ((detail.levels as Record<string, (number | null)[]>)[observed] ?? []) as
      (number | null)[];
    const pts: [number, number][] = [];
    for (let i = 0; i < od.length; i++) {
      const v = ov[i];
      if (v !== null && v !== undefined && Number.isFinite(v)) pts.push([od[i], v]);
    }
    return model.depths.map((d, i) => {
      const m = model.values[i];
      return { depth: d, mod: m !== null && Number.isFinite(m) ? m : null, obs: interp(pts, d) };
    });
  }, [model, detail, observed]);

  const usable = rows.filter((r) => r.obs !== null || r.mod !== null);
  if (!detail || !model || usable.length === 0) return null;

  // --- plot geometry -------------------------------------------------------
  const W = 560;
  const H = 520;
  const PAD = { l: 52, r: 18, t: 18, b: 34 };
  const maxDepth = Math.max(...usable.map((r) => r.depth));
  const vals = usable.flatMap((r) => [r.obs, r.mod]).filter((v): v is number => v !== null);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 1;
  const x = (v: number) =>
    PAD.l + ((v - (lo - pad)) / (hi + pad - (lo - pad))) * (W - PAD.l - PAD.r);
  const y = (d: number) => PAD.t + (d / maxDepth) * (H - PAD.t - PAD.b);

  const obsPts = usable.filter((r) => r.obs !== null);
  const modPts = usable.filter((r) => r.mod !== null);
  const both = usable.filter((r) => r.obs !== null && r.mod !== null);

  const line = (pts: Pair[], pick: (r: Pair) => number | null) =>
    pts.map((r, i) => `${i ? "L" : "M"}${x(pick(r)!).toFixed(1)},${y(r.depth).toFixed(1)}`).join(" ");

  // The residual band: down the observed side, back up the model side.
  const band =
    both.length > 1
      ? `${both.map((r, i) => `${i ? "L" : "M"}${x(r.obs!).toFixed(1)},${y(r.depth).toFixed(1)}`).join(" ")} ` +
        `${both
          .slice()
          .reverse()
          .map((r) => `L${x(r.mod!).toFixed(1)},${y(r.depth).toFixed(1)}`)
          .join(" ")} Z`
      : "";

  const at = cursor === null ? null : nearestRow(usable, cursor);
  const bandAt =
    at && scorecard
      ? scorecard.by_depth.find((b) => at.depth >= b.depth_min && at.depth <= b.depth_max) ?? null
      : null;

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = plotRef.current?.getBoundingClientRect();
    if (!r) return;
    const py = ((e.clientY - r.top) / r.height) * H;
    setCursor(((py - PAD.t) / (H - PAD.t - PAD.b)) * maxDepth);
  };

  return (
    <div className="studio" role="dialog" aria-modal="true" aria-label="Water column studio">
      <div className="studio__sheet sheet">
        <header className="studio__head">
          <div>
            <h2 className="studio__title">Water column studio</h2>
            <p className="studio__sub">
              {detail.platform_kind} {detail.wmo} &middot; {detail.lat.toFixed(2)}&deg;N{" "}
              {detail.lon.toFixed(2)}&deg;E &middot; {detail.time.slice(0, 10)} &middot;{" "}
              {detail.n_levels} levels
            </p>
          </div>
          <button type="button" className="tick studio__close" onClick={onClose}>
            Close
          </button>
        </header>

        <div className="studio__body">
          {/* The model column, coloured by the scene's own colorbar. */}
          <div className="studio__strip" aria-hidden>
            {usable.map((r, i) => {
              const next = usable[i + 1];
              const h = ((next ? next.depth - r.depth : 0) / maxDepth) * 100;
              if (r.mod === null || h <= 0) return null;
              const [cr, cg, cb] = rgbFor(r.mod, vmin, vmax, palette, scale, reverse);
              return (
                <div
                  key={r.depth}
                  style={{ height: `${h}%`, background: `rgb(${cr},${cg},${cb})` }}
                />
              );
            })}
          </div>

          <div className="studio__bands" aria-hidden>
            {BANDS.filter((b) => b.top < maxDepth).map((b) => {
              const bottom = Math.min(b.bottom, maxDepth);
              const pct = ((bottom - b.top) / maxDepth) * 100;
              return (
                <div
                  key={b.name}
                  className="studio__band"
                  style={{ top: `${(b.top / maxDepth) * 100}%`, height: `${pct}%` }}
                >
                  {/* On a 2000 m axis the mixed layer is 2.5 per cent of the
                      height, so its label and the thermocline's landed on top
                      of each other. The rule still marks the boundary; only
                      the text needs room to exist. */}
                  {pct >= 7 && (
                    <>
                      <span>{b.name}</span>
                      <span className="num">
                        {b.top} to {bottom} m
                      </span>
                    </>
                  )}
                </div>
              );
            })}
          </div>

          <svg
            ref={plotRef}
            className="studio__plot"
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            onMouseMove={onMove}
            onMouseLeave={() => setCursor(null)}
            role="img"
            aria-label={`${variableLabel} against depth: the instrument, the model, and the difference between them`}
          >
            {[0, 0.25, 0.5, 0.75, 1].map((f) => (
              <g key={f}>
                <line
                  x1={PAD.l}
                  x2={W - PAD.r}
                  y1={y(maxDepth * f)}
                  y2={y(maxDepth * f)}
                  className="studio__grid"
                />
                <text x={PAD.l - 8} y={y(maxDepth * f) + 3} className="studio__tick">
                  {Math.round(maxDepth * f)}
                </text>
              </g>
            ))}

            {band && <path d={band} className="studio__resid" />}
            {modPts.length > 1 && <path d={line(modPts, (r) => r.mod)} className="studio__model" />}
            {obsPts.length > 1 && <path d={line(obsPts, (r) => r.obs)} className="studio__obs" />}
            {obsPts.length <= 1 &&
              obsPts.map((r) => (
                <circle key={r.depth} cx={x(r.obs!)} cy={y(r.depth)} r={3} className="studio__dot" />
              ))}

            {at && (
              <line
                x1={PAD.l}
                x2={W - PAD.r}
                y1={y(at.depth)}
                y2={y(at.depth)}
                className="studio__cursor"
              />
            )}
            <text x={W / 2} y={H - 8} className="studio__axis">
              {variableLabel}
              {units ? ` · ${units}` : ""}
            </text>
          </svg>

          <div className="studio__read">
            <div className="studio__key">
              <span className="studio__swatch studio__swatch--obs" /> measured
              <span className="studio__swatch studio__swatch--mod" /> model
              <span className="studio__swatch studio__swatch--res" /> difference
            </div>

            {at ? (
              <dl className="studio__dl">
                <dt>Depth</dt>
                <dd className="num">{at.depth.toFixed(0)} m</dd>
                <dt>Measured</dt>
                <dd className="num">{at.obs === null ? "no reading" : at.obs.toFixed(3)}</dd>
                <dt>Model</dt>
                <dd className="num">{at.mod === null ? "no cell" : at.mod.toFixed(3)}</dd>
                <dt>Difference</dt>
                <dd className="num">
                  {at.obs === null || at.mod === null
                    ? "not comparable"
                    : `${(at.obs - at.mod >= 0 ? "+" : "") + (at.obs - at.mod).toFixed(3)} ${units}`}
                </dd>
              </dl>
            ) : (
              <p className="studio__hint">Move down the column to read it.</p>
            )}

            {bandAt && (
              <div className="studio__class4">
                <span className="studio__c4head">
                  Class-4, {bandAt.depth_min} to {bandAt.depth_max} m
                </span>
                <dl className="studio__dl">
                  <dt>Bias</dt>
                  <dd className="num">{fmt(bandAt.bias)}</dd>
                  <dt>RMSE</dt>
                  <dd className="num">{fmt(bandAt.rmse)}</dd>
                  <dt>Pairs</dt>
                  <dd className="num">{bandAt.n}</dd>
                </dl>
                {/* Said plainly, because the number beside a single cast
                    invites being read as that cast's own error. */}
                <p className="studio__caveat">
                  Across every cast in this box at this depth, not this one
                  alone. The shaded band above is this cast.
                </p>
              </div>
            )}

            <p className="studio__cite">
              Model: {model.cellLat.toFixed(2)}, {model.cellLon.toFixed(2)} nearest cell.{" "}
              {detail.qc_policy}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/** A depth band with no pairs in it has no statistic, and printing 0.000
 *  there would be a number nobody computed. */
function fmt(v: number | null | undefined): string {
  return v === null || v === undefined || !Number.isFinite(v) ? "no pairs" : v.toFixed(3);
}

/** Linear interpolation of the instrument onto a model depth, and NOTHING
 *  outside the range it actually measured. Extrapolating a glider that
 *  stopped at 900 m down to 2000 m would invent water. */
function interp(pts: [number, number][], d: number): number | null {
  if (pts.length === 0) return null;
  if (d < pts[0][0] || d > pts[pts.length - 1][0]) return null;
  for (let i = 1; i < pts.length; i++) {
    const [d0, v0] = pts[i - 1];
    const [d1, v1] = pts[i];
    if (d <= d1) {
      if (d1 === d0) return v1;
      return v0 + ((v1 - v0) * (d - d0)) / (d1 - d0);
    }
  }
  return null;
}

function nearestRow(rows: Pair[], depth: number): Pair {
  let best = rows[0];
  let gap = Infinity;
  for (const r of rows) {
    const g = Math.abs(r.depth - depth);
    if (g < gap) {
      gap = g;
      best = r;
    }
  }
  return best;
}
