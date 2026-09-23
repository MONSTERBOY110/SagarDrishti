---
name: SagarDrishti
description: A CTD station sheet clipped over the open water column, where hue is reserved for the measurement.
colors:
  abyss: "#05080c"
  plate: "#222B36"
  plate-shade: "#1A212A"
  ink: "#E3EBF0"
  ink-soft: "#A9B8C4"
  ink-faint: "#8493A0"
  rule: "#4A94B6"
  rule-soft: "rgba(74, 148, 182, 0.34)"
  caution: "#D4553C"
  caution-ink: "#F08A72"
  caution-stamp: "#e8735a"
  stamp: "#cfd8dc"
  stamp-soft: "#7f8f99"
typography:
  display:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "0.13em"
  title:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.11em"
  label:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    letterSpacing: "0.09em"
  stamp:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 700
    letterSpacing: "0.11em"
  body:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  value:
    fontFamily: "Courier Prime, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0"
    fontFeature: "tabular-nums lining-nums"
rounded:
  none: "0px"
  hole: "50%"
spacing:
  hair: "2px"
  thin: "3px"
  tight: "4px"
  step: "5px"
  rule-gap: "7px"
  field: "8px"
  stack: "10px"
  body: "12px"
  frame: "20px"
components:
  sheet:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 13px 11px 12px"
    width: "21rem"
  sheet-margin:
    backgroundColor: "{colors.plate-shade}"
    rounded: "{rounded.none}"
    padding: "32px 0"
    width: "20px"
  sheet-hole:
    backgroundColor: "{colors.abyss}"
    rounded: "{rounded.hole}"
    size: "8px"
  overprint:
    textColor: "{colors.caution-ink}"
    typography: "{typography.stamp}"
    rounded: "{rounded.none}"
    padding: "3px 6px"
  tick:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "2px 8px"
  tick-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.plate}"
  tick-disabled:
    textColor: "{colors.ink-faint}"
  rack-row:
    textColor: "{colors.ink-soft}"
    typography: "{typography.value}"
    padding: "2px 0"
  rack-row-active:
    backgroundColor: "rgba(74, 148, 182, 0.1)"
    textColor: "{colors.ink}"
  rack-row-hover:
    backgroundColor: "rgba(227, 235, 240, 0.07)"
    textColor: "{colors.ink}"
  rack-row-empty:
    textColor: "{colors.ink-faint}"
  field-thumb:
    backgroundColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: "6px"
    height: "18px"
  ramp:
    rounded: "{rounded.none}"
    height: "9px"
  cartouche:
    backgroundColor: "rgba(5, 8, 12, 0.78)"
    textColor: "{colors.stamp}"
    rounded: "{rounded.none}"
    padding: "8px 12px 9px"
    width: "32rem"
  scalebar:
    backgroundColor: "rgba(5, 8, 12, 0.78)"
    textColor: "{colors.stamp}"
    rounded: "{rounded.none}"
    padding: "7px 10px 8px"
  profile-panel:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: "25rem"
---

# Design System: SagarDrishti

## Overview

**Creative North Star: "The Station Logsheet"**

A CTD station sheet, printed on cool slate form stock and clipped over the
open water column. The globe is the ocean below the surface, rendered
near-black; everything a forecaster reads is printed matter laid on top of it,
opaque and square-cut. The surface deliberately refuses the category default for
ocean dashboards: no glass panels floating over a moving 3D scene, no glowing
cyan accents, no rounded cards. A translucent panel over a moving scene is
unreadable exactly when a forecaster needs it, and glow spends hue that belongs
to the measurement.

**The ground inverted on 22 September 2026.** The stock was warm manila
(`#c4b89a`) carrying near-black ink, and judges reviewing the prototype said the
colour was off and that the result did not read as a 3D model. It read as a
document, because it was one. Everything the refusal above is actually about is
unchanged: the panels are still opaque, still square, still ruled, and there is
still no glow. A dark ground is not what makes a dashboard a dashboard. Every
contrast ratio in this file was re-measured against the new plate rather than
carried over.

The organising discipline is that hue is reserved for the measurement. The
plate, the inks and the rulings are all achromatic-cool. The only saturated
colour permitted on screen is the data field's own colorbar plus one reserved
caution ink. Everything a normal interface would signal with colour is signalled
here in rule form instead: a hairline rule means available, a 3px double rule
means active, a dashed rule means pending, a half-strength rule means no data.
That is not a stylistic tic. The product's own accessibility commitment says
colour must never be the sole carrier of meaning, because the colorbar is being
read as a measuring instrument, and a state grammar built from rules leaves the
whole hue budget to the data.

Density is high and unapologetic. This is an instrument for a desk, not a
landing page: 24 depth levels print as 24 ruled rows in one column, and the rack
never scrolls internally because the rack is the water column. Type sits between
10px and 17px, tightly ranged, because a form gets its hierarchy from rules and
weight rather than from size. Motion is a stamp, not an ease: state commits in
90ms across two frames and stops. The only continuous movement is the camera and
the time scrub.

**Key Characteristics:**
- Opaque slate plate (`#222B36`) as a real seamless raster, laid on near-black water (`#05080c`)
- Hue reserved for the measurement; chrome is achromatic-cool plus one caution ink
- State carried in rule form (single, doubled, dashed, half-strength), never in hue
- Two faces with a meaningful split: the printed form versus the typewriter that filled it in
- Square corners everywhere, one shadow, a punched binding margin with a printed margin rule
- 90ms two-frame stamp for every state commit; no easing anywhere
- Every colour-mapped value is accompanied by its number and its provenance

## Colors

An achromatic-cool palette of stock and ink, ruled in a single process blue,
with one reserved caution ink held in three values and a cool near-white for
readouts that sit directly on the water. No other saturated colour belongs to
the chrome. Since the ground inverted the ink ramp DESCENDS in lightness:
"fainter" now means darker, where on the manila plate it meant lighter.

### Primary

- **Process Blue** (`#4A94B6`): the ruling ink. Lightened from `#2b6a86`,
  which measured 3.04:1 on manila and only 2.39:1 here, under the 3:1 floor a
  non-text mark needs. Every rule, track, tick mark,
  column-head underline, control border, text selection and focus ring on the
  plate is drawn in it. It carries state by weight and dash, not by shade. It
  never sets type, at any size, anywhere.
- **Process Blue, Half Strength** (`rgba(74, 148, 182, 0.34)`): the field rule
  inside a block. Used for the per-row rulings of the cast-field grid, the block
  dividers and the resting rack row, so a form full of rules does not read as a
  cage.

### Secondary

- **Caution Vermilion** (`#D4553C`): the reserved ink, for rules and marks only.
  The printed margin rule down the binding edge, the overprint stamp's double
  frame, the top rule of the errata sheet. Measured at 3.5:1 on the plate, which
  is sound for a rule and disqualifying for text.
- **Caution Ink** (`#F08A72`): the same reserved voice, now LIGHTENED until it
  can carry text on the plate (5.9:1). Used for the overprint's letters and for
  printed caveats such as the profile panel's statement that the model curve is
  a nearest cell rather than a Class-4 co-location. It was `#7e2110`, darkened
  for light paper; against slate that measures 1.4:1 and was the least legible
  value in the palette, so the two grounds' values have swapped sides.
- **Caution Stamp** (`#e8735a`): the same voice at the value that carries text
  on the water (6.7:1). Used by the frame-rate readout when the render drops
  below the floor. The one caution value the inversion did not move.

### Neutral

- **Slate Plate** (`#222B36`): the form stock, and the background of every
  readable surface. Painted as a raster tile whose mean RGB is this exact value,
  so the grain is visible rather than buried under a flat fill. It is 1.40:1
  against the water where manila was 10.2:1, so the sheet carries an explicit
  `#5A6874` hairline: light stock separated itself by luminance and needed no
  edge, and a black drop shadow on a black ground draws nothing.
- **Slate Shade** (`#1A212A`): the punched binding margin and the scrollbar
  track. The same stock a shade down. NOT multiply-blended, which is how the
  manila margin was made: multiplying this by a tile that averages the plate
  lands at 4, 6, 9, i.e. black, because multiply darkens proportionally and a
  dark ground has nothing left to take. A flat wash over the tile hits the token
  within a level per channel and keeps the grain.
- **Abyss** (`#05080c`): the water. The page background, the Cesium scene and
  globe base colour, the underground colour, and the punched holes in the
  binding margin, which show the water through the sheet.
- **Ink** (`#E3EBF0`): the printing ink. Titles, entered values, active rack
  rows, the slider's pen mark, the double rule under the cast head, the station
  mark's outline on the globe, and the model curve in the profile chart.
  11.9:1 on the plate. The station mark inverted with it: the glyph body used
  to be the manila plate colour, which on slate would vanish into the water,
  so the body follows the ink and the outline is the abyss.
- **Ink Soft** (`#A9B8C4`): secondary printed matter. Field labels, column
  heads, subtitles, resting rack rows, chart axis text. 7.1:1.
- **Ink Faint** (`#8493A0`): tertiary. Rack serial numbers, disabled controls,
  levels with no data, the dashed placeholder bar. 4.5:1, which is the floor
  for anything that still has to be read.
- **Stamp** (`#cfd8dc`): readouts printed directly on the water. Body colour,
  cartouche and scale-bar text, the scale bar's alternating segments.
- **Stamp Soft** (`#7f8f99`): secondary on the water. Box borders for the
  cartouche and scale bar, the vertical-exaggeration line, and the Cesium
  attribution.

### The data palettes

Six sequential and diverging colorbars live outside the chrome palette because
they are the instrument, not the decoration: `thermal`, `haline`, `deep`,
`balance`, `algae`, `gray`. Each is defined by seven anchor stops interpolated
into a 256-entry lookup table (`gray` uses three), and the same table drives the
globe slices, the sheet's legend ramp and the observed curve in the profile
chart, so one value can never appear as two colours. Out-of-range values clamp
and stay fully opaque, because in a hazard context the extremes are the data
that matters most. The client table is duplicated from the server's colormap on
purpose and the two must change in the same commit.

### Named Rules

**The Reserved Hue Rule.** Hue belongs to the measurement. The plate, the inks
and the rulings are achromatic-cool; the only saturated colour on screen is the
active field's colorbar plus the reserved caution ink. Base imagery on the globe
is pushed to `brightness 0.52 / saturation 0.26 / contrast 1.24` for the same
reason: land reads as context, never as content.

**The Three-Value Caution Rule.** One hue cannot be legible on two grounds. Use
`#D4553C` for rules and marks, `#F08A72` for caution text on the plate, and
`#e8735a` for caution text on the water. Never substitute one for another to
save a token. Both grounds are dark now, and the plate and water values are
still different because the plate is a lifted surface and the water is not.

**The Rule-Never-Text Rule.** Process blue draws rules, tracks, ticks, borders
and focus rings. It has zero text uses in the build and must keep zero.

**The Uncoloured Absence Rule.** Missing data is never coloured. On the globe,
land and fill values are written fully transparent and black, so nothing bleeds
under them. On the sheet, a level with no data prints `n/a` at half-strength
rule; a level not yet read prints a dot leader on a dashed rule. Pending and
missing are different facts and never share a mark.

## Typography

**Display Font:** Archivo Narrow (with `system-ui, sans-serif`)
**Body Font:** Archivo Narrow (with `system-ui, sans-serif`)
**Label/Mono Font:** Courier Prime (with `ui-monospace, monospace`)

**Character:** Two faces with one meaningful division. Archivo Narrow is the
form's own face: condensed, engraved, set in tracked uppercase for every label,
column head and stamp, and in sentence case for printed prose. Courier Prime is
the typewriter that filled the form in: every measured value, identifier,
timestamp and coordinate. On a real cast sheet the typewriter is what was
entered, and that is exactly the distinction the pairing carries here.

Both faces are self-hosted from `/fonts` with `font-display: block`, never a
CDN, because the entire demo must run air-gapped and the form must not reflow
mid-read. Archivo Narrow 3.002 is a genuine variable font, verified with
fontTools (`fvar` axes `[('wght', 400.0, 400.0, 700.0)]`), so the
`font-weight: 400 700` declaration is real interpolation rather than synthetic
bold. Courier Prime 3.018 ships as two static faces, 400 and 700. Both are SIL
Open Font License 1.1. Both are latin-subset only, which means the vendored
faces cannot currently render the Devanagari, Telugu and Tamil the product
commits to; that is a known gap for the multilingual work, not a solved problem.

### Hierarchy

- **Display** (700, `1.0625rem`, line-height 1.05, `0.13em`, uppercase): the
  sheet's own title. One per surface, immediately above the double rule that
  closes the cast head.
- **Title** (700, `0.8125rem`, `0.11em`, uppercase): a secondary sheet's head,
  such as the instrument profile panel. Also the register for the cartouche head
  at the smaller `0.6875rem`.
- **Label** (700, `0.6875rem`, `0.09em`, uppercase): every field label, block
  head and control legend on the plate. Column heads in the rack drop to
  `0.625rem` at `0.07em`, and the cast-field terms sit at `0.08em`.
- **Body** (400, `0.75rem`, line-height 1.4): printed prose. Citations, QC
  policy statements, caveats, empty-state instructions. Runs at `0.6875rem` with
  line-height 1.45 inside the profile footer.
- **Stamp** (700, `0.625rem`, `0.11em` to `0.14em`, uppercase): the smallest
  printed devices. The overprint, the scale-bar legend, the cartouche head.
  Tracking rises as size falls, which is what makes a 10px stamp read as
  pressed rather than shrunken.
- **Value** (Courier Prime 400 or 700, `0.625rem` to `0.75rem`, `tabular-nums
  lining-nums`, no tracking): every number on the surface, carried by the `.num`
  class. Tabular figures are load-bearing: a column of 24 depth values stays a
  column when the values change.

### Named Rules

**The Typewriter-Is-Entered Rule.** Courier Prime carries only what was
entered: measured values, identifiers, timestamps, coordinates, level counts.
Archivo Narrow carries the form itself: labels, heads and printed prose. Prose
never takes `.num`. Audit test: read any paragraph on screen; if it is a
sentence, it must be in the sans face.

**The Two Weights Rule.** 400 and 700 only, on both faces. The variable axis
spans 400 to 700 and the build uses neither end's interior. Do not introduce a
500 or a 600 to soften a label; a form's emphasis is binary.

**The Tracked-Uppercase Rule.** Printed matter is uppercase with `0.07em` to
`0.14em` of tracking. The typewriter face never takes tracking, because tabular
figures already own their advance width.

## Layout

An absolutely positioned instrument panel over a full-bleed scene, with a single
`1.25rem` inset that every floating device shares. The scene fills the viewport
(`.scene` at `inset: 0`) and four devices sit on top of it at `z-index: 2`:

- **Top left**, the panel stack at `--sheet-w: 21rem`: the station sheet with
  the time rule beneath it, `0.625rem` apart, capped at `calc(100vh - 2.5rem)`
  and scrolling as one column.
- **Top right**, the instrument profile at `25rem`, which is where a clicked
  station mark opens.
- **Bottom band**, the provenance cartouche, spanning from
  `calc(var(--sheet-w) + 2.5rem)` to `right: 15rem` and capped at `32rem` wide.
  It clears the sheet on the left, because a 24-row rack owns the bottom-left
  corner, and clears the scale bar on the right.
- **Bottom right**, the vertical scale bar at `bottom: 3rem`, offset upward so
  the Cesium attribution below it is never clipped. That attribution is a
  licensing obligation, so it is laid out in normal flow inside its own
  container with real room, rather than left to Cesium's absolute positioning.

The spacing rhythm is a printer's rhythm rather than an 8-point grid: it steps
in single pixels through 2, 3, 4, 5, 6, 7, 8, 10, 12, 13 and 20, because the
recurring measure is the gap between a rule and the row it rules. Blocks pad
`0.4375rem` vertically and divide with a half-strength rule; the last block and
the rack drop the divider so the sheet does not close on a stray line. The rack
itself is a four-column grid (`1.5rem 2.75rem 1fr 3rem`: serial, depth, bar,
value) with `overflow: visible`, so all 24 levels print at once.

Responsive behaviour is honest rather than adaptive, since the operating context
is a forecast desk and a stage. At `1500px` the cartouche narrows to `25rem`. At
`900px` the whole composition unstacks into one column in document order: the
scene becomes a `46vh` block at the top, then the panel stack, the scale bar,
the profile panel, the cartouche and the frame readout, each stripped of its
absolute positioning and given a `1.25rem` side margin. Nothing overlaps and
nothing becomes unreachable.

### Named Rules

**The Rack-Is-The-Column Rule.** The bottle rack never scrolls inside itself.
All 24 levels print, because the rack is a drawing of the water column and a
window onto ten of them is a different object.

**The Unclipped Attribution Rule.** Cesium's credit line carries a licensing
obligation. Nothing may cover it, and every device near the bottom-right corner
is positioned off it.

## Elevation & Depth

The system is flat by material. Printed matter does not stack; it lies on the
plate, and depth comes from the one real relationship in the world, which is a
sheet of paper resting on dark water.

There is exactly one shadow in the whole build, and it belongs to the sheet.
Every other separation is done with a rule, a border or the plate's own tone:
the binding margin steps down to `--plate-shade` and takes a 1px ink border, the
cast head closes with a 3px double rule, blocks divide on half-strength rules.
Devices that sit on the water get a bordered box at `rgba(5, 8, 12, 0.78)`
instead of a shadow, because over a moving scene a border is what makes text
legible and a shadow is not.

### Shadow Vocabulary

- **Sheet on water** (`box-shadow: 6px 8px 22px rgba(0, 0, 0, 0.55), 1px 1px 0
  rgba(0, 0, 0, 0.25)`): the only shadow. An offset and blurred cast shadow with
  a 1px hard contact line under it, which is how a clipped sheet actually sits
  on a surface. Applies to `.sheet` and nothing else.
- **Punched hole** (`box-shadow: inset 0 1px 1px rgba(0, 0, 0, 0.8)`): a 1px
  inner shade at the top of each binding hole, so the hole reads as punched
  through the stock rather than printed on it.

### Named Rules

**The One Shadow Rule.** The sheet casts a shadow. Nothing else does. There is
no hover lift, no elevated menu, no focus glow.

**The Box-Over-Water Rule.** Anything that must be read over the moving scene
sits in a bordered box on `rgba(5, 8, 12, 0.78)` with a 1px `--stamp-soft`
edge. Never set text straight onto the scene, and never make a panel interior
translucent.

## Shapes

Square, guillotined, ruled. `border-radius: 0` is declared explicitly on the
sheet and on both slider thumbs and on the control button, and no element in the
system carries a corner radius. The single curve in the build is the punched
binding hole at `50%`, which is a hole rather than a corner.

Form language is drawn from printed and engraved matter:

- **Double rules** close a head. 3px double under the cast head in ink, 3px
  double under an active rack row in process blue, 3px double on the frame
  readout when the render is at target.
- **Frames** are single or doubled hairlines. The overprint takes a 1px border
  plus a 1px outline at `2px` offset, which is how a rubber stamp's double
  frame prints. The cartouche does the same in `--stamp-soft` at `3px` offset,
  which is the double rule of an engraved chart cartouche.
- **Bars, not pills.** Every mark that indicates a position is a hard rectangle:
  the slider thumb is a `6px` by `18px` ink bar, the rack's value bar is a
  `0.5rem` band outlined at `rgba(227, 235, 240, 0.35)`, the time rule's active
  tick is a `3px` by `11px` ink bar.
- **Drawn glyphs, never an icon font.** The station mark on the globe is a
  44px canvas drawing: a light square (`#E3EBF0`) with a 2.5px abyss outline and
  a centred crosshair tick. The outline is not decoration: the mark has to stay
  legible when it lands on the brightest patch of the colorbar, and only a dark
  edge does that. Selection adds a drafting registration box (a 2px abyss square
  at 34px with a 1px light square inside it), because selection is marked by an
  added rule and not by a colour change.
- **Crisp cells.** The globe slices are painted one grid cell per pixel with
  smoothing off and `granularity` at one degree. Interpolating across a
  coastline would invent values that were never measured, and crisp cells also
  state the analysis grid's real resolution while reading as a ruled sheet.

### Named Rules

**The Guillotine Rule.** Forms are guillotined, not rounded. `border-radius: 0`
everywhere. The only exception is a punched hole.

**The State-Is-Rule-Form Rule.** State is carried by rule weight and dash, never
by hue. Single hairline is available, 3px double is active, dashed is pending,
half-strength is no data. This applies to rack rows, the time rule's ticks, the
frame readout, disabled controls and the profile chart's two curves alike.

## Components

Every stateful control on this surface carries the `.stamp` class, which is the
system's entire motion vocabulary.

**The Stamp Rule.** A form does not ease. State commits in a 90ms transition
with `steps(2)` on background, colour, border and opacity, so a change lands in
two frames and stops. No tween, no fade, no spring, and the transition is
removed entirely under `prefers-reduced-motion: reduce`. The only continuous
motion on the surface is the camera and the time scrub.

### Buttons

The control button is a ruled tick box, not a filled pill.

- **Shape:** hard rectangle, no radius, `1px` process-blue border, `2px 8px` padding.
- **Default:** transparent ground, ink letters, label typography (700,
  `0.6875rem`, `0.08em`, uppercase).
- **Pressed** (`aria-pressed="true"`): inverts to a solid ink ground with plate
  letters, stamped in 90ms. Used for the active variable and for the time rule's
  Run/Hold state.
- **Hover / Focus:** hover has no treatment; the pressed state is the only
  colour change. Focus-visible draws a `2px` ink outline at `1px` offset on the
  plate, and a `2px` process-blue outline at `2px` offset on the water.
- **Disabled:** the border switches to dashed and the letters drop to
  `--ink-faint`. The dash carries the state, so nothing needs greying out.

### Cards / Containers

- **Corner Style:** square, `0px`.
- **Background:** the stock raster painted directly over `--plate`
  (`background-image: url(/textures/plate.png)` on `background-color:
  var(--plate)`, repeating). The tile is 160px, seamless by construction, and
  its mean RGB equals the plate token exactly, which is why it is painted rather
  than washed under a colour that would bury the grain. THE TILE IS OPAQUE, so
  it silently overrides the token: the generator therefore reads `--plate` out
  of `globals.css` and refuses to run if the two disagree. That is not caution
  for its own sake. The retired `manila.png` carried the old plate's mean, and
  it was the one thing that would have let the whole palette change render as a
  no-op.
- **Shadow Strategy:** the single sheet-on-water shadow. See Elevation & Depth.
- **Border:** a `1px #5A6874` hairline on the outer edge, 3.5:1 against the
  water. The manila sheet had none, because it out-lumed the water by 10:1 and
  the shadow was enough. Internal separation is the binding margin's
  `1px rgba(227, 235, 240, 0.16)` right border, the head's 3px double ink rule,
  and half-strength rules between blocks.
- **Internal Padding:** `12px 13px 11px 12px` on the body, and the binding
  margin is a fixed `20px` column outside it.

### Inputs / Fields

A slider on a form is a value written along a scale, so it is drawn as one.

- **Style:** a `1px` process-blue track with no groove, no fill and no radius,
  inside a `1.25rem` hit area, cursor `ew-resize`.
- **Thumb:** a `6px` by `18px` solid ink bar, square, borderless. A pen mark on
  the scale, not a grip.
- **Focus:** the thumb switches from ink to process blue on `:focus-visible`.
- **Value display:** every field states its value numerically in the typewriter
  face on the same line as its label, right-aligned (`200x`, `65%`). The slider
  is never the only readout.

### Signature Component: the bottle rack

The 24 depth levels of the model column, drawn as a physical Niskin rack. Four
ruled columns: a two-digit serial number (`01` to `24`, zero-padded, because a
rack is serialised and a forecaster calls out a bottle by number), the depth in
metres right-aligned, a horizontal bar, and the level's mean value.

The bar is the only place on the plate where saturation appears: it is filled
with the field's own colorbar colour at that value and scaled to the value's
normalised position, with a minimum 6% width so a low value is still a mark. The
row's rule carries all of the state.

- **Available:** `1px` half-strength process blue.
- **Hover:** an ink wash at `rgba(227, 235, 240, 0.07)` and letters up to full ink. It was 7% of the OLD near-black ink, which darkened light stock; on slate the wash lifts instead.
- **Active** (`aria-selected="true"`): `3px` double process blue, letters at
  full ink, a `rgba(74, 148, 182, 0.1)` ground.
- **No data** (`data-empty="true"`): the rule drops to
  `rgba(74, 148, 182, 0.14)`, the value prints `n/a`, the bar becomes a `1px`
  dashed `--ink-faint` outline at reduced height, and the row is disabled.
- **Pending** (`data-state="pending"`): the rule goes `1px` dashed process
  blue, the value prints a dot leader, cursor `progress`.

The rack is a `listbox` with roving keyboard control (arrows, page, home, end)
and it scrolls the active row into view, because the depth cursor is the primary
instrument on the surface and must be operable without a mouse. One gesture
drives three synchronised readouts: the rack row, the globe's slice stack and
the profile chart's mark line.

### Signature Component: the overprint

A rubber stamp, not a badge. `0.625rem` at `0.14em` in caution ink, uppercase,
inside a `1px` caution border with a `1px` caution outline at `2px` offset, and
rotated `-3deg` so it prints slightly off square. It states what kind of product
a sheet holds (`Analysis` on the model sheet, `Argo QC 1-2` on the observation
panel). It is never a status pill and never takes a filled ground.

### Signature Component: the provenance cartouche

An engraved chart's title device, boxed so the citation stays legible over the
moving scene. A ruled head carries the product name, the region and an `offline`
flag set in the typewriter face inside its own hairline box; below the head, the
dataset citation prints as prose in the form's face, and the timestamp, level
count, depth range and retrieval date print in the typewriter. The box exists
because the product commits that every displayed number carries its dataset and
timestamp, and this is where that commitment becomes visible.

### Signature Component: the vertical scale bar

The device that makes a claim checkable. Five alternating `--stamp` segments
inside a `1px` `--stamp` frame, labelled `0` to the column's real depth, with
the current exaggeration and the resulting drawn distance in kilometres printed
beneath it. The frame-rate readout lives inside this box rather than floating
over the scene, so it reads as part of the instrument, and it prints both the
median and the 99th percentile because the median is throughput and the p1 is
the stutter a person notices. Its state is rule form: `3px` double `--stamp`
above target, a `1px` `--stamp-soft` hairline when healthy, and `1px` dashed
`--caution-stamp` with matching text when either figure falls below the floor.

### Signature Component: the profile chart

An ECharts depth profile themed entirely to the plate. `backgroundColor` is
transparent, `animation` is off because the surface's motion grammar is a stamp,
axis lines and ticks are ink, split lines are the half-strength rule, axis names
are set in the sans face at 700 and axis values in the typewriter, and the
tooltip is a plate-coloured card with a 1px ink border. Depth runs downward on an
inverted y-axis, which is the only correct orientation for this audience.

The two curves state their own difference in the system's grammar rather than in
a legend nobody reads: the observed profile is drawn solid at `2.4px` and
coloured along its own length by the same colorbar the globe slices use, because
it is a measurement; the model column is drawn as a `1.4px` dashed ink line,
because it is a computation. The legend swatch for the observed curve is the real
ramp, not an approximation of it. The depth cursor prints as a dashed ink mark
line labelled in metres, and clicking anywhere in the plot drives the same cursor
the rack does.

## Do's and Don'ts

### Do:

- **Do** reserve saturation for the measurement. Chrome is achromatic-cool plus
  the reserved caution ink; the field's colorbar is the only saturated thing on
  screen.
- **Do** carry every state in rule form: `1px` available, `3px` double active,
  dashed pending, half-strength absent.
- **Do** set every measured value, identifier and timestamp in Courier Prime via
  `.num`, and keep prose in Archivo Narrow.
- **Do** print a number beside every colour-mapped mark. Colour is never the sole
  carrier of meaning, because the colorbar is being read as an instrument.
- **Do** box anything that must be read over the moving scene:
  `rgba(5, 8, 12, 0.78)` on a `1px` `--stamp-soft` border.
- **Do** distinguish pending from missing. A dot leader on a dashed rule is "not
  read yet"; `n/a` on a half-strength rule is "no data here".
- **Do** paint the stock raster directly on `--plate`. Its mean RGB is that
  token, so it needs no colour wash, and `tools/make_plate_tile.py` with seed
  `20260907` regenerates it byte for byte. Change the token and re-run the
  script in the same commit; it refuses to run otherwise.
- **Do** self-host both faces with `font-display: block`. The demo runs
  air-gapped and the form must not reflow mid-read.
- **Do** keep the frame budget part of the design: MSAA at 1 sample, FXAA off, a
  screen-space error of 4, globe translucency confined to the data rectangle,
  and at most 10 of the 24 depth slices blended at once (log-spaced in depth,
  not index, so the thermocline is actually drawn). Measured at 44 FPS median
  at 1080p on the Intel UHD target.
- **Do** verify a new state grammar against a real render before writing its
  selector. A dead selector describing a state the render never produces reads
  as a promise the build cannot keep.

### Don't:

- **Don't** use glow, gradient fills, glass panels or cyan accents on chrome.
  That is the category default this surface exists to refuse.
- **Don't** set text in `--caution` (`#D4553C`) on the plate. At 3.5:1 it is a
  rule colour. Use `--caution-ink` on the plate and `--caution-stamp` on the
  water.
- **Don't** set type in `--rule` process blue, at any size.
- **Don't** ease, tween, fade or spring a state change. 90ms, `steps(2)`, done.
- **Don't** colour missing data. Land and fill values are fully transparent and
  black; nothing bleeds under them.
- **Don't** round a corner. The only radius in the system is a punched hole.
- **Don't** apply `.num` to a sentence. The typewriter is what was entered, not
  what was printed.
- **Don't** add a second shadow, and don't make a panel interior translucent.
- **Don't** substitute a glyph from an icon font for a drawn mark, and don't
  signal selection with a colour change; add a registration rule instead.
- **Don't** let the bottle rack scroll internally, and don't cover the Cesium
  attribution.
- **Don't** interpolate the analysis grid for smoothness. Crisp cells state the
  real resolution; smoothing invents values across coastlines.
