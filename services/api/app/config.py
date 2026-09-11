"""Runtime configuration (TRD M6).

OFFLINE=1 is the DEFAULT posture, not a special mode: the API reads only from
the local zarr/parquet cube, so the air-gapped demo path (PRD F11) is the same
code path we develop against every day. Network access lives exclusively in
tools/fetch_sample.py.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def _repo_root() -> Path:
    # services/api/app/config.py -> repo root
    return Path(__file__).resolve().parents[3]


class Settings(BaseModel):
    offline: bool = True
    repo_root: Path
    sources_file: Path
    cube_dir: Path
    raw_dir: Path

    @property
    def profiles_parquet(self) -> Path:
        return self.cube_dir / "profiles.parquet"

    @property
    def warnings_json(self) -> Path:
        return self.cube_dir / "warnings.json"

    @property
    def sagarnode_log(self) -> Path:
        """Where the sensor station's readings land.

        In the cube directory because it is runtime state written by a device,
        not source: gitignored, rebuilt by whatever is plugged in, and safe to
        delete between demos.
        """
        return self.cube_dir / "sagarnode.jsonl"

    @property
    def storyboards_dir(self) -> Path:
        """Guided tours (PRD F12). Source files in the repository, NOT derived
        into data/cube: a tour is authored content like a CAP bulletin, not an
        artifact of the ingest, so it lives in version control and needs no
        preprocess step to exist."""
        import os as _os

        return Path(_os.environ.get("SAGAR_STORYBOARDS", self.repo_root / "storyboards"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(os.environ.get("SAGAR_ROOT", _repo_root()))
    # OFFLINE defaults to "1": you must opt IN to touching the network.
    offline = os.environ.get("OFFLINE", "1") not in ("0", "false", "False", "")
    return Settings(
        offline=offline,
        repo_root=root,
        sources_file=Path(os.environ.get("SAGAR_SOURCES", root / "data" / "sources.yaml")),
        cube_dir=Path(os.environ.get("SAGAR_CUBE", root / "data" / "cube")),
        raw_dir=Path(os.environ.get("SAGAR_RAW", root / "data" / "raw")),
    )
