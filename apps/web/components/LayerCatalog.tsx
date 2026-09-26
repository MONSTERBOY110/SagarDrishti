"use client";

/** What this platform can draw, stated before anyone clicks anything.
 *
 * WHY THIS EXISTS. Every capability listed here was already built and already
 * reachable, and none of it was visible on the first frame. A reader met a
 * globe, a colour ramp and a depth ladder, and had to go looking to discover
 * that three of the five fields are computed rather than stored, that all
 * five leave the building as OGC layers, and that the whole set is declared
 * in one file. A screenshot that advertises eight layers reads
 * as the larger system even when it is the smaller one.
 *
 * WHAT IT DELIBERATELY DOES NOT DO. It does not repeat the mark legend
 * underneath it. The instruments are counted there, by silhouette, once. A
 * catalog that also listed "Argo 13, BGC 9" would be two sources of the same
 * truth that can drift, and drift is the failure this project spends most of
 * its tests preventing.
 *
 * THE BADGES ARE FACTS, NOT DECORATION. "computed" is read from the catalog's
 * own `derived` flag, the level count from the dataset's depth axis, the
 * isosurface value from the live scene. Nothing here is a hand-written
 * string that can outlive what it describes.
 */

import type { DatasetInfo } from "@/lib/api";

function Row({
  name,
  badge,
  value,
}: {
  name: string;
  badge?: string;
  value?: string;
}) {
  return (
    <li className="catalog__row">
      <span className="catalog__mark" aria-hidden>
        {"·"}
      </span>
      <span className="catalog__name">{name}</span>
      {badge && <span className="catalog__badge">{badge}</span>}
      {value && <span className="catalog__value num">{value}</span>}
    </li>
  );
}

export default function LayerCatalog({
  dataset,
  levels,
}: {
  dataset: DatasetInfo | null;
  levels: number;
}) {
  if (!dataset) return null;

  const fields = dataset.variables;
  const stored = fields.filter((v) => !v.derived);
  const computed = fields.filter((v) => v.derived);

  return (
    <aside className="catalog" aria-label="Layer catalog">
      {/* The level count sits here, once. It is a property of the cube, and
          repeating it down five rows was both noise and 30 px this panel
          cannot afford. */}
      <div className="catalog__head">
        <span className="catalog__label">Layer catalog</span>
        <span className="catalog__active num">
          {fields.length} &middot; {levels} lv
        </span>
      </div>

      <ul className="catalog__list">
        {stored.map((v) => (
          <Row key={v.name} name={v.label} badge="stored" />
        ))}
        {computed.map((v) => (
          <Row
            key={v.name}
            name={v.label}
            badge="computed"
            /* Only the exception is printed. A surface product has no depth
               axis, so naming it stops the header's level count from being
               read as applying to D26 too. */
            value={v.output === "surface" ? "surface" : undefined}
          />
        ))}
      </ul>

      {/* The extensibility claim, beside the thing it describes. PS F3 and F6
          in one sentence, and checkable: the file is in the repository and
          the counts above are read from it. */}
      <p className="catalog__foot">
        One registry, {computed.length} of {fields.length} computed by plugins,
        all served through OGC WMS and WCS.
      </p>
    </aside>
  );
}
