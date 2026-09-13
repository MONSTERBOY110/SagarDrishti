# The SIH 2026 idea submission deck

**Upload `SagarDrishti_SIH2026_Idea.pdf` to the SIH portal.** The template's own
instruction slide is explicit: *"You need to save the file in PDF and upload the
same on portal. No PPT, Word Doc or any other format will be supported."*

`SagarDrishti_SIH2026_Idea.pptx` is the editable source. Edit that, re-export to
PDF, and upload the PDF.

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
| 2 | Idea title | The problem in INCOIS's own quoted words, the solution against it, innovation, and a screenshot of the running system with the verification card enlarged |
| 3 | Technical approach | A four-stage architecture diagram (sources → ingest → data plane → browser) with labelled arrows, plus verification, the agent plane, OGC clients, and the stack |
| 4 | Feasibility and viability | A measured-evidence strip, then feasibility / risks / mitigations, then why it survives after the hackathon |
| 5 | Impact and benefits | Five stakeholder groups, benefits, national alignment, and a four-step scenario of what changes on the day a depression forms in the Bay |
| 6 | Research and references | 20 hyperlinked references in four groups, how the literature changed the build, and a gap-analysis matrix against desktop tools, web viewers and INCOIS's own portal |

---

## Every figure in the deck is measured, and re-derivable

Read off the running system on 11 to 13 September 2026. If you change anything,
re-check these against `docs/P0-STATUS.md` before exporting.

| Figure | Where it comes from |
|---|---|
| Bias +0.026 degC, RMSE 0.602 degC, 11,718 pairs, 23 casts | `GET /scorecard/incois_vam_argo/TEMP?observed=temp` |
| 2.07 degC worst band at 50 to 100 m | the same response, `by_depth` |
| 543 tests (462 data plane + 71 agent + 10 browser) | `./tasks.ps1 test` and `./tasks.ps1 e2e` |
| 51 fps at 1080p, integrated GPU | `docs/P0-STATUS.md` under F1 |
| 10.5 M gridded values | the two Zarr stores in `data/cube/` |
| 16,390 QC-passed levels, 25 casts, 17 instruments | `data/cube/profiles.parquet` |
| 13 ocean parameters | `GET /catalog` plus the profile parameters |
| 337 current arrows, 26 degC isosurface | the screenshots themselves, taken live |

---

## Rebuilding the deck

```bash
cd .ppt-build
../.venv/Scripts/python.exe compose2.py       # writes exports/…pptx
```

Then export the PDF from PowerPoint (File → Export → PDF), or re-run the
PowerShell COM snippet used during the build.

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
