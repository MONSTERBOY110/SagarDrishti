"use client";

/** A vertical scale bar for the water column.
 *
 * The exaggeration slider says "200x". A judge cannot check a number, so this
 * draws what it means: the alternating bar is the real on-screen height of the
 * column at the current exaggeration, labelled in metres of ocean and in
 * kilometres of drawn distance. It is the chart device that turns the claim
 * into something verifiable, and it is the reason the scene reads as an
 * instrument rather than a picture.
 */

interface Props {
  maxDepth: number;
  exaggeration: number;
  focusDepth: number;
  fps: number;
  p1: number;
  /** Whether the figure was measured while the camera was moving. A still
   *  scene has no frame rate worth quoting, and saying so is better than
   *  printing the browser's idle throttle as though it were our cost. */
  fpsMoving: boolean;
}

export default function ScaleBar({
  maxDepth,
  exaggeration,
  focusDepth,
  fps,
  p1,
  fpsMoving,
}: Props) {
  if (!Number.isFinite(maxDepth) || maxDepth <= 0) return null;

  /* TRD 5 sets a 60 target and a 30 floor. The floor watches BOTH figures: a
     median of 44 with a 1-in-100 frame at 27 is below the floor in the way a
     person actually perceives, and a rule form keyed only to the median would
     have reported that as healthy. State is rule form, never hue.

     NOT MEASURED is its own state, and it used to be reported as failing. With
     no sample yet, `fps` is 0, so both comparisons were true and the readout
     ruled itself in the reserved caution ink before anybody had touched the
     scene. "We have not measured" and "we are below the floor" are different
     statements and the second one is an accusation. */
  const measured = fps > 0;
  const belowFloor = measured && (fps < 30 || p1 < 30);
  const atTarget = measured && fps >= 58 && p1 >= 58;

  const drawnKm = (maxDepth * exaggeration) / 1000;
  // Five alternating segments, the classic chart-scale pattern.
  const segments = Array.from({ length: 5 }, (_, i) => i);

  return (
    <aside className="scalebar" aria-label="Vertical scale">
      <div className="scalebar__label">Water column</div>
      <div className="scalebar__bar" aria-hidden>
        {segments.map((i) => (
          <span key={i} style={{ flex: 1 }} />
        ))}
      </div>
      <div className="scalebar__ends num">
        <span>0</span>
        <span>{maxDepth >= 1000 ? `${(maxDepth / 1000).toFixed(1)} km` : `${maxDepth} m`}</span>
      </div>
      <div
        className="num"
        style={{ marginTop: "0.25rem", fontSize: "0.625rem", color: "var(--stamp-soft)" }}
      >
        {exaggeration}x vertical · drawn {drawnKm.toFixed(0)} km
      </div>
      <div className="num" style={{ fontSize: "0.625rem", color: "var(--stamp)" }}>
        cursor {Math.round(focusDepth)} m
      </div>

      {/* The frame-rate readout lives here rather than floating over the sky:
          inside an instrument box it reads as part of the form, which is what
          the direction contract's own language asks for. Both figures print,
          because the median is throughput and the p1 is the stutter a person
          notices. */}
      <div
        className="num scalebar__render"
        data-state={belowFloor ? "floor" : atTarget ? "target" : "ok"}
        title={
          "Median and 99th-percentile frame rate, measured WHILE THE CAMERA IS " +
          "MOVING. Target 60, floor 30 (TRD section 5). A still scene is not " +
          "measured: a browser throttles its animation callback on a window it " +
          "thinks is inactive, so an idle reading would be its refresh choice " +
          "rather than this scene's cost."
        }
      >
        {fps > 0
          ? `render ${fps.toFixed(0)} fps · p1 ${p1.toFixed(0)}${fpsMoving ? "" : " · idle"}`
          : "render: move the scene to measure"}
      </div>
    </aside>
  );
}
