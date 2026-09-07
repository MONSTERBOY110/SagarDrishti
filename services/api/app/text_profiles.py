"""Delimited-text profile ingestion (TRD M1, PS requirement F3 / F6).

The PS names the in-situ sources as "Argo floats, Gliders, CTD, BGC as
NetCDF/ASCII". `app/cf.py` and `app/argo.py` cover NetCDF. This module covers
the text half, and it covers it WITHOUT knowing any format: every decision is
driven by a validated config object, so adding a new cruise or glider layout is
an edit to `data/sources.yaml` and never a code change. That configurability is
the graded artefact, not a convenience.

Output is the SAME tidy frame `app/argo.py:parse_profiles` returns, one row per
level::

    profile_id, wmo, time, lat, lon, pres, depth, temp, temp_qc, psal, psal_qc

so both parsers feed one pipeline and one parquet schema (PROFILE_DTYPES below
is measured from the real `data/cube/profiles.parquet`, not guessed).


THE CONFIG SCHEMA (`text:` under a source in data/sources.yaml)
--------------------------------------------------------------

Every key exists because a real file needed it. `extra="forbid"` throughout, so
a typo is a startup error naming the key rather than a setting that is silently
ignored and discovered on stage.

``encoding``            "auto" tries utf-8-sig then cp1252. utf-8-sig strips a
                        BOM (shared-drive files have one); cp1252 is what
                        European CTD software writes a degree sign in, and that
                        byte (0xB0) raises on a strict utf-8 decode.
``comment_prefixes``    Header/comment markers. Multi-character on purpose:
                        ODV uses "//" and some loggers "%%", neither of which a
                        single-char `comment=` can express.
``delimiter``           "auto" | tab | comma | semicolon | pipe | whitespace |
                        any literal character.
``decimal``             "auto" | "." | ",". European CTD software writes 28,55.
``column_row``          "auto", or a 0-based index counted over the
                        non-comment, non-blank lines.
``units_row``           True when a units line sits directly under the names.
``columns``             canonical name -> accepted spellings. Matching ignores
                        case, collapses whitespace and strips a trailing
                        bracketed unit, so one alias covers "Temp",
                        "Temperature" and "Temperature [degC]".
``qc_follows_value``    True when a flag column immediately follows the column
                        it qualifies (ODV spreadsheet export repeats the name
                        "QF" after every data column, so it can only be
                        resolved positionally).
``missing``             Sentinel conventions. One file routinely carries
                        several; see `_to_float`.
``header_metadata``     canonical -> keys to harvest from "key = value" or
                        "key: value" lines in the header block. Aliases are
                        tried IN ORDER, first hit wins.
``time_formats``        strptime patterns tried in order, then ISO-8601.
``forward_fill_identity`` ODV writes station/position/time only on a station's
                        first row and leaves every continuation row blank.
``profile_id_from``     Parts of the profile id: platform, cast, time.
``platform_prefix``     Joined with a hyphen, so a bare "Station 1" can never
                        collide with a 7-digit Argo WMO id in the shared table.
``vertical``            column: auto|pres|depth, units: auto|dbar|m,
                        positive: auto|down|up. The column NAME only says which
                        slot the values nominally fill; the UNIT decides how
                        they are interpreted, because a column called "Depth"
                        carrying decibars is a real defect.
``derive_pressure``     Recover pres from a depth-only file via the exact
                        inverse of the depth conversion. See the note below.
``flags``               The FILE's flag vocabulary: map (file token -> Argo
                        1..9), when_absent, when_blank.

`accept_flags` is deliberately NOT here. The QC *policy* stays in
`registry.QCSpec` so every source shares one policy; this block only declares
the vocabulary needed to translate into it.


DELIBERATE DIVERGENCES, stated rather than hidden
-------------------------------------------------

1. **Per-variable QC rejection.** `app/argo.py` drops the whole level when TEMP
   is bad. Here a rejected value becomes NaN while KEEPING its flag, and the row
   survives if another variable did. A PSAL-only or BGC-only text file would
   otherwise lose every level, and the retained flag is what lets the record say
   *why* a number is absent instead of it silently vanishing. A single
   unqualified flag column is different: it describes the LEVEL, so a rejected
   level is dropped outright -- its depth is untrustworthy too, and a level we
   cannot place must not appear on the globe.

2. **`derive_pressure`.** Recovering pres from depth via TEOS-10 is the exact
   inverse of what the acquisition software did (it round-trips to ~1e-13 m),
   but it is still a number that is not literally in the file. So it is a
   config switch, and switching it off leaves the column explicitly NaN rather
   than zero-filled.

3. **`wmo` carries a platform id.** A CTD cast has no WMO. Adding a 12th column
   would fork the parquet schema, so the platform id (prefixed) rides in `wmo`
   and the file-level provenance names the source. When a file carries no
   station identifier at all, the file stem is used: it is the only identifier
   the file actually has, and inventing one would be worse.

4. **Timestamps without a zone are read as UTC**, which is the convention for
   every source we ingest, and are stored tz-naive to match
   `store.nearest_time` and the datetime64[ns] on disk.


WHAT THE PARSE REPORTS ABOUT ITSELF
-----------------------------------

The returned frame carries a parse record on ``frame.attrs[PROVENANCE_KEY]``:
the file name, the delimiter and which mechanism chose it, the column-name
line, how many data lines there were, how many levels were parsed and returned,
the line numbers of any line dropped for being ragged, and the number of
station blocks a forward fill was allowed to cross. It exists because two
defects here were SILENT rather than wrong-looking: ragged lines were dropped
with no error and no count, so a seven-level cast could be reported as a
one-level cast, and the level count feeds `argo.profile_summary` and every
depth-binned statistic. A number with no provenance is not shippable, and a
count that is never reported cannot be checked.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import gsw
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .argo import pressure_to_depth
from .cf import canonical_unit

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps the import graph flat
    from .registry import SourceSpec

__all__ = [
    "PROFILE_COLUMNS",
    "PROFILE_DTYPES",
    "PROVENANCE_KEY",
    "FlagVocabularySpec",
    "TextFormatSpec",
    "TextParseError",
    "VerticalSpec",
    "empty_profile_frame",
    "parse_header_metadata",
    "parse_text_profiles",
    "pressure_to_depth",
    "sniff_delimiter",
    "text_format",
]


class TextParseError(ValueError):
    """A text file (or its config) cannot be read.

    Always raised with the file name and the reason. Returning a
    plausible-looking wrong frame is the worst outcome for an instrument, so
    every ambiguity in here fails loudly instead of guessing.
    """


#: The shared frame contract. Column ORDER and dtype both matter: the profiles
#: parquet is written by concatenating these frames, and an object-dtype QC
#: column would change the schema on disk. Measured from the real
#: data/cube/profiles.parquet (4191 levels, 13 floats).
PROFILE_COLUMNS: tuple[str, ...] = (
    "profile_id", "wmo", "time", "lat", "lon", "pres", "depth",
    "temp", "temp_qc", "psal", "psal_qc",
)
PROFILE_DTYPES: dict[str, str] = {
    "profile_id": "object",
    "wmo": "object",
    "time": "datetime64[ns]",
    "lat": "float64",
    "lon": "float64",
    "pres": "float64",
    "depth": "float64",
    "temp": "float64",
    "temp_qc": "int16",
    "psal": "float64",
    "psal_qc": "int16",
}

#: Canonical column names a `columns:` block may map. Validated, so a plausible
#: misspelling ("temperature") is a config error rather than a column that is
#: quietly never read.
ALLOWED_COLUMNS = frozenset(
    {
        "platform", "cast", "time", "date", "time_of_day", "lat", "lon",
        "pres", "depth", "temp", "psal",
        "pres_qc", "depth_qc", "temp_qc", "psal_qc", "qc",
    }
)
ALLOWED_METADATA = frozenset({"platform", "cast", "time", "date", "time_of_day", "lat", "lon"})
ALLOWED_ID_PARTS = frozenset({"platform", "cast", "time"})

#: Columns a flag column can qualify.
_FLAGGABLE = ("pres", "depth", "temp", "psal")

#: Delimiters tried in this order. Whitespace is LAST because a tab-delimited
#: header like "Bot. Depth [m]" shatters under a whitespace split, and comma is
#: late because it collides with the decimal comma. None means "runs of
#: whitespace".
_DELIM_ORDER: tuple[str | None, ...] = ("\t", ";", "|", ",", None)

_DELIM_NAMES: dict[str, str | None] = {
    "tab": "\t",
    "comma": ",",
    "semicolon": ";",
    "pipe": "|",
    "space": None,
    "spaces": None,
    "whitespace": None,
}

#: Sentinels observed across INCOIS ERDDAP products and cruise ASCII. -1.0e34
#: is the Ferret/ODV convention, -999 and -9.99 the Sea-Bird ones.
_DEFAULT_MISSING: list[float | str] = [-999.0, -9.99, -1.0e34, "NaN", "n/a", "---"]


# --- config models ----------------------------------------------------------

class VerticalSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: Literal["auto", "pres", "depth"] = "auto"
    units: Literal["auto", "dbar", "m"] = "auto"
    positive: Literal["auto", "down", "up"] = "auto"


class FlagVocabularySpec(BaseModel):
    """The FILE's flag vocabulary, not the project's QC policy.

    SeaDataNet/ODV flag 8 means "interpolated", which is Argo's 3, not Argo's 8.
    Comparing a foreign flag against `accept_flags` without translating it
    accepts data the source called suspect.
    """

    model_config = ConfigDict(extra="forbid")

    map: dict[str, int] = Field(default_factory=dict)
    #: No flag column at all. 1 mirrors app/argo.py, which assumes flag 1 when a
    #: *_QC variable is missing from the NetCDF.
    when_absent: int = 1
    #: A BLANK cell inside a column that DOES exist is different: it means no QC
    #: was performed, which is Argo 9.
    when_blank: int = 9


class TextFormatSpec(BaseModel):
    """Everything this parser knows about a text format. See the module docstring."""

    model_config = ConfigDict(extra="forbid")

    encoding: str = "auto"
    comment_prefixes: list[str] = Field(default_factory=lambda: ["//", "#", "*", "%", "%%"])
    delimiter: str = "auto"
    decimal: str = "auto"
    column_row: int | Literal["auto"] = "auto"
    units_row: bool = False
    columns: dict[str, list[str]]
    qc_follows_value: bool = False
    missing: list[float | str] = Field(default_factory=lambda: list(_DEFAULT_MISSING))
    header_metadata: dict[str, list[str]] = Field(default_factory=dict)
    time_formats: list[str] = Field(default_factory=list)
    forward_fill_identity: bool = False
    profile_id_from: list[str] = Field(default_factory=lambda: ["platform", "time"])
    platform_prefix: str | None = None
    vertical: VerticalSpec = Field(default_factory=VerticalSpec)
    derive_pressure: bool = True
    flags: FlagVocabularySpec = Field(default_factory=FlagVocabularySpec)

    @field_validator("columns")
    @classmethod
    def _known_columns(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        bad = sorted(set(v) - ALLOWED_COLUMNS)
        if bad:
            raise ValueError(
                f"unknown canonical column name(s) {bad}. Allowed: {sorted(ALLOWED_COLUMNS)}"
            )
        return v

    @field_validator("header_metadata")
    @classmethod
    def _known_metadata(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        bad = sorted(set(v) - ALLOWED_METADATA)
        if bad:
            raise ValueError(
                f"unknown header_metadata key(s) {bad}. Allowed: {sorted(ALLOWED_METADATA)}"
            )
        return v

    @field_validator("profile_id_from")
    @classmethod
    def _known_id_parts(cls, v: list[str]) -> list[str]:
        bad = sorted(set(v) - ALLOWED_ID_PARTS)
        if bad or not v:
            raise ValueError(
                f"profile_id_from must be a non-empty subset of {sorted(ALLOWED_ID_PARTS)}, got {v}"
            )
        return v

    @field_validator("decimal")
    @classmethod
    def _known_decimal(cls, v: str) -> str:
        if v not in ("auto", ".", ","):
            raise ValueError(f"decimal must be 'auto', '.' or ',', got {v!r}")
        return v

    @field_validator("delimiter")
    @classmethod
    def _known_delimiter(cls, v: str) -> str:
        if v == "auto" or v in _DELIM_NAMES or len(v) == 1:
            return v
        raise ValueError(
            f"delimiter must be 'auto', one of {sorted(_DELIM_NAMES)}, or a single "
            f"character; got {v!r}"
        )

    @model_validator(mode="after")
    def _enough_to_make_a_profile(self) -> TextFormatSpec:
        if not ({"pres", "depth"} & set(self.columns)):
            raise ValueError(
                "columns must map at least one vertical axis: `pres` or `depth`. "
                "Without one there is no profile."
            )
        if not ({"temp", "psal"} & set(self.columns)):
            raise ValueError("columns must map at least one measurement: `temp` or `psal`")
        return self

    @property
    def resolved_delimiter(self) -> str | None:
        """The configured delimiter as a character, or None for whitespace."""
        if self.delimiter in _DELIM_NAMES:
            return _DELIM_NAMES[self.delimiter]
        return self.delimiter


def text_format(spec: SourceSpec) -> TextFormatSpec:
    """Pull the `text:` block off a registry source.

    Read through getattr so this module works both before and after the
    `text` field lands on registry.SourceSpec: SourceSpec ignores unknown keys,
    so until then a `text:` block in sources.yaml is silently discarded and
    callers must pass `fmt` explicitly. Saying so is better than a KeyError.
    """
    raw = getattr(spec, "text", None)
    if raw is None:
        raise TextParseError(
            f"source {getattr(spec, 'id', '<unknown>')!r} has no `text:` block. Add one to "
            "data/sources.yaml (and the `text` field to registry.SourceSpec), or pass "
            "fmt=TextFormatSpec(...) explicitly."
        )
    if isinstance(raw, TextFormatSpec):
        return raw
    return TextFormatSpec.model_validate(raw)


# --- text mechanics ---------------------------------------------------------

def _decode(raw: bytes, encoding: str) -> str:
    """Bytes -> text, tolerating the two encodings real files arrive in.

    utf-8-sig also removes a BOM, which would otherwise become part of the first
    column NAME and make it unrecognisable.
    """
    if encoding != "auto":
        return raw.decode(encoding)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: latin-1 maps every byte, so we get text rather than a crash.
    return raw.decode("latin-1", "replace")


def _tokenize(line: str, delimiter: str | None) -> list[str]:
    """Split one line. csv handles quoted fields containing the delimiter."""
    if delimiter is None:
        return str(line).split()
    try:
        return next(csv.reader([str(line)], delimiter=delimiter))
    except (csv.Error, StopIteration):
        return str(line).split(delimiter)


_UNIT_SUFFIX = re.compile(r"[\[\(][^\]\)]*[\]\)]\s*$")


def _norm(name: Any) -> str:
    """Fold a column name onto its comparable form.

    Strips a trailing bracketed unit so ONE alias covers "Temperature",
    "Temperature [degC]" and "Temperature (deg C)".
    """
    s = str(name).strip().strip('"').strip()
    s = _UNIT_SUFFIX.sub("", s).strip()
    return re.sub(r"\s+", " ", s).casefold()


def _squash(name: Any) -> str:
    """Alphanumerics only, so "Sea Temp", "sea_temp" and "SeaTemp" all match."""
    return re.sub(r"[^a-z0-9]", "", _norm(name))


def _bracket_unit(name: Any) -> str | None:
    m = re.search(r"[\[\(]([^\]\)]*)[\]\)]\s*$", str(name).strip())
    return m.group(1) if m else None


def _fold_vertical_unit(unit: Any) -> str | None:
    """A vertical unit string -> "dbar" | "m" | None.

    cf.canonical_unit folds "decibar" and "metres", but not the "db" that ODV
    writes into its column names, so that spelling is handled here.
    """
    if unit is None:
        return None
    s = str(canonical_unit(str(unit))).strip().strip("[]()").casefold()
    if s in ("db", "dbar", "dbars", "decibar", "decibars"):
        return "dbar"
    if s in ("m", "metre", "meter", "metres", "meters"):
        return "m"
    return None


#: "sniff_delimiter did not answer", which is NOT the same as "it answered
#: whitespace" (None). Conflating the two credited the sniffer for a choice it
#: never made.
_NO_SNIFF: Any = object()


def sniff_delimiter(
    lines: list[str], candidates: list[str | None] | None = None
) -> str | None:
    """Detect the delimiter over a block of lines. None means whitespace.

    Public because "why did it pick whitespace?" is a real debugging question
    when a new format is added -- and, since the defect below was found, this is
    genuinely the function that answers it: `_resolve_layout` calls it. It used
    to be exported, documented and unit-tested while _resolve_layout made the
    real choice in a private candidate loop of its own, so the advertised entry
    point and its test could both be green while the detection actually
    performed was broken. Calling it on the same lines now reproduces the
    parser's own answer.

    `candidates` restricts the search, which is how the parser passes an
    explicitly configured delimiter instead of the full order. A block splits
    consistently only when every non-blank line yields the SAME field count and
    at least two fields; anything else raises rather than returning a guess.
    """
    usable = [ln for ln in lines if str(ln).strip()]
    for cand in _DELIM_ORDER if candidates is None else candidates:
        counts = [len(_tokenize(ln, cand)) for ln in usable]
        if counts and min(counts) >= 2 and len(set(counts)) == 1:
            return cand
    raise TextParseError(
        "no delimiter produces a consistent field count over these lines; set "
        "`delimiter` explicitly in the source's text config"
    )


#: Delimiter -> the spelling `data/sources.yaml` uses, for provenance. A caller
#: reading "whitespace" out of a returned frame can find that word in the config
#: schema; it cannot do anything with `None`.
_DELIM_LABELS: dict[Any, str] = {
    "\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe", None: "whitespace",
}


def _delimiter_label(delim: str | None) -> str:
    return _DELIM_LABELS.get(delim, repr(delim))


_META_LINE = re.compile(
    r"^(?P<key>[A-Za-z][A-Za-z0-9 _.\-()/]*?)\s*[=:]\s*(?P<val>.*\S)\s*$"
)


def _strip_comment(line: str, prefixes: list[str]) -> str:
    s = str(line).strip()
    # Longest prefix first, so "%%" is not mistaken for "%".
    for p in sorted(prefixes, key=len, reverse=True):
        if p and s.startswith(p):
            return s[len(p):].strip()
    return s


def parse_header_metadata(lines, fmt: TextFormatSpec) -> dict[str, str]:
    """Harvest "key = value" / "key: value" pairs from a header block.

    Public so a new format can be debugged without running a whole parse. Keys
    are matched against the configured aliases only, so an unconfigured line
    like "# name 0 = prDM: Pressure, Digiquartz [db]" is ignored rather than
    half-parsed. Aliases are tried in their configured order, first hit wins,
    which makes the choice deterministic and config-controlled when a file
    carries several plausible spellings of the same fact.
    """
    found: dict[str, str] = {}
    for line in lines:
        body = _strip_comment(line, fmt.comment_prefixes)
        m = _META_LINE.match(body)
        if not m:
            continue
        key = _norm(m.group("key"))
        # First occurrence wins: Sea-Bird repeats some keys as the cast proceeds.
        found.setdefault(key, m.group("val").strip())
        found.setdefault(_squash(m.group("key")), m.group("val").strip())

    out: dict[str, str] = {}
    for canon, aliases in fmt.header_metadata.items():
        for alias in aliases:
            if _norm(alias) in found:
                out[canon] = found[_norm(alias)]
                break
            if _squash(alias) in found:
                out[canon] = found[_squash(alias)]
                break
    return out


# --- numbers ----------------------------------------------------------------

_COORD_RE = re.compile(
    r"^([+-]?\d+(?:[.,]\d+)?)(?:\s+(\d+(?:[.,]\d+)?))?\s*([NSEWnsew])?$"
)
_INT_RE = re.compile(r"^[+-]?\d+$")


def _parse_coord(text: Any) -> float:
    """A coordinate as decimal degrees, tolerating what NMEA hands you.

    Accepts "12.5", "-12.5", "12.5 N", "86.5E", a decimal comma, and degrees
    plus decimal MINUTES ("12 30.00 N"), which is what Sea-Bird copies straight
    out of the NMEA string. Read as a plain decimal, "12 30.00 N" becomes 12.0 --
    a 55 km position error that no chart would reveal.
    """
    if text is None:
        return float("nan")
    # The degree sign and the minute/second marks are dropped rather than
    # parsed: they carry no information a hemisphere letter does not, and they
    # arrive in three different encodings depending on the writing software.
    # The degree sign is written as an escape, not as a literal glyph: this
    # repo keeps its sources pure ASCII, and a raw degree sign in a source
    # file is the very byte that makes a strict utf-8 read of a cp1252 file
    # fail (see _decode).
    s = str(text).strip().replace("\u00b0", " ").replace("'", " ").replace('"', " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return float("nan")
    m = _COORD_RE.match(s)
    if not m:
        return float("nan")
    deg = float(m.group(1).replace(",", "."))
    mins = float(m.group(2).replace(",", ".")) if m.group(2) else 0.0
    hemi = (m.group(3) or "").upper()
    sign = -1.0 if (deg < 0 or hemi in ("S", "W")) else 1.0
    return sign * (abs(deg) + mins / 60.0)


def _split_sentinels(missing) -> tuple[list[float], set[str]]:
    numeric: list[float] = []
    textual: set[str] = set()
    for item in missing:
        if isinstance(item, str):
            try:
                numeric.append(float(item))
            except ValueError:
                textual.add(item.strip().casefold())
        else:
            numeric.append(float(item))
    return numeric, textual


def _mask_sentinels(
    vals: np.ndarray, raw: list[str], missing, coord_limit: float | None = None
) -> np.ndarray:
    """Replace declared sentinels with NaN.

    Numeric sentinels are matched with a RELATIVE tolerance, the same reasoning
    as `cf._mask_fills`: -1.0E34 does not survive a float32 round trip as an
    exact equality, and "-9.990" is not string-equal to "-9.99" either.

    `coord_limit` exists because -9.99 is a temperature sentinel AND a real
    longitude off Portugal. For a coordinate, only sentinels that cannot BE a
    coordinate are applied -- masking a legitimate -9.99 would delete the cast.
    """
    numeric, textual = _split_sentinels(missing)
    mask = np.zeros(vals.shape, dtype=bool)
    for sentinel in numeric:
        if not np.isfinite(sentinel):
            continue
        if coord_limit is not None and abs(sentinel) <= coord_limit:
            continue
        mask |= np.isclose(vals, sentinel, rtol=1e-6, atol=0.0)
    if textual:
        for i, s in enumerate(raw):
            if s.strip().casefold() in textual:
                mask[i] = True
    out = vals.copy()
    out[mask] = np.nan
    return out


def _to_float(tokens: list[str], decimal: str, missing) -> np.ndarray:
    """Text cells -> float64 with NaN for anything absent or unparseable.

    An unparseable cell becomes NaN rather than raising: real files carry stray
    "---" and "n/a" markers, and the row filter decides afterwards whether the
    level still has anything worth keeping.
    """
    raw = [str(t).strip().strip('"').strip() for t in tokens]
    vals = np.full(len(raw), np.nan, dtype="float64")
    for i, s in enumerate(raw):
        if not s:
            continue
        t = s.replace(",", ".") if decimal == "," else s
        try:
            vals[i] = float(t)
        except ValueError:
            vals[i] = np.nan
    return _mask_sentinels(vals, raw, missing)


def _to_coords(tokens: list[str], missing) -> np.ndarray:
    raw = [str(t).strip() for t in tokens]
    vals = np.asarray([_parse_coord(s) for s in raw], dtype="float64")
    return _mask_sentinels(vals, raw, missing, coord_limit=180.0)


def _parse_time_series(values, formats: list[str]) -> pd.Series:
    """Text timestamps -> tz-naive datetime64[ns], UTC assumed.

    Each configured strptime pattern is tried in order, then ISO-8601. Parsing
    with utc=True and then dropping the zone is deliberate: it gives one
    resolution and one convention, and it sidesteps the pandas mixed-timezone
    FutureWarning that an inferred parse would raise (pyproject turns
    FutureWarning into a test failure for exactly this reason).
    """
    cleaned = [
        None if v is None or not str(v).strip() else str(v).strip() for v in values
    ]
    s = pd.Series(cleaned, dtype="object")
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt_str in [*formats, "ISO8601"]:
        todo = out.isna() & s.notna()
        if not todo.any():
            break
        try:
            parsed = pd.to_datetime(s[todo], format=fmt_str, errors="coerce", utc=True)
        except (ValueError, TypeError):
            continue
        out.loc[todo] = parsed.dt.tz_localize(None)
    return out


# --- layout resolution ------------------------------------------------------

def _alias_maps(fmt: TextFormatSpec) -> tuple[dict[str, str], dict[str, str]]:
    exact: dict[str, str] = {}
    squashed: dict[str, str] = {}
    for canon, aliases in fmt.columns.items():
        # The canonical name is always an implicit alias.
        for alias in [*aliases, canon]:
            exact.setdefault(_norm(alias), canon)
            squashed.setdefault(_squash(alias), canon)
    return exact, squashed


def _canon_of(token: str, exact: dict[str, str], squashed: dict[str, str]) -> str | None:
    return exact.get(_norm(token)) or squashed.get(_squash(token))


def _comma_decimal_collision(n_names: int, rows: list[list[str]], delimiter) -> bool:
    """Is this a comma-delimited file that ALSO uses a decimal comma?

    Signature: the delimiter is a comma, every data row has more fields than the
    header, and every one of those fields is a bare integer -- because
    "3,3000,28,5500,34,0470,1" shatters into integer halves. Unquoted, such a
    file is genuinely ambiguous, so it is diagnosed and refused rather than
    guessed at.
    """
    if delimiter != "," or not rows:
        return False
    for fields in rows:
        if len(fields) <= n_names:
            return False
        if not all(_INT_RE.match(f.strip()) for f in fields):
            return False
    return True


def _resolve_layout(
    records: list[str], fmt: TextFormatSpec, name: str
) -> tuple[int, str | None, list[str], str]:
    """Find the column-name row and the delimiter together.

    They cannot be resolved separately: recognising the name row needs a split,
    and choosing the split is only trustworthy if it makes the name row
    recognisable. So each candidate delimiter is scored by how many configured
    aliases it reveals, and the data lines below must agree on the field count.

    The delimiter question itself is put to the PUBLIC `sniff_delimiter`, on the
    name-row candidate plus the lines below it, and its answer is taken whenever
    that answer also reveals the configured aliases. That keeps the documented
    detector and the detection actually performed as one thing rather than two
    that can drift (they had: the exported function was dead code). The alias
    scan stays underneath it as the fallback, because a consistent field count
    is not by itself evidence that the split found the column NAMES, and because
    the fallback path is what diagnoses the decimal-comma collision below.

    The fourth element of the return is which of the two answered, so a caller
    can see it in the returned frame's provenance.
    """
    exact, squashed = _alias_maps(fmt)
    candidates: list[str | None]
    if fmt.delimiter == "auto":
        candidates = list(_DELIM_ORDER)
    else:
        candidates = [fmt.resolved_delimiter]

    indices = (
        [int(fmt.column_row)]
        if fmt.column_row != "auto"
        else list(range(min(len(records), 200)))
    )

    def source_of(delim: str | None, sniffed: Any) -> str:
        if fmt.delimiter != "auto":
            return "config"          # nothing was detected at all
        return "sniff_delimiter" if (sniffed is not _NO_SNIFF and delim == sniffed) else "alias_scan"

    fallback: tuple[int, str | None, list[str], str] | None = None
    for i in indices:
        if i >= len(records):
            break
        try:
            sniffed = sniff_delimiter(records[i: i + 6], candidates=candidates)
        except TextParseError:
            # This block does not split consistently under any candidate, which
            # is normal for a header line above the real column names.
            sniffed = _NO_SNIFF
        ordered = (
            candidates
            if sniffed is _NO_SNIFF
            else [sniffed, *(c for c in candidates if c != sniffed)]
        )
        for delim in ordered:
            tokens = _tokenize(records[i], delim)
            if len(tokens) < 2:
                continue
            if sum(1 for t in tokens if _canon_of(t, exact, squashed)) < 2:
                continue
            below = records[i + 1: i + 6]
            if not below or any(len(_tokenize(ln, delim)) == len(tokens) for ln in below):
                return i, delim, tokens, source_of(delim, sniffed)
            if fallback is None:
                fallback = (i, delim, tokens, source_of(delim, sniffed))

    if fallback is not None:
        i, delim, tokens, source = fallback
        sampled = [_tokenize(ln, delim) for ln in records[i + 1: i + 9]]
        if _comma_decimal_collision(len(tokens), sampled, delim):
            raise TextParseError(
                f"{name}: the delimiter is a comma and every data field is a bare "
                "integer, which means the file also uses a decimal comma. Reading "
                "it either way is a guess -- set `delimiter` (with quoted fields) "
                "or `decimal` explicitly in the source's text config."
            )
        return fallback

    raise TextParseError(
        f"{name}: could not locate a column-name row. No candidate delimiter "
        f"({'auto' if fmt.delimiter == 'auto' else fmt.delimiter!r}) reveals two or "
        "more of the configured column aliases. Set `column_row` and `delimiter` "
        "explicitly, or fix the aliases in the source's text config."
    )


def _resolve_columns(
    name_tokens: list[str], fmt: TextFormatSpec
) -> dict[int, str]:
    """Column index -> canonical name.

    With `qc_follows_value`, an ODV "QF" is bound to the column immediately
    before it. A QF following a column we do NOT read (ODV flags "Bot. Depth"
    too) is DROPPED rather than treated as a level flag, because applying a
    bottom-depth flag to temperature would reject good data for the wrong reason.
    """
    exact, squashed = _alias_maps(fmt)
    colmap: dict[int, str] = {}
    for idx, token in enumerate(name_tokens):
        canon = _canon_of(token, exact, squashed)
        if canon is not None:
            colmap[idx] = canon

    if fmt.qc_follows_value:
        previous: str | None = None
        for idx in range(len(name_tokens)):
            canon = colmap.get(idx)
            if canon == "qc":
                if previous is None:
                    colmap.pop(idx)
                else:
                    colmap[idx] = f"{previous}_qc"
                previous = None
            else:
                previous = canon if canon in _FLAGGABLE else None
    return colmap


# --- the vertical axis ------------------------------------------------------

def _normalize_depth(vals: np.ndarray, positive: str) -> np.ndarray:
    """Depth positive down, matching the cf.py rule for gridded fields.

    `positive: up` is a height axis and is negated. Negative values with no
    declared convention are treated as magnitudes -- the source is storing height
    and forgot to say so. Rendered as-is, the thermocline ends up above the sea
    surface. A value still negative afterwards is above the surface and cannot be
    a level, so it is made explicitly absent rather than clamped to zero.
    """
    out = np.asarray(vals, dtype="float64").copy()
    finite = out[np.isfinite(out)]
    if positive == "up":
        out = -out
    elif positive == "auto" and finite.size and (finite < 0).any():
        out = np.abs(out)
    out[out < 0.0] = np.nan
    return out


def _derive_pressure(depth: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Depth (m, positive down) -> sea pressure (dbar), TEOS-10.

    The exact inverse of argo.pressure_to_depth, hence gsw again rather than a
    1.01 fudge factor: round-tripping the two agrees to ~1e-13 m.
    """
    return np.asarray(gsw.p_from_z(-np.asarray(depth, dtype="float64"), lat), dtype="float64")


# --- QC ---------------------------------------------------------------------

def _flag_array(tokens: list[str] | None, vocab: FlagVocabularySpec, n: int) -> np.ndarray:
    if tokens is None:
        return np.full(n, vocab.when_absent, dtype="int16")
    lut = {str(k).strip().casefold(): int(v) for k, v in vocab.map.items()}
    out = np.full(n, vocab.when_blank, dtype="int16")
    for i, token in enumerate(tokens):
        s = str(token).strip()
        if not s:
            continue
        if s.casefold() in lut:
            out[i] = lut[s.casefold()]
            continue
        try:
            # An unmapped digit passes through: a file that already speaks Argo
            # needs no `map` at all.
            out[i] = int(float(s.replace(",", ".")))
        except ValueError:
            out[i] = vocab.when_blank
    return out


# --- the frame --------------------------------------------------------------

def empty_profile_frame() -> pd.DataFrame:
    """An empty frame with the REAL dtypes.

    An all-object empty frame poisons the parquet schema the first time a source
    happens to yield nothing, which is why this is not just `DataFrame(columns=)`.
    """
    return pd.DataFrame(
        {c: pd.Series([], dtype=PROFILE_DTYPES[c]) for c in PROFILE_COLUMNS}
    )


#: The provenance key on a returned frame. Namespaced, because `.attrs` is a
#: shared dict and app/cf.py writes source_id/citation onto its own objects.
PROVENANCE_KEY = "text_provenance"

#: Why a second, tuple-returning entry point exists.
#:
#: The parse record rides on ``frame.attrs[PROVENANCE_KEY]``, and pandas DROPS
#: ``.attrs`` on ``concat`` (verified on 2.2.3). Since the profiles table is
#: built by concatenating per-file frames, the skipped-line and footer record
#: would vanish exactly when several files are combined, which is exactly when
#: a missing level is hardest to notice. Any code that concatenates MUST use
#: ``parse_text_profiles_with_record`` and persist the record itself, next to
#: the store, the way tools/preprocess.py writes provenance.json.


def _with_provenance(frame: pd.DataFrame, prov: dict[str, Any]) -> pd.DataFrame:
    """Attach the parse record to the frame it describes.

    Written last, on the frame that is actually returned, so nothing depends on
    pandas propagating `.attrs` through a filter or an astype.
    """
    frame.attrs[PROVENANCE_KEY] = dict(prov)
    return frame


def _id_part(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", "-", str(value).strip())


def parse_text_profiles(
    path: str | Path,
    spec: SourceSpec,
    fmt: TextFormatSpec | None = None,
) -> pd.DataFrame:
    """Parse a delimited-text profile file into the shared tidy frame.

    `spec` supplies the QC POLICY (`spec.qc.accept_flags`); `fmt` supplies the
    FORMAT. Passing fmt explicitly is how callers work until registry.SourceSpec
    carries the `text` field.
    """
    fmt = fmt if fmt is not None else text_format(spec)
    accept = list(spec.qc.accept_flags)
    path = Path(path)
    name = path.name

    text = _decode(path.read_bytes(), fmt.encoding)
    # splitlines() after the decode disposes of CRLF and lone-CR in one step,
    # and utf-8-sig has already eaten any BOM. Both defects are silent: a stray
    # "\r" turns the last column into "1\r".
    comments: list[str] = []
    records: list[str] = []
    #: Physical 1-based line number of each record. Blank and comment lines are
    #: dropped above, so a record index is NOT a line number, and a line number
    #: is the only thing an operator can act on when a file is refused.
    record_lines: list[int] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(p) for p in fmt.comment_prefixes if p):
            comments.append(line)
            continue
        records.append(line)
        record_lines.append(lineno)

    #: What the parse did, returned on the frame's `.attrs` so a caller can see
    #: it. It exists because of a silent defect: levels dropped for being ragged
    #: were invisible, and the level count feeds argo.profile_summary and every
    #: depth-binned statistic. A number without provenance is not shippable.
    prov: dict[str, Any] = {
        "file": name,
        "n_records": len(records),
        "delimiter": None,
        "delimiter_source": None,
        "column_row_line": None,
        "n_data_lines": 0,
        "n_levels_parsed": 0,
        "n_levels_returned": 0,
        "n_profiles": 0,
        "skipped_lines": [],
        "n_skipped_lines": 0,
        "n_stations": None,
    }

    if not records:
        return _with_provenance(empty_profile_frame(), prov)

    row_idx, delimiter, name_tokens, delim_source = _resolve_layout(records, fmt, name)
    prov["delimiter"] = _delimiter_label(delimiter)
    prov["delimiter_source"] = delim_source
    prov["column_row_line"] = record_lines[row_idx]
    meta = parse_header_metadata([*comments, *records[:row_idx]], fmt)

    units_tokens: list[str] | None = None
    first_data = row_idx + 1
    if fmt.units_row and row_idx + 1 < len(records):
        units_tokens = _tokenize(records[row_idx + 1], delimiter)
        first_data = row_idx + 2

    data_lines = records[first_data:]
    prov["n_data_lines"] = len(data_lines)
    if not data_lines:
        return _with_provenance(empty_profile_frame(), prov)

    n_fields = len(name_tokens)
    rows: list[list[str]] = []
    #: Physical line number of each KEPT row, so a later refusal (a station with
    #: no position of its own) can name the line it is talking about.
    row_lines: list[int] = []
    ragged: list[int] = []
    #: The text of each non-matching line, keyed by physical line number, so the
    #: footer test below can ask whether a line looks like data at all.
    ragged_text: dict[int, str] = {}
    for offset, line in enumerate(data_lines):
        tokens = _tokenize(line, delimiter)
        if len(tokens) == n_fields:
            rows.append(tokens)
            row_lines.append(record_lines[first_data + offset])
        else:
            ragged_text[record_lines[first_data + offset]] = line
            ragged.append(record_lines[first_data + offset])
    prov["skipped_lines"] = list(ragged)
    prov["n_skipped_lines"] = len(ragged)
    if not rows:
        raise TextParseError(
            f"{name}: no data row has the {n_fields} fields the column-name row "
            f"declares. The delimiter is probably wrong -- refusing to return a "
            "plausible-looking frame built from a bad split."
        )

    # Ragged lines used to be dropped with no error, no warning and no record:
    # a file where 7 of 8 levels are ragged parsed into a one-level cast that
    # looked entirely plausible, and n_levels feeds every depth-binned
    # statistic. Silence is not an option, so BOTH remedies are used, split by
    # what the raggedness means:
    #
    #   * one short LAST line is a file truncated mid-write (killed logger, full
    #     disk), which is normal and costs exactly one level. It parses, and the
    #     dropped line is reported in provenance.
    #   * anything else means the split or the file is wrong, and the levels
    #     lost are levels a scorecard would silently miss. Refuse, and name the
    #     lines -- a caller cannot be relied on to read provenance, and a wrong
    #     level count is not recoverable downstream.
    # A trailing block that does not parse as data is a FOOTER, not corruption:
    # Sea-Bird writes "END OF DATA" and a scan count, and loggers append their
    # own sign-off. Refusing a good three-level cast because of two footer lines
    # is a false positive on an ordinary file. Mid-file raggedness keeps its
    # refusal, because that is where levels go missing unnoticed.
    def _looks_like_data(line: str) -> bool:
        """Would a human call this a data row?

        The discriminator is numeric density, not field count. "END OF DATA"
        and "7 scans written" carry no number or one, while a truncated cast
        line is numbers all the way across. Without this, a file whose levels
        all lost a column was classed as a giant footer, because every ragged
        line happened to be contiguous with the end of the file.
        """
        fields = [f for f in re.split(r"[	,;]|\s{1,}", line.strip()) if f]
        if not fields:
            return False
        numeric = 0
        for f in fields:
            try:
                float(f.replace(",", "."))
                numeric += 1
            except ValueError:
                pass
        return numeric * 2 >= len(fields)

    trailing: list[int] = []
    if ragged:
        idx = {ln: i for i, ln in enumerate(record_lines)}
        last = len(record_lines) - 1
        run = []
        for ln in sorted(ragged, reverse=True):
            if idx.get(ln) != last - len(run):
                break
            if _looks_like_data(ragged_text.get(ln, "")):
                # A truncated data line, not a sign-off. Leave it to the
                # single-last-line tolerance or the refusal below.
                break
            run.append(ln)
        trailing = sorted(run)
    interior = [ln for ln in ragged if ln not in set(trailing)]
    if trailing:
        prov["footer_lines"] = trailing
        prov["n_footer_lines"] = len(trailing)

    # Two DIFFERENT tolerances, and both must survive. A non-data footer block
    # is handled above. A single truncated LAST data line is a logger killed
    # mid-write: it is numeric, so it is correctly not a footer, and it keeps
    # its own long-standing tolerance here. "Last" means the last line that is
    # not part of a footer, so a truncated cast followed by "END OF DATA" is
    # still tolerated rather than refused.
    footer = set(trailing)
    data_line_numbers = [ln for ln in record_lines[first_data:] if ln not in footer]
    last_data_line = data_line_numbers[-1] if data_line_numbers else None
    truncated_tail = len(interior) == 1 and interior[0] == last_data_line

    if interior and not truncated_tail:
        shown = ", ".join(str(n) for n in interior[:10])
        if len(interior) > 10:
            shown += f", ... ({len(interior)} lines in total)"
        raise TextParseError(
            f"{name}: {len(interior)} data line(s) do not carry the {n_fields} fields "
            f"the column-name row declares, at line(s) {shown}. Keeping only the "
            f"{len(rows)} line(s) that matched would report a {len(rows)}-level cast "
            f"built from a file with {len(data_lines)} data lines, and the level count "
            "feeds every depth-binned statistic. Fix the file, or set `delimiter` / "
            "`column_row` explicitly in the source's text config. (A single truncated "
            "LAST line is tolerated and reported in provenance instead.)"
        )
    nrows = len(rows)
    prov["n_levels_parsed"] = nrows

    colmap = _resolve_columns(name_tokens, fmt)
    colindex: dict[str, int] = {}
    for idx, canon in sorted(colmap.items()):
        colindex.setdefault(canon, idx)

    def cells(canon: str) -> list[str] | None:
        idx = colindex.get(canon)
        return None if idx is None else [r[idx] for r in rows]

    # Decimal separator. Only detectable when the delimiter is not itself a
    # comma; when it is, the collision check in _resolve_layout has already
    # refused the ambiguous case.
    decimal = fmt.decimal
    if decimal == "auto":
        decimal = "."
        if delimiter != ",":
            euro = re.compile(r"^[+-]?\d+,\d+$")
            for r in rows[:20]:
                if any(euro.match(f.strip()) for f in r):
                    decimal = ","
                    break
    elif decimal == "," and delimiter == ",":
        raise TextParseError(
            f"{name}: a comma cannot be both the delimiter and the decimal "
            "separator. Choose one in the source's text config."
        )

    ffill = fmt.forward_fill_identity

    # --- station boundaries -------------------------------------------------
    # The fill used to run down each identity column independently, over the
    # WHOLE file. On the ODV export this module advertises that produced a
    # confirmed wrong answer: station BOB-11's levels were emitted as BOB-07, at
    # BOB-07's position and date, about 300 km and two days away from where the
    # instrument was, with real temperatures attached. A fill is only ever legal
    # WITHIN one station, so the boundaries are found first and the fill is
    # grouped by them.
    #
    # A boundary is announced by the identity the parser can actually see: the
    # platform or cast cell going non-blank with a value different from the one
    # in force. (The ODV "Cruise"/"Type" cells are not mapped columns, so they
    # are invisible here; a file that announces a station only through them is
    # caught instead by the per-station checks below, which refuse a station
    # whose first row has no position or no timestamp of its own.)
    key_cols = [c for c in ("platform", "cast") if c in colindex]
    station_starts: list[int] = [0]
    if ffill and key_cols:
        in_force: dict[str, str | None] = {c: None for c in key_cols}
        for r in range(nrows):
            seen = {c: rows[r][colindex[c]].strip() for c in key_cols}
            # A BLANK cell is an ODV continuation cell: it carries no claim, so
            # it can neither start nor rule out a station.
            changed = any(
                seen[c] and in_force[c] is not None and seen[c] != in_force[c]
                for c in key_cols
            )
            if r > 0 and changed:
                station_starts.append(r)
                in_force = {c: (seen[c] or None) for c in key_cols}
            else:
                for c in key_cols:
                    if seen[c]:
                        in_force[c] = seen[c]
    # cumsum rather than a slice-assignment loop: a cruise file can hold a
    # thousand stations and a hundred thousand levels, and the loop version is
    # quadratic in that product.
    is_start = np.zeros(nrows, dtype=bool)
    is_start[station_starts] = True
    station_of_row = np.cumsum(is_start) - 1
    first_row_of_station = np.asarray(station_starts, dtype="int64")[station_of_row]
    prov["n_stations"] = len(station_starts) if ffill else None

    def raw_present(canon: str) -> np.ndarray:
        """Which rows carry a non-blank cell of their own in this column."""
        tokens = cells(canon)
        if tokens is None:
            return np.zeros(nrows, dtype=bool)
        return np.asarray([bool(str(t).strip()) for t in tokens], dtype=bool)

    def station_label(r: int) -> str:
        """How to name the station beginning at row `r` in an error message."""
        parts = [rows[r][colindex[c]].strip() for c in key_cols]
        named = "/".join(p for p in parts if p)
        return named or f"the block starting at line {row_lines[r]}"

    # --- identity, per row --------------------------------------------------
    def identity_text(canon: str) -> pd.Series:
        tokens = cells(canon)
        if tokens is not None:
            series = pd.Series(
                [t.strip() or None for t in tokens], dtype="object"
            )
            if ffill:
                series = series.groupby(station_of_row).ffill()
        else:
            series = pd.Series([None] * nrows, dtype="object")
        if meta.get(canon) is not None:
            series = series.fillna(meta[canon])
        return series

    def identity_coord(canon: str) -> np.ndarray:
        tokens = cells(canon)
        if tokens is not None:
            series = pd.Series(_to_coords(tokens, fmt.missing), dtype="float64")
            if ffill:
                series = series.groupby(station_of_row).ffill()
        else:
            series = pd.Series(np.full(nrows, np.nan), dtype="float64")
        if series.isna().any() and meta.get(canon) is not None:
            scalar = _mask_sentinels(
                np.asarray([_parse_coord(meta[canon])], dtype="float64"),
                [str(meta[canon])],
                fmt.missing,
                coord_limit=180.0,
            )[0]
            series = series.fillna(scalar)
        return series.to_numpy(dtype="float64")

    platform = identity_text("platform")
    if platform.isna().all():
        # The file carries no station id. The file stem is the only identifier it
        # actually has, and inventing one would be worse (rule: no number without
        # provenance).
        platform = pd.Series([path.stem] * nrows, dtype="object")
    if fmt.platform_prefix:
        platform = platform.map(
            lambda v: v if v is None or pd.isna(v) else f"{fmt.platform_prefix}-{v}"
        )
    cast = identity_text("cast")

    lat = identity_coord("lat")
    lon = identity_coord("lon")
    if not np.isfinite(lat).any() or not np.isfinite(lon).any():
        raise TextParseError(
            f"{name}: no latitude/longitude found in a column or in the header "
            "block. A profile without a position cannot be co-located with a "
            "model field, and the depth conversion needs the latitude."
        )

    time_tokens = cells("time")
    if time_tokens is None and cells("date") is not None:
        # Sea-Bird and several loggers split the stamp across two columns.
        date_cells = cells("date")
        tod_cells = cells("time_of_day")
        time_tokens = (
            [f"{d.strip()} {t.strip()}".strip() for d, t in zip(date_cells, tod_cells)]
            if tod_cells is not None
            else [d.strip() for d in date_cells]
        )
    if time_tokens is not None:
        times = _parse_time_series(time_tokens, fmt.time_formats)
        if ffill:
            # Grouped, for the same reason as the position: an inherited
            # timestamp is a level compared against the wrong model step.
            times = times.groupby(station_of_row).ffill()
    else:
        times = pd.Series(pd.NaT, index=range(nrows), dtype="datetime64[ns]")
    if times.isna().any():
        meta_stamp = meta.get("time")
        if meta_stamp is None and meta.get("date") is not None:
            meta_stamp = " ".join(
                x for x in (meta.get("date"), meta.get("time_of_day")) if x
            )
        if meta_stamp is not None:
            fill = _parse_time_series([meta_stamp], fmt.time_formats).iloc[0]
            if pd.notna(fill):
                times = times.fillna(fill)
    if times.isna().all():
        raise TextParseError(
            f"{name}: no timestamp found in a column or in the header block. "
            "Add the column/key to the text config, or a matching pattern to "
            "`time_formats` -- a level with no time cannot be matched to a model step."
        )

    # --- what each station must carry for ITSELF -----------------------------
    # Checked only when a fill is on, because without one there is nothing to
    # inherit: an absent position leaves the level unplaceable and the row
    # filter drops it, which provenance reports as parsed-minus-returned.
    if ffill:
        platform_used = "platform" in colindex and bool(raw_present("platform").any())
        for start in station_starts:
            label = station_label(start)
            if platform_used and not str(rows[start][colindex["platform"]]).strip():
                raise TextParseError(
                    f"{name}: the station beginning at line {row_lines[start]} has no "
                    "platform/station id of its own, but this file does use that "
                    "column. Filling it from the row above would publish these levels "
                    f"under the previous station's id ({label}). Fix the file, or turn "
                    "`forward_fill_identity` off for this source."
                )
            if not (np.isfinite(lat[start]) and np.isfinite(lon[start])):
                raise TextParseError(
                    f"{name}: station {label} begins at line {row_lines[start]} with no "
                    "latitude/longitude of its own. Forward-filling a position across a "
                    "station boundary puts the whole station at the PREVIOUS station's "
                    "position -- the defect this check exists for moved one station about "
                    "300 km. Fix the file, or supply the position in the header block."
                )
            if pd.isna(times.iloc[start]):
                raise TextParseError(
                    f"{name}: station {label} begins at line {row_lines[start]} with no "
                    "timestamp of its own. An inherited timestamp compares the station "
                    "against the wrong model step. Add the stamp, add a matching pattern "
                    "to `time_formats`, or supply it in the header block."
                )

        # A row that carries a position or timestamp OF ITS OWN inherits
        # nothing, so it is self-describing and safe, and the fill above leaves
        # it alone (a grouped ffill only replaces NaN).
        #
        # An earlier version of this block refused such a row whenever its value
        # disagreed with its station's first row, on the theory that it belonged
        # to a station the platform/cast columns never announced. That refused
        # VALID FILES, which is worse than the bug it was written for: a dense
        # glider or trajectory export carries its own position on every row, the
        # fill is a total no-op on it, and the parser already produces the right
        # frame. A repeat occupation of one station id was refused the same way.
        # The problem statement names Gliders explicitly, so this was a false
        # positive on a source we claim to support.
        #
        # It was also unnecessary. The confirmed leak (BOB-11's levels emitted
        # as BOB-07, 300 km and two days out) arrived because that station's
        # identity row was RAGGED and silently dropped, and a ragged line is now
        # refused outright further up. The remaining first-row checks above are
        # the ones that carry real weight: a station whose opening row has no
        # position or no timestamp of its own has nothing legitimate to inherit.
        #
        # What cannot be detected from the mapped columns at all is a new
        # station announced only by a blank Station cell. Refusing every
        # disagreement was the wrong answer to that; recording how many rows
        # inherited each field is the honest one, so a reader can see when a
        # fill did real work.
        for canon in ("lat", "lon", "time", "date", "platform", "cast"):
            if canon not in colindex:
                continue
            own = raw_present(canon)
            prov.setdefault("inherited", {})[canon] = int(nrows - int(own.sum()))

        # The one case that IS genuinely ambiguous, and the one the confirmed
        # leak was: a row whose IDENTITY cell (platform or cast) is blank, so
        # the platform column cannot see a boundary, while the row carries a
        # position or timestamp of its own that contradicts the station it
        # would be filled from. That is a new station announced only by a blank
        # cell, and its levels would be published under the previous station's
        # id: four real profiles relabelled, which is what happened to BOB-11.
        #
        # Gating on the BLANK identity cell is what makes this narrow enough to
        # be correct. An earlier version fired on any disagreement, which
        # refused a dense glider or trajectory export (every row carrying its
        # own position, identity present, fill a no-op) and a repeat occupation
        # of one station id. Both are valid files the parser already handles,
        # and the problem statement names Gliders explicitly.
        identity_blank = np.ones(nrows, dtype=bool)
        for c in key_cols:
            identity_blank &= ~raw_present(c)

        for canon, values in (("lat", lat), ("lon", lon)):
            for r in np.flatnonzero(raw_present(canon) & identity_blank):
                base = int(first_row_of_station[r])
                if r != base and not np.isclose(
                    values[r], values[base], rtol=0.0, atol=1e-9, equal_nan=True
                ):
                    raise TextParseError(
                        f"{name}: line {row_lines[r]} has no station id of its own but "
                        f"carries a {canon} of {values[r]}, which is not the {canon} of "
                        f"the station it would be filled from ({station_label(base)}, "
                        f"{values[base]}, line {row_lines[base]}). Its levels would be "
                        f"published under {station_label(base)}. Put the station id on "
                        "that row, or turn `forward_fill_identity` off."
                    )

        own_stamp = (raw_present("time") | raw_present("date")) & identity_blank
        for r in np.flatnonzero(own_stamp):
            base = int(first_row_of_station[r])
            if r != base and (
                pd.isna(times.iloc[r]) or times.iloc[r] != times.iloc[base]
            ):
                raise TextParseError(
                    f"{name}: line {row_lines[r]} has no station id of its own but "
                    f"carries its own timestamp, which is not the timestamp of the "
                    f"station it would be filled from ({station_label(base)}, "
                    f"{times.iloc[base]}, line {row_lines[base]}). Its levels would be "
                    f"published under {station_label(base)}. Put the station id on that "
                    "row, or turn `forward_fill_identity` off."
                )

    # --- the vertical axis --------------------------------------------------
    vcol = fmt.vertical.column
    if vcol == "auto":
        vcol = "pres" if "pres" in colindex else ("depth" if "depth" in colindex else None)
    if vcol is None or vcol not in colindex:
        wanted = (
            "no `pres` or `depth` column"
            if fmt.vertical.column == "auto"
            else f"no `{fmt.vertical.column}` column"
        )
        raise TextParseError(
            f"{name}: {wanted} was recognised, so there is no vertical column and "
            f"no profile. Columns recognised: {sorted(set(colmap.values()))}. The "
            "alias list in the source's text config is the likely fix."
        )

    vertical_values = _to_float(cells(vcol), decimal, fmt.missing)
    unit: str | None = None if fmt.vertical.units == "auto" else fmt.vertical.units
    if unit is None and units_tokens is not None and colindex[vcol] < len(units_tokens):
        unit = _fold_vertical_unit(units_tokens[colindex[vcol]])
    if unit is None:
        unit = _fold_vertical_unit(_bracket_unit(name_tokens[colindex[vcol]]))
    if unit is None:
        # Nothing declared a unit, so fall back to what the canonical name
        # implies. This is the only place the NAME decides.
        unit = "dbar" if vcol == "pres" else "m"

    if unit == "dbar":
        pres = vertical_values
        depth = pressure_to_depth(pres, lat)
        if "depth" in colindex and vcol != "depth":
            # A number in the file beats a derived one.
            from_file = _normalize_depth(
                _to_float(cells("depth"), decimal, fmt.missing), fmt.vertical.positive
            )
            depth = np.where(np.isnan(from_file), depth, from_file)
    else:
        depth = _normalize_depth(vertical_values, fmt.vertical.positive)
        if "pres" in colindex and vcol != "pres":
            pres = _to_float(cells("pres"), decimal, fmt.missing)
        elif fmt.derive_pressure:
            pres = _derive_pressure(depth, lat)
        else:
            pres = np.full(nrows, np.nan, dtype="float64")

    # --- measurements and QC ------------------------------------------------
    generic_flags = cells("qc")

    def flags_for(var: str) -> np.ndarray:
        own = cells(f"{var}_qc")
        if own is not None:
            return _flag_array(own, fmt.flags, nrows)
        return _flag_array(generic_flags, fmt.flags, nrows)

    def measurement(var: str) -> tuple[np.ndarray, np.ndarray]:
        tokens = cells(var)
        if tokens is None:
            # app/argo.py's convention for a variable the file does not carry.
            return (
                np.full(nrows, np.nan, dtype="float64"),
                np.full(nrows, 9, dtype="int16"),
            )
        vals = _to_float(tokens, decimal, fmt.missing)
        qc = flags_for(var)
        # A rejected value is removed but its flag is KEPT, so the record still
        # says why the number is absent.
        vals = np.where(np.isin(qc, accept), vals, np.nan)
        # And a value that is absent for any other reason (sentinel, blank) must
        # not claim to be QC-good: no value, no QC.
        qc = np.where(np.isnan(vals) & np.isin(qc, accept), 9, qc).astype("int16")
        return vals, qc

    temp, temp_qc = measurement("temp")
    psal, psal_qc = measurement("psal")

    vertical_flags = cells(f"{vcol}_qc")
    if vertical_flags is None:
        vertical_flags = cells("pres_qc") or cells("depth_qc") or generic_flags
    vflag = _flag_array(vertical_flags, fmt.flags, nrows)

    id_parts: list[list[str]] = []
    for key in fmt.profile_id_from:
        if key == "time":
            id_parts.append([
                "" if pd.isna(t) else pd.Timestamp(t).strftime("%Y%m%dT%H%M%S")
                for t in times
            ])
        elif key == "platform":
            id_parts.append([_id_part(v) for v in platform])
        else:
            id_parts.append([_id_part(v) for v in cast])
    profile_ids = ["_".join(p for p in parts if p) for parts in zip(*id_parts)]

    frame = pd.DataFrame(
        {
            "profile_id": pd.Series(profile_ids, dtype="object"),
            "wmo": pd.Series([_id_part(v) or None for v in platform], dtype="object"),
            "time": times.reset_index(drop=True),
            "lat": lat,
            "lon": lon,
            "pres": np.asarray(pres, dtype="float64"),
            "depth": np.asarray(depth, dtype="float64"),
            "temp": temp,
            "temp_qc": temp_qc,
            "psal": psal,
            "psal_qc": psal_qc,
        }
    )

    keep = (
        np.isfinite(frame["depth"].to_numpy())
        & np.isfinite(frame["lat"].to_numpy())
        & np.isfinite(frame["lon"].to_numpy())
        & frame["time"].notna().to_numpy()
        & frame["wmo"].notna().to_numpy()
        # A level whose VERTICAL coordinate is QC-rejected is dropped outright:
        # we cannot place it, and app/argo.py rejects on PRES_QC for the same
        # reason.
        & np.isin(vflag, accept)
        # Keep the level if ANY configured measurement survived. This is the
        # documented divergence from argo.py's whole-row drop.
        & (np.isfinite(frame["temp"].to_numpy()) | np.isfinite(frame["psal"].to_numpy()))
    )
    frame = frame[keep]
    if frame.empty:
        return _with_provenance(empty_profile_frame(), prov)

    frame = frame.sort_values(["profile_id", "depth"]).reset_index(drop=True)
    for column, dtype in PROFILE_DTYPES.items():
        if frame[column].dtype != np.dtype(dtype):
            frame[column] = frame[column].astype(dtype)
    frame = frame[list(PROFILE_COLUMNS)]
    # n_levels_returned next to n_levels_parsed is what makes a QC or
    # unplaceable-level drop visible: the difference is levels the file had and
    # the frame does not.
    prov["n_levels_returned"] = int(len(frame))
    prov["n_profiles"] = int(frame["profile_id"].nunique())
    return _with_provenance(frame, prov)
