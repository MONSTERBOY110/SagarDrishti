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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--steps", type=int, default=3, help="model timesteps to fetch")
    ap.add_argument("--argo-days", type=int, default=3, help="Argo daily files to fetch")
    ap.add_argument("--argo-from", type=str, default=None, help="YYYY-MM-DD to walk back from")
    ap.add_argument("--list-times", action="store_true", help="show the model time axis and exit")
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

    print("\nsummary")
    print(f"  model file : {'ok' if model else 'FAILED'}")
    print(f"  argo files : {len(argo)}")
    if not model or not argo:
        print("\nIncomplete. Nothing downstream will work until both succeed.")
        return 1
    print("\nNext: python tools/preprocess.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
