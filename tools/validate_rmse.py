"""Validate the model-vs-observation scorecard against published numbers -- PHASE 4.

Scope when implemented (TRD M5, PRIOR-ART.md B.12 -- Ryan et al. 2015 GODAE
OceanView Class 4):

  1. Co-locate the model field to each Argo profile in observation space --
     interpolate to the profile lat/lon/depth/time, never the reverse.
  2. Keep only QC flags 1 and 2 (Wong et al. 2020).
  3. Report per-depth-bin bias, RMSE and correlation by region and variable.
  4. Reproduce a PUBLISHED GLORYS-vs-Argo comparison number within tolerance,
     and print both figures side by side.

Step 4 is the point of this script. A scorecard nobody has checked against an
external reference is a number we cannot defend when a judge asks how we know
it is right.
"""

import sys

if __name__ == "__main__":
    sys.exit("validate_rmse.py is a Phase 4 deliverable (TRD M5).")
