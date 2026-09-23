"use client";

/** Time-step animation (PS requirement F1), driven from outside any panel.
 *
 * WHY THIS IS NOT IN TimeRule. It was, and that was a defect the moment the
 * panels became a dock. `playing` is scene state: it is in
 * `packages/scene/scene.schema.json`, the agent may patch it, and a guided
 * tour may patch it. But the only code that actually stepped the clock was a
 * `setInterval` inside `TimeRule`, which renders inside the station sheet, and
 * the station sheet is CLOSED on the opening frame.
 *
 * So the scene could be playing in every sense that anything could observe,
 * and the water would not move. Ask Samudra Sahayak to run the animation and
 * it sets `playing: true`, reports success, and nothing happens. Press Run and
 * then press `h` for the pure-globe shot, which is beat one of the recording
 * script, and the animation stops for exactly the frame it was wanted in,
 * while the store still says it is playing, and it resumes when the chrome
 * comes back.
 *
 * The rule this encodes: a control may be hidden, but the thing it controls is
 * the scene, and the scene does not stop existing because nobody is looking at
 * its switch. TimeRule is now the scrubber it looks like.
 */

import { useEffect } from "react";

/** One step per 1.4 s. Slow enough that a three-step analysis reads as three
 *  distinct states rather than as a flicker. */
export const STEP_MS = 1400;

export function useTimePlayback(
  times: string[] | undefined,
  current: string,
  playing: boolean,
  onTime: (t: string) => void,
) {
  useEffect(() => {
    if (!playing || !times || times.length < 2) return;
    const t = setInterval(() => {
      const at = times.indexOf(current);
      /* Off the axis, play starts from the BEGINNING explicitly. The original
         wrote `Math.max(0, indexOf(current))`, so a time that is not on this
         axis landed on step 0 by arithmetic accident and silently "worked",
         which is what hid the defect until a second dataset with its own epoch
         was imagined. */
      onTime(at < 0 ? times[0] : times[(at + 1) % times.length]);
    }, STEP_MS);
    return () => clearInterval(t);
  }, [playing, times, current, onTime]);
}
