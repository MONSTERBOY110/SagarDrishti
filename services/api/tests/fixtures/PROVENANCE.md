# Golden fixtures

Real files, committed on purpose. Everything else in this suite is built in
code so it stays hermetic, but a parser for a government interchange format has
to be proven against a government file rather than against my idea of one.

## sachet_ap_sdma_thunderstorm.cap.xml

- **Retrieved** 2026-09-09 from India's national CAP backbone, NDMA SACHET.
- **URL** `https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1788952195339008`
- **Discovered via** `https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml`
- **Identifier** `IN-1788952195339008_8`, sender `Andhra-Pradesh-SDMA`,
  referencing an IMD Visakhapatnam bulletin.
- **What makes it worth committing:** it is genuine CAP v1.2 in the
  `urn:oasis:names:tc:emergency:cap:1.2` namespace, `msgType: Update` with a
  populated `references` triple, and it carries **two `info` blocks in two
  languages** (en-IN and Telugu). The multilingual structure is not a
  hypothetical we designed for; it is how Indian CAP actually arrives.
- It also shows the SACHET extension this parser has to cope with: the alert
  carries no inline geometry at all, only a `Polygon URL` parameter.

## sachet_ap_sdma_thunderstorm.polygon.xml

- The geometry sidecar for the alert above, from the URL that alert names.
- **Two quirks a parser meets in the wild, both real, both pinned by tests:**
  the file is NOT in the CAP namespace (bare `<alert>`, `<polygon>`), and it
  repeats the identical ring twice.

## Licence and use

Public alert content issued in the public interest by Indian government
agencies through NDMA SACHET, held here as a parser regression fixture. It is a
test input, never a warning: nothing in the demo path renders it, and it has
long since expired (`expires 2026-09-09T19:37:00+05:30`).
