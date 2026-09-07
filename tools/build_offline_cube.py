"""Build the full offline demo cube (TRD §3) -- PHASE 4.

Scope when implemented: Bay of Bengal + Arabian Sea, one month around a cyclone
event, model T/S/U/V/chl at ~25 depth levels plus every Argo profile in the box
plus the IMD best track, rechunked to zarr at roughly 2-4 GB, shipped on the
demo laptop so the power-round demo touches no network at all (PRD F11).

Phase 1 deliberately stops at tools/preprocess.py over a 3-timestep subset:
a 2-4 GB cube is a packaging job, not a technical risk, and Phase 1 exists to
retire risk.
"""

import sys

if __name__ == "__main__":
    sys.exit(
        "build_offline_cube.py is a Phase 4 deliverable.\n"
        "For Phase 1 use: python tools/fetch_sample.py && python tools/preprocess.py"
    )
