"use client";

/** The provenance cartouche, and the reason a number on this screen can be
 *  defended.
 *
 * Built as a chart's title device rather than three lines of naked text: a
 * ruled and boxed frame carrying the title, the region, the source, the
 * sampling and the retrieval date, the way an engraved cartouche does. The box
 * is also what keeps the citation legible over a moving 3D scene.
 *
 * CONTRIBUTING.md: numbers enter an answer only with dataset, timestamp and (for
 * Argo) float WMO id. This panel is where that guarantee becomes visible to a
 * forecaster, and it is the same text the agent will speak in Phase 2, read
 * from the store's provenance.json rather than composed here.
 */

interface Props {
  citation: string;
  time: string;
  levels: number;
  depthRange: [number, number] | null;
  retrievedAt: string | null;
  offline: boolean;
}

export default function Cartouche({
  citation,
  time,
  levels,
  depthRange,
  retrievedAt,
  offline,
}: Props) {
  return (
    <footer className="cartouche">
      <div className="cartouche__head">
        <span>SagarDrishti</span>
        <span style={{ color: "var(--stamp-soft)", letterSpacing: "0.06em" }}>
          Bay of Bengal
        </span>
        {offline && (
          <span
            className="cartouche__flag"
            title="This scene is served entirely from the local cube. No network request was made."
          >
            offline
          </span>
        )}
      </div>

      {/* Printed matter in the form's own face; only entered values are set in
          the typewriter. */}
      <p>{citation || "no dataset loaded"}</p>
      <p className="num" style={{ marginTop: "0.1875rem", color: "var(--stamp-soft)" }}>
        {time || "n/a"} · {levels} levels
        {depthRange ? ` · ${depthRange[0]} to ${depthRange[1]} m` : ""}
        {retrievedAt ? ` · retrieved ${retrievedAt.slice(0, 10)}` : ""}
      </p>
    </footer>
  );
}
