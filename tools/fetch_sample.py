"""Download a small real sample from the PS-official sources (TRD M1/§3).

THIS IS THE ONLY FILE IN THE REPO THAT TOUCHES THE NETWORK. Everything else --
the API, the tests, the renderer -- reads what this leaves in data/raw/. That
is what makes OFFLINE=1 the default posture rather than a mode we remember to
switch on (PRD F11).

Sources (both open, no credentials -- see docs/adr/0003):
  * INCOIS ERDDAP griddap `incois_argo_10d_VAM`: 4D TEMP/SAL, 24 levels 5-2000 m
  * Argo GDAC (Ifremer) geo/indian_ocean daily profile files

Usage:
    python tools/fetch_sample.py                 # 3 model steps + 3 Argo days
    python tools/fetch_sample.py --steps 6
    python tools/fetch_sample.py --list-times    # just show what is available
"""

from __future__ import annotations

import argparse
import json
import sys
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


def _get(url: str, dest: Path, label: str) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {label}\n    <- {url}")
    try:
        with urlopen(url, timeout=TIMEOUT) as r, dest.open("wb") as f:
            total = 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                total += len(chunk)
    except HTTPError as e:
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--steps", type=int, default=3, help="model timesteps to fetch")
    ap.add_argument("--argo-days", type=int, default=3, help="Argo daily files to fetch")
    ap.add_argument("--argo-from", type=str, default=None, help="YYYY-MM-DD to walk back from")
    ap.add_argument("--list-times", action="store_true", help="show the model time axis and exit")
    ap.add_argument("--no-bgc", action="store_true", help="skip the BGC synthetic profiles")
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

    print("\nsummary")
    print(f"  model file : {'ok' if model else 'FAILED'}")
    print(f"  argo files : {len(argo)}")
    print(f"  bgc files  : {len(bgc)}"
          f"{'  (none found in the demo box)' if not bgc else ''}")
    if not model or not argo:
        print("\nIncomplete. Nothing downstream will work until both succeed.")
        return 1
    print("\nNext: python tools/preprocess.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
