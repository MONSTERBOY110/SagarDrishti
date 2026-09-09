# The committed sample

**614 KB of real data, in the repository on purpose.** `data/raw/` and
`data/cube/` are gitignored because they hold gigabytes of downloads and a
derived store. These three files are the exception, and the reason is CI.

## Why

The browser suite in `e2e/` is the demo-path test. Its assertions are
deliberately claims about the real Bay of Bengal, not about a DOM:

- the surface must be warmer than 2000 m
- the cartouche must cite `incois_argo_10d_VAM`
- a BGC float must be cited to the Sprof files and must actually serve
  chlorophyll, which proves the ADJUSTED product was read
- the 26 degC isosurface must vary in depth, and on 2026-07-10 must come back
  as two separate pieces

Those are the claims worth defending on stage, and every one of them is
unreachable against a synthetic field. CI previously built a small invented
cube, so four of the six browser tests could not pass there however correct the
application was, and the suite only really ran when somebody remembered to run
it locally. With a week to the internal round and a lot of building still to
do, that is the wrong thing to be relying on memory for.

So `tools/preprocess.py --fixtures` now builds from these files. CI gets the
same cube the demo runs on, without ever reaching a government server, which is
also what keeps the job from going red because INCOIS is down.

## What is here

| File | What it is | Size |
|---|---|---|
| `incois_vam_bob.nc` | The INCOIS ERDDAP griddap subset exactly as `tools/fetch_sample.py` downloads it: TEMP and SAL, 3 timesteps ending 2026-07-30, all 24 levels from 5 to 2000 m, Bay of Bengal box | 193 KB |
| `profiles.parquet` | The processed in-situ table: 25 profiles from 17 platforms, QC flags 1 and 2 only, already subset to the demo box and the model's own time window | 421 KB |
| `profiles.provenance.json` | What went into that table, per source | 4 KB |

The profile table is a DERIVED artifact rather than a raw download, and that is
a size decision stated rather than hidden: the Argo daily files are 6.6 MB each
and the BGC synthetic profiles 6 to 7 MB each, so committing the raws would be
tens of megabytes. The parquet carries the same measurements, already filtered
by the same code the demo uses.

The CAP warning bulletins are not here because they are already committed under
`data/warnings/incois/`, which is where they belong.

## Retrieved

2026-09-09, by `tools/fetch_sample.py`. Refresh with:

```
python tools/fetch_sample.py
python tools/preprocess.py
cp data/raw/incois_argo_10d_VAM_bob.nc data/sample/incois_vam_bob.nc
cp data/cube/profiles.parquet          data/sample/profiles.parquet
cp data/cube/profiles.provenance.json  data/sample/profiles.provenance.json
```

Anything asserted in `e2e/` against a specific date or float will need
rechecking after a refresh, which is the cost of testing against real data and
is worth paying.

## Attribution

These are open datasets and each carries an acknowledgement obligation that the
application already prints on screen with every number. Restated here because a
file in a repository is separated from the interface that cites it:

- **INCOIS ERDDAP**, `incois_argo_10d_VAM`: Indian National Centre for Ocean
  Information Services, Ministry of Earth Sciences, Government of India.
  Variational Analysis Method 10-day gridded Argo analysis.
- **Argo**: Argo float data were collected and made freely available by the
  International Argo Program and the national programmes that contribute to it.
  The Argo Program is part of the Global Ocean Observing System. Core profiles
  from the Ifremer GDAC `geo/indian_ocean` daily files; biogeochemical profiles
  from the synthetic profile (Sprof) files.
- **RAMA**: TAO/TRITON, RAMA and PIRATA moored buoy array, NOAA PMEL, served
  via the OSMC ERDDAP. RAMA is supported by NOAA PMEL, India's Ministry of
  Earth Sciences and INCOIS, JAMSTEC, BMKG and CSIRO.
