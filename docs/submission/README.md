# The SIH 2026 idea submission deck

**Upload `PixelPaws_SIH2026.pdf` to the SIH portal.** The template's own
instruction slide is explicit: *"You need to save the file in PDF and upload the
same on portal. No PPT, Word Doc or any other format will be supported."*

`PixelPaws_SIH2026.pptx` is the editable source. Edit that, re-export the PDF
with `.ppt-build/export_pixelpaws_pdf.py`, and upload the PDF.

> **THE FILENAME CHANGED AND THIS FILE DID NOT, UNTIL 23 SEPTEMBER.** These
> instructions said to upload `SagarDrishti_SIH2026_Idea.pdf`, which is a
> 15 September export of a deck that has since been renamed, restructured and
> re-measured. Anyone following the old line would have submitted a five-day-old
> PDF with the wrong screenshots and a wrong test count. That file is still in
> this folder because deleting one is the lead's call, not mine; it should go.
>
> Superseded, in this folder, none of them for the portal:
> `SagarDrishti_SIH2026_Idea.pdf` (15 September, wrong deck),
> `PixelPaws_SIH2026.BACKUP-20260920-1655.pptx`,
> `PixelPaws_SIH2026.BACKUP-20260923-0135.pptx` and
> `PixelPaws_SIH2026.BEFORE-REFRESH.pptx` (the last is what
> `.ppt-build/refresh_23sep.py` re-applies itself from, so keep that one until
> the refresh is settled).

---

## THREE THINGS YOU MUST FILL IN BEFORE SUBMITTING

These are deliberately left as visible placeholders rather than guessed, because
a wrong team ID on a submitted PDF cannot be withdrawn.

| Slide | Placeholder | What to do |
|---|---|---|
| 1 | `[TEAM ID]` | Your registered SIH team ID |
| 1 and 2 to 6 | `[TEAM NAME]` | Your registered team name. It appears on slide 1 and in the oval at the top-left of slides 2 to 6 |
| 1 | Problem Statement Title | **Paste the exact title from sih.gov.in/sih2026PS, character for character.** The current text is our working title and has NOT been checked against the portal |

To change them once for the whole deck, edit the constants at the top of
`../../.ppt-build/build_deck.py` (`TEAM_ID`, `TEAM_NAME`, `PS_TITLE`) and re-run
the build (see below). That is safer than hand-editing six slides.

---

## Rules this deck already satisfies

From the template's own instruction slide, which has been deleted as it tells
you to:

- [x] **Six slides maximum, including the title slide.** Exactly six.
- [x] **Points, diagrams and infographics rather than paragraphs.**
- [x] **The provided template is used**, unchanged in its chrome: the slide
      masters, the SIH logo, the header band, the footer bar and the team oval
      are all the template's own, not recreated.
- [x] **The idea-detail pointers are all answered**, label for label. Each
      guidance textbox was replaced by blocks that address the same points:
      Proposed Solution / How it addresses the problem / Innovation and
      uniqueness on slide 2; Technologies used and Methodology on slide 3;
      Feasibility / Challenges and risks / Strategies on slide 4; Potential
      impact and Benefits on slide 5; references and links on slide 6.
- [x] **PDF export produced**, 6 pages, 16:9.

---

## What is on each slide

| # | Section | The argument |
|---|---|---|
| 1 | Title page | PS identity, the product, and one line of proof that this already runs |
| 2 | Idea title | The problem in INCOIS's own quoted words, the solution against it, a branching flowchart of how one answer is made, and two photographs of the running system |
| 3 | Technical approach | A four-stage architecture diagram (sources, ingest, data plane, browser) with labelled arrows, plus verification, the agent plane, OGC clients, and the stack |
| 4 | Feasibility and viability | A measured-evidence strip, then feasibility / risks / mitigations, then why it survives after the hackathon |
| 5 | Impact and benefits | Five stakeholder groups, benefits, national alignment, and a four-step scenario of what changes on the day a depression forms in the Bay |
| 6 | Research and references | 20 hyperlinked references in four groups, how the literature changed the build, and a gap-analysis matrix against desktop tools, web viewers and INCOIS's own portal |

---

## Every figure in the deck is measured, and re-derivable

Read off the running system on 11 to 13 September 2026, and re-read on
23 September for the rows marked below. If you change anything, re-check these
against `docs/P0-STATUS.md` before exporting.

| Figure | Where it comes from |
|---|---|
| Bias +0.026 degC, RMSE 0.602 degC, 11,718 pairs, 23 casts | `GET /scorecard/incois_vam_argo/TEMP?observed=temp` |
| 2.07 degC worst band at 50 to 100 m | the same response, `by_depth` |
| **595** tests (512 data plane + 71 agent + 12 browser) | Counted by `refresh_23sep.py` itself now, not typed. It was 567, then 594 for about an hour on the 23rd until the browser suite gained a twelfth test |
| 51 fps at 1080p, integrated GPU | `docs/P0-STATUS.md` under F1 |
| 10.5 M gridded values | the two Zarr stores in `data/cube/` |
| 30,012 QC-passed levels, 149 casts, 19 instruments | `data/cube/profiles.parquet` |
| **12** ocean parameters, 3 of them plugin-derived | `GET /catalog` gives 7 gridded (TEMP, SAL, D26, SIG0, SVEL, uo, vo) and `profiles.parquet` gives 7 in-situ (temperature, salinity, oxygen, chlorophyll-a, nitrate, pH, backscattering). Temperature and salinity are on both sides and are one parameter each, so the distinct total is 12. The deck said 13 with no recorded derivation; this one is counted in the script and printed when it runs |
| **13 sources, 10 kinds, 5 plugins** | `data/sources.yaml` and `services/api/plugins/`; re-read 23 September. The deck said 9 kinds and 4 plugins |
| 337 current arrows, 26 degC isosurface | the screenshots themselves, taken live |

---

## Rebuilding the deck

**The deck has been hand-edited in PowerPoint since the composer last ran, so
the composer is no longer the authority.** `docs/submission/PixelPaws_SIH2026.pptx`
is. Two scripts act on it directly:

```bash
node tools/capture_deck_assets.mjs                              # re-take the four screenshots
../.venv/Scripts/python.exe .ppt-build/refresh_23sep.py         # re-apply the 23 Sep edits
../.venv/Scripts/python.exe .ppt-build/export_pixelpaws_pdf.py  # PDF, with the link check
```

The first needs the three services running (`api`, `agent`, `demo`). Skip it
and the refresh reuses whatever is in `.ppt-build/assets/`, which is right when
only text changed and wrong the moment the interface moves.

`refresh_23sep.py` is re-runnable: the first run keeps the deck as it was in
`PixelPaws_SIH2026.BEFORE-REFRESH.pptx`, and every run after that restores that
copy before re-applying, so editing the script and running it twice cannot apply
the same change twice. It is also where the screenshots and the counted figures
come from, so read its docstring before changing a number by hand.

The original composer (`compose.py`, `slide3.py`, `compose2.py`) still builds a
deck from the untouched template into `exports/`, and is kept for reference and
for the shape primitives `refresh_23sep.py` borrows its palette from.

Source layout:

| File | Holds |
|---|---|
| `build_deck.py` | Identity constants, palette, 12-column grid, shape and diagram primitives, template surgery |
| `compose.py` | Slides 1 and 2 |
| `slide3.py` | Slide 3, the architecture diagram |
| `compose2.py` | Slides 4, 5, 6 and the runner |
| `assets/` | Screenshots captured from the running system |
| `sources/` | The untouched official SIH template |

**One trap worth knowing about.** `build_deck.py` raises `LayoutError` if any
shape is asked for with a non-positive width or height. That check exists
because python-pptx will happily write a negative size into the XML, the file
saves without complaint, and PowerPoint then refuses to open the entire deck
with only "PowerPoint could not open the file" to go on. Do not remove it.

---

## Two export traps that are already fixed, and must stay fixed

**A hyperlink that is the LAST run of its paragraph is dropped by PowerPoint's
PDF export.** Not warned about, not logged: the PPTX carried 20 links and the
PDF carried 17. Every reference with a trailing note survived; every one
without a note did not. `compose2.py` therefore always writes a plain run after
a link, even if it is only a space. If you add a reference, keep that pattern
and re-run the link check below.

**A shape with a non-positive width or height corrupts the whole file.**
python-pptx writes the negative value happily, the save succeeds, and then
PowerPoint refuses to open the deck at all with only "PowerPoint could not open
the file" to go on. `build_deck.py` raises `LayoutError` at shape creation to
catch this at the source. Do not remove that check.

Verify both after any edit:

```bash
cd .ppt-build
../.venv/Scripts/python.exe - <<'EOF'
import pymupdf
from pptx import Presentation
d = pymupdf.open("exports/SagarDrishti_SIH2026_Idea.pdf")
pdf = {l["uri"] for p in d for l in p.get_links() if l.get("uri")}
prs = Presentation("exports/SagarDrishti_SIH2026_Idea.pptx")
ppt = {r.hyperlink.address for s in prs.slides for sh in s.shapes
       if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs
       if r.hyperlink and r.hyperlink.address}
print("pages", d.page_count, "| pptx", len(ppt), "| pdf", len(pdf),
      "| missing", sorted(ppt - pdf))
EOF
```

Expected: `pages 6 | pptx 20 | pdf 20 | missing []`.

## References: what was checked

All 20 links were fetched. Fourteen return HTTP 200 directly. Six return 403 to
a command-line fetch because the publisher blocks non-browser requests
(Taylor & Francis, ScienceDirect x2, MDPI x2, American Meteorological Society);
those open normally in a browser and four of them are canonical DOI links.

No link points at Google, Wikipedia or a chatbot. Two were verified against the
source document rather than trusted: the Argovis DOI (Tucker et al. 2020, JTECH
37(3):401-416) and the INCOIS Ocean State Forecast paper (Balakrishnan Nair et
al., Current Science 105(2), 25 July 2013, p.175), whose PDF was downloaded and
the author affiliation confirmed as INCOIS.
