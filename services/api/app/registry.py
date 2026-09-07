"""Dataset registry (TRD M1).

`data/sources.yaml` is the extensibility surface the PS grades F3 and F6 on:
adding a variable or a whole source must be a config edit, never a code change.
This module is the validator for that file -- if a registry entry is malformed
we want a startup error naming the field, not a mysterious KeyError halfway
through a demo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from .config import get_settings

#: The kinds data/sources.yaml may name. The last three are served by a
#: plugin-registered reader (PS F6 names moorings, HF-radar and ADCP
#: explicitly); app/plugins.py refuses a kind with no reader by name, so
#: listing one here is a promise the loader can actually check.
SourceKind = Literal[
    "erddap_griddap",
    "gdac_geo",
    # Argo BGC synthetic profiles (<wmo>_Sprof.nc). A separate kind from
    # gdac_geo because the path is per-float rather than per-day, and because
    # the parameters it carries (CHLA, DOXY, NITRATE, pH) are the PS's "BGC"
    # instrument class, which a reader has to be able to tell apart from a
    # core temperature-and-salinity float.
    "gdac_bgc",
    "copernicus",
    "zarr",
    "mqtt",
    "file",
    "mooring",
    "hf_radar",
    "adcp",
]


class VariableSpec(BaseModel):
    name: str
    canonical: str | None = None
    label: str | None = None
    #: The unit string the SOURCE FILE is expected to declare for this
    #: variable. Not a conversion and not a relabel: a stated expectation.
    #: app/argo.py compares it against the file's own `units` attribute and
    #: refuses a mismatch, so this cannot quietly disagree with the data.
    #: Declaring it here is what lets the API label a chart axis without the
    #: client hardcoding a units table that would drift from the files.
    units: str | None = None
    #: Genuine unit CONVERSION (arithmetic), as distinct from a cf_overrides
    #: `units` relabel (a typo fix). Keeping these separate is deliberate.
    convert_to: str | None = None


class DimSpec(BaseModel):
    time: str | None = None
    depth: str | None = None
    lat: str | None = None
    lon: str | None = None
    profile: str | None = None
    level: str | None = None


class QCSpec(BaseModel):
    #: Argo QC flags to accept. 1 = good, 2 = probably good (Wong et al. 2020).
    accept_flags: list[int] = Field(default_factory=lambda: [1, 2])
    prefer_adjusted: bool = True


class MemberSpec(BaseModel):
    store: str
    from_source: str | None = None
    format: str | None = None


class SourceSpec(BaseModel):
    id: str
    title: str
    kind: SourceKind
    enabled: bool = True
    disabled_reason: str | None = None
    url: str
    dataset_id: str | None = None
    path_template: str | None = None
    citation: str = ""
    variables: list[VariableSpec] = Field(default_factory=list)
    dims: DimSpec = Field(default_factory=DimSpec)
    qc: QCSpec = Field(default_factory=QCSpec)
    members: list[MemberSpec] = Field(default_factory=list)
    #: Per-variable / per-coordinate CF attribute corrections. Each entry
    #: documents a defect observed in the live source (see ADR-0003).
    cf_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    #: Delimited-text layout for `kind: file` sources (glider, CTD and BGC
    #: ASCII). Held as a raw mapping and validated by the validator below
    #: against app/text_profiles.py:TextFormatSpec, which is where the schema
    #: is documented. Without this field pydantic's extra="ignore" would
    #: silently DISCARD a `text:` block, so the config would look correct and
    #: do nothing at all.
    text: dict[str, Any] | None = None

    #: For `kind: gdac_bgc`, how to find the floats. Left empty on purpose:
    #: a hardcoded WMO list goes stale the moment a float stops reporting, so
    #: tools/fetch_sample.py DISCOVERS the BGC floats by reading PLATFORM_TYPE
    #: out of the core daily files already on disk. This field exists so a
    #: specific float can be pinned when a demo needs a known-good one.
    platforms: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_block_is_a_valid_layout(cls, v):
        # Validated at registry-load time so a mistyped key is a startup error
        # that names it, rather than a setting quietly ignored until a parse
        # fails on stage.
        #
        # The import is deferred deliberately: at module scope it would close
        # the cycle registry -> text_profiles -> argo -> registry and every
        # import of this module would fail.
        if v is None:
            return v
        from .text_profiles import TextFormatSpec

        TextFormatSpec.model_validate(v)
        return v

    @field_validator("disabled_reason")
    @classmethod
    def _reason_required_when_disabled(cls, v, info):
        # A source that is off without a stated reason is a source nobody dares
        # turn back on.
        if info.data.get("enabled") is False and not v:
            raise ValueError("a disabled source must carry a disabled_reason")
        return v

    def variable(self, name: str) -> VariableSpec | None:
        return next((v for v in self.variables if v.name == name), None)

    @property
    def variable_names(self) -> list[str]:
        return [v.name for v in self.variables]


class Registry(BaseModel):
    version: int
    defaults: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceSpec]

    def get(self, source_id: str) -> SourceSpec:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)

    def has(self, source_id: str) -> bool:
        return any(s.id == source_id for s in self.sources)

    def enabled(self) -> list[SourceSpec]:
        """Only enabled sources are ever offered to a client. A source with no
        credentials must not appear in a variable selector that then fails."""
        return [s for s in self.sources if s.enabled]


def load_registry_from(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    reg = Registry.model_validate(raw)

    ids = [s.id for s in reg.sources]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate source ids in {path.name}: {sorted(dupes)}")
    return reg


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    return load_registry_from(get_settings().sources_file)
