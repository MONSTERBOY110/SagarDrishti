"use client";

/** What the marks on the water mean (PS requirement F2).
 *
 * The problem statement asks for Argo floats, gliders, CTD casts and BGC
 * floats as distinguishable marks. They are told apart by SILHOUETTE, because
 * on this surface hue belongs to the measurement: spending colour on a
 * platform category would put this legend in competition with the colorbar,
 * which has to stay readable as a measuring instrument.
 *
 * Two rules this component follows and would be wrong without:
 *
 *   1. It lists only the classes ACTUALLY PRESENT in the scene. A legend
 *      advertising a glider we have no glider data for is a claim, and the
 *      whole project turns on not making claims the data does not support.
 *   2. Each swatch is drawn by the SAME function that draws the mark on the
 *      globe, so the two cannot drift apart. A legend that stops matching its
 *      map is worse than no legend.
 */

import { useEffect, useRef } from "react";

import { stationMark } from "./OceanGlobe";
import type { PlatformKind, ProfileGlyph } from "@/lib/api";

const LABELS: Record<string, string> = {
  gdac_geo: "Argo float",
  gdac_bgc: "BGC float",
  file: "Ship or glider cast",
  glider: "Glider",
  ctd: "CTD cast",
  mooring: "Mooring",
  hf_radar: "HF radar",
  adcp: "ADCP",
  sagarnode: "Demonstration rig",
};

/** Reading order: the classes we expect most of, first. */
const ORDER: PlatformKind[] = [
  "gdac_geo", "gdac_bgc", "glider", "ctd", "file", "mooring", "hf_radar", "adcp",
];

function Swatch({ kind }: { kind: string }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    const canvas = stationMark(false, kind);
    canvas.style.width = "13px";
    canvas.style.height = "13px";
    canvas.style.display = "block";
    host.replaceChildren(canvas);
  }, [kind]);

  return <span ref={ref} aria-hidden style={{ width: 13, height: 13, flexShrink: 0 }} />;
}

export default function StationLegend({
  profiles,
  platformCount,
  sagarnode = false,
}: {
  profiles: ProfileGlyph[];
  /** Distinct instruments behind the marks. A drifting float that reported
   *  three times is three marks and one float, so the counts beside the
   *  swatches are CASTS and this is what they were taken by. Printed only
   *  when the two differ, because when they are equal it is noise. */
  platformCount: number;
  /** Is the tabletop rig reporting? Passed separately rather than folded into
   *  `profiles`, because it is NOT one: SagarNode is a time series at a point
   *  on a table, it serves no cast, and counting it among the profiles would
   *  make a bucket one of the twenty-five Argo floats in every total on this
   *  page. It is listed last for the same reason. */
  sagarnode?: boolean;
}) {
  const counts = new Map<string, number>();
  for (const p of profiles) {
    counts.set(p.platform_kind, (counts.get(p.platform_kind) ?? 0) + 1);
  }
  const present: string[] = ORDER.filter((k) => counts.has(k));
  for (const kind of counts.keys()) {
    if (!present.includes(kind)) present.push(kind);
  }
  if (sagarnode) {
    counts.set("sagarnode", 1);
    present.push("sagarnode");
  }

  // One class on its own needs no legend: the panel header already names it.
  if (present.length < 2) return null;

  /* The rig reports a time series, not a cast, so it is outside this
     reconciliation entirely: it is neither one of the casts nor one of the
     instruments that took them. */
  const casts = profiles.length;

  return (
    <aside className="legend" aria-label="Station marks">
      {/* CASTS, not stations. Each mark is one profile at one position and
          one time, and a drifting float that reported three times put three
          marks on the globe. This heading used to read "Stations", which made
          the nine marks from three BGC floats read as nine BGC floats. */}
      <div className="legend__label">Casts</div>
      <ul className="legend__list">
        {present.map((kind) => (
          <li key={kind} className="legend__row">
            <Swatch kind={kind} />
            <span className="legend__name">{LABELS[kind] ?? kind}</span>
            <span className="legend__count num">{counts.get(kind)}</span>
          </li>
        ))}
      </ul>
      {platformCount > 0 && platformCount !== casts && (
        <p className="legend__foot">
          from <span className="num">{platformCount}</span> instruments
        </p>
      )}
    </aside>
  );
}
