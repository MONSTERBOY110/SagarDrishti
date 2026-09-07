# ADR-0003 - INCOIS VAM gridded analysis is the Phase 1 primary field source

**Date:** 2026-09-07 · **Status:** accepted (Phase 1) · **Owner:** lead, approved by team lead

## Context

The PS lists both INCOIS LAS and Copernicus GLORYS12 as official (★) sources
(TRD §3). GLORYS12 is the richer product - 1/12°, 50 depth levels, and it
carries **U/V currents** - but it requires a Copernicus Marine account and its
CLI client.

Probing the live sources on 2026-09-07 turned up something better for a spike:
**`erddap.incois.gov.in/griddap/incois_argo_10d_VAM`** is open, needs no login,
and is genuinely 4D - `TEMP`, `SAL`, `TERR`, `SERR` on time=813 steps (latest
2026-07-30) × `ZAX`=24 levels (5-2000 m) × 60 lat × 90 lon across the Indian
Ocean. A tiny griddap subset returned real values (29.15 °C at 5 m, 10.5 °N /
85.5 °E).

It is also usefully *dirty*: `TEMP.units = "degs"` (not a CF/UDUNITS unit),
`_FillValue = -9999.0`, and `ZAX` carries **no `positive` attribute** and a
non-standard name, so cf-xarray cannot infer the vertical axis. The sibling
dataset `incois_valueadded_products_datasets` uses a different fill (`-1.0E34`)
and `cm/sec` currents.

## Decision

Phase 1 builds the primary path on `incois_vam_argo` plus `argo_gdac_indian`.
GLORYS12 ships in `data/sources.yaml` as a complete entry with
`enabled: false` and a `disabled_reason`; enabling it is a config edit plus
credentials in `.env`.

## Consequences

- **Zero credential risk in Phase 1.** The spike cannot be blocked by a signup
  flow, and the data is INCOIS's own product - a judging asset, since we
  visualize the sponsoring organization's analysis rather than a European
  reanalysis.
- **The CF edge cases in our test suite are real, not invented.** Every
  `cf_overrides` entry in `sources.yaml` documents an observed defect with the
  date it was observed. That is a far stronger answer to "why do you need a
  source registry?" than a hypothetical would be.
- **Known limitation, stated plainly:** INCOIS ERDDAP carries no *subsurface*
  currents - only surface geostrophic `GEO_U`/`GEO_V` in the value-added set.
  PRD F1's depth-resolved current-vector layer therefore **requires GLORYS12**
  and is blocked until credentials exist. Flagged to the team lead 2026-09-07.
- 1° / 10-day resolution is coarse for a hero shot. Honest framing on stage (it
  is INCOIS's own operational analysis grid); GLORYS12 at 1/12° is the Phase 2
  visual upgrade.
