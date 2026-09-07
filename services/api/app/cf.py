"""CF-convention normalization (TRD M1).

Real operational NetCDF is not CF-clean. Every transformation here exists
because a live PS-official source needed it (see docs/adr/0003), and each one
fails *silently* if omitted -- a fill value renders as a -9999 degree ocean, a
flipped depth axis puts the thermocline at the seabed, an unconverted cm/s
current is 100x too fast. So they are tested, not trusted.

The output contract, which everything downstream may assume:

    dims   (time, depth, lat, lon)   -- canonical names, canonical order
    depth  positive down, metres, strictly increasing
    values float32/float64 with NaN for missing -- never a sentinel
    attrs  units set to a CF-valid string
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .registry import SourceSpec

#: Unit strings that are simply *mislabelled* -- the magnitudes are already
#: correct, so these are relabels. "degs" is what INCOIS ERDDAP serves for
#: degrees Celsius (verified 2026-09-07).
UNIT_RELABEL = {
    "degs": "degC",
    "deg_c": "degC",
    "degree_celsius": "degC",
    "degrees_celsius": "degC",
    "celsius": "degC",
    "psu": "1",
    "pss-78": "1",
    "meters": "m",
    "metres": "m",
    "decibar": "dbar",
}

#: Genuine conversions: (from, to) -> (multiply, add). Anything not in here
#: raises rather than silently passing values through unchanged.
UNIT_CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {
    ("cm s-1", "m s-1"): (0.01, 0.0),
    ("cm/s", "m s-1"): (0.01, 0.0),
    ("cm/sec", "m s-1"): (0.01, 0.0),
    ("m s-1", "cm s-1"): (100.0, 0.0),
    ("degK", "degC"): (1.0, -273.15),
    ("K", "degC"): (1.0, -273.15),
    ("degC", "degK"): (1.0, 273.15),
    ("mg m-3", "kg m-3"): (1e-6, 0.0),
}

_FILL_ATTRS = ("_FillValue", "missing_value")


def canonical_unit(unit: str | None) -> str | None:
    """Fold a sloppy unit string onto its CF spelling, without rescaling."""
    if unit is None:
        return None
    return UNIT_RELABEL.get(unit.strip().lower(), unit.strip())


def apply_packing(da: xr.DataArray) -> xr.DataArray:
    """Apply scale_factor / add_offset exactly once.

    xarray already unpacks when `mask_and_scale=True`, and moves the packing
    attributes into `.encoding`. So the presence of scale_factor in `.attrs`
    means the array is still raw. Checking that -- rather than unconditionally
    multiplying -- is what makes this idempotent and prevents the classic
    double-scaling bug.
    """
    attrs = da.attrs
    if "scale_factor" not in attrs and "add_offset" not in attrs:
        return da  # already unpacked by xarray

    scale = float(attrs.get("scale_factor", 1.0))
    offset = float(attrs.get("add_offset", 0.0))

    vals = np.asarray(da.values)
    fill = next((attrs[k] for k in _FILL_ATTRS if k in attrs), None)
    mask = np.isclose(vals, fill) if fill is not None else None

    out = vals.astype("float64") * scale + offset
    if mask is not None:
        out[mask] = np.nan

    keep = {k: v for k, v in attrs.items() if k not in ("scale_factor", "add_offset", *_FILL_ATTRS)}
    return xr.DataArray(out, coords=da.coords, dims=da.dims, name=da.name, attrs=keep)


def _mask_fills(da: xr.DataArray, override: dict) -> xr.DataArray:
    """Replace every declared sentinel with NaN.

    Candidates are gathered from the override, the variable attributes and the
    encoding, because sources disagree about where they put it -- and one file
    can carry two conventions (-9999.0 and -1.0E34 both appear across INCOIS
    ERDDAP datasets).
    """
    candidates: list[float] = []
    for src in (override, da.attrs, da.encoding):
        for key in _FILL_ATTRS:
            if key in src and src[key] is not None:
                try:
                    candidates.append(float(src[key]))
                except (TypeError, ValueError):
                    continue

    if not candidates:
        return da

    vals = np.asarray(da.values).astype("float64")
    mask = np.zeros(vals.shape, dtype=bool)
    for fill in candidates:
        # Sentinels are exact in the file but float32 rounding makes `==`
        # unreliable for magnitudes like 1e34, hence a relative comparison.
        mask |= np.isclose(vals, fill, rtol=1e-6, atol=0.0)
    vals[mask] = np.nan

    attrs = {k: v for k, v in da.attrs.items() if k not in _FILL_ATTRS}
    out = xr.DataArray(vals, coords=da.coords, dims=da.dims, name=da.name, attrs=attrs)
    return out


def _convert(da: xr.DataArray, to_unit: str) -> xr.DataArray:
    frm = canonical_unit(da.attrs.get("units"))
    to = to_unit.strip()
    if frm == to:
        return da
    key = (frm, to)
    if key not in UNIT_CONVERSIONS:
        raise ValueError(
            f"no conversion registered from {frm!r} to {to!r} for variable "
            f"{da.name!r}. Add it to cf.UNIT_CONVERSIONS -- refusing to guess."
        )
    mul, add = UNIT_CONVERSIONS[key]
    out = da * mul + add
    out.attrs = {**da.attrs, "units": to}
    out.name = da.name
    return out


def normalize_dataset(ds: xr.Dataset, spec: SourceSpec) -> xr.Dataset:
    """Bring a raw source dataset onto the contract in this module's docstring."""
    ds = ds.copy()
    ov = spec.cf_overrides

    # 1. Stamp the corrected CF attributes on before anything reads them.
    for name, attrs in ov.items():
        if name in ds.variables:
            for k, v in attrs.items():
                if k in _FILL_ATTRS:
                    continue  # handled by _mask_fills, not stored as an attr
                ds[name].attrs[k] = v

    # 2. Unpack, then mask sentinels. Order matters: an integer fill value must
    #    be recognised before it is multiplied by a scale factor.
    for name in list(ds.data_vars):
        da = apply_packing(ds[name])
        ds[name] = _mask_fills(da, ov.get(name, {}))

    # 3. Canonical dimension names.
    rename = {}
    for canon, src in (
        ("time", spec.dims.time),
        ("depth", spec.dims.depth),
        ("lat", spec.dims.lat),
        ("lon", spec.dims.lon),
    ):
        if src and src in ds.dims and src != canon:
            rename[src] = canon
    if rename:
        ds = ds.rename(rename)

    # 4. The depth axis: positive down, metres, strictly increasing.
    if "depth" in ds.coords:
        depth = ds["depth"]
        positive = str(depth.attrs.get("positive", "down")).lower()
        vals = np.asarray(depth.values, dtype="float64")
        if positive == "up":
            vals = -vals            # height -> depth
        elif (vals < 0).any():
            # No `positive` attribute and negative values: the source is storing
            # height and forgot to say so. Treat the magnitude as depth rather
            # than rendering the column upside down.
            vals = np.abs(vals)
        ds = ds.assign_coords(depth=("depth", vals))
        ds["depth"].attrs.update(
            units="m", positive="down", standard_name="depth", axis="Z",
            long_name=depth.attrs.get("long_name", "depth"),
        )
        ds = ds.sortby("depth")

    # 5. Units: relabel first (typo fix), then convert (arithmetic).
    for var in spec.variables:
        if var.name not in ds.variables:
            continue
        da = ds[var.name]
        declared = ov.get(var.name, {}).get("units", da.attrs.get("units"))
        da.attrs["units"] = canonical_unit(declared) or ""
        if var.convert_to:
            da = _convert(da, var.convert_to)
        ds[var.name] = da

    # 6. Canonical dim order, so the renderer never has to guess an axis.
    want = [d for d in ("time", "depth", "lat", "lon") if d in ds.dims]
    for name in list(ds.data_vars):
        dims = ds[name].dims
        if set(want) == set(dims) and tuple(want) != dims:
            ds[name] = ds[name].transpose(*want)

    ds.attrs["source_id"] = spec.id
    ds.attrs["citation"] = spec.citation
    return ds
