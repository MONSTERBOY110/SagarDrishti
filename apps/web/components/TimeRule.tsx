"use client";

/** The time scrub, drawn as a ruled scale with one tick per available step
 *  (PS requirement F4).
 *
 * Ticks, not a continuous slider: this analysis has exactly three 10-day steps
 * and a smooth track would imply timesteps that do not exist. The control
 * states the sampling.
 */

import { useEffect } from "react";

interface Props {
  times: string[];
  /** timesteps whose field is in hand; the rest rule as pending */
  loaded: Set<string>;
  current: string;
  playing: boolean;
  onTime: (t: string) => void;
  onTogglePlay: () => void;
}

const STEP_MS = 1400;

export default function TimeRule({ times, loaded, current, playing, onTime, onTogglePlay }: Props) {
  /* -1 when the scene's time is not on THIS axis, and that is deliberately
     not clamped to 0.
       `Math.max(0, indexOf(current))` used to sit here, so a time the axis
     does not contain drew the solid "you are here" tick on the FIRST step. On
     a projector that is a scrubber pointing confidently at a date the scene is
     not showing, which is worse than pointing at nothing. It is reachable
     whenever the dataset changes before the scene time is reset to the new
     axis, and it would become routine the day a second dataset with its own
     epoch is added. */
  const index = times.indexOf(current);
  const offAxis = index < 0 && times.length > 0;

  useEffect(() => {
    if (!playing || times.length < 2) return;
    const t = setInterval(() => {
      const at = times.indexOf(current);
      // Same root cause as above: -1 made this land on step 0 and silently
      // "work", which is what hid the defect. Off the axis, play starts from
      // the beginning EXPLICITLY rather than by arithmetic accident.
      onTime(at < 0 ? times[0] : times[(at + 1) % times.length]);
    }, STEP_MS);
    return () => clearInterval(t);
  }, [playing, times, current, onTime]);

  return (
    <div
      className="sheet"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.5rem 0.75rem",
      }}
    >
      <button
        type="button"
        className="tick stamp"
        aria-pressed={playing}
        disabled={times.length < 2}
        onClick={onTogglePlay}
      >
        {playing ? "Hold" : "Run"}
      </button>

      <div style={{ flex: 1, minWidth: "12rem" }}>
        <div
          className="label label--split"
          style={{ marginBottom: "0.3125rem" }}
        >
          <span>Time · UTC</span>
          {/* Saying nothing here is how the old clamp got away with it: with no
              tick lit and no message, the rule just looked idle. */}
          {offAxis && (
            <span className="overprint" title={`Scene time ${current} is not on this axis`}>
              off axis
            </span>
          )}
        </div>
        <div
          role="radiogroup"
          aria-label="Timestep"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            borderTop: "1px solid var(--rule)",
            paddingTop: "0.25rem",
          }}
        >
          {times.map((t, i) => {
            const on = i === index;
            const pending = !loaded.has(t);
            return (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => onTime(t)}
                title={pending ? `${t} - not loaded yet` : t}
                style={{
                  background: "none",
                  border: 0,
                  padding: "0 0.25rem",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "0.1875rem",
                  color: on ? "var(--ink)" : "var(--ink-soft)",
                }}
              >
                {/* The tick carries state as rule form: a solid bar for the
                    step on screen, a hairline for one in hand, and a dashed
                    stub for a step not yet fetched. Never a colour change. */}
                <span
                  aria-hidden
                  className="stamp"
                  style={
                    pending
                      ? {
                          width: 0,
                          height: "0.4375rem",
                          borderLeft: "1px dashed var(--rule)",
                        }
                      : {
                          width: on ? "0.1875rem" : "1px",
                          height: on ? "0.6875rem" : "0.4375rem",
                          background: on ? "var(--ink)" : "var(--rule)",
                        }
                  }
                />
                <span className="num" style={{ fontSize: "0.625rem", fontWeight: on ? 700 : 400 }}>
                  {t.slice(5, 10)}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
