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
import { useCallback, useEffect, useMemo, useState } from "react";

import Cartouche from "@/components/Cartouche";
import ScaleBar from "@/components/ScaleBar";
import SceneSummary from "@/components/SceneSummary";
import ProfilePanel from "@/components/ProfilePanel";
import HazardPanel from "@/components/HazardPanel";
import AskPanel from "@/components/AskPanel";
import ScorecardPanel from "@/components/ScorecardPanel";
import StoryPlayer from "@/components/StoryPlayer";
import SagarNodePanel from "@/components/SagarNodePanel";
import ColumnStudio from "@/components/ColumnStudio";
import LayerCatalog from "@/components/LayerCatalog";
import StationLegend from "@/components/StationLegend";
import StationSheet from "@/components/StationSheet";
import TimeRule from "@/components/TimeRule";
import {
  api,
  displayUnits,
  robustRange,
  type DatasetInfo,
  type FieldColumn,
  type ProfileDetail,
  type IsosurfaceMesh,
  type CurrentField,
  type ProfileGlyph,
  type SagarNodeStation,
  type WarningAlert,
} from "@/lib/api";
import { describeMesh } from "@/lib/isosurface";
import { CURRENT_SOURCE, describeCurrents } from "@/lib/currents";
import { defaultIsovalue, useScene } from "@/lib/scene";

// Cesium is browser-only and large; it must never enter the server bundle.
const OceanGlobe = dynamic(() => import("@/components/OceanGlobe"), { ssr: false });

export default function Page() {
  const scene = useScene();
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [columns, setColumns] = useState<Record<string, FieldColumn>>({});
  const [profiles, setProfiles] = useState<ProfileGlyph[]>([]);
  const [fps, setFps] = useState({ fps: 0, p1: 0, moving: false });
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isosurface, setIsosurface] = useState<IsosurfaceMesh | null>(null);
  /* Kept apart from `error`: a failed isosurface must not blank the scene the
     way a failed catalogue does. The slices and the floats are still valid. */
  const [isoError, setIsoError] = useState<string | null>(null);
  /* Lifted out of HazardPanel so the globe draws exactly the list the panel
     lists. Two components each fetching their own warnings could disagree
     about what is being warned about, which on this layer is not a cosmetic
     inconsistency. */
  const [warnings, setWarnings] = useState<WarningAlert[]>([]);
  /* Depth-resolved currents (PS F1), a SECOND dataset (Copernicus, not
     INCOIS). Kept apart from `columns` because it is fetched per depth rather
     than per timestep: the arrows live on one level and the depth cursor moves
     constantly, so caching a whole column here would fetch 40 levels to draw
     one. */
  const [currents, setCurrents] = useState<CurrentField | null>(null);
  const [currentsError, setCurrentsError] = useState<string | null>(null);
  /* The tabletop rig (PS F6), lifted out of its panel for the same reason the
     warnings are: the globe has to draw exactly the station the panel lists,
     and two pollers could disagree about whether the threshold has tripped.
     Null is the normal state and means no mark and no panel. */
  const [sagarnode, setSagarnode] = useState<SagarNodeStation | null>(null);
  /* The water column studio (beat-competition.md T2). Closed by default and
     mounted only while open, so an overlay can never be in the way of the
     scene and a fault in it cannot reach the globe. */
  const [studioOpen, setStudioOpen] = useState(false);

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

  /* --- the isosurface, fetched only while its layer is on -----------------
     Not prefetched across timesteps like the columns are: extraction is a few
     milliseconds and the mesh is a few kilobytes, so a request per change is
     cheaper than holding three meshes for a layer that is off by default. */
  useEffect(() => {
    if (!dataset || !scene.isosurfaceOn || !scene.time) {
      setIsosurface(null);
      return;
    }
    // The RAW unit the cube declares, never the printed label: the server
    // checks the isovalue against the served units and would rightly refuse
    // "PSU" where the dataset says "1".
    const units = dataset.variables.find((v) => v.name === scene.variable)?.units ?? "";
    let cancelled = false;

    (async () => {
      try {
        const mesh = await api.isosurface(
          dataset.id,
          scene.variable,
          scene.isovalue,
          units,
          dataset.bbox.join(","),
          scene.time,
        );
        if (!cancelled) setIsosurface(mesh);
      } catch (e) {
        if (!cancelled) {
          setIsosurface(null);
          setIsoError(String(e));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, scene.isosurfaceOn, scene.isovalue, scene.variable, scene.time]);

  /* --- the current arrows, fetched only while their layer is on ------------
     Per (time, depth) rather than per column: at 1/12 degree one level is
     43,621 cells, so fetching all 40 to draw one would move 42 MB to show a
     few hundred arrows. The server decimates before it answers, so what
     arrives is already a few tens of kilobytes. */
  useEffect(() => {
    if (!dataset || !scene.currentsOn || !scene.time) {
      setCurrents(null);
      return;
    }
    let cancelled = false;

    (async () => {
      try {
        const field = await api.currents(
          CURRENT_SOURCE,
          dataset.bbox.join(","),
          scene.time,
          scene.focusDepth,
        );
        if (!cancelled) {
          setCurrents(field);
          setCurrentsError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setCurrents(null);
          // Kept apart from `error`, like the isosurface's: a missing
          // Copernicus cube must not blank a scene whose slices and floats are
          // all still valid. It is a second dataset and it can be absent.
          //
          // The SENTENCE, not the exception. The commonest way to land here is
          // moving the depth cursor to 2000 m, where the INCOIS field has a
          // level and GLORYS does not, and the server answers that with a
          // plain explanation. Printing "Error: 400 ..." in front of it turned
          // a good message into what looks like a crash.
          setCurrentsError(String(e).replace(/^Error:\s*\d{3}\s*/, ""));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, scene.currentsOn, scene.time, scene.focusDepth]);

  const column = columns[`${scene.variable}@${scene.time}`] ?? null;
  const depths = column?.depths ?? dataset?.depths ?? [];
  /* What the panels PRINT for the unit. The cube declares salinity as CF's
     dimensionless "1", which is correct and unreadable on a form, so the label
     is translated by standard name while every request keeps the raw string
     (lib/api.ts:displayUnits). */
  const variableInfo = dataset?.variables.find((v) => v.name === scene.variable) ?? null;
  const unitsLabel = displayUnits(
    column?.units ?? variableInfo?.units ?? "",
    variableInfo?.canonical ?? null,
  );
  /* Which timesteps are actually in hand. The time rule rules an unfetched
     step with a dashed tick rather than pretending every step is ready. */
  const loadedTimes = new Set(
    Object.keys(columns)
      .filter((k) => k.startsWith(`${scene.variable}@`))
      .map((k) => k.slice(k.indexOf("@") + 1)),
  );

  /* The range the field itself suggests: robust percentiles over the WHOLE
     column, not the visible slice, because a range that jumped every time the
     depth cursor moved would make the colours meaningless as a measurement. */
  const dataRange: [number, number] | null = useMemo(() => {
    if (!column) return null;
    const [lo, hi] = robustRange(column);
    return [Math.floor(lo), Math.ceil(hi)];
  }, [column]);

  /* Per instrument class, TWO counts, and the difference between them is not
     pedantry.

     A mark on the globe is one PROFILE: one cast, at one position, at one
     time. A drifting float that reported three times is three marks in three
     places, and three BGC floats produced the nine BGC marks in this box.
     Counting the marks and calling the total "floats" would have this page
     claim nine biogeochemical floats in the Bay of Bengal where there are
     three, which is precisely the kind of overstatement an INCOIS reviewer is
     equipped to catch.

     Both numbers are computed once, here, so the legend, the spoken summary
     and the profile panel cannot disagree about them. */
  const stationKinds = useMemo(() => {
    const counts: Record<string, { profiles: number; platforms: number }> = {};
    const seen: Record<string, Set<string>> = {};
    for (const profile of profiles) {
      const kind = profile.platform_kind;
      seen[kind] ??= new Set();
      seen[kind].add(profile.wmo);
      counts[kind] = {
        profiles: (counts[kind]?.profiles ?? 0) + 1,
        platforms: seen[kind].size,
      };
    }
    return counts;
  }, [profiles]);

  /** Distinct instruments behind those marks, across every class. */
  const platformCount = useMemo(
    () => new Set(profiles.map((p) => p.wmo)).size,
    [profiles],
  );

  /* Follow that suggestion only until the forecaster sets the range by hand.
     Overwriting an edited limit on the next timestep would change the colours
     under a value the reader has already interpreted. */
  useEffect(() => {
    if (!dataRange) return;
    if (useScene.getState().colorbarLocked) return;
    useScene.setState({ vmin: dataRange[0], vmax: dataRange[1] });
  }, [dataRange]);

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

  /* Which profile column the scene's variable is scored against. The studio
     draws the residual between these two, so passing the wrong one would
     shade the gap between a temperature and a salinity. */
  const observedColumn = scene.variable === "SAL" ? "psal" : "temp";

  const onFps = useCallback(
    (s: { fps: number; p1: number; moving: boolean }) => setFps(s),
    [],
  );
  const onPick = useCallback((id: string | null) => useScene.setState({ selection: id }), []);
  /* A studio with no cast behind it would render an empty frame over the
     scene, so deselecting closes it. */
  useEffect(() => {
    if (!scene.selection) setStudioOpen(false);
  }, [scene.selection]);

  /* Bring a newly opened cast into view inside the right column.
     That column scrolls, and on anything shorter than about 900 px the
     verification card alone pushes the profile's chart past the bottom: the
     parameter chips are visible and the curve under them is not, which looks
     exactly like a station that failed to load. It is worst during a guided
     tour, where nobody has a hand on the scroll wheel. `nearest` scrolls the
     minimum needed, so on a tall screen it does nothing at all. */
  useEffect(() => {
    if (!detail) return;
    document
      .querySelector('[aria-label="Instrument profile"]')
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [detail]);
  const onReady = useCallback(() => undefined, []);

  return (
    <main style={{ position: "relative", height: "100vh", overflow: "hidden" }}>
      {/* A labelled region, because a bare canvas has no accessible name and
          the scene is this product's primary display. */}
      <div className="scene" role="region" aria-label="Ocean scene">
        <OceanGlobe
          column={column}
          isosurface={isosurface}
          profiles={profiles}
          warnings={warnings}
          currents={currents}
          sagarnode={sagarnode}
          selection={scene.selection}
          focusDepth={scene.focusDepth}
          exaggeration={scene.exaggeration}
          opacity={scene.opacity}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          reverse={scene.reverse}
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
          reverse={scene.reverse}
          colorbarLocked={scene.colorbarLocked}
          dataRange={dataRange}
          isosurfaceOn={scene.isosurfaceOn}
          isovalue={scene.isovalue}
          currentsOn={scene.currentsOn}
          currentSummary={currentsError ?? describeCurrents(currents)}
          onToggleCurrents={() =>
            useScene.setState({ currentsOn: !useScene.getState().currentsOn })
          }
          units={unitsLabel}
          isoSummary={isoError ?? (isosurface ? describeMesh(isosurface) : null)}
          onToggleIsosurface={scene.toggleIsosurface}
          onIsovalue={scene.setIsovalue}
          onVariable={(v) =>
            useScene.setState({
              variable: v,
              colorbarLocked: false,
              // 26 is a thermocline in degC and nothing at all in psu, so the
              // isovalue follows the variable rather than carrying over.
              isovalue: defaultIsovalue(v, useScene.getState().isovalue),
            })
          }
          onColorbar={(patch) => useScene.setState(patch)}
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

      {/* --- the certificate, then the clicked instrument -------------------
          The verification card sits ABOVE the profile, because it is the claim
          the profile is evidence for: a reader meets "the model is 0.60 degC
          off" before they meet one cast that shows why. */}
      <div className="panel-right">
        <ScorecardPanel
          sourceId={dataset?.id ?? null}
          variable={scene.variable}
          variableLabel={
            dataset?.variables.find((v) => v.name === scene.variable)?.label ?? scene.variable
          }
        />
        {/* Opens the column studio for the cast already on screen. Rendered
            here rather than inside ProfilePanel so that the panel, which the
            browser suite drives heavily, is untouched by this feature. */}
        {detail && column && (
          <button
            type="button"
            className="tick studio__open"
            onClick={() => setStudioOpen(true)}
          >
            Inspect the water column
          </button>
        )}
        <ProfilePanel
          detail={detail}
          column={column}
          variable={scene.variable}
          units={unitsLabel}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          reverse={scene.reverse}
          focusDepth={scene.focusDepth}
          stationCount={profiles.length}
          platformCount={platformCount}
          loading={loadingDetail}
          onFocusDepth={scene.setFocusDepth}
          onClose={() => scene.select(null)}
        />
      </div>

      {/* The scene in words, for a reader who cannot see the canvas. */}
      <SceneSummary
        datasetTitle={dataset?.title ?? null}
        variable={scene.variable}
        units={unitsLabel}
        focusDepth={scene.focusDepth}
        depthMin={depths.length ? depths[0] : 0}
        depthMax={depths.length ? depths[depths.length - 1] : 0}
        levels={depths.length}
        time={column?.time ?? scene.time}
        exaggeration={scene.exaggeration}
        stationCount={profiles.length}
        stationKinds={stationKinds}
        platformCount={platformCount}
        selectedWmo={detail?.wmo ?? null}
        selectedKind={detail?.platform_kind ?? null}
        vmin={scene.vmin}
        vmax={scene.vmax}
        warnings={warnings}
        sagarnode={sagarnode}
      />

      {/* --- the open band beside the sheet: what the marks are, and what is
              being warned about over this water (PS F13) ------------------ */}
      <div className="panel-mid">
        <StationLegend
          profiles={profiles}
          platformCount={platformCount}
          sagarnode={sagarnode !== null}
        />
        {/* The live rig, above the warnings and below the legend. Absent
            entirely when nothing is plugged in, which is most of the time. */}
        <SagarNodePanel onStation={setSagarnode} />
        <HazardPanel
          at={column?.time ?? scene.time}
          bbox={dataset ? dataset.bbox.join(",") : null}
          rehearsal={scene.rehearsal}
          onRehearsal={(rehearsal) => useScene.setState({ rehearsal })}
          onLayer={setWarnings}
        />
        {/* What the platform can draw, stated on the first frame.

            LAST IN THIS COLUMN, AND THAT IS LOAD BEARING. This panel is inert
            (pointer-events: none), so it never intercepts a click on the
            water. HazardWatch below it is not. Placed FIRST, this panel's
            243 px pushed HazardWatch from y 376 down to y 629, directly onto
            the glider track at x 310 to 622, y 610 to 785, and clicking a
            dive opened the warning card instead of the profile. The e2e suite
            caught it. Ordered last, HazardWatch never moves and the measured
            cost of this panel is zero blocked marks. */}
        <LayerCatalog dataset={dataset} levels={depths.length} />
      </div>

      {/* --- the vertical scale, so 200x is checkable rather than asserted -- */}
      <ScaleBar
        maxDepth={depths.length ? depths[depths.length - 1] : 0}
        exaggeration={scene.exaggeration}
        focusDepth={scene.focusDepth}
        fps={fps.fps}
        p1={fps.p1}
        fpsMoving={fps.moving}
      />

      {/* --- the two surfaces that narrate rather than control ---------------
          The agent (PS F8) and the guided tours (PS F12), in the one band the
          four corners leave free. Both drive the same store the controls
          drive, so there is no second path through the renderer to keep in
          step, and the agent panel is absent entirely when its service is not
          running, which is TRD section 6.5 made visible. */}
      <div className="stage-foot">
        <AskPanel />
        <StoryPlayer />
      </div>

      {studioOpen && (
        <ColumnStudio
          detail={detail}
          column={column}
          variableLabel={variableInfo?.label ?? scene.variable}
          units={unitsLabel}
          palette={scene.palette}
          scale={scene.scale}
          vmin={scene.vmin}
          vmax={scene.vmax}
          reverse={scene.reverse}
          sourceId={dataset?.id ?? null}
          variable={scene.variable}
          observed={observedColumn}
          onClose={() => setStudioOpen(false)}
        />
      )}

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
