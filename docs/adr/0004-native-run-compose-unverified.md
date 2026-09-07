# ADR-0004 - Compose files authored but unexecuted; Phase 1 runs natively

**Date:** 2026-09-07 · **Status:** accepted (Phase 1) · **Owner:** lead, approved by team lead

## Context

PS requirement F5 ("Web-based, Scalable Architecture … deployable on INCOIS
infrastructure") and TRD §8 both call for Docker Compose. Docker is not
installed on the build machine, and installing Docker Desktop on Windows means a
large download, WSL2 setup and a restart - hours we do not have before the
internal round.

## Decision

- `docker-compose.yml` and `docker-compose.offline.yml` are written per TRD §8
  and kept in the tree, each with a header stating **"AUTHORED, NOT YET
  EXECUTED."** Screening reviewers read compose files; having them is worth more
  than not having them, provided we never claim they are verified.
- Phase 1 spikes run natively: `uvicorn app.main:app --reload` for the API and
  `pnpm web:dev` for the client.
- **SQLite and parquet stand in for PostGIS.** This is not a shortcut: TRD M6
  already names SQLite as the offline substitute for PostGIS, so the offline
  demo path is the one we develop against every day.

## Consequences

- `docker compose up` must be verified before F5 is claimed to a judge, and
  before Phase 4 exit. Tracked as a Phase 4 checklist item.
- No Dockerfiles exist yet - the compose `build:` stanzas point at directories
  that still need them. Also Phase 4.
- The `network_mode: none` line in the offline overlay is the cheapest possible
  proof that the API needs no network, the moment Docker exists to run it.
