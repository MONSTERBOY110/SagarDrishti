"use client";

/** The one piece of chrome that is always there: how to get the rest back.
 *
 * A clean opening frame is only an improvement if the things it hides are
 * obviously reachable. An empty globe with no affordance is not minimal, it is
 * broken, and a judge who cannot find the layer catalog concludes there isn't
 * one. So every panel the first frame suppresses is named here, in a row, with
 * its state visible.
 *
 * It sits in the footer band because that band is empty on the opening frame
 * anyway once the agent and the tours become panels rather than fixtures. That
 * costs no vertical space, which matters: the last regression this project
 * shipped was a panel stack that grew past the bottom of a 768 px laptop.
 */

import { useEffect } from "react";

import { PANEL_LABELS, PANEL_ORDER, usePanels } from "@/lib/panels";

export default function PanelDock() {
  const open = usePanels((s) => s.open);
  const chromeHidden = usePanels((s) => s.chromeHidden);
  const toggle = usePanels((s) => s.toggle);
  const toggleChrome = usePanels((s) => s.toggleChrome);

  /* One key for the pure-globe shot, which is how the video should open.
     Ignored while typing, or asking the agent a question would hide the panel
     being typed into on every "h". */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "h" && e.key !== "H") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || el?.isContentEditable) return;
      e.preventDefault();
      toggleChrome();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleChrome]);

  return (
    <nav className="dock" aria-label="Panels">
      {PANEL_ORDER.map((id) => {
        const on = !chromeHidden && open[id];
        return (
          <button
            key={id}
            type="button"
            className="dock__tab"
            aria-pressed={on}
            onClick={() => toggle(id)}
          >
            {PANEL_LABELS[id]}
          </button>
        );
      })}
      <button
        type="button"
        className="dock__tab dock__tab--chrome"
        aria-pressed={chromeHidden}
        onClick={toggleChrome}
        title="Hide every overlay and leave the water (h)"
      >
        {chromeHidden ? "Show panels" : "Water only"}
        <kbd className="dock__key">h</kbd>
      </button>
    </nav>
  );
}
