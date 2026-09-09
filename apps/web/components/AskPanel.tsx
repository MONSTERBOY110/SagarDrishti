"use client";

/** Samudra Sahayak: ask the scene a question (PRD F8, TRD M4).
 *
 * Three things this panel does that a chat box would not, and each is the
 * reason it exists in this form.
 *
 * IT SHOWS THE WORKING. Every answer arrives with the tool calls that produced
 * it, and they are printed. TRD M4 asks for a panel where judges can watch it
 * think; the deeper reason is that an answer whose working is visible is one a
 * reviewer can disagree with, and an answer without it has to be taken on
 * trust. This is the only surface in the product where a sentence is composed
 * rather than measured, so it is the one that owes the most evidence.
 *
 * IT SAYS WHAT PRODUCED IT. Every response carries `planner`, and it is
 * printed verbatim. Today it reads "rules", because there is no language model
 * in the loop: the planner is a deterministic router over the tools. An
 * audience that assumes an LLM is reasoning when a regular expression is
 * matching has been misled, and being found out is worse than being modest.
 *
 * IT DISAPPEARS WHEN THE AGENT IS NOT RUNNING. The agent is a separate service
 * (TRD section 6.5: "kill the agent and every P0 still passes"), so this panel
 * probes it once and renders nothing at all if it is absent. That is the
 * property demonstrated rather than described: stop one process and the tool
 * carries on, minus one panel, with no broken control left behind.
 */

import { useEffect, useRef, useState } from "react";

import { agent, type AgentAnswer } from "@/lib/agent";
import { useScene } from "@/lib/scene";

/** Questions worth putting in front of someone who has never seen this.
 *
 * Not a feature list: each one exercises a different tool and lands on a
 * different part of the screen, so clicking through them IS a demo. */
const SUGGESTIONS = [
  "How warm is it at 100 m?",
  "How good is the model?",
  "Are there any warnings?",
  "Show me float 2903831",
];

export default function AskPanel() {
  const [up, setUp] = useState<boolean | null>(null);
  const [note, setNote] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AgentAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const box = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let live = true;
    agent
      .healthz()
      .then((h) => {
        if (!live) return;
        setUp(true);
        // Printed, not inferred. If the agent is up but the data plane under
        // it is not, every answer will be an apology and the cause should be
        // one glance away rather than a mystery on stage.
        setNote(h.api_reachable ? h.llm_note : `The data plane is unreachable: ${h.api_error}`);
      })
      .catch(() => {
        if (live) setUp(false);
      });
    return () => {
      live = false;
    };
  }, []);

  async function send(q: string) {
    const asked = q.trim();
    if (!asked || busy) return;
    setBusy(true);
    setQuestion(asked);
    try {
      const a = await agent.ask(asked);
      setAnswer(a);
      // The agent's ONLY channel to the view: a patch, applied through the
      // same store a person's clicks go through. It cannot draw.
      if (a.patch && Object.keys(a.patch).length > 0) {
        useScene.setState(a.patch as never);
      }
    } catch (e) {
      setAnswer({
        question: asked,
        answer: `I could not reach the agent: ${(e as Error).message}`,
        trace: [],
        citations: [],
        patch: {},
        planner: "unavailable",
        refused: true,
        n_tool_calls: 0,
      });
    } finally {
      setBusy(false);
    }
  }

  // Absent, not broken. The whole point of the agent being a separate service.
  if (up !== true) return null;

  return (
    <section className="ask" aria-label="Ask Samudra Sahayak">
      <form
        className="ask__form"
        onSubmit={(e) => {
          e.preventDefault();
          send(box.current?.value ?? "");
        }}
      >
        <label className="ask__label" htmlFor="ask-input">
          Samudra Sahayak
        </label>
        <input
          id="ask-input"
          ref={box}
          className="ask__input"
          type="text"
          maxLength={500}
          placeholder="Ask about the water on screen"
          defaultValue={question}
          disabled={busy}
        />
        <button type="submit" className="tick stamp" disabled={busy}>
          {busy ? "Working" : "Ask"}
        </button>
      </form>

      {!answer && (
        <ul className="ask__suggest">
          {SUGGESTIONS.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => {
                  if (box.current) box.current.value = s;
                  send(s);
                }}
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}

      {answer && (
        <div className="ask__answer" aria-live="polite">
          <p className="ask__text" data-refused={answer.refused ? "true" : undefined}>
            {answer.answer}
          </p>

          <div className="ask__meta">
            {/* Printed verbatim. An audience must not be left to assume a
                language model is in the loop when one is not. */}
            <span className="ask__planner num" title={note}>
              planner: {answer.planner}
            </span>
            {answer.n_tool_calls > 0 && (
              <button
                type="button"
                className="ask__tracetoggle"
                aria-expanded={showTrace}
                onClick={() => setShowTrace((v) => !v)}
              >
                {answer.n_tool_calls} tool call{answer.n_tool_calls === 1 ? "" : "s"}
              </button>
            )}
          </div>

          {showTrace && (
            <ol className="ask__trace">
              {answer.trace.map((t, i) => (
                <li key={`${t.tool}-${i}`} data-ok={t.ok ? "true" : "false"}>
                  <span className="ask__tool num">{t.tool}</span>
                  {t.error ? (
                    <span className="ask__toolerr">{t.error}</span>
                  ) : (
                    <ul className="ask__facts">
                      {t.facts.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ol>
          )}

          {answer.citations.length > 0 && (
            <ul className="ask__cites">
              {answer.citations.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
