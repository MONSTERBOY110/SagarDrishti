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
 *
 * IT CAN LISTEN AND SPEAK (PRD F10), WITHOUT MOVING THE AUTHORITY. Speech goes
 * through our agent server to Bhashini, never from the browser. A spoken Hindi,
 * Telugu or Tamil question is transcribed, shown, and translated to English for
 * the planner; the English answer is still the one the guard checked, and the
 * translation is printed beside it labelled as machine translation. Offline,
 * the microphone says why it cannot listen, and English answers are read aloud
 * by the computer's own voice, which needs no network.
 */

import { useEffect, useRef, useState } from "react";

import { agent, type AgentAnswer } from "@/lib/agent";
import { useScene } from "@/lib/scene";
import {
  canSpeakLocally,
  playWav,
  speakLocally,
  startRecording,
  stopSpeaking,
  voice,
  type Spoken,
  type VoiceLang,
  type VoiceStatus,
} from "@/lib/voice";

const LANG_NAMES: Record<VoiceLang, string> = {
  en: "English",
  hi: "हिन्दी",
  te: "తెలుగు",
  ta: "தமிழ்",
};

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

  // Voice (PRD F10). `vs` is what the agent server says about speech here.
  const [vs, setVs] = useState<VoiceStatus | null>(null);
  const [lang, setLang] = useState<VoiceLang>("en");
  const [aloud, setAloud] = useState(false);
  const [recording, setRecording] = useState(false);
  const [heard, setHeard] = useState<{ transcript: string; english: string } | null>(null);
  const [spoken, setSpoken] = useState<Spoken | null>(null);
  const [voiceNote, setVoiceNote] = useState("");
  const stopRec = useRef<null | (() => Promise<string>)>(null);

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

  useEffect(() => {
    if (up !== true) return;
    let live = true;
    voice
      .status()
      .then((v) => live && setVs(v))
      .catch(() => live && setVs(null));
    return () => {
      live = false;
      stopSpeaking();
    };
  }, [up]);

  const remote = vs?.available === true;

  /** After an answer: translate and speak it if asked, never replacing the
   *  English. Failures are printed, not swallowed. */
  async function voiceAnswer(a: AgentAnswer) {
    setSpoken(null);
    setVoiceNote("");
    if (a.refused && a.planner === "unavailable") return;
    if (lang === "en") {
      if (aloud) speakLocally(a.answer);
      return;
    }
    if (!remote) return;
    try {
      const s = await voice.speak(a.answer, lang);
      setSpoken(s);
      if (aloud && s.audio) await playWav(s.audio);
    } catch (e) {
      setVoiceNote(`Translation failed: ${(e as Error).message}`);
    }
  }

  async function toggleMic() {
    if (!remote || busy) return;
    if (!recording) {
      try {
        stopRec.current = await startRecording();
        setRecording(true);
        setVoiceNote("Listening. Press again to stop.");
      } catch (e) {
        setVoiceNote(`The microphone could not start: ${(e as Error).message}`);
      }
      return;
    }
    setRecording(false);
    const stop = stopRec.current;
    stopRec.current = null;
    if (!stop) return;
    setVoiceNote("Transcribing through Bhashini");
    try {
      const wav = await stop();
      const h = await voice.asr(wav, lang);
      setHeard({ transcript: h.transcript, english: h.english });
      setVoiceNote("");
      if (!h.english) {
        setVoiceNote("Nothing was heard. Try again, a little closer to the microphone.");
        return;
      }
      if (box.current) box.current.value = h.english;
      send(h.english, true);
    } catch (e) {
      setVoiceNote(`Speech input failed: ${(e as Error).message}`);
    }
  }

  async function send(q: string, fromVoice = false) {
    const asked = q.trim();
    if (!asked || busy) return;
    setBusy(true);
    setQuestion(asked);
    if (!fromVoice) setHeard(null);
    stopSpeaking();
    try {
      const a = await agent.ask(asked);
      setAnswer(a);
      void voiceAnswer(a);
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

      <div className="ask__voice" data-voice={remote ? "on" : "off"}>
        <label className="ask__lang">
          <span className="sr-only">Answer language</span>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value as VoiceLang)}
            aria-label="Answer language"
          >
            {(Object.keys(LANG_NAMES) as VoiceLang[]).map((l) => (
              <option key={l} value={l} disabled={l !== "en" && !remote} lang={l}>
                {LANG_NAMES[l]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="ask__mic"
          aria-pressed={recording}
          disabled={!remote || busy}
          onClick={toggleMic}
          title={remote ? "Push to talk" : vs?.message}
        >
          {recording ? "Stop" : "Speak"}
        </button>
        {(canSpeakLocally() || remote) && (
          <label className="ask__aloud">
            <input type="checkbox" checked={aloud} onChange={(e) => setAloud(e.target.checked)} />
            Read answers aloud
          </label>
        )}
      </div>
      {!remote && vs && (
        <p className="ask__voicenote" data-reason={vs.reason}>
          {vs.message}
        </p>
      )}
      {voiceNote && <p className="ask__voicenote">{voiceNote}</p>}
      {heard && (
        <p className="ask__heard">
          <span className="ask__mtlabel">Heard</span> <span lang={lang}>{heard.transcript}</span>
        </p>
      )}

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

          {spoken && spoken.machine_translation && (
            <div className="ask__mt">
              <p className="ask__mttext" lang={spoken.language}>
                {spoken.text}
              </p>
              <p className="ask__mtlabel">
                Machine translation through Bhashini. The English above is the answer the numbers were
                checked against.
              </p>
            </div>
          )}

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
