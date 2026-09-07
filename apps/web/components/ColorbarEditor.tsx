"use client";

/** The colorbar editor (PS requirement F4: "Customizable Colorbar & Variable
 *  Controls", specified in PRD F4 as palette, min/max, log/linear).
 *
 * Built as an ink-sample block on the sheet, because that is what it is: a
 * printer's form choosing which ink the field is set in, and between which two
 * values. The palettes are shown as ramps rather than named in a dropdown, for
 * two reasons. A native select is a browser surface with no place in this world,
 * and more importantly a palette is a scientific choice, not a preference: a
 * diverging ramp on an absolute field misreads the data, so the editor states
 * what each ramp is for and warns when a diverging one is put on an absolute
 * field.
 *
 * Two honesty rules the control must not break:
 *   - Editing a limit LOCKS the range. Auto-derivation would otherwise recompute
 *     it on the next timestep and change the colours under a value the reader
 *     has already interpreted.
 *   - A log scale needs a strictly positive minimum. Rather than throw and blank
 *     the scene, the editor moves to the nearest legal range and says on screen
 *     that it did. A silently clamped axis is a lying axis.
 */

import { useEffect, useState } from "react";

import {
  PALETTE_DIVERGING,
  PALETTE_USE,
  legalRange,
  rampCss,
  type Palette,
  type Scale,
} from "@/lib/colormap";

interface Props {
  variable: string;
  units: string;
  palette: Palette;
  scale: Scale;
  vmin: number;
  vmax: number;
  reverse: boolean;
  locked: boolean;
  /** the range the data itself suggests, for the reset action */
  dataRange: [number, number] | null;
  onChange: (patch: {
    palette?: Palette;
    scale?: Scale;
    vmin?: number;
    vmax?: number;
    reverse?: boolean;
    colorbarLocked?: boolean;
  }) => void;
}

/* Derived from PALETTE_USE rather than from the LUT map, so the editor lists
   exactly the palettes that have a documented purpose. A ramp nobody can say
   what it is for has no business in a scientific control. */
const NAMES = Object.keys(PALETTE_USE) as Palette[];

export default function ColorbarEditor(p: Props) {
  const [open, setOpen] = useState(false);
  // Free text while typing, so a half-entered "-" or "1." is not rejected
  // mid-keystroke and the caret does not jump.
  const [loText, setLoText] = useState(String(p.vmin));
  const [hiText, setHiText] = useState(String(p.vmax));
  /* Whether the LAST action had to move the range to keep it legal.
     This has to be remembered, not recomputed: once the clamp is applied the
     range IS legal, so asking "is the current range legal" always answers yes
     and the notice never shows. That was a real bug, and it was the exact
     silent clamp the honesty rule in this file's header forbids. */
  const [adjusted, setAdjusted] = useState(false);

  useEffect(() => {
    setLoText(String(p.vmin));
    setHiText(String(p.vmax));
  }, [p.vmin, p.vmax]);

  const commit = (which: "vmin" | "vmax", text: string) => {
    const n = Number(text);
    if (!Number.isFinite(n)) {
      setLoText(String(p.vmin));
      setHiText(String(p.vmax));
      return;
    }
    const next = which === "vmin" ? { vmin: n, vmax: p.vmax } : { vmin: p.vmin, vmax: n };
    if (next.vmax <= next.vmin) {
      // A zero-width or inverted range paints the whole ocean one colour.
      setLoText(String(p.vmin));
      setHiText(String(p.vmax));
      return;
    }
    const legal = legalRange(next.vmin, next.vmax, p.scale);
    setAdjusted(legal.adjusted);
    p.onChange({ vmin: legal.vmin, vmax: legal.vmax, colorbarLocked: true });
  };

  const setScale = (scale: Scale) => {
    const legal = legalRange(p.vmin, p.vmax, scale);
    // A linear scale can represent anything, so leaving log clears the notice.
    setAdjusted(scale === "log" ? legal.adjusted : false);
    p.onChange({
      scale,
      vmin: legal.vmin,
      vmax: legal.vmax,
      colorbarLocked: legal.adjusted ? true : p.locked,
    });
  };

  const logAdjusted = p.scale === "log" && adjusted;
  const divergingOnAbsolute = PALETTE_DIVERGING[p.palette];

  return (
    <div className="block">
      <div className="label label--split">
        <span>Scale{p.units ? ` in ${p.units}` : ""}</span>
        <button
          type="button"
          className="tick stamp"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          title="Edit the palette, the limits and the scale"
        >
          {open ? "Close" : "Edit"}
        </button>
      </div>

      <div
        className="ramp"
        style={{ background: rampCss(p.palette, 24, p.reverse) }}
        role="img"
        aria-label={`${p.palette} ramp from ${p.vmin} to ${p.vmax} ${p.units}, ${p.scale} scale`}
      />
      <div className="ramp__ends num">
        <span>{fmt(p.vmin)}</span>
        <span style={{ color: "var(--ink-faint)" }}>
          {p.scale === "log" ? "log" : "linear"}
          {p.reverse ? ", reversed" : ""}
          {p.locked ? ", held" : ""}
        </span>
        <span>{fmt(p.vmax)}</span>
      </div>

      {open && (
        <div className="cbar">
          {/* --- the limits ------------------------------------------------ */}
          <div className="cbar__row">
            <label className="cbar__field">
              <span className="cbar__key">Min</span>
              <input
                className="num cbar__input"
                inputMode="decimal"
                value={loText}
                onChange={(e) => setLoText(e.target.value)}
                onBlur={() => commit("vmin", loText)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commit("vmin", loText);
                }}
              />
            </label>
            <label className="cbar__field">
              <span className="cbar__key">Max</span>
              <input
                className="num cbar__input"
                inputMode="decimal"
                value={hiText}
                onChange={(e) => setHiText(e.target.value)}
                onBlur={() => commit("vmax", hiText)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commit("vmax", hiText);
                }}
              />
            </label>
          </div>

          {/* --- scale, direction, reset ----------------------------------- */}
          <div className="cbar__row">
            <div style={{ display: "flex", gap: "0.25rem" }}>
              {(["linear", "log"] as Scale[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  className="tick stamp"
                  aria-pressed={p.scale === s}
                  onClick={() => setScale(s)}
                  title={
                    s === "log"
                      ? "Log scale, for fields read over orders of magnitude such as chlorophyll"
                      : "Linear scale"
                  }
                >
                  {s}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: "0.25rem" }}>
              <button
                type="button"
                className="tick stamp"
                aria-pressed={p.reverse}
                onClick={() => p.onChange({ reverse: !p.reverse })}
                title="Reverse the ramp direction"
              >
                Flip
              </button>
              <button
                type="button"
                className="tick stamp"
                disabled={!p.dataRange}
                onClick={() => {
                  if (!p.dataRange) return;
                  setAdjusted(false);
                  p.onChange({
                    vmin: p.dataRange[0],
                    vmax: p.dataRange[1],
                    colorbarLocked: false,
                  });
                }}
                title={
                  p.dataRange
                    ? `Return to the range the data suggests, ${fmt(p.dataRange[0])} to ${fmt(p.dataRange[1])}, and follow it again`
                    : "No field loaded"
                }
              >
                Auto
              </button>
            </div>
          </div>

          {/* --- the ink samples ------------------------------------------- */}
          <div className="cbar__key" style={{ marginTop: "0.375rem" }}>
            Ink
          </div>
          <ul className="cbar__inks">
            {NAMES.map((name) => (
              <li key={name}>
                <button
                  type="button"
                  className="cbar__ink stamp"
                  aria-pressed={name === p.palette}
                  onClick={() => p.onChange({ palette: name })}
                  title={`For ${PALETTE_USE[name]}`}
                >
                  <span
                    className="cbar__inkramp"
                    aria-hidden
                    style={{ background: rampCss(name, 16, p.reverse) }}
                  />
                  <span className="cbar__inkname">{name}</span>
                  <span className="cbar__inkuse">{PALETTE_USE[name]}</span>
                </button>
              </li>
            ))}
          </ul>

          {/* --- errata: stated, never silent ------------------------------ */}
          {(logAdjusted || divergingOnAbsolute) && (
            <p className="cbar__errata">
              {logAdjusted
                ? `A log scale needs a positive minimum, so the range was moved to the nearest legal one, now ${fmt(p.vmin)} to ${fmt(p.vmax)}. `
                : ""}
              {divergingOnAbsolute
                ? "This is a diverging ramp. It carries a meaningful midpoint, so it belongs on an anomaly or a model minus observation residual rather than on an absolute field."
                : ""}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function fmt(v: number): string {
  if (!Number.isFinite(v)) return "n/a";
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.01 || a >= 100000)) return v.toExponential(1);
  return a >= 100 ? v.toFixed(0) : v.toFixed(a < 1 ? 3 : 1);
}
