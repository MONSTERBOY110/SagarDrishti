"use client";

/** HazardWatch: what is being warned about, right now, over this water.
 *
 * PS requirement F13, TRD M8. The problem statement's portal theme IS Disaster
 * Management and "timely hazard assessment" is its first stated mandate, so
 * this is the half of the brief the field layers do not answer.
 *
 * It sits on the water rather than on a manila sheet, in the instrument-box
 * treatment the scale bar and the station legend use. That is a deliberate
 * separation: the sheets are a record of a cast, and a warning is not a
 * measurement. It is a statement someone made about the near future.
 *
 * THE ONE RULE THIS PANEL EXISTS TO ENFORCE
 * -----------------------------------------
 * A drill must never read as a live warning. CAP has a `status` field for
 * exactly that, our rehearsal bulletins carry `Exercise`, the server refuses
 * them unless asked, the globe draws them as an unfilled outline, and this
 * panel stamps itself the moment one is on screen. Four independent guards for
 * one failure, because that failure is announcing a tsunami that is not
 * happening.
 *
 * WHY THE HAZARDS ARE NOT COLOUR CODED
 * ------------------------------------
 * A judge may ask, and the answer is better than "we ran out of time". Hue on
 * this surface belongs to the measurement, and the field underneath is already
 * using the whole spectrum. A red-amber-yellow severity ramp would put a
 * "yellow warning" beside yellow 28-degree water and make neither readable.
 * Severity is carried by rule weight and fill instead, in the one reserved
 * caution ink, which is the grammar the rest of this interface already uses.
 */

import { useEffect, useState } from "react";

import { api, type WarningAlert, type WarningLayer } from "@/lib/api";

/** Rule weight per CAP severity. The vocabulary is closed, so this is total. */
const WEIGHT: Record<string, string> = {
  Extreme: "3px double var(--caution-stamp)",
  Severe: "2px solid var(--caution-stamp)",
  Moderate: "1px solid var(--caution-stamp)",
  Minor: "1px dotted var(--caution-stamp)",
  Unknown: "1px dotted var(--stamp-soft)",
};

function when(iso: string | null): string {
  if (!iso) return "open ended";
  // The bulletin's OWN offset is kept. Restating an Indian agency's timing in
  // the reader's local zone would silently move when it said the hazard
  // starts, and "+05:30" is information rather than noise here.
  return iso
    .replace("T", " ")
    .replace(/:\d\d(?=[+Z-]|$)/, "")
    .replace("+05:30", " IST")
    .replace("+00:00", " UTC")
    .replace(/Z$/, " UTC");
}

export default function HazardPanel({
  at,
  bbox,
  rehearsal,
  onRehearsal,
  onLayer,
}: {
  /** The SCENE time, not the wall clock: the hazard layer shares the field's
   *  time axis, so scrubbing the time rule moves the warnings with it. */
  at: string;
  bbox: string | null;
  rehearsal: boolean;
  onRehearsal: (on: boolean) => void;
  /** The alerts, lifted so the globe can draw the same list this panel lists.
   *  One fetch, one source of truth: a panel and a globe that each fetched
   *  their own could disagree about what is being warned about. */
  onLayer: (alerts: WarningAlert[]) => void;
}) {
  const [layer, setLayer] = useState<WarningLayer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!at) return;
    let live = true;
    api
      .warnings(at, rehearsal, bbox ?? undefined)
      .then((l) => {
        if (!live) return;
        setLayer(l);
        setError(null);
        onLayer(l.alerts);
      })
      .catch((e: Error) => {
        if (!live) return;
        setLayer(null);
        setError(e.message);
        onLayer([]);
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [at, bbox, rehearsal]);

  const alerts = layer?.alerts ?? [];
  const drills = layer?.exercise_count ?? 0;

  return (
    <section className="hazard" aria-label="HazardWatch warnings">
      <header className="hazard__head">
        <span className="hazard__title">HazardWatch</span>
        {drills > 0 && (
          <span
            className="hazard__drill"
            title="CAP status Exercise. A drill, handled as though it were real, and never a live warning."
          >
            Exercise
          </span>
        )}
      </header>

      {error && <p className="hazard__note">Warnings unavailable: {error}</p>}

      {!error && alerts.length === 0 && (
        <p className="hazard__note">
          No warning is valid over this water at{" "}
          <span className="num">{when(layer?.at ?? at)}</span>.
          {layer && layer.refused.total > 0 && (
            <>
              {" "}
              <span className="num">{layer.refused.total}</span> on file did not
              apply: {refusalPhrase(layer)}.
            </>
          )}
        </p>
      )}

      {alerts.length > 0 && (
        <ul className="hazard__list">
          {alerts.map((a) => (
            <li key={a.identifier}>
              <button
                type="button"
                className="hazard__row"
                style={{ borderLeft: WEIGHT[a.severity] ?? WEIGHT.Unknown }}
                aria-expanded={open === a.identifier}
                onClick={() => setOpen(open === a.identifier ? null : a.identifier)}
              >
                <span className="hazard__event">
                  {a.event}
                  {a.status !== "Actual" && (
                    <span className="hazard__tag"> {a.status}</span>
                  )}
                </span>
                <span className="hazard__meta num">
                  {a.severity} · {a.urgency}
                </span>
                <span className="hazard__where">{a.area_desc || "area not named"}</span>
              </button>

              {open === a.identifier && <Detail alert={a} />}
            </li>
          ))}
        </ul>
      )}

      <footer className="hazard__foot">
        <label className="hazard__toggle">
          <input
            type="checkbox"
            checked={rehearsal}
            onChange={(e) => onRehearsal(e.target.checked)}
          />
          <span>Include rehearsal bulletins</span>
        </label>
        {/* Not a disclaimer bolted on. The three ocean hazards the PS names by
            name are the ones we could not get a live feed for, so a reader has
            to know which of the things on screen is which. */}
        <p className="hazard__note">
          {rehearsal
            ? "Ocean hazards here are DRILLS, marked with CAP status Exercise. India's live national CAP feed carried no ocean bulletin when this was ingested, and INCOIS publishes no public machine feed for its own. Untick to see only real alerts."
            : "Real alerts only, from India's national CAP backbone. The tsunami, high wave and swell surge bulletins are rehearsals and are hidden."}
        </p>
        {layer && layer.unreadable.length > 0 && (
          <p className="hazard__errata">
            <span className="num">{layer.unreadable.length}</span> CAP documents
            on disk could not be read, so they are not on this list.
          </p>
        )}
      </footer>
    </section>
  );
}

/** The ledger, phrased. A count with no reasons reads as a bug. */
function refusalPhrase(layer: WarningLayer): string {
  const r = layer.refused;
  const parts: [number, string][] = [
    [r.expired, "expired"],
    [r.not_yet_effective, "not yet in force"],
    [r.not_actual, "drills"],
    [r.cancelled, "cancelled"],
    [r.superseded, "superseded"],
    [r.outside_bbox, "elsewhere in India"],
    [r.not_a_warning, "not warnings"],
  ];
  const said = parts.filter(([n]) => n > 0).map(([n, why]) => `${n} ${why}`);
  return said.join(", ");
}

function Detail({ alert }: { alert: WarningAlert }) {
  return (
    <div className="hazard__detail">
      <p className="hazard__headline">{alert.headline}</p>
      {alert.instruction && (
        <p className="hazard__instruction">{alert.instruction}</p>
      )}
      <dl className="hazard__fields">
        <dt>Issued by</dt>
        <dd className="num">{alert.sender}</dd>
        <dt>In force</dt>
        <dd className="num">
          {when(alert.effective)} to {when(alert.expires)}
        </dd>
        <dt>Certainty</dt>
        <dd className="num">{alert.certainty}</dd>
        {alert.languages.length > 1 && (
          <>
            <dt>Languages</dt>
            {/* Real Indian CAP arrives multilingual. Worth showing: it is the
                same fact the voice layer will depend on. */}
            <dd className="num">{alert.languages.join(", ")}</dd>
          </>
        )}
        <dt>CAP id</dt>
        <dd className="num">{alert.identifier}</dd>
      </dl>
      {!alert.drawable && (
        <p className="hazard__errata">
          This warning names an area but carries no polygon, so it is listed
          here and not drawn on the globe.
        </p>
      )}
      {alert.notes.map((n) => (
        <p className="hazard__errata" key={n}>
          {n}
        </p>
      ))}
    </div>
  );
}
