/** Client for the Samudra Sahayak agent plane (TRD M4).
 *
 * A SEPARATE BASE URL from the data plane, and that is the architecture rather
 * than a deployment detail. TRD section 6.5 states the property as "kill the
 * agent and every P0 still passes": the agent is its own service, the client
 * probes it, and when it is not running the ask panel renders nothing at all.
 * Nothing else in the application imports this module.
 */

const AGENT_BASE = process.env.NEXT_PUBLIC_AGENT_BASE ?? "http://127.0.0.1:8010";

/** One tool call, as it happened. Printed in the trace panel, because an
 *  answer whose working is visible is one a reviewer can disagree with. */
export interface AgentToolCall {
  tool: string;
  ok: boolean;
  values: Record<string, unknown>;
  /** Phrases the tool produced. Every numeral in the answer came from one of
   *  these or from `values`; the server refuses an answer where it did not. */
  facts: string[];
  citations: string[];
  patch: Record<string, unknown>;
  error: string;
}

export interface AgentAnswer {
  question: string;
  answer: string;
  trace: AgentToolCall[];
  citations: string[];
  /** The agent's ONLY channel to the view. Applied through the same store a
   *  person's clicks go through, so the agent cannot draw. */
  patch: Record<string, unknown>;
  /** What produced the answer. "rules" today: there is no language model in
   *  the loop, and the UI prints this rather than letting an audience assume
   *  otherwise. */
  planner: string;
  refused: boolean;
  n_tool_calls: number;
}

export interface AgentHealth {
  status: string;
  planner: string;
  llm: string | null;
  llm_note: string;
  api_base: string;
  api_reachable: boolean;
  api_error: string;
  tools: string[];
  max_tool_calls: number;
}

/** Generous, and RETRIED, because this decides whether the panel appears at
 *  all and it races the Cesium bundle.
 *
 *  The first version used 2.5 seconds and no retry, and the panel intermittently
 *  did not appear: the probe is issued at mount, while several megabytes of
 *  renderer are still being fetched and parsed on the same connection, so the
 *  request can sit queued long enough to abort even though the agent answers in
 *  a seventh of a second when asked directly. Intermittent absence is the worst
 *  possible failure for a control that is SUPPOSED to be absent sometimes: it
 *  would read as "the agent is off" when it is running. */
const PROBE_TIMEOUT = 8000;
/** Delays before each attempt. Three tries over about seven seconds, which
 *  outlasts a cold page load without leaving a hole for long if the agent is
 *  genuinely not running. */
const PROBE_BACKOFF = [0, 1500, 5000];

export const agent = {
  /** Is the agent there? Retried, because a single probe races the page load. */
  async healthz(): Promise<AgentHealth> {
    let last: unknown;
    for (const wait of PROBE_BACKOFF) {
      if (wait) await new Promise((r) => setTimeout(r, wait));
      try {
        const r = await fetch(`${AGENT_BASE}/healthz`, {
          signal: AbortSignal.timeout(PROBE_TIMEOUT),
        });
        if (r.ok) return (await r.json()) as AgentHealth;
        last = new Error(`agent ${r.status}`);
      } catch (e) {
        last = e;
      }
    }
    throw last instanceof Error ? last : new Error("the agent did not answer");
  },

  async ask(question: string): Promise<AgentAnswer> {
    const r = await fetch(`${AGENT_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        detail = (await r.json()).detail ?? detail;
      } catch {
        /* a non-JSON error body is still an error */
      }
      throw new Error(`${r.status} ${detail}`);
    }
    return r.json() as Promise<AgentAnswer>;
  },
};
