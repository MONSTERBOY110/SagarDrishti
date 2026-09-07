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
  const index = Math.max(0, times.indexOf(current));

  useEffect(() => {
    if (!playing || times.length < 2) return;
    const t = setInterval(() => {
      onTime(times[(times.indexOf(current) + 1 + times.length) % times.length]);
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
        <div className="label" style={{ marginBottom: "0.3125rem" }}>
          Time · UTC
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
