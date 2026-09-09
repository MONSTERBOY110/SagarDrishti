"use client";

/** The guided tour player (PRD F12, TRD M7).
 *
 * A tour is a list of steps: a patch to the scene, a line of narration, and
 * the evidence that line rests on. Playing one drives the SAME store the
 * controls drive, so a tour can do nothing a presenter could not do by hand,
 * and there is no second code path through the renderer to keep in step.
 *
 * WHY THIS EXISTS BEFORE THE AGENT DOES
 * -------------------------------------
 * Two reasons, and the second is the better one.
 *
 * It is the demo's safety net. A live demo where somebody has to remember
 * seven clicks under stage lights is a demo that goes wrong; press play and it
 * drives itself, with the narration on screen to read from.
 *
 * And it is the agent plane's plumbing, built and tested a phase early. TRD M4
 * gives Samudra Sahayak exactly one channel to affect the view, `set_scene`
 * with a validated patch, and this is that channel with a JSON file in front
 * of it instead of a language model. When the agent lands it inherits a patch
 * path that has already been driven in front of an audience.
 *
 * A STEP THAT CANNOT BE APPLIED SAYS SO
 * -------------------------------------
 * The keys a tour may patch are checked against the LIVE store rather than a
 * list kept in parallel with it, and an unknown key is reported on screen
 * rather than skipped. That matters more here than it looks: a step that
 * quietly no-ops is indistinguishable from a step that worked, so the tour
 * would appear to run correctly while doing nothing, in front of the people we
 * are trying to convince.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Tour, type TourStep } from "@/lib/api";
import { INITIAL_SCENE, useScene } from "@/lib/scene";

/** Everything the scene store actually holds, read from the store itself.
 *
 * Derived rather than declared, so it cannot drift from the state it is
 * describing. The server keeps its own copy of this list for validation at
 * load time; if the two ever disagree, this one is right and the mismatch
 * surfaces as a visible refusal instead of a silent no-op. */
const LIVE_KEYS = new Set(Object.keys(INITIAL_SCENE));

export default function StoryPlayer() {
  const [tours, setTours] = useState<Tour[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<Tour | null>(null);
  const [index, setIndex] = useState(0);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let live = true;
    api
      .storyboards()
      .then((r) => {
        if (!live) return;
        setTours(r.tours);
        // A tour that failed to load is a tour nobody can run, and finding
        // that out on stage is the failure. Say it here.
        if (r.refused.length > 0) {
          setProblem(
            `${r.refused.length} tour file${r.refused.length === 1 ? "" : "s"} could not be read: ` +
              r.refused.map((x) => `${x.file} (${x.reason})`).join("; "),
          );
        }
      })
      .catch(() => {
        if (live) setTours([]);
      });
    return () => {
      live = false;
    };
  }, []);

  /** Apply one step to the live scene, refusing what the store cannot hold. */
  const apply = useCallback((step: TourStep) => {
    const patch = step.patch ?? {};
    const unknown = Object.keys(patch).filter((k) => !LIVE_KEYS.has(k));
    if (unknown.length > 0) {
      setProblem(
        `This step asks to set ${unknown.join(", ")}, which this scene does not have. ` +
          "It has been skipped rather than silently ignored.",
      );
    }
    const usable: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(patch)) if (LIVE_KEYS.has(k)) usable[k] = v;
    if (Object.keys(usable).length > 0) useScene.setState(usable as never);
  }, []);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setRunning(false);
    setActive(null);
    setIndex(0);
  }, []);

  const goto = useCallback(
    (tour: Tour, i: number) => {
      if (i < 0 || i >= tour.steps.length) return;
      setIndex(i);
      apply(tour.steps[i]);
    },
    [apply],
  );

  const start = useCallback(
    (tour: Tour) => {
      setProblem(null);
      setOpen(false);
      setActive(tour);
      setRunning(true);
      goto(tour, 0);
    },
    [goto],
  );

  /* Advance on a timer while running. The hold is per step and authored,
     because a sentence about the oxygen minimum needs longer on screen than
     "watch the colour change", and the server refuses a hold nobody could read
     or sit through. */
  useEffect(() => {
    if (!active || !running) return;
    const step = active.steps[index];
    if (!step) return;
    timer.current = setTimeout(
      () => {
        if (index + 1 < active.steps.length) goto(active, index + 1);
        else setRunning(false); // hold on the last frame rather than snapping away
      },
      Math.max(1, step.hold) * 1000,
    );
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [active, running, index, goto]);

  /* Space, arrows and Escape, because a presenter's hands are on a clicker or
     a keyboard and not on a mouse. Bound only while a tour is open. */
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      if (e.key === "Escape") {
        e.preventDefault();
        stop();
      } else if (e.key === " ") {
        e.preventDefault();
        setRunning((r) => !r);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setRunning(false);
        goto(active, index + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setRunning(false);
        goto(active, index - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, index, goto, stop]);

  if (tours.length === 0 && !problem) return null;

  const step: TourStep | null = active ? active.steps[index] ?? null : null;

  return (
    <div className="tour">
      {!active && (
        <>
          <button
            type="button"
            className="tour__open"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            Guided tours
            <span className="tour__count num">{tours.length}</span>
          </button>
          {open && (
            <ul className="tour__menu">
              {tours.map((t) => (
                <li key={t.id}>
                  <button type="button" className="tour__pick" onClick={() => start(t)}>
                    <span className="tour__picktitle">{t.title}</span>
                    <span className="tour__picksub">{t.subtitle}</span>
                    <span className="tour__picklen num">
                      {t.n_steps} steps · {Math.round(t.seconds)} s ·{" "}
                      {t.audience === "classroom" ? "outreach" : "judge"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {active && step && (
        <section className="tour__stage" aria-label="Guided tour" aria-live="polite">
          <header className="tour__head">
            <span className="tour__title">{active.title}</span>
            <span className="tour__step num">
              {index + 1} of {active.steps.length}
            </span>
          </header>

          {/* The ruled progress bar, one segment per step: a presenter needs to
              know how much is left without counting. */}
          <div className="tour__ticks" aria-hidden>
            {active.steps.map((_, i) => (
              <span key={i} data-state={i < index ? "done" : i === index ? "here" : "todo"} />
            ))}
          </div>

          <p className="tour__narration">{step.narration}</p>

          {step.evidence.length > 0 && (
            <ul className="tour__evidence">
              {step.evidence.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}

          <div className="tour__controls">
            <button
              type="button"
              className="tick stamp"
              onClick={() => {
                setRunning(false);
                goto(active, index - 1);
              }}
              disabled={index === 0}
            >
              Back
            </button>
            <button
              type="button"
              className="tick stamp"
              aria-pressed={running}
              onClick={() => setRunning((r) => !r)}
            >
              {running ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              className="tick stamp"
              onClick={() => {
                setRunning(false);
                goto(active, index + 1);
              }}
              disabled={index + 1 === active.steps.length}
            >
              Next
            </button>
            <button type="button" className="tick stamp tour__end" onClick={stop}>
              End
            </button>
          </div>
        </section>
      )}

      {problem && <p className="tour__problem">{problem}</p>}
    </div>
  );
}
