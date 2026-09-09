"""CAP v1.2 warning parsing for HazardWatch (PRD F13, TRD M8).

The problem statement's portal theme is DISASTER MANAGEMENT and "timely hazard
assessment" is its first stated mandate, so a viewer of the Indian Ocean that
cannot show a warning is answering half the brief. This module is the half that
reads warnings; app/main.py serves them and the globe draws them.

WHY CAP, AND WHY THE REAL ONE
-----------------------------
The Common Alerting Protocol (OASIS CAP v1.2) is what INCOIS's own tsunami
service and India's national alert backbone, NDMA SACHET, actually speak.
Reading CAP is therefore not an integration we invented; it is the format the
customer already publishes in.

This parser is proven against REAL government CAP, not against a sample we
wrote: tests/fixtures/ holds an alert retrieved from SACHET on 2026-09-09 with
its geometry sidecar, and two tests pin the quirks that file exposes.

THE ONLY THING THAT MATTERS HERE IS NOT SHOWING A WARNING THAT IS NOT THERE
--------------------------------------------------------------------------
Every other module in this project can be wrong and misinform. This one can
raise a false alarm. Five refusals exist for that reason and each is counted:

  * `Cancel` withdraws the alerts it references. A cancelled tsunami warning
    still on a globe is the worst thing this layer could do.
  * `Update` supersedes what it references, so one hazard is not drawn twice
    with two different severities.
  * `status` other than `Actual` (Exercise, Test, Draft, System) is never live.
    CAP has this field precisely so a drill can be written to be identical to
    the real thing in every other respect.
  * An expired alert is not active, compared in its own timezone. The real feed
    stamps +05:30 and a naive clock is five and a half hours wrong.
  * An alert whose effective time has not arrived is not active yet.

THE COORDINATE TRAP
-------------------
CAP writes coordinates LATITUDE FIRST. GeoJSON, Cesium, and everything
downstream of this file write LONGITUDE FIRST. A parser that forgets puts a Bay
of Bengal warning in the Arctic and draws it perfectly convincingly. Every
coordinate leaves this module as (lon, lat), and a latitude outside +/-90 is
refused rather than drawn, because that is what a transposed pair usually looks
like.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

#: CAP's own closed vocabularies. A value outside one of these is recorded and
#: replaced with "Unknown" rather than believed: an unranked severity cannot be
#: ordered against the others, and guessing where it sits would rank a hazard
#: this parser does not understand.
SEVERITIES = ("Extreme", "Severe", "Moderate", "Minor", "Unknown")
URGENCIES = ("Immediate", "Expected", "Future", "Past", "Unknown")
CERTAINTIES = ("Observed", "Likely", "Possible", "Unlikely", "Unknown")
STATUSES = ("Actual", "Exercise", "System", "Test", "Draft")
MSG_TYPES = ("Alert", "Update", "Cancel", "Ack", "Error")

#: The two message types that CARRY a hazard. Ack and Error are transport
#: bookkeeping and Cancel is a withdrawal, so none of them is ever drawn.
WARNING_MSG_TYPES = ("Alert", "Update")

METHOD = (
    "OASIS Common Alerting Protocol v1.2 (also accepting v1.1 and unnamespaced "
    "producers). An alert is shown only when status is Actual, msgType is Alert "
    "or Update, it is neither cancelled nor superseded by a later message's "
    "references, and the current time lies between its effective and expires "
    "stamps compared in the alert's own timezone. Coordinates are converted "
    "from CAP's latitude-first order to longitude-first"
)


class CapError(ValueError):
    """The bytes handed in are not a CAP alert this module will guess at."""


def severity_rank(severity: str) -> int:
    """Higher is worse. Unknown ranks below Minor, not above it.

    An alert whose severity we could not read must not sort to the top of a
    banner and displace a real Extreme warning.
    """
    order = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1}
    return order.get(severity, 0)


def parse_time(value: str | None) -> datetime | None:
    """A CAP timestamp, or None when there is not one.

    None rather than a default, deliberately. Defaulting a missing expiry to
    "now" would silently expire every alert; defaulting it to now plus some
    duration would invent how long a hazard lasts.
    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Python's fromisoformat has handled "Z" since 3.11, but the feed also
    # carries "+05:30" and the occasional trailing space.
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # CAP requires an offset. A producer that omits one is read as UTC, which
    # is stated here rather than left as an accident of comparison.
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _localname(tag: str) -> str:
    """`{urn:...cap:1.2}info` -> `info`.

    Matching on the local name is what lets one parser read CAP 1.2, CAP 1.1
    and the unnamespaced documents some producers emit, including SACHET's own
    geometry sidecar. Refusing a real warning over a namespace URI would be a
    refusal about serialisation rather than about content.
    """
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(node: ET.Element, name: str) -> ET.Element | None:
    for c in node:
        if _localname(c.tag) == name:
            return c
    return None


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in node if _localname(c.tag) == name]


def _text(node: ET.Element | None, name: str, default: str = "") -> str:
    if node is None:
        return default
    c = _child(node, name)
    return (c.text or default).strip() if c is not None else default


def _vocabulary(value: str, allowed: tuple[str, ...], label: str, notes: list[str]) -> str:
    if value in allowed:
        return value
    if value:
        notes.append(f"{label} {value!r} is not in CAP's vocabulary; read as Unknown")
    return "Unknown"


def _coordinates(text: str, notes: list[str]) -> list[tuple[float, float]]:
    """CAP's "lat,lon lat,lon ..." into a list of (lon, lat).

    The transposition happens HERE and nowhere else, so there is exactly one
    place in the codebase where the convention can be got wrong.
    """
    points: list[tuple[float, float]] = []
    for pair in text.split():
        parts = pair.split(",")
        if len(parts) != 2:
            notes.append(f"coordinate {pair!r} is not a lat,lon pair; dropped")
            return []
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            notes.append(f"coordinate {pair!r} is not numeric; dropped")
            return []
        if not math.isfinite(lat) or not math.isfinite(lon):
            notes.append(f"coordinate {pair!r} is not finite; dropped")
            return []
        if abs(lat) > 90.0:
            # The usual signature of a transposed pair, and the reason this
            # check exists at all: 80,15 draws as happily as 15,80.
            notes.append(
                f"latitude {lat} in {pair!r} is outside +/-90, which is what a "
                "transposed lat,lon pair looks like; polygon dropped"
            )
            return []
        if abs(lon) > 180.0:
            notes.append(f"longitude {lon} in {pair!r} is outside +/-180; polygon dropped")
            return []
        points.append((lon, lat))
    return points


def _ring(text: str, notes: list[str]) -> list[tuple[float, float]] | None:
    """One CAP polygon as a closed lon,lat ring, or None if it is not an area."""
    points = _coordinates(text, notes)
    if not points:
        return None
    if len(points) < 3:
        # Two points is a line. Closing it gives a zero-area polygon that draws
        # as nothing and still counts as a warning, which is the worst of both.
        notes.append(f"polygon has only {len(points)} points and is not an area; dropped")
        return None
    if points[0] != points[-1]:
        # CAP says the ring MUST be closed. Dropping a live warning over one
        # missing repeated coordinate would be absurd, so it is closed and the
        # fact is recorded rather than smoothed over.
        notes.append("polygon ring was not closed by the producer; closed here")
        points.append(points[0])
    if len(points) < 4:
        notes.append("polygon collapses to fewer than three distinct points; dropped")
        return None
    return points


#: Ramer-Douglas-Peucker tolerance in degrees, for the ingest.
#:
#: 0.01 degrees is about 1.1 km. The model field these polygons are drawn over
#: is on a ONE DEGREE grid, so a warning boundary resolved to a hundredth of a
#: degree is already two orders of magnitude finer than anything underneath it.
#:
#: This is not a nicety. A real SACHET alert fetched on 2026-09-09 carried a
#: single ring of 93,478 vertices, and twelve alerts came to 114,412 between
#: them: enough to blow the frame budget in TRD section 5 on its own, before
#: the 24 volumetric slices are drawn. Simplification is DISCLOSED on every
#: polygon it touches rather than done quietly.
SIMPLIFY_TOLERANCE_DEG = 0.01

#: Above this, a ring is simplified. Below it, it is left exactly as issued:
#: most warning polygons are a few dozen points and rounding those would be
#: damage for no gain.
SIMPLIFY_ABOVE = 200


def _perpendicular_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Distance from `point` to the segment start-end, in degrees."""
    (px, py), (x1, y1), (x2, y2) = point, start, end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    # Projection parameter, clamped to the segment so an endpoint-adjacent
    # point is measured to the endpoint rather than to the infinite line.
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def simplify_ring(
    ring: list[tuple[float, float]],
    tolerance: float = SIMPLIFY_TOLERANCE_DEG,
) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker, keeping the ring closed.

    Chosen over plain decimation (keep every Nth point) because decimation
    drops whichever vertices happen to fall on the stride, which on a coastline
    removes headlands and can fold the ring across itself. Douglas-Peucker
    keeps the points that carry the shape and removes the ones that lie on a
    line between their neighbours, which is the cartographic answer and has a
    tolerance a reader can argue with.

    The result is never fewer than four points, so a simplified area is still
    an area.
    """
    if len(ring) <= 4 or tolerance <= 0:
        return ring

    closed = ring[0] == ring[-1]
    points = ring[:-1] if closed else ring[:]

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    # Iterative rather than recursive: a 93,478-point ring recurses deeper than
    # Python's stack allows, which is not hypothetical here.
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        worst, worst_at = 0.0, first
        for i in range(first + 1, last):
            d = _perpendicular_distance(points[i], points[first], points[last])
            if d > worst:
                worst, worst_at = d, i
        if worst > tolerance:
            keep[worst_at] = True
            stack.append((first, worst_at))
            stack.append((worst_at, last))

    out = [p for p, k in zip(points, keep) if k]
    if len(out) < 3:
        # Too aggressive for this shape: keep the original rather than return
        # something that is no longer an area.
        return ring
    if closed:
        out.append(out[0])
    return out


@dataclass
class Area:
    """One CAP `<area>`: what it is called, and where it is if we can tell."""

    desc: str = ""
    #: Closed rings, longitude first.
    polygons: list[list[tuple[float, float]]] = field(default_factory=list)
    #: (lon, lat, radius_km). CAP's radius is KILOMETRES.
    circles: list[tuple[float, float, float]] = field(default_factory=list)
    #: Named areas with no geometry. Kept, because a warning this tool cannot
    #: place on a globe is still a warning and dropping it under-reports.
    geocodes: dict[str, str] = field(default_factory=dict)

    @property
    def drawable(self) -> bool:
        return bool(self.polygons or self.circles)

    def as_dict(self) -> dict:
        return {
            "desc": self.desc,
            "polygons": [[list(p) for p in ring] for ring in self.polygons],
            "circles": [list(c) for c in self.circles],
            "geocodes": self.geocodes,
            "drawable": self.drawable,
        }


@dataclass
class Info:
    """One CAP `<info>` block, which is to say one LANGUAGE of one alert.

    These are authored per language rather than translated from a canonical
    block, and in the real SACHET files only one of them carries the geometry.
    """

    language: str = ""
    category: str = ""
    event: str = ""
    urgency: str = "Unknown"
    severity: str = "Unknown"
    certainty: str = "Unknown"
    effective: datetime | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    headline: str = ""
    description: str = ""
    instruction: str = ""
    web: str = ""
    parameters: dict[str, str] = field(default_factory=dict)
    areas: list[Area] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "category": self.category,
            "event": self.event,
            "urgency": self.urgency,
            "severity": self.severity,
            "certainty": self.certainty,
            "effective": _iso(self.effective),
            "onset": _iso(self.onset),
            "expires": _iso(self.expires),
            "headline": self.headline,
            "description": self.description,
            "instruction": self.instruction,
            "web": self.web,
            "parameters": self.parameters,
            "areas": [a.as_dict() for a in self.areas],
        }


def _iso(stamp: datetime | None) -> str | None:
    return stamp.isoformat() if stamp else None


@dataclass
class Alert:
    """One CAP message. Its `infos` are its languages, not its hazards."""

    identifier: str
    sender: str
    sent: datetime | None
    status: str
    msg_type: str
    scope: str
    references: list[str]
    infos: list[Info]
    source: str = ""
    #: Every departure from the standard this file made, in the order met.
    #: Served, so a reader can see what we had to cope with.
    notes: list[str] = field(default_factory=list)

    # -- the fields a banner needs, taken from the primary language ---------

    @property
    def _primary(self) -> Info:
        return self.infos[0]

    @property
    def event(self) -> str:
        return self._primary.event

    @property
    def severity(self) -> str:
        return self._primary.severity

    @property
    def urgency(self) -> str:
        return self._primary.urgency

    @property
    def certainty(self) -> str:
        return self._primary.certainty

    @property
    def effective(self) -> datetime | None:
        return self._primary.effective

    @property
    def expires(self) -> datetime | None:
        return self._primary.expires

    @property
    def languages(self) -> list[str]:
        return [i.language for i in self.infos]

    @property
    def polygon_url(self) -> str | None:
        """SACHET puts geometry in a separate file and names it here.

        Not a CAP field: a `<parameter>` whose valueName is "Polygon URL". Real
        producers extend CAP through parameters and a reader has to look.
        """
        for info in self.infos:
            for name, value in info.parameters.items():
                if "polygon" in name.lower() and value.startswith("http"):
                    return value
        return None

    def info(self, language: str) -> Info:
        """The block for a language, falling back to the first.

        A prefix match, because the feed carries "en-IN" where a caller asks
        for "en". Falls back rather than returning nothing: an alert a reader
        cannot read in their own language is still a warning they need.
        """
        want = language.lower()
        for i in self.infos:
            if i.language.lower() == want:
                return i
        for i in self.infos:
            if i.language.lower().startswith(want) or want.startswith(i.language.lower()):
                return i
        return self.infos[0]

    def geometry(self) -> list[Area]:
        """Every drawable area on this alert, from whichever language has it.

        Deliberately not per-language: only the English block in a real SACHET
        alert carries the area, and a Telugu reader must still see the polygon.
        """
        seen: list[Area] = []
        for info in self.infos:
            for area in info.areas:
                if area.drawable:
                    seen.append(area)
        return seen

    def attach_geometry(self, rings: list[list[tuple[float, float]]]) -> None:
        """Place an alert whose producer put its geometry in a separate file."""
        if not rings:
            return
        target = self.infos[0]
        area = target.areas[0] if target.areas else Area(desc=target.event)
        if not target.areas:
            target.areas.append(area)
        area.polygons.extend(rings)
        self.notes.append(f"geometry taken from the producer's polygon sidecar ({len(rings)})")

    def simplify(
        self,
        tolerance: float = SIMPLIFY_TOLERANCE_DEG,
        above: int = SIMPLIFY_ABOVE,
    ) -> None:
        """Reduce oversized rings for the renderer, and SAY that it happened.

        Called by the ingest, not by the parser: a reader of CAP should return
        what the producer issued, and thinning geometry is a pipeline decision
        about a frame budget. The note it leaves travels with the alert to the
        client, so a polygon that has been thinned can never be presented as
        the boundary the agency drew.
        """
        before = after = 0
        for info in self.infos:
            for area in info.areas:
                for i, ring in enumerate(area.polygons):
                    if len(ring) <= above:
                        continue
                    thinner = simplify_ring(ring, tolerance)
                    before += len(ring)
                    after += len(thinner)
                    area.polygons[i] = thinner
        if before:
            self.notes.append(
                f"geometry simplified for rendering, {before} points to {after} "
                f"at a {tolerance} degree tolerance (about "
                f"{tolerance * 111:.1f} km); the issued boundary is finer than this"
            )

    def is_live(self, now: datetime) -> bool:
        """Actual, a warning, and inside its own time window.

        Cancellation and supersession are NOT decided here: they depend on the
        other messages in the batch, so `active()` owns them.
        """
        if self.status != "Actual":
            return False
        if self.msg_type not in WARNING_MSG_TYPES:
            return False
        if self.effective and now < self.effective:
            return False
        if self.expires and now >= self.expires:
            return False
        return True

    def as_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "sender": self.sender,
            "sent": _iso(self.sent),
            "status": self.status,
            "msg_type": self.msg_type,
            "scope": self.scope,
            "references": self.references,
            "source": self.source,
            "event": self.event,
            "severity": self.severity,
            "severity_rank": severity_rank(self.severity),
            "urgency": self.urgency,
            "certainty": self.certainty,
            "effective": _iso(self.effective),
            "expires": _iso(self.expires),
            "languages": self.languages,
            "infos": [i.as_dict() for i in self.infos],
            "areas": [a.as_dict() for a in self.geometry()],
            "notes": self.notes,
        }


@dataclass
class Refusals:
    """Why an alert is not on the globe. Counted, never swallowed."""

    #: status is Exercise, Test, Draft or System. A drill, not a hazard.
    not_actual: int = 0
    #: msgType is Cancel, Ack or Error: bookkeeping rather than a warning.
    not_a_warning: int = 0
    #: Withdrawn by a later Cancel that references it.
    cancelled: int = 0
    #: Replaced by a later Update that references it.
    superseded: int = 0
    expired: int = 0
    not_yet_effective: int = 0
    #: Live and real, but with no geometry this tool can place on a globe.
    #: Still served, because a warning you cannot draw is still a warning; the
    #: banner lists it and says it has no polygon.
    not_drawable: int = 0

    @property
    def total(self) -> int:
        return (
            self.not_actual
            + self.not_a_warning
            + self.cancelled
            + self.superseded
            + self.expired
            + self.not_yet_effective
        )

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "not_actual": self.not_actual,
            "not_a_warning": self.not_a_warning,
            "cancelled": self.cancelled,
            "superseded": self.superseded,
            "expired": self.expired,
            "not_yet_effective": self.not_yet_effective,
            "not_drawable": self.not_drawable,
        }


def _parse_area(node: ET.Element, notes: list[str]) -> Area:
    area = Area(desc=_text(node, "areaDesc"))
    for poly in _children(node, "polygon"):
        ring = _ring(poly.text or "", notes)
        if ring and ring not in area.polygons:
            area.polygons.append(ring)
    for circ in _children(node, "circle"):
        parts = (circ.text or "").split()
        if len(parts) != 2:
            notes.append(f"circle {circ.text!r} is not 'lat,lon radius'; dropped")
            continue
        centre = _coordinates(parts[0], notes)
        try:
            radius_km = float(parts[1])
        except ValueError:
            notes.append(f"circle radius {parts[1]!r} is not numeric; dropped")
            continue
        if centre and radius_km > 0:
            area.circles.append((centre[0][0], centre[0][1], radius_km))
    for geo in _children(node, "geocode"):
        name = _text(geo, "valueName")
        value = _text(geo, "value")
        if name:
            area.geocodes[name] = value
    return area


def _parse_info(node: ET.Element, notes: list[str]) -> Info:
    info = Info(
        language=_text(node, "language", "en-US"),
        category=_text(node, "category"),
        event=_text(node, "event"),
        urgency=_vocabulary(_text(node, "urgency"), URGENCIES, "urgency", notes),
        severity=_vocabulary(_text(node, "severity"), SEVERITIES, "severity", notes),
        certainty=_vocabulary(_text(node, "certainty"), CERTAINTIES, "certainty", notes),
        effective=parse_time(_text(node, "effective")),
        onset=parse_time(_text(node, "onset")),
        expires=parse_time(_text(node, "expires")),
        headline=_text(node, "headline"),
        description=_text(node, "description"),
        instruction=_text(node, "instruction"),
        web=_text(node, "web"),
    )
    for param in _children(node, "parameter"):
        name = _text(param, "valueName")
        if name:
            info.parameters[name] = _text(param, "value")
    for area in _children(node, "area"):
        info.areas.append(_parse_area(area, notes))
    return info


#: `sender,identifier,sent` triples, separated by whitespace. A Cancel may
#: withdraw a whole batch at once, which is why this returns a list.
_REFERENCE = re.compile(r"\S+")


def parse_alert(raw: bytes | str, *, source: str = "") -> Alert:
    """One CAP document into an Alert, or CapError.

    Refuses rather than guesses. A truncated file, an HTML error page served
    where XML was expected, and an alert with no info block are all things this
    will not turn into a warning.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CapError(f"not well-formed XML: {exc}") from None

    if _localname(root.tag) != "alert":
        raise CapError(
            f"root element is <{_localname(root.tag)}>, not <alert>; this is not a CAP document"
        )

    notes: list[str] = []
    infos = [_parse_info(n, notes) for n in _children(root, "info")]
    if not infos:
        # CAP permits it for a Cancel, but an alert with no info carries no
        # hazard, and treating the empty case as a Minor warning would put an
        # unexplained polygon on a globe.
        raise CapError(
            f"CAP alert {_text(root, 'identifier')!r} has no <info> block, so it "
            "states no hazard and cannot be shown"
        )

    references = [
        part.split(",")[1].strip()
        for part in _REFERENCE.findall(_text(root, "references"))
        if len(part.split(",")) >= 2 and part.split(",")[1].strip()
    ]

    return Alert(
        identifier=_text(root, "identifier"),
        sender=_text(root, "sender"),
        sent=parse_time(_text(root, "sent")),
        status=_vocabulary(_text(root, "status"), STATUSES, "status", notes),
        msg_type=_vocabulary(_text(root, "msgType"), MSG_TYPES, "msgType", notes),
        scope=_text(root, "scope"),
        references=references,
        infos=infos,
        source=source,
        notes=notes,
    )


def parse_polygon_sidecar(raw: bytes | str) -> list[list[tuple[float, float]]]:
    """SACHET's separate geometry file: bare `<alert><polygon>...`.

    Not in the CAP namespace, and it repeats the identical ring, both of which
    are real and both of which are pinned by tests. Duplicates are dropped here
    so an alert is not drawn twice over itself at double the opacity.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CapError(f"polygon sidecar is not well-formed XML: {exc}") from None

    notes: list[str] = []
    rings: list[list[tuple[float, float]]] = []
    for node in root.iter():
        if _localname(node.tag) != "polygon":
            continue
        ring = _ring(node.text or "", notes)
        if ring and ring not in rings:
            rings.append(ring)
    return rings


def active(
    alerts: list[Alert],
    *,
    now: datetime,
    allow_exercise: bool = False,
) -> tuple[list[Alert], Refusals]:
    """The alerts that may be drawn, and a counted reason for every one that may not.

    `allow_exercise` exists so a rehearsal can show a drill deliberately. It
    does not hide the fact: an alert returned under it keeps its own status,
    and the panel that draws it is required to say so.
    """
    refusals = Refusals()

    # Two passes, because whether an alert survives depends on messages that
    # may appear after it in the batch.
    cancelled: set[str] = set()
    superseded: set[str] = set()
    for a in alerts:
        if a.msg_type == "Cancel":
            cancelled.update(a.references)
        elif a.msg_type == "Update":
            superseded.update(a.references)

    live: list[Alert] = []
    for a in alerts:
        if a.identifier in cancelled:
            refusals.cancelled += 1
            continue
        if a.identifier in superseded:
            refusals.superseded += 1
            continue
        if a.msg_type not in WARNING_MSG_TYPES:
            refusals.not_a_warning += 1
            continue
        if a.status != "Actual" and not (allow_exercise and a.status == "Exercise"):
            refusals.not_actual += 1
            continue
        if a.effective and now < a.effective:
            refusals.not_yet_effective += 1
            continue
        if a.expires and now >= a.expires:
            refusals.expired += 1
            continue
        if not a.geometry():
            # Counted but STILL RETURNED. A live warning with no polygon is a
            # warning the banner has to list; hiding it because we cannot draw
            # it would under-report the hazard, which is the opposite of the
            # error this module exists to prevent.
            refusals.not_drawable += 1
        live.append(a)

    # Worst first, then soonest to expire. A banner shows the top of this list.
    live.sort(
        key=lambda a: (
            -severity_rank(a.severity),
            URGENCIES.index(a.urgency) if a.urgency in URGENCIES else len(URGENCIES),
            a.expires or datetime.max.replace(tzinfo=timezone.utc),
        )
    )
    return live, refusals
