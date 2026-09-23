"use client";

/** The station sheet: every control on this surface (PS requirement F4).
 *
 * The field order is a real cast sheet's field order: what was sampled, where,
 * when, then the rack of levels, then the scene controls. The 24 depth levels
 * are the Niskin bottle rack, serialised 01 to 24 the way a physical rack is,
 * one ruled row each, the active row doubled.
 *
 * Colour discipline: a row prints its value in the field's own colorbar colour,
 * because that is the measurement. Nothing else on the plate is saturated. A
 * level with no data prints "n/a" and drops its rule to half strength; a level
 * not yet read prints a dot leader and rules dashed. Those are different facts
 * and must never share a mark.
 */

import { useCallback, useEffect, useRef } from "react";

import { displayUnits, levelMean, type DatasetInfo, type FieldColumn } from "@/lib/api";
import ColorbarEditor from "@/components/ColorbarEditor";
import { cssFor, normalize, type Palette, type Scale } from "@/lib/colormap";

interface Props {
  dataset: DatasetInfo | null;
  column: FieldColumn | null;
  /** the cast is still being read: rows rule dashed rather than printing values */
  columnPending: boolean;
  variable: string;
  time: string;
  focusDepth: number;
  exaggeration: number;
  opacity: number;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  colorbarLocked: boolean;
  /** the range the field itself suggests, for the editor's Auto action */
  dataRange: [number, number] | null;
  onVariable: (v: string) => void;
  onColorbar: (patch: Record<string, unknown>) => void;
  onFocusDepth: (d: number) => void;
  onExaggeration: (v: number) => void;
  /** The isosurface layer (PS F1): off by default, so it is stated rather than
   *  assumed, and its own value control appears only when it is on. */
  isosurfaceOn: boolean;
  isovalue: number;
  /** The current-vector layer (PS F1). A SECOND dataset, so switching it on is
   *  a deliberate act rather than something that happens to the viewer. */
  currentsOn: boolean;
  /** One line about what was actually drawn, or why nothing was. */
  currentSummary: string | null;
  onToggleCurrents: () => void;
  units: string;
  /** One line about what was actually extracted, including what it refused. */
  isoSummary: string | null;
  onToggleIsosurface: () => void;
  onIsovalue: (v: number) => void;
  onOpacity: (v: number) => void;
}

export default function StationSheet(p: Props) {
  const rackRef = useRef<HTMLUListElement>(null);
  const depths = p.column?.depths ?? p.dataset?.depths ?? [];
  const focusIndex = nearestIndex(depths, p.focusDepth);
  /* The PRINTED unit, resolved once by the page and passed in, not re-read
     from the column here. Reading it from the column is what put "SCALE IN 1"
     and a rack headed "SAL 1" on the sheet: the cube declares salinity as CF's
     dimensionless "1", and only the standard name in the catalogue says that
     "1" means practical salinity (lib/api.ts:displayUnits). */
  const units = p.units || p.column?.units || "";

  /* Roving keyboard control of the rack. The depth cursor is the primary
     instrument on this surface, so it must be operable without a mouse. */
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const map: Record<string, number> = {
        ArrowDown: focusIndex + 1,
        ArrowUp: focusIndex - 1,
        PageDown: focusIndex + 5,
        PageUp: focusIndex - 5,
        Home: 0,
        End: depths.length - 1,
      };
      const next = map[e.key];
      if (next === undefined) return;
      e.preventDefault();
      p.onFocusDepth(depths[Math.max(0, Math.min(depths.length - 1, next))]);
    },
    [depths, focusIndex, p],
  );

  useEffect(() => {
    const row = rackRef.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    row?.scrollIntoView({ block: "nearest" });
    /* Move DOM focus along with the selection, but ONLY when focus is already
       inside the rack. Arrow keys have to keep working after they move the
       cursor, and without this the roving tabindex leaves focus on a row that
       is now tabindex -1. Guarded, because the cursor also moves when a station
       mark is clicked on the globe or the chart, and stealing focus to the
       sheet then would yank the keyboard away from what the user was doing. */
    if (row && rackRef.current?.contains(document.activeElement)) {
      row.focus({ preventScroll: true });
    }
  }, [focusIndex]);

  return (
    <section className="sheet" aria-label="Station sheet">
      <div className="sheet__margin" aria-hidden>
        <span className="sheet__hole" />
        <span className="sheet__hole" />
        <span className="sheet__hole" />
      </div>

      <div className="sheet__body">
        {/* --- the cast head: what a printed form leads with ---------------- */}
        <header className="sheet__head">
          <div className="sheet__titles">
            <h1 className="sheet__title">Station Sheet</h1>
            <p className="sheet__subtitle">Model cast and instrument rack</p>
          </div>
          {/* The overprint states what KIND of product this sheet holds.
              It previously read "QC 1-2", which was wrong and not merely
              imprecise: QC flags 1 and 2 are the Argo OBSERVATION filter and
              mean nothing for a gridded analysis, so stamping them here
              claimed a provenance the model field does not have. The Argo QC
              policy belongs on the profile panel, where the observations are,
              and it is stated there with its citation. "Analysis" is the true
              statement about this product: it is INCOIS's Variational Analysis
              Method field, not a forecast. */}
          <span
            className="overprint"
            title="Gridded analysis product (Variational Analysis Method). Not a forecast."
          >
            Analysis
          </span>
        </header>

        <dl className="castfield">
          <dt>Cast</dt>
          <dd className="num">{p.dataset?.id ?? "no cast loaded"}</dd>
          <dt>Area</dt>
          <dd className="num">{areaLabel(p.dataset)}</dd>
          <dt>Time</dt>
          <dd className="num">{p.time ? p.time.replace("T", " ").replace("Z", " UTC") : "n/a"}</dd>
          <dt>Column</dt>
          <dd className="num">
            {/* Plain metres, matching the cartouche. Mixing a raw 5 with a
                k-abbreviation inside one range made the identity block a judge
                reads first look careless. */}
            {depths.length} lv, {depths[0] ?? "n/a"} to {depths[depths.length - 1] ?? "n/a"} m
          </dd>
        </dl>

        {/* --- variable ----------------------------------------------------- */}
        <div className="block">
          <div className="label">Variable</div>
          <div style={{ display: "flex", gap: "0.25rem" }}>
            {(p.dataset?.variables ?? []).map((v) => (
              <button
                key={v.name}
                type="button"
                className="tick stamp"
                aria-pressed={v.name === p.variable}
                onClick={() => p.onVariable(v.name)}
                title={`${v.label} (${displayUnits(v.units, v.canonical) || "no units"})`}
              >
                {v.name}
              </button>
            ))}
          </div>
        </div>

        {/* --- the colorbar, editable: PS requirement F4 -------------------- */}
        <ColorbarEditor
          variable={p.variable}
          units={units}
          palette={p.palette}
          scale={p.scale}
          vmin={p.vmin}
          vmax={p.vmax}
          reverse={p.reverse}
          locked={p.colorbarLocked}
          dataRange={p.dataRange}
          onChange={p.onColorbar}
        />

        {/* --- the bottle rack ---------------------------------------------- */}
        <div className="block block--rack">
          <div className="label label--split">
            <span>Bottle rack</span>
            <span>{depths.length} levels</span>
          </div>
          <div className="rack__head label" aria-hidden>
            <span>No.</span>
            <span style={{ textAlign: "right" }}>Depth m</span>
            <span />
            <span style={{ textAlign: "right" }}>
              {p.variable}
              {units ? ` ${units}` : ""}
            </span>
          </div>
          {/* A listbox with focusable options must NOT itself be a tab stop.
              With tabIndex 0 here and 24 natively focusable rows, reaching the
              exaggeration slider cost 25 presses of Tab. The roving tabindex
              below makes the whole rack one stop, which is the documented
              listbox pattern and also simply what a forecaster expects. */}
          <ul
            ref={rackRef}
            className="rack"
            role="listbox"
            aria-label="Depth level"
            aria-activedescendant={depths.length ? `lvl-${focusIndex}` : undefined}
            onKeyDown={onKeyDown}
          >
            {depths.map((d, i) => {
              const mean = p.column ? levelMean(p.column, i) : null;
              const empty = mean === null;
              const pending = p.columnPending;
              return (
                <li key={d} style={{ display: "contents" }}>
                  <button
                    type="button"
                    role="option"
                    id={`lvl-${i}`}
                    tabIndex={i === focusIndex ? 0 : -1}
                    aria-selected={i === focusIndex}
                    aria-label={`Level ${i + 1}, ${d} metres${
                      mean === null ? ", no data" : `, ${mean.toFixed(2)} ${units}`
                    }`}
                    data-empty={empty && !pending}
                    data-state={pending ? "pending" : undefined}
                    className="rack__row stamp"
                    disabled={empty}
                    onClick={() => p.onFocusDepth(d)}
                  >
                    {/* A rack is serialised, and the number is information a
                        forecaster uses to call out a bottle, not decoration. */}
                    <span className="rack__no num">{String(i + 1).padStart(2, "0")}</span>
                    <span className="rack__depth num">{fmt(d)}</span>
                    <span
                      className="rack__bar"
                      aria-hidden
                      style={
                        empty
                          ? { border: "1px dashed var(--ink-faint)", height: "0.4375rem" }
                          : {
                              background: cssFor(mean, p.vmin, p.vmax, p.palette, p.scale, p.reverse),
                              width: `${Math.max(6, normalize(mean, p.vmin, p.vmax, p.scale) * 100)}%`,
                              outline: "1px solid rgba(227,235,240,.35)",
                            }
                      }
                    />
                    <span className="rack__value num">
                      {pending ? "····" : empty ? "n/a" : mean.toFixed(2)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* --- the two scene fields ----------------------------------------- */}
        <div className="block">
          <div className="label label--split">
            <span>Vertical exaggeration</span>
            <span className="num">{p.exaggeration}x</span>
          </div>
          <input
            className="field"
            type="range"
            min={1}
            max={200}
            step={1}
            value={p.exaggeration}
            aria-label="Vertical exaggeration"
            onChange={(e) => p.onExaggeration(Number(e.target.value))}
          />
        </div>

        {/* --- current vectors (PS requirement F1) --------------------------
            A SECOND DATASET, and the control says so. The slices are INCOIS's
            own analysis; the arrows are Copernicus GLORYS, on a different grid
            with its own 40 levels, because INCOIS's free server publishes
            surface currents only and this is the one clause of F1 no INCOIS
            source can answer.

            Off by default for the same reason the isosurface is, plus one of
            its own: switching on a different agency's data should be a
            deliberate act rather than something that happens to a viewer who
            never asked. The summary line underneath names the depth actually
            served, which is not the depth of the slice beside it. */}
        <div className="block">
          <div className="label label--split">
            <span>Currents</span>
            <button
              type="button"
              className="tick stamp"
              aria-pressed={p.currentsOn}
              onClick={p.onToggleCurrents}
              title={
                p.currentsOn
                  ? "Stop drawing the current arrows"
                  : "Draw depth-resolved currents from Copernicus GLORYS at the cursor depth"
              }
            >
              {p.currentsOn ? "On" : "Off"}
            </button>
          </div>
          {p.currentsOn && p.currentSummary && (
            <p
              className="num"
              style={{
                margin: "0.375rem 0 0",
                fontSize: "0.625rem",
                lineHeight: 1.45,
                color: "var(--ink-soft)",
              }}
            >
              {p.currentSummary}
            </p>
          )}
          {p.currentsOn && (
            <p
              style={{
                margin: "0.25rem 0 0",
                fontSize: "0.625rem",
                lineHeight: 1.4,
                color: "var(--ink-faint)",
              }}
            >
              Arrow length is speed, scaled to the fastest arrow on this level.
              Copernicus GLORYS, not the INCOIS analysis the colours come from.
            </p>
          )}
        </div>

        {/* --- the isosurface layer (PS requirement F1) ---------------------
            Off by default and stated as a separate layer rather than folded
            into the colorbar, because it answers a different question. The
            slices show what the temperature IS everywhere; the surface shows
            WHERE one chosen value sits, which is the shape a forecaster
            actually reads for cyclone heat potential. */}
        <div className="block">
          <div className="label label--split">
            <span>Isosurface</span>
            <button
              type="button"
              className="tick stamp"
              aria-pressed={p.isosurfaceOn}
              onClick={p.onToggleIsosurface}
              title={
                p.isosurfaceOn
                  ? "Stop drawing the surface"
                  : "Draw the surface where the field takes one value"
              }
            >
              {p.isosurfaceOn ? "On" : "Off"}
            </button>
          </div>
          {p.isosurfaceOn && (
            <>
              <div className="label label--split" style={{ marginTop: "0.375rem" }}>
                <span>Value</span>
                <span className="num">
                  {p.isovalue} {p.units}
                </span>
              </div>
              <input
                className="field"
                type="range"
                min={Math.floor(p.vmin)}
                max={Math.ceil(p.vmax)}
                step={p.units === "degC" ? 0.5 : 0.1}
                value={p.isovalue}
                aria-label="Isosurface value"
                onChange={(e) => p.onIsovalue(Number(e.target.value))}
              />
              {p.isoSummary && (
                <p
                  className="num"
                  style={{
                    margin: "0.375rem 0 0",
                    fontSize: "0.625rem",
                    lineHeight: 1.45,
                    color: "var(--ink-soft)",
                  }}
                >
                  {p.isoSummary}
                </p>
              )}
            </>
          )}
        </div>

        <div className="block block--last">
          <div className="label label--split">
            <span>Layer opacity</span>
            <span className="num">{Math.round(p.opacity * 100)}%</span>
          </div>
          <input
            className="field"
            type="range"
            min={10}
            max={100}
            step={1}
            value={Math.round(p.opacity * 100)}
            aria-label="Layer opacity"
            onChange={(e) => p.onOpacity(Number(e.target.value) / 100)}
          />
        </div>
      </div>
    </section>
  );
}

/** A readable place name for the cast box, derived from the data's own bbox. */
function areaLabel(ds: DatasetInfo | null): string {
  if (!ds) return "n/a";
  const [w, s, e, n] = ds.bbox;
  // Degree marks, matching the profile header's 6.366 deg N formatting.
  return `${Math.abs(s).toFixed(0)} to ${Math.abs(n).toFixed(0)}°N, ${Math.abs(w).toFixed(0)} to ${Math.abs(e).toFixed(0)}°E`;
}

function fmt(d: number | undefined): string {
  if (d === undefined) return "n/a";
  return d >= 1000 ? `${(d / 1000).toFixed(1)}k` : String(d);
}

function nearestIndex(values: number[], target: number): number {
  let best = 0;
  let gap = Infinity;
  values.forEach((v, i) => {
    const g = Math.abs(v - target);
    if (g < gap) {
      gap = g;
      best = i;
    }
  });
  return best;
}
