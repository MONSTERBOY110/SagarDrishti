"use client";

/** The water column, rendered (ROADMAP Phase 1, Spikes A and C).
 *
 * Composition, as built and as recorded in the direction contract in
 * layout.tsx: full-bleed dark globe; the station sheet at the left with the
 * time rule beneath it; a clicked instrument's profile panel at the top right;
 * the provenance cartouche boxed in the bottom band beside the sheet; and the
 * water-column scale bar bottom right, carrying the vertical exaggeration, the
 * depth cursor and the frame-rate readout.
 *
 * An earlier version of this comment promised the frame readout in the
 * top-right margin and the cartouche bottom-left. Both moved (the top right is
 * where the profile opens, and the bottom left is the time rule's corner), and
 * a stale docblock describing a layout that no longer exists is how the next
 * reader gets misled.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import Cartouche from "@/components/Cartouche";
import ScaleBar from "@/components/ScaleBar";
import ProfilePanel from "@/components/ProfilePanel";
import StationSheet from "@/components/StationSheet";
import TimeRule from "@/components/TimeRule";
import {
  api,
  robustRange,
  type DatasetInfo,
  type FieldColumn,
  type ProfileDetail,
  type ProfileGlyph,
} from "@/lib/api";
import { useScene } from "@/lib/scene";

// Cesium is browser-only and large; it must never enter the server bundle.
const OceanGlobe = dynamic(() => import("@/components/OceanGlobe"), { ssr: false });

export default function Page() {
  const scene = useScene();
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [columns, setColumns] = useState<Record<string, FieldColumn>>({});
  const [profiles, setProfiles] = useState<ProfileGlyph[]>([]);
  const [fps, setFps] = useState({ fps: 0, p1: 0 });
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* --- load the cast ------------------------------------------------------- */
  useEffect(() => {
    (async () => {
      try {
        const { datasets } = await api.catalog();
        const ds = datasets.find((d) => d.id === scene.sourceId) ?? datasets[0];
        if (!ds) {
          setError(
            "The catalogue is empty. Run tools/fetch_sample.py then tools/preprocess.py to build the local cube.",
          );
          return;
        }
        setDataset(ds);
        useScene.setState({
          sourceId: ds.id,
          time: ds.times[ds.times.length - 1],
          // Open on the thermocline, not the surface. Two reasons: it is the
          // level a forecaster actually interrogates (cyclone heat potential
          // lives here), and a focus level at the very top of the stack sits
          // in front of every other slice and hides the stratification.
          focusDepth: nearest(ds.depths, 100),
        });

        const { profiles: glyphs } = await api.profiles();
        setProfiles(glyphs);
      } catch (e) {
        setError(
          `Cannot reach the data plane at ${process.env.NEXT_PUBLIC_API_BASE}. ` +
            `Start it with ./tasks.ps1 api. (${String(e)})`,
        );
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* --- prefetch every timestep --------------------------------------------
     Three steps is a few hundred KB, and prefetching makes the time scrub
     instant instead of a request per tick. */
  useEffect(() => {
    if (!dataset) return;
    const bbox = dataset.bbox.join(",");
    let cancelled = false;

    (async () => {
      for (const t of dataset.times) {
        const key = `${scene.variable}@${t}`;
        if (columns[key]) continue;
        try {
          const col = await api.column(dataset.id, scene.variable, bbox, t);
          if (cancelled) return;
          setColumns((prev) => ({ ...prev, [key]: col }));
        } catch (e) {
          if (!cancelled) setError(String(e));
          return;
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, scene.variable]);

  const column = columns[`${scene.variable}@${scene.time}`] ?? null;
  const depths = column?.depths ?? dataset?.depths ?? [];
  /* Which timesteps are actually in hand. The time rule rules an unfetched
     step with a dashed tick rather than pretending every step is ready. */
  const loadedTimes = new Set(
    Object.keys(columns)
      .filter((k) => k.startsWith(`${scene.variable}@`))
      .map((k) => k.slice(k.indexOf("@") + 1)),
  );

  /* Lock the colorbar to a robust range over the WHOLE column, not the visible
     slice: a range that jumped every time the depth cursor moved would make the
     colours meaningless as a measurement. */
  useEffect(() => {
    if (!column) return;
    const [lo, hi] = robustRange(column);
    useScene.setState({ vmin: Math.floor(lo), vmax: Math.ceil(hi) });
  }, [column]);

  /* --- a clicked station mark becomes a profile ---------------------------- */
  useEffect(() => {
    if (!scene.selection) {
      setDetail(null);
      return;
    }
    const id = scene.selection;
    let cancelled = false;
    setLoadingDetail(true);
    (async () => {
      try {
        const d = await api.profile(id);
        if (!cancelled) setDetail(d);
      } catch (e) {
        if (!cancelled) {
          setDetail(null);
          setError(`Could not read profile ${id}: ${String(e)}`);
        }
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scene.selection]);

  const onFps = useCallback((s: { fps: number; p1: number }) => setFps(s), []);
  const onPick = useCallback((id: string | null) => useScene.setState({ selection: id }), []);
  const onReady = useCallback(() => undefined, []);

  return (
    <main style={{ position: "relative", height: "100vh", overflow: "hidden" }}>
      <div className="scene">
        <OceanGlobe
          column={column}
          profiles={profiles}
          selection={scene.selection}
          focusDepth={scene.focusDepth}
          exaggeration={scene.exaggeration}
          opacity={scene.opacity}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          onFps={onFps}
          onPickProfile={onPick}
          onReady={onReady}
          onError={setError}
        />
      </div>

      {/* --- the sheet, and the time rule under it --------------------------- */}
      <div className="panel-stack">
        <StationSheet
          dataset={dataset}
          column={column}
          columnPending={!column && !error}
          variable={scene.variable}
          time={scene.time}
          focusDepth={scene.focusDepth}
          exaggeration={scene.exaggeration}
          opacity={scene.opacity}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          onVariable={(v) => useScene.setState({ variable: v })}
          onFocusDepth={scene.setFocusDepth}
          onExaggeration={(exaggeration) => useScene.setState({ exaggeration })}
          onOpacity={(opacity) => useScene.setState({ opacity })}
        />
        {dataset && (
          <TimeRule
            times={dataset.times}
            loaded={loadedTimes}
            current={scene.time}
            playing={scene.playing}
            onTime={scene.setTime}
            onTogglePlay={scene.togglePlaying}
          />
        )}
      </div>

      {/* --- the clicked instrument, as its own profile ---------------------- */}
      <div className="panel-right">
        <ProfilePanel
          detail={detail}
          column={column}
          variable={scene.variable}
          units={column?.units ?? ""}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          focusDepth={scene.focusDepth}
          stationCount={profiles.length}
          loading={loadingDetail}
          onFocusDepth={scene.setFocusDepth}
          onClose={() => scene.select(null)}
        />
      </div>

      {/* --- the vertical scale, so 200x is checkable rather than asserted -- */}
      <ScaleBar
        maxDepth={depths.length ? depths[depths.length - 1] : 0}
        exaggeration={scene.exaggeration}
        focusDepth={scene.focusDepth}
        fps={fps.fps}
        p1={fps.p1}
      />

      {/* --- provenance ------------------------------------------------------ */}
      <div className="provenance">
        <Cartouche
          citation={column?.citation ?? dataset?.citation ?? ""}
          time={column?.time ?? scene.time}
          levels={depths.length}
          depthRange={depths.length ? [depths[0], depths[depths.length - 1]] : null}
          retrievedAt={dataset?.retrieved_at ?? null}
          offline
        />
      </div>

      {/* --- the one error state that matters: no data plane ----------------- */}
      {error && (
        <div
          className="sheet"
          role="alert"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            zIndex: 4,
            maxWidth: "30rem",
            padding: "1rem 1.125rem",
            borderTop: "3px solid var(--caution)",
          }}
        >
          <h2
            className="label"
            style={{ margin: 0, color: "var(--caution-ink)", fontSize: "0.75rem" }}
          >
            Errata - no cast on file
          </h2>
          {/* Prose in the form's own face, per the typewriter rule in
              globals.css: the monospace is for entered values, not sentences. */}
          <p style={{ margin: "0.375rem 0 0", fontSize: "0.8125rem", lineHeight: 1.5 }}>
            {error}
          </p>
        </div>
      )}
    </main>
  );
}

/** Nearest available value - the depth axis is non-uniform, so a requested
 *  depth is always snapped to a level that exists. */
function nearest(values: number[], target: number): number {
  return values.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a), values[0]);
}
