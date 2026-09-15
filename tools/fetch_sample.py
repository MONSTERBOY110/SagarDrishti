"""Download a small real sample from the PS-official sources (TRD M1/§3).

THIS IS THE ONLY FILE IN THE REPO THAT TOUCHES THE NETWORK. Everything else --
the API, the tests, the renderer -- reads what this leaves in data/raw/. That
is what makes OFFLINE=1 the default posture rather than a mode we remember to
switch on (PRD F11).

Sources. The first four are open and need no credentials (docs/adr/0003):
  * INCOIS ERDDAP griddap `incois_argo_10d_VAM`: 4D TEMP/SAL, 24 levels 5-2000 m
  * Argo GDAC (Ifremer) geo/indian_ocean daily profile files, core and BGC
  * RAMA moored buoys via the OSMC ERDDAP
  * NDMA SACHET, India national CAP alert feed
  * Copernicus Marine GLORYS currents. The ONE source needing an account, and
    the only part of PS requirement F1 no INCOIS source can answer: their free
    ERDDAP publishes surface geostrophic currents only. Credentials live in
    .env, which is gitignored. Absent, the fetch says so and skips.

Usage:
    python tools/fetch_sample.py                 # 3 model steps + 3 Argo days
    python tools/fetch_sample.py --steps 6
    python tools/fetch_sample.py --list-times    # just show what is available
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app.registry import load_registry_from  # noqa: E402

RAW = REPO / "data" / "raw"
TIMEOUT = 180

# Bay of Bengal spike box (data/sources.yaml defaults.demo_bbox)
BBOX = (80.0, 5.0, 95.0, 25.0)  # west, south, east, north


def _get(url: str, dest: Path, label: str, *, empty_is_ok: bool = False) -> bool:
    """Download to `dest`. False on failure, and the reason is printed.

    `empty_is_ok` turns an ERDDAP 404 from an error into a stated fact. ERDDAP
    answers 404 for "your constraints matched no rows", which for a moored
    array is not a fault at all: it means that buoy was not in the water in the
    window asked for. Two of the three Bay of Bengal RAMA moorings answer this
    way today (12n90e stopped 2026-03-10, 8n90e stopped 2025-09-12), and
    printing "!! HTTP 404" for a mooring that is simply not deployed would
    read as a broken fetch rather than as a degraded array.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {label}\n    <- {url}")
    try:
        with urlopen(url, timeout=TIMEOUT) as r, dest.open("wb") as f:
            total = 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                total += len(chunk)
    except HTTPError as e:
        if e.code == 404 and empty_is_ok:
            print("    -- no data in this window (not an error)")
        else:
            print(f"    !! HTTP {e.code} {e.reason}")
        return False
    except URLError as e:
        print(f"    !! network error: {e.reason}")
        return False
    print(f"    -> {dest.relative_to(REPO)}  ({total / 1024:.0f} KB)")
    return True


def erddap_times(base: str, dataset_id: str) -> list[str]:
    """Read the time axis so we ask for steps that actually exist."""
    url = f"{base}/griddap/{dataset_id}.json?time"
    with urlopen(url, timeout=TIMEOUT) as r:
        body = json.load(r)
    return [row[0] for row in body["table"]["rows"]]


def fetch_model(steps: int, list_only: bool = False) -> Path | None:
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    spec = reg.get("incois_vam_argo")
    base, dsid = spec.url, spec.dataset_id

    print(f"INCOIS ERDDAP griddap: {dsid}")
    times = erddap_times(base, dsid)
    print(f"  {len(times)} timesteps available, latest {times[-1]}")
    if list_only:
        for t in times[-8:]:
            print(f"    {t}")
        return None

    if steps < 1:
        # `times[-0:]` is `times[0:]`, which is EVERY timestep. This is the
        # classic Python slice trap and it is not hypothetical: --steps 0,
        # meant as "skip the model", downloaded all 813 steps back to 2004,
        # 52 MB of them, and the next preprocess rebuilt the demo cube around
        # a twenty-two year time axis that the renderer then tried to prefetch
        # in full. Guarded here rather than at the argument parser so no caller
        # of this function can reintroduce it.
        print(f"  --steps {steps} means skip; nothing fetched")
        return None

    w, s, e, n = BBOX
    wanted = times[-steps:]
    # ERDDAP subset syntax: [(start):(stop)] per dimension, in declared order
    # (time, ZAX, latitude, longitude). Asking for both variables in one
    # request keeps the grids identical, which the renderer relies on.
    dim = f"[({wanted[0]}):({wanted[-1]})][(5.0):(2000.0)][({s}):({n})][({w}):({e})]"
    query = f"TEMP{dim},SAL{dim}"
    # Square brackets MUST be percent-encoded: Tomcat rejects raw [ and ] in a
    # query string with a bare 400 before ERDDAP ever sees the request, which
    # looks like a query bug and is not one. Parens and colons stay literal.
    url = f"{base}/griddap/{dsid}.nc?{quote(query, safe='():,.-')}"

    dest = RAW / f"{dsid}_bob.nc"
    return dest if _get(url, dest, f"{steps} steps x 24 levels, BoB {BBOX}") else None


def fetch_argo(days: int, around: date) -> list[Path]:
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    spec = reg.get("argo_gdac_indian")

    print(f"\nArgo GDAC: {spec.url}")
    got: list[Path] = []
    # Walk backwards from `around`: the most recent day is not always posted,
    # and one missing day must not fail the whole fetch.
    day = around
    attempts = 0
    while len(got) < days and attempts < days * 4:
        attempts += 1
        rel = spec.path_template.format(year=day.year, month=day.month, day=day.day)
        url = f"{spec.url}/{rel}"
        dest = RAW / "argo" / Path(rel).name
        if dest.is_file():
            print(f"  {dest.name} already present")
            got.append(dest)
        elif _get(url, dest, f"Indian Ocean profiles for {day.isoformat()}"):
            got.append(dest)
        day -= timedelta(days=1)
    return got


# Argo DATA_CENTRE code -> DAC directory name on the GDAC. Needed because the
# core daily file records the two-letter centre code while the Sprof path uses
# the directory name. Note IN: INCOIS is itself an Argo DAC, which is worth
# knowing on stage.
DAC_DIRECTORY = {
    "AO": "aoml", "BO": "bodc", "CS": "csiro", "HZ": "csio", "IF": "coriolis",
    "IN": "incois", "JA": "jma", "KM": "kma", "KO": "kordi", "ME": "meds",
    "NM": "nmdis", "CI": "csio", "SI": "incois",
}


def _argo_chars(var) -> list[str]:
    """One row of an Argo fixed-width char array -> a stripped string.

    Same three-way decode as app/argo.py:_as_char, kept local so this script
    stays importable without the API package's dependencies.
    """
    import numpy as np

    out = []
    for row in np.asarray(var[:]):
        chars = []
        for c in np.atleast_1d(row):
            if isinstance(c, bytes):
                chars.append(c.decode("ascii", "ignore"))
            elif isinstance(c, str):
                chars.append(c)
            else:
                try:
                    code = int(c)
                except (TypeError, ValueError):
                    continue
                if 0 < code < 128:
                    chars.append(chr(code))
        out.append("".join(chars).strip())
    return out


def discover_bgc_floats(core_files: list[Path]) -> dict[str, str]:
    """WMO -> DAC directory for BGC floats inside the demo box.

    Read out of the core daily files already on disk rather than from a pinned
    list, because a pinned list goes stale the moment a float stops reporting
    and then the BGC panel is empty for a reason nobody can see. PLATFORM_TYPE
    is the discriminator: a BGC float announces itself as SOLO_BGC,
    SOLO_BGC_MRV, PROVOR_BGC and so on.
    """
    import numpy as np
    from netCDF4 import Dataset

    west, south, east, north = BBOX
    found: dict[str, str] = {}
    for path in core_files:
        with Dataset(path) as nc:
            if "PLATFORM_TYPE" not in nc.variables:
                continue
            types = _argo_chars(nc["PLATFORM_TYPE"])
            wmos = _argo_chars(nc["PLATFORM_NUMBER"])
            centres = _argo_chars(nc["DATA_CENTRE"])
            lat = np.asarray(nc["LATITUDE"][:], dtype="float64")
            lon = np.asarray(nc["LONGITUDE"][:], dtype="float64")
            for i, kind in enumerate(types):
                if "BGC" not in kind.upper():
                    continue
                if not (west <= lon[i] <= east and south <= lat[i] <= north):
                    continue
                dac = DAC_DIRECTORY.get(centres[i].upper())
                if dac and wmos[i]:
                    found[wmos[i]] = dac
    return found


def fetch_argo_bgc(core_files: list[Path]) -> list[Path]:
    """Download the Sprof file for each BGC float found in the demo box.

    A BGC float's chlorophyll, oxygen, nitrate and pH are NOT in the core daily
    files: those carry TEMP and PSAL only, so a BGC float looks like an
    ordinary float there. The synthetic profile file is where the
    biogeochemistry lives, and it is per float rather than per day.
    """
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    spec = reg.get("argo_bgc_indian")
    if not spec.enabled:
        print("\nArgo BGC: source disabled in sources.yaml, skipping")
        return []

    floats = dict.fromkeys(spec.platforms)  # pinned floats first, if any
    if floats:
        # A pinned float still needs a DAC; look it up from the core files and
        # fall back to aoml only if the discovery finds nothing for it.
        discovered = discover_bgc_floats(core_files)
        floats = {w: discovered.get(w, "aoml") for w in floats}
        print(f"\nArgo BGC: {len(floats)} pinned float(s) from sources.yaml")
    else:
        floats = discover_bgc_floats(core_files)
        print(f"\nArgo BGC: {len(floats)} BGC float(s) discovered in the demo box "
              f"{BBOX} by PLATFORM_TYPE")

    got: list[Path] = []
    for wmo, dac in sorted(floats.items()):
        rel = spec.path_template.format(dac=dac, wmo=wmo)
        dest = RAW / "argo_bgc" / f"{wmo}_Sprof.nc"
        if dest.is_file():
            print(f"  {dest.name} already present")
            got.append(dest)
        elif _get(f"{spec.url}/{rel}", dest, f"BGC float {wmo} (dac {dac})"):
            got.append(dest)
    return got


#: The Bay of Bengal arm of the RAMA moored array, on the 90 E line. Found by
#: asking the array itself which stations lie in the demo box rather than by
#: pasting a list: tabledap/pmelTaoDyT.json?array,station,latitude,longitude
#: &distinct() returns 154 stations globally, of which exactly three fall
#: inside (80-95 E, 5-25 N).
RAMA_TABLEDAP = "https://osmc.noaa.gov/erddap/tabledap/pmelTaoDyT.nc"
RAMA_STATIONS = "https://osmc.noaa.gov/erddap/tabledap/pmelTaoDyT.json"
RAMA_COLUMNS = (
    "array,station,wmo_platform_code,longitude,latitude,time,depth,T_20,QT_5020"
)


def discover_rama_stations() -> list[str]:
    """Which RAMA moorings are inside the demo box, asked of the array itself."""
    url = RAMA_STATIONS + "?array,station,latitude,longitude&distinct()"
    print(f"\nRAMA moored array: {url}")
    try:
        with urlopen(url, timeout=TIMEOUT) as r:
            table = json.load(r)["table"]
    except (HTTPError, URLError) as e:
        print(f"    !! could not list stations: {e}")
        return []

    west, south, east, north = BBOX
    columns = table["columnNames"]
    i_station = columns.index("station")
    i_lat = columns.index("latitude")
    i_lon = columns.index("longitude")
    inside = [
        str(row[i_station])
        for row in table["rows"]
        if isinstance(row[i_lat], (int, float))
        and isinstance(row[i_lon], (int, float))
        and south <= row[i_lat] <= north
        and west <= row[i_lon] <= east
    ]
    print(
        f"    {len(inside)} of {len(table['rows'])} stations inside {BBOX}: "
        f"{', '.join(inside) or 'none'}"
    )
    return inside


def fetch_moorings(around: date, days: int = 30) -> list[Path]:
    """One NetCDF per RAMA mooring, covering the model window.

    The window is centred on the model's own latest date so the moorings are
    CONTEMPORANEOUS with the field they are drawn beside. That is the property
    the Oceansat-2 chlorophyll source could not offer, and it is the reason
    this source is worth ingesting where that one is not.
    """
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    if not reg.has("rama_mooring_bob"):
        return []
    spec = reg.get("rama_mooring_bob")
    if not spec.enabled:
        print("\nRAMA: source disabled in sources.yaml, skipping")
        return []

    stations = spec.platforms or discover_rama_stations()
    if not stations:
        return []

    start = (around - timedelta(days=days)).isoformat()
    end = (around + timedelta(days=5)).isoformat()

    got: list[Path] = []
    for station in stations:
        dest = RAW / "moorings" / f"rama_{station}.nc"
        if dest.is_file():
            print(f"  {dest.name} already present")
            got.append(dest)
            continue
        # Tomcat rejects a raw quote, < or > in a query string (RFC 7230) and
        # answers a bare HTML 400 that never mentions ERDDAP. Encode those and
        # keep only the separators ERDDAP needs to parse the constraint list.
        constraints = (
            '&station="' + station + '"'
            + f"&time>={start}T00:00:00Z&time<={end}T23:59:59Z"
        )
        url = RAMA_TABLEDAP + "?" + RAMA_COLUMNS + quote(constraints, safe="&=.:-_")
        if _get(
            url,
            dest,
            f"RAMA mooring {station}, {start} to {end}",
            empty_is_ok=True,
        ):
            got.append(dest)

    if got and len(got) < len(stations):
        # Stated rather than left to be inferred from a shorter list. The Bay
        # of Bengal RAMA line has a known loss and vandalism problem, so a
        # partly reporting array is the normal condition, not a fetch bug.
        missing = len(stations) - len(got)
        print(
            f"    {len(got)} of {len(stations)} moorings reported in this window; "
            f"{missing} were not in the water"
        )
    return got


def _dotenv() -> dict[str, str]:
    """Read .env, which is the only place in this repository holding a secret.

    Parsed here rather than exported into the process environment by a shell
    step, so a reader of this file can see exactly which two variables the
    fetch needs and where they come from. `.env` is gitignored.
    """
    path = REPO / ".env"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def fetch_currents(around: date) -> Path | None:
    """Depth-resolved currents from Copernicus Marine (PS requirement F1).

    THE ONE PART OF F1 NO INCOIS SOURCE CAN ANSWER. The problem statement names
    current vectors among the fields to render, and INCOIS's free ERDDAP
    publishes SURFACE geostrophic currents only. This needs a free Copernicus
    account, which is why it was blocked until 2026-09-09.

    Fetched to match the model cube EXACTLY: the same three dates, the same
    Bay of Bengal box. Contemporaneity is not a nicety here. The registry
    originally named the GLORYS12V1 multi-year reanalysis, and probing it with
    real credentials showed it ends 2026-06-23, before every date in this cube;
    an analysis-and-forecast product is configured instead. See the long block
    above this source in data/sources.yaml.

    Credentials never reach a log or an argument: the client reads them from
    the environment we set here, and this function prints only the username's
    presence, never its value.
    """
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    if not reg.has("glorys12_cur"):
        return None
    spec = reg.get("glorys12_cur")
    if not spec.enabled:
        print("\nCurrents: glorys12_cur disabled in sources.yaml, skipping")
        return None

    env = _dotenv()
    user = env.get("COPERNICUS_USERNAME") or os.environ.get("COPERNICUS_USERNAME")
    password = env.get("COPERNICUS_PASSWORD") or os.environ.get("COPERNICUS_PASSWORD")
    if not user or not password:
        print(
            "\nCurrents: no Copernicus credentials. Put COPERNICUS_USERNAME and "
            "COPERNICUS_PASSWORD in .env (free account at data.marine.copernicus.eu). "
            "Everything else still works; this is the only source that needs them."
        )
        return None

    try:
        import copernicusmarine as cm
    except ImportError:
        print(
            "\nCurrents: the copernicusmarine client is not installed. "
            "pip install copernicusmarine"
        )
        return None

    dest = RAW / "glorys" / "glorys12_cur_bob.nc"
    if dest.is_file():
        print(f"\nCurrents: {dest.name} already present")
        return dest

    w, s, e, n = BBOX
    # The model cube's own three steps, so the currents and the field share a
    # time axis and the scrubber cannot show one date above another.
    wanted = [around - timedelta(days=20), around - timedelta(days=10), around]
    print(f"\nCurrents: Copernicus {spec.dataset_id}")
    print(f"  user {user[:2]}{'*' * max(0, len(user) - 2)}, "
          f"{len(wanted)} dates ending {around}, box {BBOX}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        cm.login(username=user, password=password, force_overwrite=True)
        ds = cm.open_dataset(
            dataset_id=spec.dataset_id,
            variables=[v.name for v in spec.variables],
            minimum_longitude=w, maximum_longitude=e,
            minimum_latitude=s, maximum_latitude=n,
            # The demo column is 5 to 2000 m; the product goes to 5728 and
            # those levels would triple the download for water nothing else
            # here draws.
            minimum_depth=0, maximum_depth=2000,
            start_datetime=str(wanted[0]), end_datetime=str(wanted[-1]),
        )
        import pandas as _pd

        sub = ds.sel(time=_pd.to_datetime([str(d) for d in wanted]), method="nearest")
        got = [str(x)[:10] for x in _pd.to_datetime(sub.time.values)]
        sub.to_netcdf(dest)
        ds.close()
    except Exception as exc:  # noqa: BLE001
        # Additive, like BGC and the moorings: a Copernicus outage or a wrong
        # password must not fail a run that already has a working demo.
        print(f"    !! {type(exc).__name__}: {str(exc)[:200]}")
        return None

    print(f"    dates {got}")
    print(f"    -> {dest.relative_to(REPO)}  ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def fetch_insitu_casts() -> list[Path]:
    """Gliders and CTD casts from the Copernicus in-situ TAC (PS F2).

    THE ARCHIVE THE PROBLEM STATEMENT NAMES. SIH26067's own "Dataset Link"
    field lists four sources, and the third is the Ifremer EGO glider FTP. Its
    published index, glider_prof_index.txt, is 248 MB of whitespace: a broken
    build on the publisher's side, checked at four offsets. The same holdings
    are in the Copernicus in-situ TAC, whose index is not broken, so that is
    what this reads.

    THE HISTORY PART, NOT THE LATEST PART. This is the whole reason gliders
    were once written off as unobtainable here. `cmems_obs-ins_...mynrt_na_irr`
    has two parts: `latest`, a rolling thirty-day window, and `history`, the
    archive. Searching `latest` for a glider in the Bay of Bengal returns
    nothing, correctly, and that is not the same fact as there being no glider.
    `history` indexes 89,115 files; five gliders and twenty-four CTD
    collections intersect the demo box.

    Additive, like BGC, the moorings and the currents: a failure here must not
    fail a run that already has a working demo.
    """
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    specs = [reg.get(i) for i in ("cmems_glider_bob", "cmems_ctd_bob")]
    specs = [s for s in specs if s is not None and s.enabled]
    if not specs:
        print("\nCasts: no in-situ TAC source enabled, skipping")
        return []

    env = _dotenv()
    user = env.get("COPERNICUS_USERNAME") or os.environ.get("COPERNICUS_USERNAME")
    password = env.get("COPERNICUS_PASSWORD") or os.environ.get("COPERNICUS_PASSWORD")
    if not user or not password:
        print(
            "\nCasts: no Copernicus credentials. Put COPERNICUS_USERNAME and "
            "COPERNICUS_PASSWORD in .env. Everything else still works."
        )
        return []

    try:
        import copernicusmarine as cm
    except ImportError:
        print("\nCasts: the copernicusmarine client is not installed.")
        return []

    dest = RAW / "insitu"
    dest.mkdir(parents=True, exist_ok=True)
    existing = sorted(dest.glob("*.nc"))
    if existing:
        print(f"\nCasts: {len(existing)} file(s) already present")
        return existing

    # Named rather than discovered, and that is a decision. The box holds five
    # glider files, but three of them are multi-deployment aggregates whose
    # bounding box crosses the Indian Ocean without the glider ever having been
    # in it, and the fourth, GL_PR_GL_SLU29, is the SAME physical glider as
    # ru29 republished by a second data centre with a blank WMO field. Taking
    # every file the index offers would put one glider on the globe twice and
    # three others in water they never flew.
    wanted = ("GL_PR_GL_2801900", "GL_PR_CT_JFCL")
    print("\nCasts: Copernicus in-situ TAC, history part")
    print(f"  user {user[:2]}{'*' * max(0, len(user) - 2)}, {len(wanted)} platform(s)")

    try:
        cm.login(username=user, password=password, force_overwrite=True)
        cm.get(
            dataset_id="cmems_obs-ins_glo_phybgcwav_mynrt_na_irr",
            dataset_part="history",
            regex=r"(" + "|".join(wanted) + r")\.nc$",
            output_directory=dest,
            no_directories=True,
            overwrite=True,
            disable_progress_bar=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"    !! {type(exc).__name__}: {str(exc)[:200]}")
        return []

    got = sorted(dest.glob("*.nc"))
    for f in got:
        print(f"    -> {f.relative_to(REPO)}  ({f.stat().st_size / 1e6:.1f} MB)")
    return got


def fetch_warnings(limit: int) -> list[Path]:
    """CAP v1.2 alerts from NDMA SACHET, India's national CAP backbone (F13).

    TRD M8 planned for curated samples "where a machine feed isn't public".
    Probing on 2026-09-09 found that one IS: SACHET publishes a public RSS
    index of real CAP documents, and it carried 99 live alerts that afternoon
    from CWC, IMD and the state disaster authorities. Reading the real feed
    beats anything we could write, so this is what HazardWatch ingests.

    Two shapes have to be handled, and both are real rather than defensive:

      * The RSS item is an INDEX. The CAP document itself is behind the item's
        link, so this is two requests per alert, not one.
      * SACHET puts the GEOMETRY IN A SEPARATE FILE. The CAP document carries a
        `Polygon URL` parameter instead of an inline `<cap:polygon>`, so an
        alert fetched without its sidecar has no shape at all.

    The ocean hazards the PS names by name (tsunami, high wave, swell surge)
    were NOT on this feed at ingest time and INCOIS's ITEWC publishes no public
    machine feed, so those are the second `kind: cap` source in sources.yaml,
    marked with CAP's own `status: Exercise`. See data/warnings/incois/README.md.
    """
    reg = load_registry_from(REPO / "data" / "sources.yaml")
    if not reg.has("cap_sachet_india"):
        return []
    spec = reg.get("cap_sachet_india")
    if not spec.enabled:
        print("\nCAP: cap_sachet_india disabled in sources.yaml, skipping")
        return []

    out = RAW / "cap" / "sachet"
    out.mkdir(parents=True, exist_ok=True)
    index = out / "_index.rss.xml"

    print(f"\nCAP warnings: NDMA SACHET national feed (newest {limit})")
    if not _get(spec.url, index, "SACHET alert index"):
        return []

    try:
        root = ET.fromstring(index.read_bytes())
    except ET.ParseError as e:
        print(f"    !! the SACHET index is not well-formed XML: {e}")
        return []

    items = root.findall("./channel/item")
    if not items:
        print("    -- the feed carried no alerts (not an error: India can be quiet)")
        return []

    # Newest first is the feed's own order. The cap is STATED rather than
    # applied silently: a reader of this output has to be able to tell
    # "30 alerts" from "30 of 99 alerts".
    if len(items) > limit:
        print(f"    feed carries {len(items)} alerts; taking the {limit} newest")
    items = items[:limit]

    got: list[Path] = []
    for item in items:
        ident = (item.findtext("guid") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not ident or not link:
            continue
        dest = out / f"{ident}.cap.xml"
        if not dest.is_file() and not _get(link, dest, f"CAP {ident}"):
            continue
        got.append(dest)

        # The geometry sidecar. Absent is not a failure: an alert can be
        # geocoded to a named district with no polygon at all, and the parser
        # counts that as "named but not drawable" rather than dropping it.
        poly = out / f"{ident}.polygon.xml"
        if poly.is_file():
            continue
        url = link.replace("FetchXMLFile", "FetchPolygonXMLFile")
        if url != link:
            _get(url, poly, f"  geometry for {ident}", empty_is_ok=True)

    drawable = sum(1 for p in got if (p.parent / p.name.replace(".cap.", ".polygon.")).is_file())
    print(f"    {len(got)} alerts, {drawable} with geometry")
    return got


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--steps", type=int, default=3, help="model timesteps to fetch")
    ap.add_argument("--argo-days", type=int, default=3, help="Argo daily files to fetch")
    ap.add_argument("--argo-from", type=str, default=None, help="YYYY-MM-DD to walk back from")
    ap.add_argument("--list-times", action="store_true", help="show the model time axis and exit")
    ap.add_argument("--no-bgc", action="store_true", help="skip the BGC synthetic profiles")
    ap.add_argument("--no-moorings", action="store_true", help="skip the RAMA moorings")
    ap.add_argument("--no-warnings", action="store_true", help="skip the CAP alert feed")
    ap.add_argument("--no-currents", action="store_true", help="skip the Copernicus currents")
    ap.add_argument("--no-casts", action="store_true", help="skip the glider and CTD casts")
    ap.add_argument("--cap-alerts", type=int, default=30, help="newest CAP alerts to fetch")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)

    model = fetch_model(args.steps, list_only=args.list_times)
    if args.list_times:
        return 0

    # Default to the model's own latest date, so profiles and fields overlap in
    # time -- otherwise the scorecard has nothing to co-locate.
    if args.argo_from:
        around = date.fromisoformat(args.argo_from)
    else:
        times = erddap_times(
            load_registry_from(REPO / "data" / "sources.yaml").get("incois_vam_argo").url,
            "incois_argo_10d_VAM",
        )
        around = date.fromisoformat(times[-1][:10])

    argo = fetch_argo(args.argo_days, around)

    # BGC is additive: the core floats already give a working demo, so a BGC
    # failure must not fail the fetch. It is fetched last for that reason.
    bgc: list[Path] = []
    if argo and not args.no_bgc:
        bgc = fetch_argo_bgc(argo)

    # Moorings are additive too, and fetched last for the same reason as BGC:
    # a failure here must not fail a run that already has a working demo.
    moorings: list[Path] = []
    if not args.no_moorings:
        moorings = fetch_moorings(around)

    # Warnings are additive and fetched last, for the same reason as BGC and
    # the moorings: a feed outage must not fail a run that already has a
    # working demo. HazardWatch also still has its rehearsal bulletins, which
    # live in the repository and need no network at all.
    warnings: list[Path] = []
    if not args.no_warnings:
        warnings = fetch_warnings(args.cap_alerts)

    # Currents last, and additive for the same reason as the rest: this is the
    # only source needing an account, and a checkout without one still has a
    # complete demo of everything INCOIS can answer.
    currents: Path | None = None
    if not args.no_currents:
        currents = fetch_currents(around)

    # The glider and the CTD casts, additive for the same reason as the rest.
    casts: list[Path] = []
    if not args.no_casts:
        casts = fetch_insitu_casts()

    print("\nsummary")
    print(f"  model file : {'ok' if model else 'FAILED'}")
    print(f"  argo files : {len(argo)}")
    print(f"  bgc files  : {len(bgc)}"
          f"{'  (none found in the demo box)' if not bgc else ''}")
    print(f"  moorings   : {len(moorings)}"
          f"{'  (none found in the demo box)' if not moorings else ''}")
    print(f"  cap alerts : {len(warnings)}"
          f"{'  (feed unreachable or quiet; rehearsal bulletins still apply)' if not warnings else ''}")
    print(f"  currents   : {'ok' if currents else 'skipped (no Copernicus credentials)'}")
    print(f"  casts      : {len(casts)}"
          f"{'  (skipped; needs Copernicus credentials)' if not casts else '  (glider + CTD)'}")
    if not model or not argo:
        print("\nIncomplete. Nothing downstream will work until both succeed.")
        return 1
    print("\nNext: python tools/preprocess.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
