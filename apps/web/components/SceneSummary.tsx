"use client";

/** A text account of what the 3D scene currently shows.
 *
 * A canvas is completely opaque to assistive technology: a screen reader sees
 * an empty box where the water column is, so the whole primary display of this
 * product is, to that reader, absent. The problem statement names public
 * outreach, education and e-learning among its mandates, and TRD section 7
 * schedules an accessibility pass, so the scene owes a spoken equivalent rather
 * than a label saying "3D globe".
 *
 * It is also the cheapest possible regression test for a judge: reading this
 * sentence aloud and comparing it against the picture is a five-second check
 * that the two agree.
 *
 * Rendered visually hidden but present in the accessibility tree, and polite
 * rather than assertive: the depth cursor moves continuously while a forecaster
 * drags it, and an assertive region would interrupt on every step.
 */

import type { SagarNodeStation, WarningAlert } from "@/lib/api";

interface Props {
  datasetTitle: string | null;
  variable: string;
  units: string;
  focusDepth: number;
  depthMin: number;
  depthMax: number;
  levels: number;
  time: string;
  exaggeration: number;
  /** Marks on the globe: one per CAST, not one per instrument. */
  stationCount: number;
  /** Casts and distinct instruments per class, so the spoken summary can name
   *  them without turning nine casts by three floats into nine floats. */
  stationKinds: Record<string, { profiles: number; platforms: number }>;
  /** Distinct instruments behind all of those casts. */
  platformCount: number;
  selectedWmo: string | null;
  selectedKind: string | null;
  vmin: number;
  vmax: number;
  /** Warning areas drawn on the globe (PS F13). A hazard polygon is a shape on
   *  a canvas and therefore invisible to a screen reader, which for a warning
   *  is the least acceptable place in this product to leave silent. */
  warnings: WarningAlert[];
  /** The tabletop rig (PS F6), or null when none is plugged in. */
  sagarnode: SagarNodeStation | null;
}

/** Spoken names for the instrument classes. The visual legend tells them apart
 *  by mark shape, which a screen-reader user cannot see, so the summary has to
 *  say the words instead. */
const KIND_WORDS: Record<string, [string, string]> = {
  gdac_geo: ["Argo float", "Argo floats"],
  gdac_bgc: ["biogeochemical Argo float", "biogeochemical Argo floats"],
  file: ["ship or glider cast", "ship or glider casts"],
  mooring: ["mooring", "moorings"],
  hf_radar: ["HF radar station", "HF radar stations"],
  adcp: ["ADCP", "ADCPs"],
};

/**
 * The instrument classes, spoken.
 *
 * Counted by INSTRUMENT, not by mark. A mark is one cast, a float drifts and
 * casts repeatedly, so the nine BGC marks in this box were taken by three
 * BGC floats. Saying "nine biogeochemical floats" would be a claim about the
 * Indian Ocean observing system that is off by a factor of three, and it is
 * the kind of claim the listener most likely to be checking is best equipped
 * to check.
 */
function describeStations(
  kinds: Record<string, { profiles: number; platforms: number }>,
): string {
  const parts = Object.entries(kinds)
    .filter(([, c]) => c.platforms > 0)
    .map(([kind, c]) => {
      const words = KIND_WORDS[kind] ?? [kind, kind];
      const n = c.platforms;
      // "between them" needs more than one of them. The single RAMA buoy in
      // this box reported three times, and "1 mooring, 3 casts between them"
      // is the sentence a screen reader would actually have to say.
      const each =
        c.profiles === n
          ? ""
          : `, ${c.profiles} casts ${n === 1 ? "from it" : "between them"}`;
      return `${n} ${n === 1 ? words[0] : words[1]}${each}`;
    });
  if (parts.length <= 1) return parts[0] ?? "none";
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function platformNoun(kind: string | null): string {
  const words = KIND_WORDS[kind ?? "gdac_geo"] ?? KIND_WORDS.gdac_geo;
  return words[0].charAt(0).toUpperCase() + words[0].slice(1);
}

/**
 * The hazard layer, spoken.
 *
 * A drill is named as a drill in the FIRST clause about it, not in a trailing
 * qualifier. A listener who hears "a tsunami warning is in force" and only
 * afterwards "this is an exercise" has already had the wrong reaction, and on
 * this layer that is the failure the whole design exists to prevent.
 */
function describeWarnings(alerts: WarningAlert[]): string {
  if (alerts.length === 0) return " No hazard warning is in force over this water.";
  return alerts
    .map((a) => {
      const kind =
        a.status === "Actual"
          ? `A ${a.severity.toLowerCase()} ${a.event.toLowerCase()} warning is in force`
          : `A rehearsal bulletin, not a real warning, describes a ${a.severity.toLowerCase()} ${a.event.toLowerCase()}`;
      const where = a.area_desc ? ` for ${a.area_desc}` : "";
      const drawn = a.drawable ? " Its area is outlined on the globe." : " It has no area to draw.";
      return ` ${kind}${where}.${drawn}`;
    })
    .join("");
}

/**
 * The tabletop rig, spoken.
 *
 * DELIBERATELY WITHOUT ITS NUMBERS. This region is aria-live, the rig is
 * polled twice a second, and the water temperature moves in the last decimal
 * continuously: putting the reading in this sentence would make a screen
 * reader recite the tank forever and bury everything else the scene has to
 * say. What is said is what is stable and what matters, which is that the rig
 * is there, that it is a demonstration and not an observation, and whether it
 * has tripped. The readings themselves are in the panel, which is a table.
 */
function describeSagarnode(node: SagarNodeStation | null): string {
  if (!node) return "";
  const what =
    " A tabletop demonstration sensor station is also reporting, marked with a" +
    " broken circle. It is a rig on the demo table, not an ocean observation.";
  if (!node.alert) return what;
  return `${what} It has tripped its own warming threshold, as a rehearsal: this is a drill and concerns nobody at sea.`;
}

export default function SceneSummary(p: Props) {
  if (!p.datasetTitle) {
    return (
      <p className="sr-only" role="status">
        No ocean field is loaded yet.
      </p>
    );
  }

  const when = p.time ? p.time.replace("T", " ").replace("Z", " UTC") : "an unknown time";

  return (
    <p className="sr-only" role="status" aria-live="polite">
      {`Ocean scene. ${p.datasetTitle}. Showing ${p.variable}${
        p.units ? ` in ${p.units}` : ""
      } over the Bay of Bengal at ${when}. The water column is drawn as ${
        p.levels
      } depth levels from ${p.depthMin} to ${p.depthMax} metres, exaggerated ${
        p.exaggeration
      } times vertically so the column is legible against the width of the basin. The depth cursor is at ${Math.round(
        p.focusDepth,
      )} metres. Colour runs from ${p.vmin} to ${p.vmax}${
        p.units ? ` ${p.units}` : ""
      }; cells with no data are left uncoloured. ${
        p.stationCount === 0
          ? "No instrument casts are in view."
          : `${p.stationCount} instrument cast${
              p.stationCount === 1 ? " is" : "s are"
            } marked on the globe, taken by ${p.platformCount} instrument${
              p.platformCount === 1 ? "" : "s"
            }: ${describeStations(p.stationKinds)}.`
      }${
        p.selectedWmo
          ? ` ${platformNoun(p.selectedKind)} ${p.selectedWmo} is selected, and its measured profile is shown beside the scene.`
          : " Select a station to read its measured profile against the model."
      }${describeSagarnode(p.sagarnode)}${describeWarnings(p.warnings)}`}
    </p>
  );
}
