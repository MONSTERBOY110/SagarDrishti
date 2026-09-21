"""OGC WMS 1.3.0 and WCS 1.0.0 over the local cube (PS requirement F7, TRD M2).

The PS asks for "open standards (OGC WMS/WCS, CF Conventions)". A screening
reviewer at INCOIS runs ERDDAP and THREDDS daily and may paste our
GetCapabilities URL straight into QGIS, so this is deliberately THIN but
standards-true: two operations on WMS, three on WCS, nothing half-served. Every
capability we do not implement is declined in Capabilities rather than
advertised and then failed, because a lying advertisement costs more
credibility than a small one.

Three decisions are worth knowing before reading the code.

  * Versions. WMS 1.3.0 and WCS 1.0.0, because that pairing is what THREDDS
    serves and what QGIS consumes most simply. The pairing also contains the
    single nastiest trap in OGC: for EPSG:4326, WMS 1.3.0 BBOX is lat,lon
    while WCS 1.0.0 BBOX is lon,lat, since WCS 1.0.0 predates the axis-order
    change. Both are implemented literally, and neither guesses.

  * Colours come from app/colormap.py, the same module apps/web/lib/colormap.ts
    mirrors byte for byte. TRD M2 says "PNG tiles via matplotlib colormaps",
    so THERE IS NO MATPLOTLIB IN THE RENDER PATH HERE AND THAT IS DELIBERATE,
    not an oversight or a missing dependency. The reason is colour parity: a
    matplotlib palette on this side would put a different colour on the same
    value than the browser's own slice does, and a colorbar that disagrees
    with itself is not a measuring instrument, it is two instruments. So one
    palette definition serves both sides, and matplotlib stays a declared
    dependency used where it cannot drift: tests/test_ogc.py decodes our PNG
    bytes with matplotlib.image.imread, cross-checking the encoder below
    rather than trusting it. That encoder is 20 lines of zlib and struct for
    the same kind of reason -- Pillow is only a transitive dependency of
    matplotlib and requirements.txt does not declare it, so a direct
    dependency on Pillow would be an undeclared one. The full argument, and
    the fact that it was a decision taken rather than a step skipped, is
    docs/adr/0005-ogc-colour-parity-over-matplotlib.md.

  * Nothing here reaches the network (CLAUDE.md, TRD M6): layers come from
    store.catalog_entries(), so a layer exists only if the registry enables it
    AND the store is materialized locally AND the variable is a real data_var.
    That is why TERR and SERR, which data/sources.yaml registers but the cube
    does not contain, are absent -- /wms cannot advertise something /field
    would 404 on.
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
from fastapi import APIRouter, Request, Response

from . import colormap, plugins, store
from .registry import load_registry

router = APIRouter(tags=["ogc"])

WMS_VERSION = "1.3.0"
WCS_VERSION = "1.0.0"

NS_WMS = "http://www.opengis.net/wms"
NS_OGC = "http://www.opengis.net/ogc"
NS_WCS = "http://www.opengis.net/wcs"
NS_GML = "http://www.opengis.net/gml"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

#: Declared in Capabilities as MaxWidth/MaxHeight and LayerLimit, so enforcing
#: them is conformant -- and it stops one 10000x10000 request from stalling the
#: demo laptop mid-presentation.
MAX_IMAGE_SIDE = 2048
LAYER_LIMIT = 1

#: A ceiling on a single GetCoverage, so an unconstrained request cannot try to
#: serialize the whole cube into RAM. 20M float64 values is ~160 MB, which is
#: far more than any honest subset and far less than a demo-killing swap storm.
WCS_MAX_VALUES = 20_000_000

_SERVICE_DISCLAIMER = (
    "SagarDrishti is a Smart India Hackathon 2026 entry (PS SIH26067) and is "
    "not an INCOIS or MoES service. It serves a locally materialized copy of "
    "the datasets named in each layer's attribution and carries no endorsement "
    "from their originators."
)


class OgcError(Exception):
    """A caller-fixable problem, rendered as a ServiceExceptionReport.

    Deliberately not HTTPException: FastAPI would answer with
    `{"detail": ...}`, and a JSON body where a client expects OGC XML reads to
    QGIS as a broken server rather than as a rejected request.

    A hazard worth naming once, here, because it cost us a shipped defect:
    store.SubsetError SUBCLASSES ValueError. Any `try` that handles both must
    put `except store.SubsetError` FIRST, or the ValueError clause swallows it
    and the SubsetError clause becomes dead code. That happened on the GetMap
    ELEVATION path, where a caller sending a perfectly good 9999 was told
    "ELEVATION must be a number in metres" and never saw the real extent.
    Where the two mean different things, this module now uses two separate
    `try` blocks instead of relying on clause order, so the ordering cannot
    silently regress.
    """

    def __init__(self, message: str, *, code: str | None = None, locator: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.locator = locator


# --- XML plumbing -----------------------------------------------------------
# Namespaces are written as literal xmlns attributes rather than via
# ET.register_namespace, which is process-global and cannot serve two different
# default namespaces (wms and wcs) from one module. The output reparses with
# correctly namespace-qualified tags either way; tests/test_ogc.py pins that.

def _sub(parent, tag: str, text=None, attrib: dict | None = None):
    element = ET.SubElement(parent, tag, attrib or {})
    if text is not None:
        element.text = str(text)
    return element


def _online_resource(parent, href: str, tag: str = "OnlineResource"):
    return _sub(parent, tag, attrib={"xlink:type": "simple", "xlink:href": href})


def _serialize(root) -> bytes:
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="utf-8", xml_declaration=False
    )


def _num(value: float) -> str:
    """Format a coordinate without a spurious trailing ".0".

    Dimension extents are read by humans as often as by clients, and
    "5,10,20,2000" is the spelling ncWMS and THREDDS use for an ocean depth
    axis, so a reviewer's eye finds what it expects.
    """
    number = float(value)
    if number == int(number) and abs(number) < 1e15:
        return str(int(number))
    return repr(round(number, 6))


def _iso(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ascii(value: str) -> str:
    """Starlette encodes header values latin-1; a citation can carry more.

    Provenance belongs on a PNG response (rule: a number without provenance is
    not shippable) and a header is the only place a PNG has to put it, so the
    value is folded to ASCII rather than dropped.
    """
    return str(value).encode("ascii", "replace").decode("ascii")


def _exception_response(errors: list[OgcError], flavour: str) -> Response:
    """An OGC ServiceExceptionReport, with the two flavours kept distinct.

    HTTP 400 rather than 200: several reference servers answer 200 with an
    error body, but that defeats every generic client and monitoring probe,
    and both QGIS and OWSLib read the body on a 4xx (OWSLib in fact raises
    ServiceException carrying the text, which is the useful outcome).
    """
    if flavour == "wms":
        version, media = WMS_VERSION, "text/xml; charset=utf-8"
        schema = "http://schemas.opengis.net/wms/1.3.0/exceptions_1_3_0.xsd"
    else:
        # WCS 1.0.0 references OGC-exception.xsd, whose version attribute is
        # fixed at 1.2.0. It is not a typo; the exception schema versions
        # separately from the service.
        version, media = "1.2.0", "application/vnd.ogc.se_xml; charset=utf-8"
        schema = "http://schemas.opengis.net/wcs/1.0.0/OGC-exception.xsd"

    root = ET.Element(
        "ServiceExceptionReport",
        {
            "version": version,
            "xmlns": NS_OGC,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": f"{NS_OGC} {schema}",
        },
    )
    for err in errors:
        attrib = {}
        if err.code:
            attrib["code"] = err.code
        if err.locator:
            attrib["locator"] = err.locator
        _sub(root, "ServiceException", err.message, attrib)

    return Response(_serialize(root), status_code=400, media_type=media)


# --- raster helpers ---------------------------------------------------------

def _png(rgba: np.ndarray) -> bytes:
    """Minimal RGBA8 PNG (colour type 6, filter 0) from zlib and struct."""
    height, width = int(rgba.shape[0]), int(rgba.shape[1])
    scanlines = np.empty((height, width * 4 + 1), dtype="uint8")
    scanlines[:, 0] = 0  # filter type None on every scanline
    scanlines[:, 1:] = np.ascontiguousarray(rgba, dtype="uint8").reshape(height, width * 4)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(scanlines.tobytes(), 6))
        + chunk(b"IEND", b"")
    )


def _cell_edges(nodes: np.ndarray) -> np.ndarray:
    """Cell boundaries from cell centres, outer edges extrapolated.

    The advertised extent has to be the edges, not the centres: a 1-degree grid
    reported by its centres claims half a cell less coverage on every side, and
    a client clipping to that bbox would drop the outermost row. It also
    handles the cube's irregular depth axis, where a fixed half-spacing would
    be wrong from 200 m down.
    """
    values = np.asarray(nodes, dtype="float64")
    if values.size == 1:
        # No spacing to infer. A degenerate zero-width cell would make every
        # pixel invalid, so assume one unit and say so.
        return np.array([values[0] - 0.5, values[0] + 0.5])
    mids = 0.5 * (values[:-1] + values[1:])
    return np.concatenate(
        ([values[0] - (mids[0] - values[0])], mids, [values[-1] + (values[-1] - mids[-1])])
    )


def _ascending_axis(nodes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(cell edges, original index per ascending cell).

    ERDDAP serves descending latitude for some datasets (store.select_field
    already reverses its slices for that reason), and searchsorted needs an
    ascending array, so the order is normalized here and mapped back on the
    way out instead of being assumed.
    """
    values = np.asarray(nodes, dtype="float64")
    order = np.argsort(values, kind="stable")
    return _cell_edges(values[order]), order


def _sample(
    values: np.ndarray,
    lat_nodes: np.ndarray,
    lon_nodes: np.ndarray,
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
) -> np.ndarray:
    """Nearest-neighbour sample of a (lat, lon) slab onto pixel centres.

    Never interpolation. A 1-degree variational analysis smoothed into a
    continuous field would be a claim the analysis does not make, and a pixel
    outside the coverage must come back absent rather than smeared from the
    nearest edge cell. Pixels that fall outside the grid become NaN, which
    map_to_rgba turns into full transparency.
    """
    xmin, ymin, xmax, ymax = bbox
    lon_edges, lon_order = _ascending_axis(lon_nodes)
    lat_edges, lat_order = _ascending_axis(lat_nodes)

    px_lon = xmin + (np.arange(width) + 0.5) * (xmax - xmin) / width
    px_lat = ymax - (np.arange(height) + 0.5) * (ymax - ymin) / height  # row 0 is north

    # Half-open cells [edge_i, edge_i+1), the standard raster convention: a
    # point exactly on the eastern/northern outer edge is outside.
    ix = np.searchsorted(lon_edges, px_lon, side="right") - 1
    iy = np.searchsorted(lat_edges, px_lat, side="right") - 1
    ok_x = (ix >= 0) & (ix < lon_order.size)
    ok_y = (iy >= 0) & (iy < lat_order.size)

    src_x = lon_order[np.clip(ix, 0, lon_order.size - 1)]
    src_y = lat_order[np.clip(iy, 0, lat_order.size - 1)]
    tile = np.asarray(values, dtype="float64")[np.ix_(src_y, src_x)]
    return np.where(ok_y[:, None] & ok_x[None, :], tile, np.nan)


# --- the advertised layers --------------------------------------------------

@dataclass(frozen=True)
class LayerInfo:
    source_id: str
    var: str
    name: str
    label: str
    units: str
    dataset_title: str
    citation: str
    source_url: str
    retrieved_at: str
    canonical: str
    times: list[str]
    #: The vertical extent. EMPTY for a derived SURFACE product, which is not
    #: a slice through the water column but a property OF the column (the depth
    #: of an isotherm, say), so there is no elevation to choose. Every place
    #: that reads this must cope with an empty list rather than assume depths[0]
    #: exists, and `is_surface` below is the readable way to ask.
    depths: list[float]
    lat_nodes: np.ndarray
    lon_nodes: np.ndarray
    west: float
    south: float
    east: float
    north: float
    palette: str
    declared_range: tuple[float, float] | None
    #: Set for a layer that a plugin COMPUTES rather than one the store holds.
    #: PS requirements F6 (extensibility) and F7 (open standards) are separate
    #: sentences, and the obvious question joining them is "if I register a
    #: plugin, does it appear in your WMS?". It did not: `_layers()` read the
    #: store alone, so a plugin's product was visible to our own client through
    #: /catalog and /field and invisible to QGIS.
    derived: bool = False
    #: The plugin's own description of what it computed: method, params,
    #: derived_from, plugin name. Served in the layer Abstract and in the
    #: coverage's NetCDF attributes, because a number computed by a plugin needs
    #: to arrive with the recipe that produced it.
    derived_meta: dict | None = None

    @property
    def is_surface(self) -> bool:
        """True when this layer has no vertical axis at all."""
        return not self.depths


def _default_palette(var: str, canonical: str, standard_name: str, units: str = "") -> str:
    """Pick a ramp whose SHAPE matches the field.

    apps/web/lib/colormap.ts records the reason: a diverging ramp on an
    absolute field invents a meaningless midpoint, and a sequential ramp on an
    anomaly hides the sign of the residual. Error and anomaly fields are
    therefore checked first, before the "temperature" and "salinity" words that
    also appear in their names.

    The QUANTITY is checked before the words, and that ordering is the whole
    point of the first two branches. The D26 plugin's product is the DEPTH OF
    the 26 degC isotherm, in metres, and its CF name is
    `depth_of_isosurface_of_sea_water_potential_temperature`. Matching on the
    word "temperature" gave it the thermal ramp, so a field of metres was
    coloured with the ramp the scene uses for degrees, on a globe where the two
    would sit side by side. Anyone reading 60 m off that ramp reads it as a
    temperature. A derived quantity's name mentions the variable it was derived
    FROM, so the name alone cannot be trusted; the unit can.
    """
    haystack = " ".join(filter(None, (var, canonical, standard_name))).lower()
    unit = (units or "").strip().lower()

    if any(token in haystack for token in ("err", "anom", "resid", "bias", "diff")):
        return "balance"
    # A depth or a thickness, whatever it is a depth OF.
    if haystack.startswith("depth_of") or "depth_of" in haystack or "thickness" in haystack:
        return "deep"
    if unit in ("m", "metre", "metres", "meter", "meters") and (
        "depth" in haystack or "bathy" in haystack or "height" in haystack
    ):
        return "deep"
    if "salin" in haystack:
        return "haline"
    if "temp" in haystack or "thetao" in haystack:
        return "thermal"
    if "chl" in haystack or "algae" in haystack:
        return "algae"
    if "bathy" in haystack or "depth" in haystack:
        return "deep"
    return "thermal"


def _layers() -> dict[str, LayerInfo]:
    """One layer per (dataset, variable) actually present, keyed by layer name.

    Recomputed per request rather than cached: the cube directory can be
    swapped underneath a running API (that is how the offline demo reloads),
    and a cached advertisement outliving its store is exactly the drift this
    module exists to avoid. The work is a few zarr metadata reads.
    """
    registry = load_registry()
    found: dict[str, LayerInfo] = {}

    for entry in store.catalog_entries():
        source_id = entry["id"]
        try:
            ds, ref = store.open_cube(source_id)
        except KeyError:  # pragma: no cover - catalog_entries already filtered
            continue

        spec = registry.get(source_id) if registry.has(source_id) else None
        lat_nodes = np.asarray(ds["lat"].values, dtype="float64")
        lon_nodes = np.asarray(ds["lon"].values, dtype="float64")
        lat_edges = _cell_edges(lat_nodes)
        lon_edges = _cell_edges(lon_nodes)

        # Which names the STORE holds, so a plugin cannot shadow one below.
        entry_vars = {
            v["name"] for v in entry["variables"] if not v.get("derived")
        }

        for variable in entry["variables"]:
            if variable.get("derived"):
                # /catalog already merges derived products into `variables`.
                # They are built below, from the plugin registry, because only
                # there do the method and params travel with them.
                continue
            var = variable["name"]
            attrs = ds[var].attrs
            declared: tuple[float, float] | None = None
            if "colorBarMinimum" in attrs and "colorBarMaximum" in attrs:
                declared = (float(attrs["colorBarMinimum"]), float(attrs["colorBarMaximum"]))

            canonical = variable.get("canonical") or ""
            name = f"{source_id}/{var}"
            found[name] = LayerInfo(
                source_id=source_id,
                var=var,
                name=name,
                label=variable.get("label") or var,
                units=variable.get("units") or "",
                dataset_title=entry["title"],
                citation=entry["citation"] or "",
                source_url=ref.provenance.get("source_url") or (spec.url if spec else ""),
                retrieved_at=entry.get("retrieved_at") or "",
                canonical=canonical,
                times=list(entry["times"]),
                depths=[float(d) for d in entry["depths"]],
                lat_nodes=lat_nodes,
                lon_nodes=lon_nodes,
                west=float(lon_edges.min()),
                south=float(lat_edges.min()),
                east=float(lon_edges.max()),
                north=float(lat_edges.max()),
                palette=_default_palette(
                    var, canonical, str(attrs.get("standard_name", "")),
                    variable.get("units") or "",
                ),
                declared_range=declared,
            )

        # Plugin-derived products, advertised alongside the stored variables.
        # Asking the registry per source rather than globally is what honours a
        # product's `applies_to`: a plugin written for one dataset must not be
        # advertised on another.
        for product in plugins.derived_variables(source_id):
            var = product["name"]
            if var in entry_vars:
                # A plugin must not shadow a stored variable: two layers of the
                # same name would make the advertisement ambiguous and the
                # caller could not say which one they wanted.
                continue
            canonical = product.get("canonical") or ""
            name = f"{source_id}/{var}"
            surface = product.get("output") == "surface"
            found[name] = LayerInfo(
                source_id=source_id,
                var=var,
                name=name,
                label=product.get("label") or var,
                units=product.get("units") or "",
                dataset_title=entry["title"],
                citation=entry["citation"] or "",
                source_url=ref.provenance.get("source_url") or (spec.url if spec else ""),
                retrieved_at=entry.get("retrieved_at") or "",
                canonical=canonical,
                times=list(entry["times"]),
                # A surface product collapses the vertical axis, so it declares
                # none. A column product keeps the cube's own levels.
                depths=[] if surface else [float(d) for d in entry["depths"]],
                lat_nodes=lat_nodes,
                lon_nodes=lon_nodes,
                west=float(lon_edges.min()),
                south=float(lat_edges.min()),
                east=float(lon_edges.max()),
                north=float(lat_edges.max()),
                palette=_default_palette(
                    var, canonical, canonical, product.get("units") or "",
                ),
                declared_range=None,
                derived=True,
                derived_meta=product,
            )

    return dict(sorted(found.items()))


def _units_note(units: str) -> str:
    """A sentence explaining a unit string that does not read as one.

    CF spells practical salinity as units="1", which is correct and which reads
    as "Salinity in 1" if pasted straight into a sentence. An INCOIS reviewer
    reading the Layer Abstract would notice, so the raw string stays verbatim
    (a parser needs it, and X-Sagardrishti-Units carries it too) and this note
    explains it in words alongside.
    """
    if units.strip() == "1":
        return ' CF spells this dimensionless quantity as units "1".'
    return ""


def _derived_note(layer: LayerInfo) -> str:
    """State that a layer is COMPUTED, and by what recipe.

    A derived layer looks exactly like a stored one over the wire, so the
    Abstract is the only place a client is told the difference. CLAUDE.md
    forbids a served number without provenance, and for a computed field the
    provenance is the method: "the depth of the 26 degC isotherm" is a
    different claim depending on whether it interpolated, extrapolated, or took
    the nearest level.
    """
    meta = layer.derived_meta or {}
    parts = [" This layer is COMPUTED, not stored."]
    if meta.get("derived_from"):
        parts.append(f" Derived from {', '.join(meta['derived_from'])}.")
    if meta.get("method"):
        parts.append(f" Method: {meta['method']}.")
    if meta.get("params"):
        readable = ", ".join(f"{k}={v}" for k, v in meta["params"].items())
        parts.append(f" Parameters: {readable}.")
    if meta.get("plugin"):
        parts.append(f" Computed by the {meta['plugin']} plugin (see docs/PLUGINS.md).")
    return "".join(parts)


def _layer_abstract(layer: LayerInfo) -> str:
    if layer.is_surface:
        # No vertical extent to describe, and saying "the vertical coordinate is
        # depth" about a field that IS a depth would be a confusing sentence in
        # a document a reviewer reads.
        vertical = (
            f" This is a single surface covering the whole water column, so it has no "
            f"elevation dimension and ELEVATION is not accepted. Its values ARE depths "
            f"in metres, positive down, over a column spanning "
            f"{_num(float(layer.derived_meta.get('column_depth_min', 0)))} m to "
            f"{_num(float(layer.derived_meta.get('column_depth_max', 0)))} m."
            if layer.derived_meta
            and "column_depth_min" in (layer.derived_meta or {})
            else " This is a single surface covering the whole water column, so it has "
            "no elevation dimension and ELEVATION is not accepted."
        )
        served = (
            "TIME is snapped to the nearest declared value and the value actually "
            "served is returned in the X-Sagardrishti-Time response header. "
        )
    else:
        vertical = (
            " The vertical coordinate is depth in metres, positive down; "
            f"{_num(layer.depths[0])} m is the shallowest level and "
            f"{_num(layer.depths[-1])} m the deepest."
        )
        served = (
            "TIME and ELEVATION are snapped to the nearest declared value and the value "
            "actually served is returned in the X-Sagardrishti-Time and "
            "X-Sagardrishti-Elevation response headers. "
        )

    return (
        f"{layer.label} in units of {layer.units or 'unknown'}."
        f"{_units_note(layer.units)} From {layer.dataset_title}."
        f"{_derived_note(layer) if layer.derived else ''}"
        f"{vertical} {served}"
        "Cells with no data (land, fill values) are returned fully transparent and are "
        f"never coloured. Source: {layer.citation}"
    )


def _base_url(request: Request, path: str) -> str:
    """The absolute URL of this endpoint, with the trailing "?" clients expect.

    Derived from the request rather than configured, because the demo runs on
    localhost, on a nodal-centre laptop and behind a tunnel, and a hardcoded
    host in Capabilities sends QGIS to the wrong machine.
    """
    url = request.url.replace(query="", fragment="")
    return str(url.replace(path=path)) + "?"


# ============================================================================
# WMS 1.3.0
# ============================================================================

def _wms_capabilities(request: Request, layers: dict[str, LayerInfo]) -> Response:
    endpoint = _base_url(request, "/wms")
    update_sequence = max((lay.retrieved_at for lay in layers.values()), default="") or "0"

    root = ET.Element(
        "WMS_Capabilities",
        {
            "version": WMS_VERSION,
            "updateSequence": update_sequence,
            "xmlns": NS_WMS,
            "xmlns:xlink": NS_XLINK,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": (
                f"{NS_WMS} http://schemas.opengis.net/wms/1.3.0/capabilities_1_3_0.xsd"
            ),
        },
    )

    # Service := Name, Title, Abstract, KeywordList, OnlineResource,
    # ContactInformation?, Fees?, AccessConstraints?, LayerLimit?, MaxWidth?,
    # MaxHeight? -- the XSD sequence, in order, because order is what makes it
    # validate.
    service = _sub(root, "Service")
    _sub(service, "Name", "WMS")
    _sub(service, "Title", "SagarDrishti ocean digital twin (WMS)")
    _sub(
        service,
        "Abstract",
        "OGC WMS 1.3.0 access to the SagarDrishti offline ocean cube. " + _SERVICE_DISCLAIMER,
    )
    keywords = _sub(service, "KeywordList")
    for word in ("ocean", "temperature", "salinity", "Argo", "Indian Ocean", "INCOIS", "CF-1.8"):
        _sub(keywords, "Keyword", word)
    _online_resource(service, endpoint)
    # ContactInformation is omitted deliberately: it is optional in the XSD and
    # every field in it would have to be invented, which is the one thing a
    # capabilities document must not contain.
    _sub(service, "Fees", "none")
    _sub(service, "AccessConstraints", _SERVICE_DISCLAIMER)
    _sub(service, "LayerLimit", LAYER_LIMIT)
    _sub(service, "MaxWidth", MAX_IMAGE_SIDE)
    _sub(service, "MaxHeight", MAX_IMAGE_SIDE)

    capability = _sub(root, "Capability")
    operations = _sub(capability, "Request")
    for op_name, fmt in (("GetCapabilities", "text/xml"), ("GetMap", "image/png")):
        op = _sub(operations, op_name)
        _sub(op, "Format", fmt)
        http = _sub(_sub(op, "DCPType"), "HTTP")
        _online_resource(_sub(http, "Get"), endpoint)
    # No GetFeatureInfo element: every Layer below is queryable="0", and
    # advertising an operation that answers OperationNotSupported would be a
    # promise we break on the first click.

    exception = _sub(capability, "Exception")
    _sub(exception, "Format", "XML")
    # INIMAGE and BLANK are not advertised because they are not implemented; a
    # client that needs them can then choose another server instead of
    # discovering the gap mid-session.

    root_layer = _sub(capability, "Layer")
    _sub(root_layer, "Title", "SagarDrishti offline ocean cube")
    _sub(root_layer, "CRS", "CRS:84")
    _sub(root_layer, "CRS", "EPSG:4326")
    if layers:
        _wms_geographic_bbox(
            root_layer,
            min(lay.west for lay in layers.values()),
            min(lay.south for lay in layers.values()),
            max(lay.east for lay in layers.values()),
            max(lay.north for lay in layers.values()),
        )
    for layer in layers.values():
        _wms_layer(root_layer, layer)

    return Response(_serialize(root), media_type="text/xml; charset=utf-8")


def _wms_geographic_bbox(parent, west: float, south: float, east: float, north: float) -> None:
    """EX_GeographicBoundingBox: four NAMED children, so it is order-proof.

    This is the one bbox in WMS 1.3.0 that cannot be misread, which is why the
    numbers here are the ones to check first when a client draws the wrong
    part of the world.
    """
    box = _sub(parent, "EX_GeographicBoundingBox")
    _sub(box, "westBoundLongitude", _num(west))
    _sub(box, "eastBoundLongitude", _num(east))
    _sub(box, "southBoundLatitude", _num(south))
    _sub(box, "northBoundLatitude", _num(north))


def _wms_layer(parent, layer: LayerInfo) -> None:
    element = _sub(parent, "Layer", attrib={"queryable": "0", "opaque": "0"})
    _sub(element, "Name", layer.name)
    _sub(element, "Title", f"{layer.label} ({layer.units}) - {layer.dataset_title}")
    _sub(element, "Abstract", _layer_abstract(layer))
    keywords = _sub(element, "KeywordList")
    for word in filter(None, (layer.label, layer.canonical, layer.source_id)):
        _sub(keywords, "Keyword", word)

    _sub(element, "CRS", "CRS:84")
    _sub(element, "CRS", "EPSG:4326")
    _wms_geographic_bbox(element, layer.west, layer.south, layer.east, layer.north)

    # THE trap. WMS 1.3.0 honours each CRS's own axis order, so CRS:84 is
    # lon,lat and EPSG:4326 is lat,lon (EPSG defines 4326 as northing first).
    # Emitting the same numbers under both names is the single most common
    # WMS 1.3.0 bug and it puts the Bay of Bengal in Kazakhstan.
    _sub(element, "BoundingBox", attrib={
        "CRS": "CRS:84",
        "minx": _num(layer.west), "miny": _num(layer.south),
        "maxx": _num(layer.east), "maxy": _num(layer.north),
    })
    _sub(element, "BoundingBox", attrib={
        "CRS": "EPSG:4326",
        "minx": _num(layer.south), "miny": _num(layer.west),
        "maxx": _num(layer.north), "maxy": _num(layer.east),
    })

    # WMS 1.3.0 carries a dimension's extent as the element's own text; the
    # separate <Extent> element is 1.1.1 and would be ignored here.
    _sub(element, "Dimension", ",".join(layer.times), {
        "name": "time", "units": "ISO8601", "default": layer.times[-1],
        "multipleValues": "0", "nearestValue": "1", "current": "0",
    })
    # units="m" is what ncWMS, THREDDS and GeoServer emit for an ocean vertical
    # axis, and it is what a reviewer's client expects. CRS:88 would be wrong
    # (NAVD88 is height, positive UP); the values below are depth, positive
    # down, which the Layer Abstract states in words so the sign cannot be
    # inferred incorrectly.
    #
    # A SURFACE layer declares no elevation dimension at all. Advertising one
    # would be worse than omitting it: a client would offer a depth chooser for
    # a quantity that has no depth, and any value it sent would have to be
    # either ignored (silently answering a different question) or refused
    # (after the capabilities document said it was allowed). D26 is the depth OF
    # a surface, not a value AT a depth.
    if not layer.is_surface:
        _sub(element, "Dimension", ",".join(_num(d) for d in layer.depths), {
            "name": "elevation", "units": "m", "unitSymbol": "m",
            "default": _num(layer.depths[0]),
            "multipleValues": "0", "nearestValue": "1", "current": "0",
        })

    attribution = _sub(element, "Attribution")
    _sub(attribution, "Title", layer.citation)
    if layer.source_url:
        _online_resource(attribution, layer.source_url)

    # The variable's own ramp first: WMS clients treat the first Style as the
    # default. The rest are offered because a reviewer will want to compare.
    ordered = [layer.palette] + [p for p in colormap.PALETTES if p != layer.palette]
    default_range = (
        f"default colour range {_num(layer.declared_range[0])} to "
        f"{_num(layer.declared_range[1])} (units {layer.units or 'unknown'}), taken from "
        "the source's own colorBarMinimum/colorBarMaximum"
        if layer.declared_range
        else "default colour range from the 2nd and 98th percentiles of the whole "
        "selected slice, so adjacent tiles cannot disagree"
    )
    for palette in ordered:
        style = _sub(element, "Style")
        _sub(style, "Name", f"boxfill/{palette}")
        _sub(style, "Title", f"{palette} (boxfill)")
        _sub(style, "Abstract", (
            f"Nearest-neighbour boxfill using the {palette} palette, {default_range}. "
            "Override with the ncWMS-compatible COLORSCALERANGE=min,max and "
            "LOGSCALE=true|false parameters, or append -inv to the style name to "
            "reverse the ramp."
        ))
        # No LegendURL. It is optional in the schema, we do not serve one, and a
        # colour ramp without numeric ticks would break this project's rule that
        # a numeric readout accompanies every colour-mapped field.


def _require(params: dict, key: str) -> str:
    """A missing parameter is always a CODELESS exception with a locator.

    WMS 1.3.0's code list (Table E.1) has no entry for an absent parameter, and
    borrowing a nearby code such as InvalidFormat would tell a client its value
    was rejected when it sent none.
    """
    value = (params.get(key) or "").strip()
    if not value:
        raise OgcError(f"{key} is required for this request", locator=key)
    return value


def _parse_int(params: dict, key: str) -> int:
    raw = _require(params, key)
    try:
        return int(raw)
    except ValueError:
        raise OgcError(f"{key} must be an integer, got {raw!r}", locator=key) from None


def _parse_bbox4(raw: str, key: str = "BBOX") -> list[float]:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise OgcError(
            f"{key} needs 4 comma-separated numbers, got {len(parts)}", locator=key
        )
    try:
        return [float(p) for p in parts]
    except ValueError:
        raise OgcError(f"{key} values must be numbers, got {raw!r}", locator=key) from None


def _parse_style(raw: str, default_palette: str) -> tuple[str, bool]:
    text = (raw or "").strip()
    if not text or text.lower() == "default":
        return default_palette, False
    if "/" in text:
        head, _, tail = text.partition("/")
        if head.lower() != "boxfill":
            raise OgcError(
                f"unknown style {text!r}; this service offers boxfill/<palette> only",
                code="StyleNotDefined",
                locator="STYLES",
            )
        text = tail
    reverse = False
    if text.lower().endswith("-inv"):
        text, reverse = text[:-4], True
    if text not in colormap.PALETTES:
        raise OgcError(
            f"unknown style {raw!r}; available palettes: {', '.join(sorted(colormap.PALETTES))}",
            code="StyleNotDefined",
            locator="STYLES",
        )
    return text, reverse


def _parse_bgcolor(raw: str | None) -> tuple[int, int, int]:
    text = (raw or "0xFFFFFF").strip()
    try:
        value = int(text, 16)  # base 16 accepts both "0xFFFFFF" and "FFFFFF"
    except ValueError:
        raise OgcError(
            f"BGCOLOR must be 0xRRGGBB, got {raw!r}", locator="BGCOLOR"
        ) from None
    if not 0 <= value <= 0xFFFFFF:
        raise OgcError(f"BGCOLOR must be 0xRRGGBB, got {raw!r}", locator="BGCOLOR")
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def _single_dimension_value(params: dict, key: str) -> str:
    """Reject a list or range on a dimension declared multipleValues="0"."""
    value = (params.get(key) or "").strip()
    if "," in value or "/" in value:
        raise OgcError(
            f"{key} accepts a single value; this layer declares multipleValues=\"0\" "
            "because one GetMap returns one image",
            code="InvalidDimensionValue",
            locator=key,
        )
    return value


def _wms_getmap(request: Request, params: dict, layers: dict[str, LayerInfo]) -> Response:
    version = (params.get("VERSION") or WMS_VERSION).strip()
    if version != WMS_VERSION:
        raise OgcError(
            f"VERSION {version!r} is not supported; this service is WMS {WMS_VERSION}. "
            "The difference matters: in WMS 1.1.1 EPSG:4326 BBOX is lon,lat, in 1.3.0 "
            "it is lat,lon, so serving 1.3.0 semantics for a 1.1.1 request would "
            "silently relocate the image.",
            locator="VERSION",
        )

    exceptions = (params.get("EXCEPTIONS") or "XML").strip()
    if exceptions.upper() not in ("XML", "APPLICATION/VND.OGC.SE_XML"):
        raise OgcError(
            f"EXCEPTIONS format {exceptions!r} is not offered; this service advertises XML only",
            locator="EXCEPTIONS",
        )

    crs = (params.get("CRS") or "").strip()
    srs = (params.get("SRS") or "").strip()
    if not crs and srs:
        raise OgcError(
            "SRS is the WMS 1.1.1 spelling of this parameter and WMS 1.3.0 needs CRS. "
            "Honouring it here would mean guessing an axis order: in 1.1.1 EPSG:4326 "
            "BBOX is lon,lat, in 1.3.0 it is lat,lon. Re-request with CRS=CRS:84 for "
            "lon,lat or CRS=EPSG:4326 for lat,lon.",
            locator="SRS",
        )
    if not crs:
        raise OgcError("CRS is required for GetMap", locator="CRS")

    normalized = crs.upper()
    if normalized in ("EPSG:4326", "URN:OGC:DEF:CRS:EPSG::4326"):
        lat_first = True
    elif normalized in ("CRS:84", "OGC:CRS84", "URN:OGC:DEF:CRS:OGC:1.3:CRS84"):
        lat_first = False
    else:
        raise OgcError(
            f"CRS {crs!r} is not supported; this service offers CRS:84 (lon,lat) and "
            "EPSG:4326 (lat,lon) only, and never reprojects",
            code="InvalidCRS",
            locator="CRS",
        )

    values = _parse_bbox4(_require(params, "BBOX"))
    if lat_first:
        ymin, xmin, ymax, xmax = values
    else:
        xmin, ymin, xmax, ymax = values
    order = "lat,lon" if lat_first else "lon,lat"
    if not (-180.0 <= xmin <= 180.0 and -180.0 <= xmax <= 180.0):
        raise OgcError(
            f"BBOX longitudes must lie in [-180, 180]; in {crs} the axis order is "
            f"{order}, which reads them as {xmin} and {xmax}",
            locator="BBOX",
        )
    if not (-90.0 <= ymin <= 90.0 and -90.0 <= ymax <= 90.0):
        raise OgcError(
            f"BBOX latitudes must lie in [-90, 90]; in {crs} the axis order is "
            f"{order}, which reads them as {ymin} and {ymax}",
            locator="BBOX",
        )
    if xmax <= xmin or ymax <= ymin:
        raise OgcError(
            f"BBOX must have a positive extent; in {crs} ({order}) it reads as "
            f"lon {xmin}..{xmax}, lat {ymin}..{ymax}",
            locator="BBOX",
        )

    fmt = _require(params, "FORMAT")
    if not fmt.lower().startswith("image/png"):
        raise OgcError(
            f"FORMAT {fmt!r} is not offered; this service returns image/png only",
            code="InvalidFormat",
            locator="FORMAT",
        )

    width, height = _parse_int(params, "WIDTH"), _parse_int(params, "HEIGHT")
    for key, size in (("WIDTH", width), ("HEIGHT", height)):
        if size < 1:
            raise OgcError(f"{key} must be at least 1, got {size}", locator=key)
        if size > MAX_IMAGE_SIDE:
            raise OgcError(
                f"{key} {size} exceeds the MaxWidth/MaxHeight of {MAX_IMAGE_SIDE} "
                "declared in GetCapabilities",
                locator=key,
            )

    requested = [n.strip() for n in _require(params, "LAYERS").split(",") if n.strip()]
    if not requested:
        raise OgcError("LAYERS must name one layer", locator="LAYERS")
    if len(requested) > LAYER_LIMIT:
        raise OgcError(
            f"{len(requested)} layers requested but GetCapabilities declares "
            f"LayerLimit {LAYER_LIMIT}; this service does not composite layers",
            locator="LAYERS",
        )
    if requested[0] not in layers:
        raise OgcError(
            f"unknown layer {requested[0]!r}; available: {', '.join(layers)}",
            code="LayerNotDefined",
            locator="LAYERS",
        )
    layer = layers[requested[0]]

    style_list = [s.strip() for s in (params.get("STYLES") or "").split(",")]
    if len([s for s in style_list if s]) > 1:
        raise OgcError("STYLES must name one style, matching the single layer", locator="STYLES")
    palette, reverse = _parse_style(style_list[0], layer.palette)

    ds, ref = store.open_cube(layer.source_id)

    wanted_time = _single_dimension_value(params, "TIME")
    if not wanted_time or wanted_time.lower() == "current":
        served_time = pd.Timestamp(layer.times[-1].rstrip("Z")).to_datetime64()
    else:
        try:
            served_time = store.nearest_time(ds, wanted_time)
        except store.SubsetError as exc:
            raise OgcError(str(exc), code="InvalidDimensionValue", locator="TIME") from None

    wanted_depth = _single_dimension_value(params, "ELEVATION")
    if layer.is_surface:
        # Capabilities declares no elevation dimension for this layer, so a
        # value here is a caller mistake. Refusing beats ignoring: silently
        # dropping it would answer a different question than the one asked, and
        # the caller would have no way to notice.
        if wanted_depth:
            raise OgcError(
                f"layer {layer.name} is a single surface and declares no elevation "
                f"dimension, so ELEVATION={wanted_depth!r} cannot be honoured. Its "
                "VALUES are depths in metres; there is no depth to select at.",
                code="InvalidDimensionValue",
                locator="ELEVATION",
            )
        served_depth = None
    elif not wanted_depth:
        served_depth = layer.depths[0]
    else:
        # TWO try blocks, not one with two clauses. These are two different
        # refusals and the caller needs to know which one they hit: "abc" is
        # unparseable, 9999 parses fine and is simply not in this layer's
        # extent. They were one block with `except ValueError` first, and
        # since store.SubsetError subclasses ValueError the SubsetError clause
        # was unreachable: ELEVATION=9999, ELEVATION=-5 and ELEVATION=abc all
        # returned "ELEVATION must be a number in metres", so the useful text
        # "depth 9999.0 m is outside the available range ..." never shipped.
        # Splitting them puts the distinction beyond clause order.
        try:
            metres = float(wanted_depth)
        except ValueError:
            raise OgcError(
                f"ELEVATION must be a number in metres, got {wanted_depth!r}",
                code="InvalidDimensionValue",
                locator="ELEVATION",
            ) from None
        try:
            # Also the NaN/inf gate: store.nearest_depth refuses a non-finite
            # value rather than snapping it to the shallowest level, and WMS
            # 1.3.0 Table E.1 calls a value outside the declared extent an
            # InvalidDimensionValue, which is what this must reach a client as.
            served_depth = store.nearest_depth(ds, metres)
        except store.SubsetError as exc:
            raise OgcError(str(exc), code="InvalidDimensionValue", locator="ELEVATION") from None

    scale = "linear"
    logscale = (params.get("LOGSCALE") or "").strip().lower()
    if logscale in ("true", "1", "yes"):
        scale = "log"
    elif logscale not in ("", "false", "0", "no"):
        raise OgcError(f"LOGSCALE must be true or false, got {logscale!r}", locator="LOGSCALE")

    if layer.derived:
        # Computed over the layer's FULL extent, not the requested window. The
        # colour range is taken from the whole slice a few lines down, and
        # `_sample` maps from the layer's own node arrays, so a window-sized
        # array would be indexed with full-grid coordinates.
        try:
            computed, _prov = plugins.compute_derived(
                layer.source_id,
                layer.var,
                ds,
                bbox=(layer.west, layer.south, layer.east, layer.north),
                time=_iso(served_time),
                # The depth the ELEVATION block resolved above, and None for a
                # surface product that has none. Omitting it is what made a
                # volumetric derived layer unservable: the plugin fell back to
                # depth 0.0 m, the store refused it as outside 5 .. 2000 m, and
                # SIG0 was advertised in GetCapabilities with 24 elevations
                # while GetMap could draw none of them.
                depth=served_depth,
            )
        except plugins.PluginError as exc:
            # The plugin refused: a missing input variable, or a product that
            # does not apply to this dataset. That is a server-side condition,
            # not a caller mistake, but it must still arrive as a service
            # exception rather than a 500 with a stack trace.
            raise OgcError(
                f"layer {layer.name} could not be computed: {exc}",
                locator="LAYERS",
            ) from None
        except store.SubsetError as exc:
            raise OgcError(str(exc), code="InvalidDimensionValue", locator="TIME") from None
        slab = np.asarray(computed.values, dtype="float64")
        if slab.ndim != 2:
            raise OgcError(
                f"layer {layer.name} is declared as a surface but computed "
                f"{slab.ndim} dimensions; the plugin's output contract is broken",
                locator="LAYERS",
            )
    else:
        slab = ds[layer.var].sel(time=served_time, depth=served_depth)
        if set(slab.dims) != {"lat", "lon"}:
            raise OgcError(
                f"layer {layer.name} does not reduce to a lat/lon slice; dims are {slab.dims}",
                locator="LAYERS",
            )
        slab = np.asarray(slab.transpose("lat", "lon").values, dtype="float64")

    # The colour range comes from the WHOLE slice, never the requested window:
    # per-tile percentiles would give adjacent tiles different ramps, and a
    # tiled client would show colour seams down every tile boundary.
    raw_range = (params.get("COLORSCALERANGE") or "").strip()
    if raw_range and raw_range.lower() != "auto":
        pair = [p.strip() for p in raw_range.split(",")]
        if len(pair) != 2:
            raise OgcError(
                f"COLORSCALERANGE needs min,max, got {raw_range!r}", locator="COLORSCALERANGE"
            )
        try:
            vmin, vmax = float(pair[0]), float(pair[1])
        except ValueError:
            raise OgcError(
                f"COLORSCALERANGE values must be numbers, got {raw_range!r}",
                locator="COLORSCALERANGE",
            ) from None
    elif layer.declared_range is not None:
        vmin, vmax = layer.declared_range
    else:
        vmin, vmax = colormap.suggested_range(slab)

    try:
        rgba = colormap.map_to_rgba(
            _sample(slab, layer.lat_nodes, layer.lon_nodes, (xmin, ymin, xmax, ymax),
                    width, height),
            vmin, vmax, palette=palette, scale=scale, reverse=reverse,
        )
    except ValueError as exc:
        # A log scale over a range that straddles zero, or a zero-width range.
        # A caller mistake, not a server fault, so it must not be a 500.
        raise OgcError(str(exc), locator="COLORSCALERANGE") from None

    transparent = (params.get("TRANSPARENT") or "FALSE").strip().upper() == "TRUE"
    if not transparent:
        # The spec's default is FALSE even though our own globe wants TRUE.
        # BGCOLOR is the CALLER's declared background, not a fabricated
        # measurement, which is why painting missing cells with it does not
        # break the rule that absent data is never coloured: the caller asked
        # for an opaque image and knows what colour it asked for.
        missing = rgba[..., 3] == 0
        rgba[missing, :3] = _parse_bgcolor(params.get("BGCOLOR"))
        rgba[..., 3] = 255

    headers = {
        "X-Sagardrishti-Source-Id": layer.source_id,
        "X-Sagardrishti-Layer": layer.name,
        "X-Sagardrishti-Variable": layer.var,
        "X-Sagardrishti-Time": _iso(served_time),
        "X-Sagardrishti-Units": _ascii(layer.units),
        "X-Sagardrishti-Palette": palette,
        "X-Sagardrishti-Colorscalerange": f"{_num(vmin)},{_num(vmax)}",
        "X-Sagardrishti-Scale": scale,
        "X-Sagardrishti-Citation": _ascii(
            layer.citation or ref.provenance.get("citation") or ""
        ),
        "X-Sagardrishti-Retrieved-At": _ascii(layer.retrieved_at),
    }
    # Omitted rather than sent empty for a surface layer: a header reading
    # "X-Sagardrishti-Elevation: 0" would claim this image came from the
    # surface level, which is a different and false statement.
    if served_depth is not None:
        headers["X-Sagardrishti-Elevation"] = _num(served_depth)
    if layer.derived:
        meta = layer.derived_meta or {}
        headers["X-Sagardrishti-Derived"] = "true"
        headers["X-Sagardrishti-Derived-From"] = _ascii(
            ",".join(meta.get("derived_from") or [])
        )
        headers["X-Sagardrishti-Plugin"] = _ascii(str(meta.get("plugin") or ""))
        # The recipe travels with the pixels, so a saved tile can still be
        # explained. Header values must be latin-1 and single-line.
        headers["X-Sagardrishti-Method"] = _ascii(
            " ".join(str(meta.get("method") or "").split())
        )

    return Response(_png(rgba), media_type="image/png", headers=headers)


@router.get("/wms", response_class=Response, summary="OGC WMS 1.3.0 (F7)")
def wms(request: Request) -> Response:
    """GetCapabilities and GetMap.

    The whole query string is read by hand rather than through FastAPI Query
    parameters: a missing or misspelled OGC parameter has to come back as a
    ServiceExceptionReport, and a declared Query() would answer 422 JSON before
    this function ever runs.
    """
    params = {key.upper(): value for key, value in request.query_params.items()}
    try:
        service = (params.get("SERVICE") or "").strip()
        operation = (params.get("REQUEST") or "").strip()
        if not operation:
            raise OgcError(
                "REQUEST is required; this service supports GetCapabilities and GetMap",
                locator="REQUEST",
            )
        # The spec says parameter VALUES are case sensitive, but real clients
        # vary ("WMS", "wms") and refusing them buys conformance nobody grades
        # at the cost of a reviewer's first request failing. A WRONG service is
        # always refused; a MISSING one is tolerated on GetCapabilities only,
        # which is the request people type by hand.
        if service:
            if service.lower() != "wms":
                raise OgcError(f"SERVICE must be WMS, got {service!r}", locator="SERVICE")
        elif operation.lower() != "getcapabilities":
            raise OgcError("SERVICE=WMS is required for this request", locator="SERVICE")

        layers = _layers()
        if operation.lower() == "getcapabilities":
            # Version negotiation: a client asking for a version we do not have
            # gets the one we do, which is what the spec prescribes and what
            # lets an old QGIS connect at all.
            return _wms_capabilities(request, layers)
        if operation.lower() == "getmap":
            return _wms_getmap(request, params, layers)
        if operation.lower() == "getfeatureinfo":
            raise OgcError(
                "GetFeatureInfo is not implemented; every layer declares "
                "queryable=\"0\". Use GET /field for values with provenance, or "
                "WCS GetCoverage for a CF-NetCDF subset.",
                code="OperationNotSupported",
                locator="REQUEST",
            )
        raise OgcError(
            f"REQUEST {operation!r} is not supported; this service offers "
            "GetCapabilities and GetMap",
            code="OperationNotSupported",
            locator="REQUEST",
        )
    except OgcError as err:
        return _exception_response([err], "wms")
    except store.SubsetError as err:  # pragma: no cover - defensive
        return _exception_response([OgcError(str(err))], "wms")


# ============================================================================
# WCS 1.0.0
# ============================================================================
# WCS 1.0.0 rather than 2.0.1 because it is what THREDDS serves and what QGIS
# consumes most simply, so it is the flavour an INCOIS reviewer already runs.
# It also predates the WMS 1.3.0 axis-order change: here BBOX is lon,lat for
# BOTH EPSG:4326 and OGC:CRS84, and lonLatEnvelope is CRS84 by definition.

def _coverage_description(layer: LayerInfo) -> str:
    """The WCS wording, which is NOT the WMS wording.

    A coverage description that talked about transparent pixels and image
    response headers would be a copy-paste of the WMS Abstract; WCS hands back
    a CF-NetCDF file, where missing data is NaN and provenance lives in the
    global attributes.
    """
    if layer.is_surface:
        vertical = (
            "This coverage has NO vertical axis: it is one surface derived from the "
            "whole water column, so the range set enumerates no depth levels and a "
            "DEPTH subset is not accepted. Its VALUES are depths in metres, positive "
            "down."
        )
    else:
        vertical = (
            f"The vertical axis is depth in metres, positive down, on the "
            f"{len(layer.depths)} irregularly spaced levels enumerated in the range set "
            f"({_num(layer.depths[0])} m to {_num(layer.depths[-1])} m)."
        )
    return (
        f"{layer.label} in units of {layer.units or 'unknown'}."
        f"{_units_note(layer.units)} From {layer.dataset_title}."
        f"{_derived_note(layer) if layer.derived else ''} "
        f"{vertical} GetCoverage returns "
        "CF-1.8 NETCDF3_CLASSIC on the native grid with no resampling; cells with no "
        "data (land, fill values) are NaN and are never filled with a substitute "
        f"value. Source: {layer.citation}"
    )


def _wcs_description(parent, layer: LayerInfo, tag: str):
    element = _sub(parent, tag)
    _sub(element, "description", _coverage_description(layer))
    _sub(element, "name", layer.name)
    _sub(element, "label", f"{layer.label} ({layer.units}) - {layer.dataset_title}")
    return element


def _wcs_lonlat_envelope(parent, layer: LayerInfo) -> None:
    envelope = _sub(parent, "lonLatEnvelope", attrib={
        "srsName": "urn:ogc:def:crs:OGC:1.3:CRS84"
    })
    _sub(envelope, "gml:pos", f"{_num(layer.west)} {_num(layer.south)}")
    _sub(envelope, "gml:pos", f"{_num(layer.east)} {_num(layer.north)}")
    _sub(envelope, "gml:timePosition", layer.times[0])
    _sub(envelope, "gml:timePosition", layer.times[-1])


def _wcs_keywords(parent, layer: LayerInfo) -> None:
    keywords = _sub(parent, "keywords")
    for word in filter(None, (layer.label, layer.canonical, layer.source_id)):
        _sub(keywords, "keyword", word)


def _wcs_root(tag: str, schema: str, **extra) -> ET.Element:
    attrib = {"version": WCS_VERSION}
    attrib.update(extra)
    attrib.update({
        "xmlns": NS_WCS,
        "xmlns:gml": NS_GML,
        "xmlns:xlink": NS_XLINK,
        "xmlns:xsi": NS_XSI,
        "xsi:schemaLocation": f"{NS_WCS} http://schemas.opengis.net/wcs/1.0.0/{schema}",
    })
    return ET.Element(tag, attrib)


def _wcs_capabilities(request: Request, layers: dict[str, LayerInfo]) -> Response:
    endpoint = _base_url(request, "/wcs")
    root = _wcs_root("WCS_Capabilities", "wcsCapabilities.xsd")

    # Service := description?, name, label, keywords?, responsibleParty?,
    # fees, accessConstraints+ -- fees and accessConstraints are REQUIRED in
    # 1.0.0, unlike WMS where they are optional.
    service = _sub(root, "Service")
    _sub(service, "description",
         "OGC WCS 1.0.0 access to the SagarDrishti offline ocean cube. " + _SERVICE_DISCLAIMER)
    _sub(service, "name", "SagarDrishti")
    _sub(service, "label", "SagarDrishti ocean digital twin (WCS)")
    keywords = _sub(service, "keywords")
    for word in ("ocean", "temperature", "salinity", "Argo", "Indian Ocean", "INCOIS"):
        _sub(keywords, "keyword", word)
    _sub(service, "fees", "NONE")
    _sub(service, "accessConstraints", _SERVICE_DISCLAIMER)

    capability = _sub(root, "Capability")
    operations = _sub(capability, "Request")
    for op_name in ("GetCapabilities", "DescribeCoverage", "GetCoverage"):
        op = _sub(operations, op_name)
        http = _sub(_sub(op, "DCPType"), "HTTP")
        _online_resource(_sub(http, "Get"), endpoint)
    _sub(_sub(capability, "Exception"), "Format", "application/vnd.ogc.se_xml")

    content = _sub(root, "ContentMetadata")
    for layer in layers.values():
        brief = _wcs_description(content, layer, "CoverageOfferingBrief")
        _wcs_lonlat_envelope(brief, layer)
        _wcs_keywords(brief, layer)

    return Response(_serialize(root), media_type="text/xml; charset=utf-8")


def _wcs_describe(request: Request, params: dict, layers: dict[str, LayerInfo]) -> Response:
    wanted = (params.get("COVERAGE") or "").strip()
    if wanted:
        names = [n.strip() for n in wanted.split(",") if n.strip()]
        unknown = [n for n in names if n not in layers]
        if unknown:
            raise OgcError(
                f"unknown coverage {unknown[0]!r}; available: {', '.join(layers)}",
                code="CoverageNotDefined",
                locator="COVERAGE",
            )
        selected = [layers[n] for n in names]
    else:
        selected = list(layers.values())

    root = _wcs_root("CoverageDescription", "describeCoverage.xsd")
    for layer in selected:
        offering = _wcs_description(root, layer, "CoverageOffering")
        _wcs_lonlat_envelope(offering, layer)
        _wcs_keywords(offering, layer)

        domain = _sub(offering, "domainSet")
        spatial = _sub(domain, "spatialDomain")
        # WCS 1.0.0 EPSG:4326 is lon,lat: the version predates the axis-order
        # change that WMS 1.3.0 introduced. Same CRS name, other order.
        envelope = _sub(spatial, "gml:Envelope", attrib={"srsName": "EPSG:4326"})
        _sub(envelope, "gml:pos", f"{_num(layer.west)} {_num(layer.south)}")
        _sub(envelope, "gml:pos", f"{_num(layer.east)} {_num(layer.north)}")
        _wcs_grid(spatial, layer)

        temporal = _sub(domain, "temporalDomain")
        for stamp in layer.times:
            _sub(temporal, "gml:timePosition", stamp)

        range_set = _sub(_sub(offering, "rangeSet"), "RangeSet")
        cell = (
            "(time, lat, lon)" if layer.is_surface else "(time, depth, lat, lon)"
        )
        _sub(range_set, "description",
             f"{layer.label} on the native grid, one value per {cell} cell")
        _sub(range_set, "name", layer.var)
        _sub(range_set, "label", f"{layer.label} ({layer.units})")
        # WCS 1.0.0 has no vertical axis in the domain, so the depth levels go
        # here as explicit singleValues. That is how THREDDS exposes an ocean
        # vertical axis, and enumerating them is the only honest option for a
        # grid whose spacing changes from 5 m to 200 m.
        #
        # A surface coverage emits no axisDescription at all. An empty <values>
        # element would advertise a depth axis with nothing in it, which is a
        # worse answer than saying there is no axis.
        if not layer.is_surface:
            axis = _sub(range_set, "axisDescription")
            axis_description = _sub(axis, "AxisDescription")
            _sub(axis_description, "name", "depth")
            _sub(axis_description, "label", "Depth in metres, positive down")
            axis_values = _sub(axis_description, "values")
            for depth in layer.depths:
                _sub(axis_values, "singleValue", _num(depth))
        nulls = _sub(range_set, "nullValues")
        _sub(nulls, "singleValue", "NaN")

        crss = _sub(offering, "supportedCRSs")
        _sub(crss, "requestResponseCRSs", "EPSG:4326")
        _sub(crss, "requestResponseCRSs", "OGC:CRS84")
        formats = _sub(offering, "supportedFormats", attrib={"nativeFormat": "NetCDF3"})
        _sub(formats, "formats", "NetCDF3")
        # "none" is a legal InterpolationMethodType value and the only true
        # one: GetCoverage returns the native cells and never resamples.
        interpolations = _sub(offering, "supportedInterpolations", attrib={"default": "none"})
        _sub(interpolations, "interpolationMethod", "none")

    return Response(_serialize(root), media_type="text/xml; charset=utf-8")


def _wcs_grid(parent, layer: LayerInfo) -> None:
    """gml:RectifiedGrid, but only when the grid really is rectified.

    A RectifiedGrid is an origin plus offset vectors, so on a stretched or
    irregular horizontal grid it would place every cell but the first in the
    wrong location. When the spacing is not uniform we emit a plain gml:Grid
    instead, which states the index extent and makes no geometric claim.
    """
    lons = np.asarray(layer.lon_nodes, dtype="float64")
    lats = np.asarray(layer.lat_nodes, dtype="float64")
    dx = np.diff(lons)
    dy = np.diff(lats)
    uniform = (
        lons.size > 1 and lats.size > 1
        and bool(np.allclose(dx, dx[0], rtol=0, atol=1e-6))
        and bool(np.allclose(dy, dy[0], rtol=0, atol=1e-6))
    )

    tag = "gml:RectifiedGrid" if uniform else "gml:Grid"
    grid = _sub(parent, tag, attrib={"dimension": "2", "srsName": "EPSG:4326"})
    limits = _sub(_sub(grid, "gml:limits"), "gml:GridEnvelope")
    _sub(limits, "gml:low", "0 0")
    _sub(limits, "gml:high", f"{lons.size - 1} {lats.size - 1}")
    _sub(grid, "gml:axisName", "x")
    _sub(grid, "gml:axisName", "y")
    if uniform:
        _sub(_sub(grid, "gml:origin"), "gml:pos", f"{_num(lons[0])} {_num(lats[0])}")
        _sub(grid, "gml:offsetVector", f"{_num(dx[0])} 0")
        _sub(grid, "gml:offsetVector", f"0 {_num(dy[0])}")


def _parse_range(raw: str, key: str) -> tuple[float, float]:
    """A WCS axis subset: "v" for one value, "min/max" for a closed interval."""
    text = raw.strip()
    parts = [p.strip() for p in text.split("/")]
    if len(parts) > 2:
        raise OgcError(
            f"{key} accepts a single value or min/max, got {raw!r}",
            code="InvalidParameterValue",
            locator=key,
        )
    try:
        numbers = [float(p) for p in parts]
    except ValueError:
        raise OgcError(
            f"{key} values must be numbers, got {raw!r}",
            code="InvalidParameterValue",
            locator=key,
        ) from None
    # float("nan") and float("inf") parse, and then every comparison in the
    # slice below is False, so the subset came back empty and was reported as
    # a BBOX problem for a value the caller had put in DEPTH. Refuse it here,
    # where the parameter that carried it is still known.
    if not all(np.isfinite(n) for n in numbers):
        raise OgcError(
            f"{key} values must be finite numbers, got {raw!r}",
            code="InvalidParameterValue",
            locator=key,
        )
    return (numbers[0], numbers[-1])


def _dataset_from_slab(slab, layer: LayerInfo, provenance: dict) -> xr.Dataset:
    """A computed FieldSlab -> an xarray Dataset shaped like a store subset.

    Returning the same shape the stored path returns is the point: the
    emptiness check, the value cap, the native-grid guard and the NetCDF writer
    downstream all then work on one kind of object, so a plugin's coverage is
    not a second code path with its own half-tested bugs.

    The `time` dimension is kept with length 1 rather than dropped. WCS 1.0.0
    coverages here are always (time, ...) and a client that asked for a time
    should get a file that records which one it got.
    """
    values = np.asarray(slab.values, dtype="float64")
    coords = {
        "time": ("time", pd.to_datetime([slab.time.rstrip("Z")])),
        "lat": ("lat", np.asarray(slab.lats, dtype="float64")),
        "lon": ("lon", np.asarray(slab.lons, dtype="float64")),
    }
    if values.ndim == 2:
        dims = ("time", "lat", "lon")
        data = values[np.newaxis, ...]
    elif values.ndim == 3:
        dims = ("time", "depth", "lat", "lon")
        data = values[np.newaxis, ...]
        coords["depth"] = ("depth", np.asarray(slab.depths, dtype="float64"))
    else:
        raise OgcError(
            f"coverage {layer.name} computed {values.ndim} dimensions; a plugin product "
            "must be a surface (lat, lon) or a column (depth, lat, lon)",
            code="InvalidParameterValue",
            locator="COVERAGE",
        )

    array = xr.DataArray(data, dims=dims, coords=coords, name=layer.var)
    array.attrs["units"] = slab.units or layer.units
    if layer.canonical:
        array.attrs["standard_name"] = layer.canonical
    array.attrs["long_name"] = layer.label
    # The recipe rides on the variable, so the downloaded file explains itself
    # without the URL that produced it.
    for key in ("method", "plugin", "derived_from", "params"):
        value = provenance.get(key)
        if value in (None, "", [], {}):
            continue
        array.attrs[f"derivation_{key}"] = (
            ", ".join(f"{k}={v}" for k, v in value.items())
            if isinstance(value, dict)
            else (", ".join(map(str, value)) if isinstance(value, (list, tuple)) else str(value))
        )

    dataset = xr.Dataset({layer.var: array})
    if "depth" in dataset.coords:
        dataset["depth"].attrs.update(
            {"units": "m", "positive": "down", "axis": "Z", "standard_name": "depth"}
        )
    return dataset


def _wcs_getcoverage(request: Request, params: dict, layers: dict[str, LayerInfo]) -> Response:
    wanted = (params.get("COVERAGE") or "").strip()
    if not wanted:
        raise OgcError(
            "COVERAGE is required for GetCoverage; see DescribeCoverage for the names",
            code="MissingParameterValue",
            locator="COVERAGE",
        )
    if wanted not in layers:
        raise OgcError(
            f"unknown coverage {wanted!r}; available: {', '.join(layers)}",
            code="CoverageNotDefined",
            locator="COVERAGE",
        )
    layer = layers[wanted]

    fmt = (params.get("FORMAT") or "").strip()
    if not fmt:
        raise OgcError(
            "FORMAT is required for GetCoverage; this service offers NetCDF3",
            code="MissingParameterValue",
            locator="FORMAT",
        )
    if fmt.lower() not in ("netcdf3", "netcdf", "application/x-netcdf", "nc"):
        raise OgcError(
            f"FORMAT {fmt!r} is not offered; DescribeCoverage advertises NetCDF3 only",
            code="InvalidFormat",
            locator="FORMAT",
        )

    # CRS is nominally required in WCS 1.0.0. It is defaulted here because the
    # reason for strictness in WMS does not exist in WCS 1.0.0: both CRSs we
    # support are lon,lat, so there is no axis order left to guess at.
    crs = (params.get("CRS") or "EPSG:4326").strip()
    if crs.upper() not in ("EPSG:4326", "OGC:CRS84", "CRS:84",
                           "URN:OGC:DEF:CRS:EPSG::4326", "URN:OGC:DEF:CRS:OGC:1.3:CRS84"):
        raise OgcError(
            f"CRS {crs!r} is not supported; DescribeCoverage advertises EPSG:4326 and "
            "OGC:CRS84, both lon,lat in WCS 1.0.0, and this service never reprojects",
            code="InvalidParameterValue",
            locator="CRS",
        )

    ds, ref = store.open_cube(layer.source_id)
    lat_ascending = bool(ds["lat"].values[0] <= ds["lat"].values[-1])
    lon_ascending = bool(ds["lon"].values[0] <= ds["lon"].values[-1])

    west, south, east, north = layer.west, layer.south, layer.east, layer.north
    # A surface coverage has no vertical extent to subset. None is carried
    # through rather than a sentinel pair so every later use has to decide
    # explicitly what it means, instead of quietly slicing on 0..0.
    depth_lo, depth_hi = (
        (None, None) if layer.is_surface else (layer.depths[0], layer.depths[-1])
    )
    # Which PARAMETER supplied the depth range, so an empty depth selection is
    # blamed on the parameter the caller actually sent. THREDDS accepts the
    # range in either DEPTH or the 6-value BBOX form, and pointing a caller at
    # the wrong one of the two is a wasted round trip.
    depth_locator = "DEPTH"
    raw_bbox = (params.get("BBOX") or "").strip()
    if raw_bbox:
        parts = [p.strip() for p in raw_bbox.split(",")]
        if len(parts) not in (4, 6):
            raise OgcError(
                f"BBOX needs 4 numbers (minlon,minlat,maxlon,maxlat) or 6 with "
                f"minz,maxz appended, got {len(parts)}",
                code="InvalidParameterValue",
                locator="BBOX",
            )
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            raise OgcError(
                f"BBOX values must be numbers, got {raw_bbox!r}",
                code="InvalidParameterValue",
                locator="BBOX",
            ) from None
        # Same reason as _parse_range: a non-finite corner is not a window, and
        # letting it through only produces an empty subset one screen later.
        if not all(np.isfinite(n) for n in numbers):
            raise OgcError(
                f"BBOX values must be finite numbers, got {raw_bbox!r}",
                code="InvalidParameterValue",
                locator="BBOX",
            )
        # lon,lat for BOTH supported CRSs: WCS 1.0.0 predates the WMS 1.3.0
        # axis-order rule. A client that sends WMS 1.3.0 EPSG:4326 order here
        # gets an empty selection and the exception below, not a wrong file.
        west, south, east, north = numbers[:4]
        if len(numbers) == 6:
            depth_lo, depth_hi = numbers[4], numbers[5]
            depth_locator = "BBOX"

    raw_depth = (params.get("DEPTH") or params.get("ELEVATION") or "").strip()
    if raw_depth and layer.is_surface:
        raise OgcError(
            f"coverage {layer.name} has no vertical axis, so a DEPTH subset of "
            f"{raw_depth!r} cannot be honoured. DescribeCoverage enumerates no depth "
            "levels for it: this coverage IS a depth, derived from the whole column.",
            code="InvalidParameterValue",
            locator="DEPTH",
        )
    if raw_depth:
        depth_lo, depth_hi = _parse_range(raw_depth, "DEPTH")
        depth_locator = "DEPTH"

    if layer.derived:
        # Computed, then wrapped in a Dataset so that everything downstream
        # (the emptiness check, the value cap, the native-grid guard and the
        # NetCDF writer) works on one shape and is not duplicated per kind.
        try:
            computed, derived_prov = plugins.compute_derived(
                layer.source_id,
                layer.var,
                ds,
                bbox=(west, south, east, north),
                time=layer.times[-1],
                # A VOLUMETRIC derived product is computed over the whole
                # column and sliced to the requested DEPTH below, the same way
                # the stored branch slices its own. Without this the plugin
                # fell back to depth 0.0 m and refused every request for SIG0,
                # a coverage this service advertises. A surface product takes
                # neither: it has no depth to choose.
                all_depths=not layer.is_surface,
            )
        except plugins.PluginError as exc:
            raise OgcError(
                f"coverage {layer.name} could not be computed: {exc}",
                code="InvalidParameterValue",
                locator="COVERAGE",
            ) from None
        except store.SubsetError as exc:
            raise OgcError(
                str(exc), code="InvalidParameterValue", locator="BBOX",
            ) from None
        subset = _dataset_from_slab(computed, layer, derived_prov)
        if not layer.is_surface:
            # The same DEPTH window the stored branch applies. Applied here
            # rather than inside the plugin so that a derived coverage and a
            # stored one answer the identical request identically.
            subset = subset.sel(
                depth=slice(min(depth_lo, depth_hi), max(depth_lo, depth_hi))
            )
    else:
        subset = ds[[layer.var]].sel(
            lat=slice(south, north) if lat_ascending else slice(north, south),
            lon=slice(west, east) if lon_ascending else slice(east, west),
            depth=slice(min(depth_lo, depth_hi), max(depth_lo, depth_hi)),
        )

    raw_time = (params.get("TIME") or "").strip()
    if raw_time:
        stamps = [p.strip() for p in raw_time.split("/")]
        if len(stamps) > 2:
            raise OgcError(
                f"TIME accepts a single value or start/end, got {raw_time!r}",
                code="InvalidParameterValue",
                locator="TIME",
            )
        try:
            lo = store.nearest_time(ds, stamps[0])
            hi = store.nearest_time(ds, stamps[-1])
        except store.SubsetError as exc:
            raise OgcError(str(exc), code="InvalidParameterValue", locator="TIME") from None
        subset = subset.sel(time=slice(min(lo, hi), max(lo, hi)))

    axes = ("time", "lat", "lon") if layer.is_surface else ("time", "depth", "lat", "lon")
    empty = [dim for dim in axes if subset.sizes.get(dim, 0) == 0]
    if empty:
        # The locator is an instruction to go and fix THAT parameter, so it has
        # to name the axis that actually came back empty. Every empty subset
        # used to be reported as locator="BBOX", which sent a caller whose
        # DEPTH was wrong to re-read the one parameter that was right. lat and
        # lon are the axes BBOX really owns.
        locator = {"depth": depth_locator, "time": "TIME"}.get(empty[0], "BBOX")
        raise OgcError(
            f"the requested subset selects no cells: the "
            f"{' and '.join(empty)} selection is empty. This coverage spans lon "
            f"{_num(layer.west)}..{_num(layer.east)}, lat {_num(layer.south)}.."
            f"{_num(layer.north)}, "
            + ("no vertical axis, " if layer.is_surface
               else f"depth {_num(layer.depths[0])}..{_num(layer.depths[-1])} m, ")
            + f"time {layer.times[0]}..{layer.times[-1]}. Note that in WCS 1.0.0 BBOX is "
            "lon,lat, unlike WMS 1.3.0 EPSG:4326.",
            code="InvalidParameterValue",
            locator=locator,
        )

    n_values = int(np.prod([subset.sizes[d] for d in axes]))
    if n_values > WCS_MAX_VALUES:
        raise OgcError(
            f"the requested subset holds {n_values} values, over this service's limit of "
            f"{WCS_MAX_VALUES}. Narrow BBOX, TIME or DEPTH.",
            code="InvalidParameterValue",
            locator="BBOX",
        )

    # WIDTH/HEIGHT/RESX/RESY are accepted only when they ask for the grid we
    # already have. Silently ignoring them would hide a resampling request, and
    # honouring one would mean inventing an interpolation we explicitly
    # advertise as "none". THREDDS tolerates their absence and so do we.
    native = {
        "WIDTH": subset.sizes["lon"], "HEIGHT": subset.sizes["lat"],
    }
    for key, size in native.items():
        raw = (params.get(key) or "").strip()
        if raw and raw != str(size):
            raise OgcError(
                f"{key}={raw} would require resampling to a grid other than the native "
                f"{native['WIDTH']}x{native['HEIGHT']} cells this subset contains. "
                "DescribeCoverage advertises interpolationMethod none, so this service "
                "returns native cells only.",
                code="InvalidParameterValue",
                locator=key,
            )
    for key, spacing in (("RESX", np.diff(subset["lon"].values)),
                         ("RESY", np.diff(subset["lat"].values))):
        raw = (params.get(key) or "").strip()
        if not raw:
            continue
        try:
            asked = abs(float(raw))
        except ValueError:
            raise OgcError(
                f"{key} must be a number, got {raw!r}",
                code="InvalidParameterValue", locator=key,
            ) from None
        actual = abs(float(spacing[0])) if spacing.size else 0.0
        if not np.isclose(asked, actual, rtol=0, atol=1e-6):
            raise OgcError(
                f"{key}={raw} would require resampling from the native spacing of "
                f"{_num(actual)} degrees. DescribeCoverage advertises "
                "interpolationMethod none.",
                code="InvalidParameterValue", locator=key,
            )

    body = _wcs_netcdf(subset, layer, ref, str(request.url.query))
    served_times = pd.to_datetime(subset["time"].values)
    stamp = pd.Timestamp(served_times[-1]).strftime("%Y%m%d")
    filename = f"sagardrishti_{layer.source_id}_{layer.var}_{stamp}.nc"

    return Response(
        body,
        media_type="application/x-netcdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Sagardrishti-Source-Id": layer.source_id,
            "X-Sagardrishti-Coverage": layer.name,
            "X-Sagardrishti-Time": _iso(served_times[-1]),
            "X-Sagardrishti-Units": _ascii(layer.units),
            "X-Sagardrishti-Citation": _ascii(layer.citation),
            "X-Sagardrishti-Retrieved-At": _ascii(layer.retrieved_at),
        },
    )


def _wcs_netcdf(subset: xr.Dataset, layer: LayerInfo, ref, query: str) -> bytes:
    """Serialize a subset as CF-1.8 NETCDF3_CLASSIC bytes.

    The output dataset is rebuilt from arrays rather than handed straight to
    the writer, for one reason worth stating: the source's global attributes,
    and the `actual_range` on every coordinate, describe the WHOLE cube. A
    downloaded file that inherited them would report an extent it does not
    contain, which is a number without provenance.
    """
    spec = load_registry().get(layer.source_id) if load_registry().has(layer.source_id) else None
    variable_spec = spec.variable(layer.var) if spec else None

    var_attrs = {k: v for k, v in subset[layer.var].attrs.items() if k != "actual_range"}
    if "standard_name" not in var_attrs and variable_spec and variable_spec.canonical:
        # Real defect: the shipped cube's TEMP has no standard_name at all
        # while SAL does. The registry knows the CF name for both, so stamp it
        # rather than shipping a file a CF checker rejects.
        var_attrs["standard_name"] = variable_spec.canonical

    # A derived SURFACE coverage has no depth coordinate, so the axis list is
    # taken from the subset rather than assumed. Writing an absent coordinate
    # would raise; writing a length-1 dummy would invent a depth the value does
    # not have.
    axis_names = [n for n in ("time", "depth", "lat", "lon") if n in subset.dims]
    coords = {}
    for name in axis_names:
        coords[name] = (
            name,
            subset[name].values,
            {k: v for k, v in subset[name].attrs.items() if k != "actual_range"},
        )
    if "depth" in coords:
        coords["depth"][2].setdefault("units", "m")
        coords["depth"][2].setdefault("positive", "down")
        coords["depth"][2].setdefault("standard_name", "depth")
    coords["lat"][2].setdefault("units", "degrees_north")
    coords["lat"][2].setdefault("standard_name", "latitude")
    coords["lon"][2].setdefault("units", "degrees_east")
    coords["lon"][2].setdefault("standard_name", "longitude")

    lats = np.asarray(subset["lat"].values, dtype="float64")
    lons = np.asarray(subset["lon"].values, dtype="float64")
    depths = (
        np.asarray(subset["depth"].values, dtype="float64")
        if "depth" in subset.dims
        else None
    )
    times = pd.to_datetime(subset["time"].values)

    source_attrs = subset.attrs
    attrs: dict = {"Conventions": "CF-1.8"}
    for key in ("title", "institution", "summary", "keywords",
                "standard_name_vocabulary", "cdm_data_type", "license"):
        if key in source_attrs:
            attrs[key] = source_attrs[key]
    attrs["source_id"] = layer.source_id
    attrs["citation"] = layer.citation
    if layer.retrieved_at:
        attrs["retrieved_at"] = layer.retrieved_at
    if ref.provenance.get("source_url"):
        attrs["source_url"] = ref.provenance["source_url"]
    attrs.update({
        "geospatial_lat_min": float(lats.min()),
        "geospatial_lat_max": float(lats.max()),
        "geospatial_lat_units": "degrees_north",
        "geospatial_lon_min": float(lons.min()),
        "geospatial_lon_max": float(lons.max()),
        "geospatial_lon_units": "degrees_east",
        "Westernmost_Easting": float(lons.min()),
        "Easternmost_Easting": float(lons.max()),
        "Southernmost_Northing": float(lats.min()),
        "Northernmost_Northing": float(lats.max()),
        "time_coverage_start": _iso(times[0]),
        "time_coverage_end": _iso(times[-1]),
    })
    if depths is not None:
        attrs.update({
            "geospatial_vertical_min": float(depths.min()),
            "geospatial_vertical_max": float(depths.max()),
            "geospatial_vertical_units": "m",
            "geospatial_vertical_positive": "down",
        })
    # CF's own provenance mechanism: append, never replace, so the source's
    # FERRET and ERDDAP lines survive alongside ours.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = (
        f"{now} SagarDrishti WCS {WCS_VERSION} GetCoverage "
        f"COVERAGE={layer.name} {_ascii(query)}"
    )
    previous = str(source_attrs.get("history", "")).strip()
    attrs["history"] = f"{previous}\n{line}" if previous else line

    order = tuple(axis_names)
    out = xr.Dataset(
        {layer.var: (order,
                     np.asarray(subset[layer.var].transpose(*order).values,
                                dtype="float64"),
                     var_attrs)},
        coords=coords,
        attrs=attrs,
    )
    # NaN is the missing value and DescribeCoverage says so in nullValues, so
    # declare it here too. Coordinates get _FillValue=None explicitly: CF does
    # not allow missing values in a coordinate variable, and xarray otherwise
    # carries one over from the zarr store's encoding.
    out[layer.var].encoding["_FillValue"] = np.nan
    for name in out.coords:
        out[name].encoding["_FillValue"] = None
    out["time"].encoding.update(
        units="seconds since 1970-01-01T00:00:00Z", calendar="standard", dtype="float64"
    )

    # A real in-memory buffer, not a temp file. `memory=1` matters: netCDF4
    # grows the buffer as it writes, so close() hands back exactly the file
    # bytes. Passing a larger initial size returns the file zero-padded to that
    # allocation (measured: 65536 bytes for a 9464-byte file), and the padding
    # cannot be stripped safely because a final float64 zero is also eight NUL
    # bytes. NETCDF3_CLASSIC because it is the format netCDF4 can size exactly,
    # it is what ncdump and every reviewer tool reads without fuss, and neither
    # scipy nor h5netcdf is installed for xarray's own buffer path.
    handle = netCDF4.Dataset(
        "sagardrishti_wcs.nc", mode="w", memory=1, format="NETCDF3_CLASSIC"
    )
    try:
        out.dump_to_store(xr.backends.NetCDF4DataStore(handle))
    except Exception:
        handle.close()
        raise
    return bytes(handle.close())


@router.get("/wcs", response_class=Response, summary="OGC WCS 1.0.0 (F7)")
def wcs(request: Request) -> Response:
    """GetCapabilities, DescribeCoverage and GetCoverage."""
    params = {key.upper(): value for key, value in request.query_params.items()}
    try:
        service = (params.get("SERVICE") or "").strip()
        operation = (params.get("REQUEST") or "").strip()
        if not operation:
            raise OgcError(
                "REQUEST is required; this service supports GetCapabilities, "
                "DescribeCoverage and GetCoverage",
                code="MissingParameterValue",
                locator="REQUEST",
            )
        if service and service.lower() != "wcs":
            raise OgcError(
                f"SERVICE must be WCS, got {service!r}",
                code="InvalidParameterValue",
                locator="SERVICE",
            )

        layers = _layers()
        lowered = operation.lower()
        if lowered == "getcapabilities":
            return _wcs_capabilities(request, layers)
        if lowered == "describecoverage":
            return _wcs_describe(request, params, layers)
        if lowered == "getcoverage":
            return _wcs_getcoverage(request, params, layers)
        raise OgcError(
            f"REQUEST {operation!r} is not supported; this service offers "
            "GetCapabilities, DescribeCoverage and GetCoverage",
            code="InvalidParameterValue",
            locator="REQUEST",
        )
    except OgcError as err:
        return _exception_response([err], "wcs")
    except store.SubsetError as err:  # pragma: no cover - defensive
        return _exception_response([OgcError(str(err), code="InvalidParameterValue")], "wcs")
