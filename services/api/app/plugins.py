"""Plugin extension points (TRD M1, PS requirement F6 "Extensible Design").

The PS asks for "a documented plugin interface for future sensors (moorings,
HF-radar, ADCP) and ML-derived products", and PRD section 11 step 6 turns that
into a stage move: a new product is registered in front of judges and appears
in the variable selector. So this module has to be real machinery, not a
paragraph. There are exactly two extension points:

    SOURCE READER    keyed by the sources.yaml `kind` field. Registering a
                     reader for "mooring" makes `kind: mooring` a usable
                     source without touching this repo's core.
    DERIVED PRODUCT  a new selectable variable computed from an existing
                     field -- a diagnostic (D26, mixed-layer depth) or an
                     ML-derived product -- with no new store on disk.

Three properties are non-negotiable and are what most of the code below is for:

  * Zero network, zero install. Discovery is a scan of a local directory. The
    `sagardrishti.plugins` entry-point group is consulted as well, because a
    future INCOIS-internal wheel is the natural distribution channel, but with
    nothing installed that lookup is empty and free.
  * Explicit and inspectable. A plugin CALLS a registration method; nothing is
    picked up by naming convention or decorator magic. `describe()` then says
    what loaded and from which file, so "is my plugin in there?" is answerable
    in one HTTP GET rather than by reading logs.
  * Loud refusal. A plugin that fails silently on stage is worse than one that
    refuses to load, so every rule below has an id (R1-R9 registration,
    C1-C5 compute output, D1-D5 reader output) that appears in both the error
    message and docs/PLUGINS.md.

Discovery is deliberately NOT triggered at import time. tests/test_offline.py
imports every module under app/ to prove no network client is present, and
import-time discovery would make that test execute third-party plugin code.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol

import numpy as np
import xarray as xr

from . import cf

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Imported for annotations only. app.plugins must stay importable without
    # pulling in app.registry, so that a later change making store.py or
    # registry.py consult the plugin registry cannot create an import cycle.
    from .registry import SourceSpec

#: Entry-point group for plugins shipped as installed distributions.
ENTRY_POINT_GROUP = "sagardrishti.plugins"

#: A product name becomes a URL path segment (/field/{source}/{name}) and a key
#: in the client's variable selector, so it is restricted like one.
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
#: A reader kind is written by hand into data/sources.yaml.
_KIND_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

_CANONICAL_DIMS = frozenset({"time", "depth", "lat", "lon", "profile", "level"})
_OUTPUTS = frozenset({"surface", "column"})

#: Bound against a compute/open signature to check arity without calling it.
_PROBE = object()

_DOCS = "docs/PLUGINS.md"


class PluginError(Exception):
    """A plugin is malformed, or produced output that cannot be trusted.

    Deliberately not a ValueError: store.SubsetError (a caller-fixable request
    problem -> HTTP 400) is one, and these two must never be confused. A
    PluginError is our fault or the plugin author's, never the caller's, so it
    is a 500 with the rule id in the body.
    """


# --- the two protocols ------------------------------------------------------

class DerivedCompute(Protocol):
    """Compute a derived product from one subset water column.

    `ds` carries every variable named in the product's `requires`, on dims
    (depth, lat, lon) with a `depth` coordinate in metres positive down, and
    NaN for missing. Return an array of the declared output shape, using NaN
    (never a sentinel, never a default) wherever the answer does not exist.
    """

    def __call__(self, ds: xr.Dataset) -> xr.DataArray | np.ndarray: ...


class SourceOpen(Protocol):
    """Open one registry source and return it on the cf.py output contract."""

    def __call__(self, spec: "SourceSpec") -> xr.Dataset: ...


# --- what the registry holds ------------------------------------------------

@dataclass(frozen=True)
class DerivedProduct:
    name: str
    label: str
    units: str
    #: variable -> the units it is expected in, or None to skip the check.
    #: Declaring the units is what lets us refuse to compute D26 from Kelvin
    #: instead of returning a plausible-looking wrong depth.
    requires: Mapping[str, str | None]
    compute: DerivedCompute
    #: "surface" -> (lat, lon); "column" -> (depth, lat, lon). Declared rather
    #: than inferred, so the framework can validate the returned shape.
    output: str
    #: Echoed as provenance on every response, hence mandatory (rule R7).
    method: str
    params: Mapping[str, Any]
    canonical: str | None
    #: Empty means "any dataset carrying the required variables", which is why
    #: D26 starts working on GLORYS12 the day those credentials land.
    applies_to: tuple[str, ...]
    plugin: str


@dataclass(frozen=True)
class SourceReader:
    kind: str
    open: SourceOpen
    doc: str
    plugin: str


@dataclass(frozen=True)
class PluginFailure:
    #: "directory:<path>" or "entry_point:<name>" -- always traceable to a file.
    origin: str
    name: str
    error: str
    hint: str = ""


class PluginRegistry:
    """What loaded, what it registered, and what refused to load.

    Failures are kept rather than raised (outside strict mode) because one bad
    plugin must not take the working ones down with it: on stage, "nine of ten
    loaded and here is why the tenth did not" is recoverable, a dead API is not.
    """

    def __init__(self) -> None:
        self._derived: dict[str, DerivedProduct] = {}
        self._readers: dict[str, SourceReader] = {}
        self._failures: list[PluginFailure] = []
        self._origins: dict[str, str] = {}
        self._loading: tuple[str, str] = ("<direct>", "<direct>")

    # -- called by the loader, around each register() hook
    def _begin(self, name: str, origin: str) -> None:
        self._loading = (name, origin)
        self._origins[name] = origin

    def _end(self) -> None:
        self._loading = ("<direct>", "<direct>")

    def _record_failure(self, *, origin: str, name: str, error: str, hint: str = "") -> None:
        failure = PluginFailure(origin=origin, name=name, error=error, hint=hint)
        # Deduplicated: derived_variables() reports a shadowing product on every
        # /catalog call, and an ever-growing failure list would bury the rest.
        if failure not in self._failures:
            self._failures.append(failure)

    # -- registration
    def register_derived_product(
        self,
        *,
        name: str,
        label: str,
        units: str,
        requires: Mapping[str, str | None],
        compute: DerivedCompute,
        method: str,
        output: str = "surface",
        params: Mapping[str, Any] | None = None,
        canonical: str | None = None,
        applies_to: tuple[str, ...] = (),
    ) -> DerivedProduct:
        plugin, _origin = self._loading

        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise PluginError(
                f"R1: product name {name!r} is not usable. A name becomes a URL "
                f"path segment, so it must match {_NAME_RE.pattern} "
                f"(letters, digits, underscore; starts with a letter)."
            )
        if not isinstance(label, str) or not label.strip():
            raise PluginError(
                f"R2: product {name!r} has no label. The label is what a "
                f"forecaster reads in the variable selector."
            )
        if not isinstance(units, str) or not units.strip():
            raise PluginError(
                f"R3: product {name!r} has no units. A number without a unit is "
                f"not shippable -- use '1' for a dimensionless index."
            )
        if not isinstance(requires, Mapping) or not requires:
            raise PluginError(
                f"R4: product {name!r} must declare at least one required "
                f"variable, as {{'TEMP': 'degC'}}. Got {requires!r}."
            )
        for var, want in requires.items():
            if not isinstance(var, str) or not var:
                raise PluginError(f"R4: product {name!r} has a non-string required variable {var!r}")
            if want is not None and not isinstance(want, str):
                raise PluginError(
                    f"R4: product {name!r} declares required units {want!r} for "
                    f"{var!r}; use a unit string, or None to skip the check."
                )
        _check_arity(compute, what=f"R5: product {name!r} compute")
        if output not in _OUTPUTS:
            raise PluginError(
                f"R6: product {name!r} declares output {output!r}; expected one "
                f"of {sorted(_OUTPUTS)}. 'surface' returns (lat, lon), 'column' "
                f"returns (depth, lat, lon)."
            )
        if not isinstance(method, str) or not method.strip():
            raise PluginError(
                f"R7: product {name!r} has no method string. It is echoed as "
                f"provenance on every response, so it cannot be optional -- "
                f"state in one sentence how the number is produced."
            )
        if name in self._derived:
            other = self._derived[name]
            raise PluginError(
                f"R8: product name {name!r} is already registered by plugin "
                f"{other.plugin!r}; plugin {plugin!r} tried to register it "
                f"again. Rename one of them -- silently overwriting would mean "
                f"the selector and the numbers disagree."
            )

        product = DerivedProduct(
            name=name,
            label=label.strip(),
            units=units.strip(),
            requires=dict(requires),
            compute=compute,
            output=output,
            method=method.strip(),
            params=dict(params or {}),
            canonical=canonical,
            applies_to=tuple(applies_to),
            plugin=plugin,
        )
        self._derived[name] = product
        return product

    def register_source_reader(
        self, *, kind: str, open: SourceOpen, doc: str = ""
    ) -> SourceReader:
        plugin, _origin = self._loading

        if not isinstance(kind, str) or not _KIND_RE.match(kind):
            raise PluginError(
                f"R9: reader kind {kind!r} is not usable. A kind is written by "
                f"hand into data/sources.yaml, so it must match "
                f"{_KIND_RE.pattern} (lowercase, digits, underscore)."
            )
        _check_arity(open, what=f"R9: reader for kind {kind!r} open")
        if kind in self._readers:
            other = self._readers[kind]
            raise PluginError(
                f"R9: kind {kind!r} already has a reader from plugin "
                f"{other.plugin!r}; plugin {plugin!r} tried to register a "
                f"second one. One kind, one reader."
            )

        reader = SourceReader(kind=kind, open=open, doc=doc.strip(), plugin=plugin)
        self._readers[kind] = reader
        return reader

    # -- inspection
    def derived_products(self) -> list[DerivedProduct]:
        return [self._derived[k] for k in sorted(self._derived)]

    def derived(self, name: str) -> DerivedProduct | None:
        return self._derived.get(name)

    def source_readers(self) -> list[SourceReader]:
        return [self._readers[k] for k in sorted(self._readers)]

    def source_reader(self, kind: str) -> SourceReader | None:
        return self._readers.get(kind)

    @property
    def failures(self) -> tuple[PluginFailure, ...]:
        return tuple(self._failures)

    def describe(self) -> dict:
        """Everything a judge (or we, at 3 a.m.) needs to answer "did it load?"."""
        return {
            "plugins": [
                {
                    "name": name,
                    "origin": origin,
                    "derived_products": sorted(
                        p.name for p in self._derived.values() if p.plugin == name
                    ),
                    "source_readers": sorted(
                        r.kind for r in self._readers.values() if r.plugin == name
                    ),
                }
                for name, origin in sorted(self._origins.items())
            ],
            "derived_products": [_product_entry(p) for p in self.derived_products()],
            "source_readers": [
                {"kind": r.kind, "doc": r.doc, "plugin": r.plugin}
                for r in self.source_readers()
            ],
            "failures": [
                {"origin": f.origin, "name": f.name, "error": f.error, "hint": f.hint}
                for f in self._failures
            ],
        }


def _check_arity(fn: Any, *, what: str) -> None:
    if not callable(fn):
        raise PluginError(f"{what} is not callable (got {type(fn).__name__})")
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return  # a C builtin cannot be introspected; trust it rather than refuse
    try:
        # bind() type-checks the call without making it.
        sig.bind(_PROBE)
    except TypeError as exc:
        raise PluginError(
            f"{what} must accept exactly one positional argument, but its "
            f"signature is {sig} ({exc}). Bind extra arguments with "
            f"functools.partial and register the partial."
        ) from None


def _product_entry(p: DerivedProduct) -> dict:
    """The catalog-shaped dict. Same keys the client already reads for a stored
    variable, plus the provenance that makes a computed number defensible."""
    return {
        "name": p.name,
        "label": p.label,
        "units": p.units,
        "canonical": p.canonical,
        "derived": True,
        "derived_from": sorted(p.requires),
        "method": p.method,
        "params": dict(p.params),
        "output": p.output,
        "plugin": p.plugin,
    }


# --- discovery --------------------------------------------------------------

def plugins_dir() -> Path:
    """Where drop-in plugins live.

    Read from the environment on every call rather than through the lru_cached
    Settings, so a test (or a judge at a shell) can point discovery somewhere
    else without cache surgery.
    """
    env = os.environ.get("SAGAR_PLUGINS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "plugins"


def load_plugins(
    *, directory: str | Path | None = None, strict: bool = False
) -> PluginRegistry:
    """Scan the plugin directory (and entry points) once, then cache."""
    target = Path(directory) if directory is not None else plugins_dir()
    return _load_cached(str(target), strict)


def clear_plugin_cache() -> None:
    _load_cached.cache_clear()


def reload_plugins(
    *, directory: str | Path | None = None, strict: bool = False
) -> PluginRegistry:
    """Re-scan from disk. This is the live stage move in PRD section 11 step 6."""
    clear_plugin_cache()
    return load_plugins(directory=directory, strict=strict)


@lru_cache(maxsize=4)
def _load_cached(directory: str, strict: bool) -> PluginRegistry:
    reg = PluginRegistry()
    path = Path(directory)
    if path.is_dir():
        # Sorted so load order is reproducible, which matters for R8 collision
        # messages: the same pair of plugins always names the same offender.
        for candidate in sorted(path.glob("*.py")):
            if candidate.name == "__init__.py" or candidate.name.startswith("_"):
                continue  # a leading underscore is how a plugin is switched off
            _load_file(reg, candidate, strict=strict)
    # A missing directory is not a failure: a deployment with no plugins is the
    # normal case, and P0 must not depend on P2 machinery being present.
    _load_entry_points(reg, strict=strict)
    return reg


def _load_file(reg: PluginRegistry, path: Path, *, strict: bool) -> None:
    origin = f"directory:{path}"
    try:
        module = _import_by_path(path)
        _run_register_hook(reg, module, name=path.stem, origin=origin)
    except Exception as exc:
        if strict:
            raise PluginError(f"{origin}: {type(exc).__name__}: {exc}") from exc
        reg._record_failure(
            origin=origin,
            name=path.stem,
            error=f"{path.name}: {type(exc).__name__}: {exc}",
            hint=f"fix the file or rename it to _{path.name} to disable it ({_DOCS})",
        )


def _import_by_path(path: Path):
    """Load a .py file as its own module, never as part of a package.

    By path, not by package import, so a judge can drop a file into the
    directory with no __init__.py edit; and under a `sagardrishti_plugin_`
    prefix so a plugin called `store.py` cannot shadow `app.store`.
    """
    mod_name = f"sagardrishti_plugin_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise PluginError(f"{path.name} is not importable as a Python module")
    module = importlib.util.module_from_spec(spec)
    # In sys.modules before exec, because dataclasses and pickle look their own
    # module up by name during class creation. Removed again on failure so a
    # half-executed module cannot be handed out by a later reload.
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return module


def _run_register_hook(reg: PluginRegistry, module: Any, *, name: str, origin: str) -> None:
    hook = getattr(module, "register", None)
    if hook is None:
        raise PluginError(
            f"{Path(origin.split(':', 1)[-1]).name} defines no register(registry) "
            f"hook. A plugin must expose exactly one function "
            f"`def register(registry): ...` and call registry.register_* inside "
            f"it ({_DOCS}). Registration is explicit on purpose: nothing here is "
            f"picked up by naming convention."
        )
    if not callable(hook):
        raise PluginError(
            f"{origin}: `register` is {type(hook).__name__}, not a function "
            f"taking one argument ({_DOCS})"
        )
    _check_arity(hook, what=f"{origin}: register")
    reg._begin(name, origin)
    try:
        hook(reg)
    finally:
        reg._end()


def _load_entry_points(reg: PluginRegistry, *, strict: bool) -> None:
    """Second discovery channel, for a plugin shipped as an installed wheel.

    With nothing installed this returns an empty set, touching no network and
    costing nothing -- which is why it can sit in the default offline path.
    """
    try:
        found = list(importlib.metadata.entry_points(group=ENTRY_POINT_GROUP))
    except Exception as exc:  # a broken dist-info must not kill startup
        if strict:
            raise PluginError(f"entry-point scan failed: {type(exc).__name__}: {exc}") from exc
        reg._record_failure(
            origin=f"entry_point:{ENTRY_POINT_GROUP}",
            name=ENTRY_POINT_GROUP,
            error=f"entry-point scan failed: {type(exc).__name__}: {exc}",
        )
        return

    for ep in found:
        origin = f"entry_point:{ep.name}"
        try:
            obj = ep.load()
            if inspect.ismodule(obj):
                _run_register_hook(reg, obj, name=ep.name, origin=origin)
            elif callable(obj):
                _check_arity(obj, what=f"{origin}: register")
                reg._begin(ep.name, origin)
                try:
                    obj(reg)
                finally:
                    reg._end()
            else:
                raise PluginError(
                    f"entry point {ep.name!r} resolves to {type(obj).__name__}; "
                    f"point it at a module exposing register(registry), or at "
                    f"the register function itself ({_DOCS})"
                )
        except Exception as exc:
            if strict:
                raise PluginError(f"{origin}: {type(exc).__name__}: {exc}") from exc
            reg._record_failure(
                origin=origin, name=ep.name, error=f"{type(exc).__name__}: {exc}"
            )


# --- the derived-product extension point, wired to the cube -----------------

def derived_variables(source_id: str, *, registry: PluginRegistry | None = None) -> list[dict]:
    """Catalog entries for every derived product this dataset can actually serve.

    "Can actually serve" is the whole point: /catalog already refuses to
    advertise a source that is registered but not materialized, because a
    selector offering something undrawable is worse than one offering less.
    A derived product is held to the same standard, so a product whose required
    variable is absent is simply not listed.
    """
    from . import store  # lazy: keeps app.plugins importable by store itself

    reg = registry if registry is not None else load_plugins()
    try:
        ds, _ref = store.open_cube(source_id)
    except KeyError:
        return []

    out: list[dict] = []
    for product in reg.derived_products():
        if product.applies_to and source_id not in product.applies_to:
            continue
        if any(var not in ds.data_vars for var in product.requires):
            continue
        if product.name in ds.data_vars:
            # Not merely skipped: a shadowing name means one of two different
            # numbers wins by load order, which is exactly the sort of quiet
            # ambiguity this registry exists to prevent.
            reg._record_failure(
                origin=reg._origins.get(product.plugin, product.plugin),
                name=product.name,
                error=(
                    f"derived product {product.name!r} from plugin "
                    f"{product.plugin!r} shadows a variable in dataset "
                    f"{source_id!r}; it will not be offered. Rename the product."
                ),
            )
            continue
        out.append(_product_entry(product))
    return out


def compute_derived(
    source_id: str,
    name: str,
    ds: xr.Dataset,
    *,
    bbox: tuple[float, float, float, float],
    time: str,
    depth: float | None = None,
    all_depths: bool = False,
    registry: PluginRegistry | None = None,
) -> tuple[Any, dict]:
    """Compute one derived product and return it as a store.FieldSlab.

    Returning the same FieldSlab the stored-variable path returns is deliberate:
    the response body, the NaN-to-null masking and the renderer all stay
    unchanged, so a plugin-registered variable is not a second-class citizen
    with its own half-tested code path.
    """
    from . import store

    reg = registry if registry is not None else load_plugins()
    product = reg.derived(name)
    if product is None:
        raise KeyError(name)
    if product.applies_to and source_id not in product.applies_to:
        raise PluginError(
            f"derived product {name!r} declares applies_to={list(product.applies_to)} "
            f"and does not apply to {source_id!r}"
        )

    missing = [v for v in product.requires if v not in ds.data_vars]
    if missing:
        raise PluginError(
            f"derived product {name!r} needs {missing}, which dataset "
            f"{source_id!r} does not carry (it has "
            f"{', '.join(sorted(ds.data_vars))})"
        )

    # Subset through store.select_field so the validated bbox/time refusals are
    # reused rather than reimplemented -- a derived request that silently
    # accepted an out-of-range time would be a worse lie than a stored one.
    slabs = {}
    for var, want_units in product.requires.items():
        slab = store.select_field(ds, var, bbox=bbox, time=time, all_depths=True)
        if want_units is not None:
            got = cf.canonical_unit(slab.units) or ""
            if got != (cf.canonical_unit(want_units) or ""):
                raise PluginError(
                    f"derived product {name!r} declares {var} in {want_units!r} "
                    f"but {source_id!r} serves it in {slab.units!r}. Refusing to "
                    f"compute: the same arithmetic on the wrong unit gives a "
                    f"wrong number with a plausible magnitude."
                )
        slabs[var] = slab

    ref = next(iter(slabs.values()))
    sub = xr.Dataset(
        {v: (("depth", "lat", "lon"), s.values) for v, s in slabs.items()},
        coords={
            "depth": ("depth", np.asarray(ref.depths, dtype="float64")),
            "lat": ("lat", np.asarray(ref.lats, dtype="float64")),
            "lon": ("lon", np.asarray(ref.lons, dtype="float64")),
        },
    )
    for var, slab in slabs.items():
        sub[var].attrs["units"] = slab.units
    sub["depth"].attrs.update(units="m", positive="down")
    sub.attrs.update(source_id=source_id, time=ref.time)

    try:
        result = product.compute(sub)
    except Exception as exc:
        raise PluginError(
            f"derived product {name!r} (plugin {product.plugin!r}) raised "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    result, notes = _split_compute_result(product, result)
    values = _validate_compute_result(product, result, sub)
    served, depths, out_values = _shape_for_transport(
        product, values, ref, all_depths=all_depths, depth=depth, ds=ds
    )

    prov = {
        "derived": True,
        "source_id": source_id,
        "time": ref.time,
        "units": product.units,
        "derived_from": sorted(product.requires),
        "method": product.method,
        "params": dict(product.params),
        "output": product.output,
        "plugin": product.plugin,
        # For a surface product asked for as a column, the single 0.0 level in
        # `depths` is a TRANSPORT PLACEHOLDER so the volumetric renderer needs
        # no special case. It is not a level the field sits at, and for D26 the
        # values themselves are depths, so reading 0.0 as "the surface" would
        # be exactly backwards. Stated rather than left to be inferred.
        **(
            {"surface_level_is_a_placeholder": True}
            if product.output == "surface" and all_depths
            else {}
        ),
        # The honesty counter. A judge sees 209 of 336 columns rather than a
        # picture that implies the whole box was computed (binding rule 7).
        "n_cells": int(values.size),
        "n_valid": int(np.isfinite(values).sum()),
    }
    if notes:
        # What the product wants to say about THIS run, as distinct from the
        # method, which describes every run. D26 uses it to report how many
        # columns held more than one 26 degC crossing, because in those the
        # single number it serves is a choice between two defensible answers
        # and a reader is entitled to know a choice was made.
        prov["notes"] = notes
    citation = _citation_for(source_id)
    if citation:
        prov["citation"] = citation

    return (
        store.FieldSlab(
            values=out_values,
            lats=ref.lats,
            lons=ref.lons,
            depths=depths,
            depth=served,
            time=ref.time,
            units=product.units,
        ),
        prov,
    )


def _citation_for(source_id: str) -> str:
    """The store's own provenance, or "" -- never a plausible-looking default."""
    from . import store

    ref = store.discover_stores().get(source_id)
    return str(ref.provenance.get("citation", "")) if ref else ""


def compute_values(product: DerivedProduct, ds: xr.Dataset) -> np.ndarray:
    """Run a product's compute and return just its values.

    A convenience for callers that want the field and not the run notes, so
    that `compute` returning `(values, notes)` does not force every caller to
    know about the tuple. The notes-aware path is `compute_derived`, which puts
    them in the response provenance.
    """
    values, _notes = _split_compute_result(product, product.compute(ds))
    return np.asarray(values)


def _split_compute_result(product: DerivedProduct, result: Any) -> tuple[Any, dict]:
    """Allow a compute to return `(values, notes)` as well as bare `values`.

    Why the extension point needed this: `method` and `params` describe what a
    product ALWAYS does, and `n_cells`/`n_valid` are counted generically for
    every product. Neither can say anything specific about the run in hand. D26
    is the case that showed the gap: on 2026-07-10 seven Bay of Bengal columns
    cross 26 degC twice, a genuine subsurface temperature inversion, and D26
    serves the shallowest crossing at about 65 to 71 m where a deepest-crossing
    convention would say about 100 to 110 m. Serving one number and saying
    nothing hides that a choice was made.

    Backward compatible on purpose: a plugin that returns a bare array keeps
    working, and every note is optional. The notes are DATA about the
    computation, so the keys are the plugin's own and nothing here interprets
    them.
    """
    if isinstance(result, tuple):
        if len(result) != 2 or not isinstance(result[1], dict):
            raise PluginError(
                f"C1: product {product.name!r} returned a {len(result)}-tuple; a "
                "compute returns either an array or exactly (array, notes_dict)"
            )
        values, notes = result
        for key in notes:
            if not isinstance(key, str):
                raise PluginError(
                    f"C1: product {product.name!r} returned a notes key of type "
                    f"{type(key).__name__}; notes keys must be strings so they can "
                    "be serialized into the response provenance"
                )
        return values, dict(notes)
    return result, {}


def _validate_compute_result(product: DerivedProduct, result: Any, sub: xr.Dataset) -> np.ndarray:
    name = product.name
    if isinstance(result, xr.DataArray):
        result = result.values
    if not isinstance(result, np.ndarray):
        raise PluginError(
            f"C1: product {name!r} returned {type(result).__name__}; a compute "
            f"must return a numpy array or an xarray.DataArray"
        )
    if not np.issubdtype(result.dtype, np.floating):
        raise PluginError(
            f"C2: product {name!r} returned dtype {result.dtype}; a derived "
            f"product must be floating-point because NaN is how absent data is "
            f"expressed, and an integer array cannot hold it"
        )

    nz, ny, nx = (sub.sizes["depth"], sub.sizes["lat"], sub.sizes["lon"])
    want = (ny, nx) if product.output == "surface" else (nz, ny, nx)
    if result.shape != want:
        raise PluginError(
            f"C3: product {name!r} declares output={product.output!r} so it must "
            f"return shape {want}, but returned {result.shape}"
        )

    values = np.asarray(result, dtype="float64")
    if np.isinf(values).any():
        raise PluginError(
            f"C4: product {name!r} returned +/-inf. Use NaN for a value that "
            f"does not exist; infinity survives JSON encoding as a number and "
            f"would be drawn as one"
        )

    # C5 is the machine-checkable form of binding rule 7. A cell where every
    # level of a required input is missing is land (or below the seabed); a
    # finite answer there was invented, not computed.
    absent = np.zeros((ny, nx), dtype=bool)
    for var in product.requires:
        absent |= ~np.isfinite(np.asarray(sub[var].values, dtype="float64")).any(axis=0)
    mask = absent if product.output == "surface" else np.broadcast_to(absent, (nz, ny, nx))
    if np.isfinite(values[mask]).any():
        n = int(np.isfinite(values[mask]).sum())
        raise PluginError(
            f"C5: product {name!r} returned a finite value in {n} cell(s) where "
            f"every level of its input is missing. Land, fill values and "
            f"QC-rejected levels must stay absent -- return NaN there rather "
            f"than a default"
        )
    return values


def _shape_for_transport(
    product: DerivedProduct,
    values: np.ndarray,
    ref: Any,
    *,
    all_depths: bool,
    depth: float | None,
    ds: xr.Dataset,
) -> tuple[float | None, list[float] | None, np.ndarray]:
    """Fit the result into the same transport shape a stored variable uses."""
    from . import store

    if product.output == "surface":
        # A 2-D diagnostic has no depth axis, and the two cases below differ in
        # a way that matters.
        #
        # ALL-DEPTHS is a TRANSPORT shape. The volumetric client wants a column
        # and gets a one-level array so the renderer needs no special case. The
        # 0.0 is a placeholder index into that array, not a claim about where
        # the field sits, and the response says so with
        # `surface_level_is_a_placeholder`.
        #
        # THE SINGLE SLAB used to return 0.0 as the SERVED DEPTH, and that was
        # a fabricated number. /field/incois_vam_argo/D26 answered
        # `"depth": 0.0` for a field whose own values run from 41 to 96 metres:
        # a reader was being told the slab came from the surface level, when
        # the field describes the whole water column and its values ARE depths.
        # There is no depth to report, so None is reported.
        if all_depths:
            return None, [0.0], values.reshape((1,) + values.shape)
        return None, None, values

    if all_depths:
        return None, list(ref.depths), values
    served = store.nearest_depth(ds, 0.0 if depth is None else float(depth))
    idx = int(np.argmin(np.abs(np.asarray(ref.depths, dtype="float64") - served)))
    return served, None, values[idx]


# --- the source-reader extension point --------------------------------------

def open_source(spec: "SourceSpec", *, registry: PluginRegistry | None = None) -> xr.Dataset:
    """Open a source whose `kind` is handled by a plugin, and hold it to the contract."""
    reg = registry if registry is not None else load_plugins()
    reader = reg.source_reader(spec.kind)
    if reader is None:
        raise PluginError(
            f"source {spec.id!r} has kind {spec.kind!r} but no plugin registered "
            f"a reader for it; drop a reader into services/api/plugins/ "
            f"({_DOCS}). Known kinds: "
            f"{', '.join(r.kind for r in reg.source_readers()) or 'none'}"
        )
    try:
        ds = reader.open(spec)
    except Exception as exc:
        raise PluginError(
            f"reader for kind {spec.kind!r} (plugin {reader.plugin!r}) raised "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    _validate_reader_dataset(ds, spec=spec, reader=reader)
    return ds


def _validate_reader_dataset(ds: Any, *, spec: "SourceSpec", reader: SourceReader) -> None:
    """Check the cf.py output contract, because everything downstream assumes it.

    Each of these fails *silently* if unchecked: a flipped depth axis puts the
    thermocline at the seabed, a missing unit makes the colorbar meaningless,
    an integer array cannot express "no measurement here".
    """
    where = f"reader for kind {spec.kind!r} (plugin {reader.plugin!r})"
    if not isinstance(ds, xr.Dataset):
        raise PluginError(f"D1: {where} returned {type(ds).__name__}, not an xarray.Dataset")
    if not ds.data_vars:
        raise PluginError(f"D2: {where} returned a Dataset with no data variables")

    unknown = sorted(set(map(str, ds.dims)) - _CANONICAL_DIMS)
    if unknown:
        raise PluginError(
            f"D2: {where} returned non-canonical dimension(s) {unknown}. Rename "
            f"them to {sorted(_CANONICAL_DIMS)} (app.cf.normalize_dataset does "
            f"this from the source's `dims:` block) -- the renderer must never "
            f"guess which axis is depth"
        )

    if "depth" in ds.coords:
        z = np.asarray(ds["depth"].values, dtype="float64")
        if z.size > 1 and not np.all(np.diff(z) > 0):
            raise PluginError(
                f"D3: {where} returned a depth axis that is not strictly "
                f"increasing ({z[:4]} ...). Depth is positive down in metres"
            )
        if (z < 0).any():
            raise PluginError(
                f"D3: {where} returned negative depths ({z.min()} m). That is a "
                f"height axis; negate it and set positive='down'"
            )

    for var in ds.data_vars:
        da = ds[var]
        if not np.issubdtype(da.dtype, np.floating):
            raise PluginError(
                f"D4: {where} returned {var!r} as dtype {da.dtype}. Measurements "
                f"must be floating-point so a missing value can be NaN rather "
                f"than a sentinel that renders as data"
            )
        if not str(da.attrs.get("units", "")).strip():
            raise PluginError(
                f"D5: {where} returned {var!r} with no units attribute. A number "
                f"without a unit is not shippable"
            )
