# Contributing to SagarDrishti

The rules the code comments refer to. Each one is enforced by a test, a guard
or a CI check rather than by good intentions.

## 1. Offline first

Every feature works with `OFFLINE=1`: the local Zarr and Parquet cube, the
rule-based agent, vendored fonts and Cesium assets. The browser suite
(`e2e/demo-path.spec.ts`) fails if a single request leaves the machine, and the
air-gapped compose profile runs the data plane with no network at all.

## 2. No number is invented

The agent (Samudra Sahayak) never computes or invents a figure. Numbers enter
an answer only as tool results, carrying their dataset, timestamp and platform
ID. `services/agent/app/guard.py` checks every finished answer against the tool
results and withholds one that states a number no tool produced.

## 3. Test first on the data plane

Parsers, co-location maths and colorbar mapping are written test first, with
the CF edge cases pinned: `scale_factor` and `add_offset`, `_FillValue`,
depth positive down, and a level refused rather than guessed. Verify before
claiming done: run it and show the output.

## 4. Say what the instrument measures

A quantity is named for what was measured, not for what it stands in for: a
conductivity probe reports a "conductivity-derived salinity proxy", never
"salinity". The same care applies to scores: an analysis that has already
assimilated the floats it is scored against says so, and its score is
"analysis fit", not forecast skill.

## 5. House style

No em or en dashes anywhere in the repository. Colour contrast tokens are
measured against their own ground (`tools/check_contrast.py`).

## Running the checks

```
python -m pytest services/api/tests      # data plane
python -m pytest services/agent/tests    # agent, guard and voice
pnpm e2e                                 # the demo path in a real browser
python tools/check_contrast.py
```
