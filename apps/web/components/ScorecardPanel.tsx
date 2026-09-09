"use client";

/** The verification certificate: how far the model sits from the instruments.
 *
 * PS requirement F9, TRD M5. Every other surface in this application draws
 * data. This one makes a CLAIM ABOUT THE MODEL, which is why it is built as a
 * separate document rather than as another block on the station sheet: in the
 * paper world it is the certificate clipped to the front of the log, not a
 * line inside it.
 *
 * Three rules govern everything below, and each of them is a decision that
 * could have gone the other way:
 *
 *   1. THE CAVEAT IS NOT A FOOTNOTE. The INCOIS analysis assimilates the very
 *      Argo profiles it is scored against, so the residual bounds how closely
 *      the analysis fits data it has already seen. That is a real and useful
 *      number. It is not forecast skill, and the overprint says so in the
 *      reserved ink before a reader reaches the figures.
 *   2. BIAS AND RMSE ARE PRINTED TOGETHER. A model two degrees warm in half
 *      the ocean and two degrees cold in the other half has a bias of zero.
 *      Printing bias alone would call it perfect.
 *   3. THE REFUSALS ARE PART OF THE ANSWER. "11,718 pairs" without "4,672
 *      levels could not be paired, and here is why" is a selected number.
 *
 * Hue stays reserved for the measurement, as everywhere else in this world, so
 * the error bars are ink rather than a red-to-green scale. The one exception is
 * the band the model is worst in, which is ruled in the reserved caution ink:
 * that is the same grammar the errata block uses, and it is the one line on
 * this certificate a forecaster has to leave with.
 */

import { useEffect, useState } from "react";

import { api, displayUnits, type Scorecard, type ScoreBin } from "@/lib/api";

/**
 * The profile column each model variable is verified against.
 *
 * Explicit, and deliberately not inferred from the variable name. Scoring TEMP
 * against a salinity column would return a perfectly well formed number with
 * no meaning, and nothing downstream could tell that had happened.
 */
const OBSERVED_FOR: Record<string, string> = { TEMP: "temp", SAL: "psal" };

/** The CF standard name behind each variable, so the printed unit can be
 *  resolved the same way the rest of the application resolves it: the cube
 *  declares salinity as the dimensionless "1" and only the standard name says
 *  that "1" means practical salinity (lib/api.ts:displayUnits). */
const CANONICAL_FOR: Record<string, string> = {
  TEMP: "sea_water_temperature",
  SAL: "sea_water_practical_salinity",
};

/** Decimals that suit the magnitude: 0.10 psu and 2.07 degC both need three. */
function fig(value: number | null, dp = 3): string {
  return value === null || !Number.isFinite(value) ? "n/a" : value.toFixed(dp);
}

function signed(value: number | null, dp = 3): string {
  if (value === null || !Number.isFinite(value)) return "n/a";
  // ASCII hyphen rather than U+2212: the typewriter face is subsetted and a
  // glyph it does not carry renders as tofu in the middle of a figure.
  return (
    (value > 0 ? "+" : value < 0 ? "-" : " ") + Math.abs(value).toFixed(dp)
  );
}

function bandLabel(bin: ScoreBin): string {
  return `${bin.depth_min.toFixed(0)} to ${bin.depth_max.toFixed(0)}`;
}

function count(n: number): string {
  return n.toLocaleString("en-IN");
}

/** The refusal ledger, in the order a reader should meet it: the largest
 *  cause first, so the number that dominates is not buried under three that
 *  do not. Only non-zero causes are printed; a ledger of zeroes is noise. */
const REFUSAL_LABELS: Array<[keyof Scorecard["refused"], string, string]> = [
  [
    "no_observation",
    "Not measured",
    "The instrument reported no value at this level. Not a quality judgement: a biogeochemical float samples oxygen at depths where its CTD did not report.",
  ],
  [
    "outside_grid",
    "Outside the box",
    "The profile surfaced beyond the bounds of the downloaded model box.",
  ],
  [
    "missing_stencil",
    "Model cell missing",
    "One or more of the four surrounding grid cells has no value at that level, usually near a coast. Filling from the cells that remain would invent the shelf.",
  ],
  [
    "outside_depth_range",
    "Beyond model depth",
    "The level lies outside the model's own depth range, and no value is extrapolated to reach it.",
  ],
  [
    "rejected_qc",
    "Failed QC",
    "The observation carries a QC flag outside the accepted set.",
  ],
  [
    "no_qc_flag",
    "Unflagged",
    "The value carries no quality flag at all, so it has passed nothing.",
  ],
  [
    "no_model_time",
    "No field in time",
    "The nearest model step is further away than the analysis window allows.",
  ],
];

export default function ScorecardPanel({
  sourceId,
  variable,
  variableLabel,
}: {
  sourceId: string | null;
  variable: string;
  variableLabel: string;
}) {
  const [card, setCard] = useState<Scorecard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Collapsed by default. The three headline figures are the claim and they
  // stay on screen beside the field, which is the whole point of the feature;
  // the breakdown is a deliberate reveal, and expanding it by default pushed
  // the cast panel below the fold before anyone had asked a second question.
  const [open, setOpen] = useState(false);

  const observed = OBSERVED_FOR[variable] ?? null;

  useEffect(() => {
    if (!sourceId || !observed) {
      setCard(null);
      setError(null);
      return;
    }
    let live = true;
    setPending(true);
    setError(null);
    api
      .scorecard(sourceId, variable, observed)
      .then((c) => {
        if (live) setCard(c);
      })
      .catch((e: Error) => {
        if (live) {
          setCard(null);
          setError(e.message);
        }
      })
      .finally(() => {
        if (live) setPending(false);
      });
    return () => {
      live = false;
    };
  }, [sourceId, variable, observed]);

  // A derived product has no instrument counterpart. Saying nothing would read
  // as "the scorecard is broken"; the honest statement is that nothing in the
  // water measures a diagnosed isotherm depth directly.
  if (!observed) {
    return (
      <section
        className="sheet"
        // .sheet is a flex ROW (its binding margin is a sibling of the body),
        // so a certificate that lays its blocks out vertically has to say so.
        style={{ width: "25rem", display: "flex", flexDirection: "column" }}
        aria-label="Model verification"
      >
        <Head
          variable={variableLabel}
          subtitle="no in-situ counterpart"
          stamp={null}
        />
        <div style={{ padding: "0.625rem 0.75rem 0.75rem" }}>
          <p
            style={{
              margin: 0,
              fontSize: "0.75rem",
              lineHeight: 1.5,
              color: "var(--ink-soft)",
            }}
          >
            {variableLabel} is diagnosed from the model field rather than
            measured, so no instrument in the water reports it and there is
            nothing to verify it against. Switch the scene to temperature or
            salinity to read the certificate.
          </p>
        </div>
      </section>
    );
  }

  const worst = card ? worstBand(card.by_depth) : null;
  const scale = card
    ? Math.max(...card.by_depth.map((b) => b.rmse ?? 0), 1e-9)
    : 1;
  const u = card ? displayUnits(card.units, CANONICAL_FOR[variable] ?? null) : "";

  return (
    <section
      className="sheet"
      // .sheet is a flex ROW (its binding margin is a sibling of the body),
      // so a certificate that lays its blocks out vertically has to say so.
      style={{ width: "25rem", display: "flex", flexDirection: "column" }}
      aria-label="Model verification"
    >
      <Head
        variable={variableLabel}
        subtitle={
          card
            ? `${u ? u + " · " : ""}${count(card.overall.n)} pairs · ${card.n_profiles} casts`
            : pending
              ? "reading…"
              : "no certificate"
        }
        stamp={card ? "Analysis fit" : null}
      />

      {error && (
        <p
          style={{
            margin: 0,
            padding: "0.625rem 0.75rem 0.75rem",
            fontSize: "0.75rem",
            lineHeight: 1.5,
            color: "var(--caution-ink)",
          }}
        >
          {error}
        </p>
      )}

      {card && card.overall.n === 0 && !error && (
        <p
          style={{
            margin: 0,
            padding: "0.625rem 0.75rem 0.75rem",
            fontSize: "0.75rem",
            lineHeight: 1.5,
            color: "var(--ink-soft)",
          }}
        >
          No observation could be paired with this field. All{" "}
          <span className="num">{count(card.refused.total)}</span> levels were
          refused, which is a statement about coverage rather than about the
          model.
        </p>
      )}

      {card && card.overall.n > 0 && (
        <>
          {/* --- the three figures, together, because one alone misleads ---
              The unit is printed once, in the head. Repeated under each figure
              it said the same thing three times and spent the only line that
              could have said what each figure MEANS. */}
          <div className="verdict">
            <Figure
              label="Bias"
              value={signed(card.overall.bias)}
              note="model minus observed"
            />
            <Figure
              label="RMSE"
              value={fig(card.overall.rmse)}
              note="root mean square"
            />
            <Figure
              label="Mean abs"
              value={fig(card.overall.mae)}
              note="typical miss"
            />
          </div>

          <button
            type="button"
            className="verdict__toggle stamp"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span>Error by depth, and what was refused</span>
            <span aria-hidden>{open ? "hide" : "show"}</span>
          </button>

          {open && (
            <div style={{ padding: "0 0.75rem 0.25rem" }}>
              <div className="scoretable__head">
                <span>Band m</span>
                <span style={{ textAlign: "right" }}>n</span>
                <span style={{ textAlign: "right" }}>Bias</span>
                {/* The bar carries no heading of its own: it is the RMSE
                    column's own figure drawn to length, and heading it "RMSE"
                    a second time made the table look like it held two. */}
                <span aria-hidden />
                <span style={{ textAlign: "right" }}>RMSE</span>
              </div>
              <ul className="scoretable">
                {card.by_depth.map((bin) => (
                  <li
                    key={`${bin.depth_min}-${bin.depth_max}`}
                    className="scoretable__row"
                    data-empty={bin.n === 0 ? "true" : undefined}
                    data-worst={worst === bin ? "true" : undefined}
                  >
                    <span className="num">{bandLabel(bin)}</span>
                    <span
                      className="num"
                      style={{ textAlign: "right", fontSize: "0.625rem" }}
                    >
                      {bin.n === 0 ? "0" : count(bin.n)}
                    </span>
                    <span
                      className="num"
                      style={{ textAlign: "right", fontSize: "0.625rem" }}
                    >
                      {signed(bin.bias, 2)}
                    </span>
                    {/* Ink, not hue: an error is not a measurement, and hue is
                        spent on the field's own colorbar. The one band ruled in
                        the reserved ink is the one the model is worst in. */}
                    <span className="scoretable__bar" aria-hidden>
                      <span
                        style={{ width: `${((bin.rmse ?? 0) / scale) * 100}%` }}
                      />
                    </span>
                    <span
                      className="num"
                      style={{
                        textAlign: "right",
                        fontWeight: 700,
                        fontSize: "0.6875rem",
                      }}
                    >
                      {fig(bin.rmse, 2)}
                    </span>
                  </li>
                ))}
              </ul>

              {worst && (
                <p className="scoretable__read">
                  Worst between <span className="num">{bandLabel(worst)}</span>{" "}
                  m, at{" "}
                  <span className="num">
                    {fig(worst.rmse, 2)}
                    {u ? ` ${u}` : ""}
                  </span>
                  . Where the water changes fastest with depth, a small error in
                  where the model puts a layer becomes a large error in its
                  value.
                </p>
              )}

              {/* --- what did not become a pair --------------------------- */}
              <div
                className="label label--split"
                style={{ marginTop: "0.5rem" }}
              >
                <span>Levels not paired</span>
                <span className="num">{count(card.refused.total)}</span>
              </div>
              <dl
                className="castfield castfield--wide castfield--tally"
                style={{ margin: "0 0 0.25rem" }}
              >
                {REFUSAL_LABELS.filter(([k]) => card.refused[k] > 0).map(
                  ([k, label, why]) => (
                    <div key={k} style={{ display: "contents" }}>
                      <dt title={why}>{label}</dt>
                      <dd className="num">{count(card.refused[k])}</dd>
                    </div>
                  ),
                )}
              </dl>

              <dl
                className="castfield castfield--wide castfield--notes"
                style={{ margin: 0 }}
              >
                <dt>Offset</dt>
                <dd className="num">
                  median {fig(card.time_offset_hours.median, 1)} h, max{" "}
                  {fig(card.time_offset_hours.max, 1)} h
                </dd>
                <dt>QC</dt>
                <dd className="num">
                  flags {card.accept_flags.join(" and ")} accepted
                </dd>
                <dt>Method</dt>
                <dd>bilinear in position, linear in depth, no extrapolation</dd>
              </dl>
            </div>
          )}

          {/* --- the sentence that must travel with every figure above ---- */}
          <footer className="verdict__caveat">
            <p style={{ margin: 0 }}>{card.caveat}</p>
            <p style={{ margin: "0.3125rem 0 0", color: "var(--ink-soft)" }}>
              {card.citation}
            </p>
            {/* Named, not reprinted. Four full dataset citations here buried
                the caveat above them, and the cartouche at the foot of the
                screen already carries the model's in full. Attribution stays
                whole: each programme is named on its own line, and its full
                citation is on the row. */}
            {card.observation_titles.length > 0 && (
              <div style={{ margin: "0.3125rem 0 0", color: "var(--ink-soft)" }}>
                <span className="verdict__against">Scored against</span>
                <ul className="verdict__sources">
                  {card.observation_titles.map((title, i) => (
                    <li key={title} title={card.observation_citations[i]}>
                      {title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </footer>
        </>
      )}
    </section>
  );
}

/** The band with the largest RMSE, ignoring bands nobody sampled.
 *
 * A band holding two levels can win on noise alone, so a band is only eligible
 * once it holds enough pairs for its RMSE to mean anything. Twenty is the
 * number, and it is arbitrary in the way a threshold has to be: stated here
 * rather than hidden, so a reader can disagree with it.
 */
function worstBand(bins: ScoreBin[]): ScoreBin | null {
  let best: ScoreBin | null = null;
  for (const b of bins) {
    if (b.n < 20 || b.rmse === null) continue;
    if (!best || b.rmse > (best.rmse ?? -Infinity)) best = b;
  }
  return best;
}

function Head({
  variable,
  subtitle,
  stamp,
}: {
  variable: string;
  subtitle: string;
  stamp: string | null;
}) {
  return (
    <header className="verdict__head">
      <div style={{ minWidth: 0 }}>
        <h2 className="verdict__title">Model verification</h2>
        <p className="num verdict__sub">
          {variable} · {subtitle}
        </p>
      </div>
      {stamp && (
        <span
          className="overprint"
          title="The analysis assimilates these same profiles, so this is the fit to data it has already seen, not forecast skill."
        >
          {stamp}
        </span>
      )}
    </header>
  );
}

function Figure({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="verdict__fig">
      <span className="verdict__figlabel">{label}</span>
      <span className="num verdict__figvalue">{value}</span>
      <span className="verdict__fignote">{note}</span>
    </div>
  );
}
