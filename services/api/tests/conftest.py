"""Test fixtures for the SagarDrishti data plane.

Every fixture here is built in code rather than committed as a binary, so the
suite is hermetic and CI never touches INCOIS. The synthetic files deliberately
reproduce defects observed in the LIVE sources on 2026-09-07 (see
docs/adr/0003-incois-vam-primary-field.md):

  * TEMP.units == "degs"          -- not a CF/UDUNITS unit string
  * _FillValue == -9999.0         -- and -1.0E34 in the value-added datasets
  * ZAX has no `positive` attr    -- so the vertical axis cannot be inferred
  * scale_factor / add_offset     -- packed integers, as ERDDAP often serves

If a fixture stops matching the real source, the tests are lying. Re-probe the
source before "fixing" a test.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from netCDF4 import Dataset as NCDataset

# Bay of Bengal spike box, matching data/sources.yaml defaults.demo_bbox
LATS = np.array([10.5, 11.5, 12.5, 13.5], dtype="float64")
LONS = np.array([85.5, 86.5, 87.5], dtype="float64")
ZAX = np.array([5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0], dtype="float64")
# seconds since 1970-01-01, three 10-day steps ending 2026-07-30 (the real latest)
TIMES = np.array([1783641600.0, 1784505600.0, 1785369600.0], dtype="float64")

FILL = -9999.0


def _temp_field() -> np.ndarray:
    """A plausible tropical water column: warm mixed layer, sharp thermocline."""
    nt, nz, ny, nx = len(TIMES), len(ZAX), len(LATS), len(LONS)
    prof = 29.2 - 24.0 * (1.0 - np.exp(-ZAX / 350.0))  # 29.2 C at 5 m -> ~5 C at 1000 m
    field = np.broadcast_to(prof[None, :, None, None], (nt, nz, ny, nx)).astype("float32").copy()
    field += np.linspace(0.0, 0.3, nt)[:, None, None, None].astype("float32")
    return field


@pytest.fixture
def vam_like_nc(tmp_path):
    """INCOIS incois_argo_10d_VAM look-alike, with its real CF defects."""
    path = tmp_path / "vam_like.nc"
    data = _temp_field()
    # A land/no-data cell, as the real analysis has over the Andaman landmass.
    data[:, :, 0, 0] = FILL

    with NCDataset(path, "w") as nc:
        nc.createDimension("time", len(TIMES))
        nc.createDimension("ZAX", len(ZAX))
        nc.createDimension("latitude", len(LATS))
        nc.createDimension("longitude", len(LONS))

        t = nc.createVariable("time", "f8", ("time",))
        t.units = "seconds since 1970-01-01T00:00:00Z"
        t.standard_name = "time"
        t.long_name = "TAXIS"
        t[:] = TIMES

        z = nc.createVariable("ZAX", "f8", ("ZAX",))
        z.units = "METERS"          # not "m"
        z.long_name = "ZAX"
        # NOTE: no `positive`, no `standard_name`, no `axis` -- exactly as observed.
        z[:] = ZAX

        la = nc.createVariable("latitude", "f8", ("latitude",))
        la.units = "degrees_north"
        la.standard_name = "latitude"
        la[:] = LATS

        lo = nc.createVariable("longitude", "f8", ("longitude",))
        lo.units = "degrees_east"
        lo.standard_name = "longitude"
        lo[:] = LONS

        # netCDF4 requires _FillValue at creation time, not via setncattr.
        v = nc.createVariable(
            "TEMP", "f4", ("time", "ZAX", "latitude", "longitude"),
            fill_value=np.float32(FILL),
        )
        v.units = "degs"            # not a CF unit
        v.long_name = "Temperature"
        v[:] = data

    return path


@pytest.fixture
def packed_nc(tmp_path):
    """A packed-integer variable: scale_factor + add_offset + integer _FillValue.

    ERDDAP and many operational NetCDF products serve fields this way. The
    classic bug is applying the scaling twice, or applying it to the fill value.
    """
    path = tmp_path / "packed.nc"
    scale, offset, ifill = 0.01, 15.0, -32768
    # true values, then the packed integers that represent them
    true_vals = np.array([[15.0, 20.0, 25.5], [28.25, 29.0, np.nan]], dtype="float64")
    packed = np.where(
        np.isnan(true_vals), ifill, np.round((true_vals - offset) / scale)
    ).astype("i2")

    with NCDataset(path, "w") as nc:
        nc.createDimension("y", 2)
        nc.createDimension("x", 3)
        v = nc.createVariable("sst", "i2", ("y", "x"), fill_value=np.int16(ifill))
        v.units = "degC"
        v.scale_factor = scale
        v.add_offset = offset
        # netCDF4-python auto-PACKS on write when scale_factor/add_offset are
        # set. Writing already-packed integers through that would pack them
        # twice, so turn it off and lay the exact bytes down ourselves.
        v.set_auto_maskandscale(False)
        v[:] = packed

    return path, true_vals


@pytest.fixture
def argo_like_nc(tmp_path):
    """Argo GDAC multi-profile look-alike (N_PROF x N_LEVELS).

    Mirrors the structure of geo/indian_ocean/YYYY/MM/YYYYMMDD_prof.nc:
    PLATFORM_NUMBER as fixed-width char, PRES in dbar (NOT metres), per-value
    QC flags as single characters, and *_ADJUSTED variants.

    Three profiles:
      0  WMO 2902746 -- good, QC flags all "1"
      1  WMO 5906521 -- mixed: some levels flagged "4" (bad) and "3" (dubious)
      2  WMO 2902746 -- second profile from the same float, later in the day
    """
    path = tmp_path / "argo_like.nc"
    n_prof, n_lev = 3, 6
    pres = np.array(
        [
            [5.0, 10.0, 20.0, 50.0, 100.0, 200.0],
            [4.8, 9.9, 25.0, 60.0, 120.0, 250.0],
            [5.1, 11.0, 21.0, 49.0, 99.0, 199.0],
        ],
        dtype="float32",
    )
    temp = np.array(
        [
            [29.10, 29.05, 28.90, 27.10, 22.40, 15.20],
            [29.20, 29.15, 28.40, 26.50, 21.90, 14.80],
            [29.05, 29.00, 28.85, 27.00, 22.30, 15.10],
        ],
        dtype="float32",
    )
    psal = np.full((n_prof, n_lev), 34.5, dtype="float32")

    # Per-level QC. Profile 1 has a bad level (4) and a dubious one (3).
    temp_qc = np.array([list("111111"), list("114131"), list("111111")], dtype="S1")

    wmos = ["2902746", "5906521", "2902746"]
    juld = np.array([27969.0, 27969.1, 27969.5], dtype="float64")  # days since 1950-01-01 -> 2026-07-30
    lat = np.array([12.5, 15.2, 12.6], dtype="float64")
    lon = np.array([86.5, 88.1, 86.6], dtype="float64")

    with NCDataset(path, "w") as nc:
        nc.createDimension("N_PROF", n_prof)
        nc.createDimension("N_LEVELS", n_lev)
        nc.createDimension("STRING8", 8)

        pn = nc.createVariable("PLATFORM_NUMBER", "S1", ("N_PROF", "STRING8"))
        for i, w in enumerate(wmos):
            pn[i, :] = np.array(list(w.ljust(8)), dtype="S1")

        j = nc.createVariable("JULD", "f8", ("N_PROF",))
        j.units = "days since 1950-01-01 00:00:00 UTC"
        j.standard_name = "time"
        j[:] = juld

        for name, arr, unit in (
            ("LATITUDE", lat, "degree_north"),
            ("LONGITUDE", lon, "degree_east"),
        ):
            v = nc.createVariable(name, "f8", ("N_PROF",))
            v.units = unit
            v[:] = arr

        p = nc.createVariable("PRES", "f4", ("N_PROF", "N_LEVELS"))
        p.units = "decibar"
        p.long_name = "Sea water pressure, equals 0 at sea-level"
        p[:] = pres

        t = nc.createVariable("TEMP", "f4", ("N_PROF", "N_LEVELS"))
        t.units = "degree_Celsius"
        t[:] = temp

        s = nc.createVariable("PSAL", "f4", ("N_PROF", "N_LEVELS"))
        s.units = "psu"
        s[:] = psal

        for name, src in (("TEMP_QC", temp_qc), ("PRES_QC", np.full((n_prof, n_lev), b"1", dtype="S1")),
                          ("PSAL_QC", np.full((n_prof, n_lev), b"1", dtype="S1"))):
            q = nc.createVariable(name, "S1", ("N_PROF", "N_LEVELS"))
            q[:] = src

    return path


@pytest.fixture
def cube_dir(tmp_path):
    """A tiny normalized zarr cube, as tools/preprocess.py would write it."""
    from app.provenance import write_provenance

    root = tmp_path / "cube"
    root.mkdir()
    field = _temp_field()
    # Post-normalization, the source's -9999 land cell is NaN. Keep it, so the
    # API's null-masking is exercised against a real hole in the grid.
    field[:, :, 0, 0] = np.nan
    ds = xr.Dataset(
        {"TEMP": (("time", "depth", "lat", "lon"), field)},
        coords={
            "time": ("time", np.array(TIMES, dtype="datetime64[s]").astype("datetime64[ns]")),
            "depth": ("depth", ZAX),
            "lat": ("lat", LATS),
            "lon": ("lon", LONS),
        },
    )
    ds.TEMP.attrs.update(units="degC", long_name="Temperature")
    ds.depth.attrs.update(units="m", positive="down", standard_name="depth")
    ds.attrs["source_id"] = "incois_vam_argo"
    store = root / "incois_vam_bob.zarr"
    ds.to_zarr(store, mode="w")
    write_provenance(
        store,
        source_id="incois_vam_argo",
        title="INCOIS Argo 10-day gridded analysis (test fixture)",
        citation="test fixture -- not real data",
        variables=["TEMP"],
        extra={"fixture": True},
    )
    return root


@pytest.fixture
def client(cube_dir, monkeypatch):
    """TestClient with settings pointed at the fixture cube."""
    from starlette.testclient import TestClient

    from app.config import get_settings

    monkeypatch.setenv("SAGAR_CUBE", str(cube_dir))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def argo_mixed_qc_nc(tmp_path):
    """One profile whose parameters are flagged INDEPENDENTLY of each other.

    This is the shape the real GDAC files have and the shape `argo_like_nc`
    does not: that fixture flags TEMP only and leaves PSAL_QC all "1", which is
    why six passing tests never noticed that salinity was being filtered by
    temperature's flag. Verified against the 10 real Indian Ocean daily files:
    60,643 levels there have a good TEMP flag and a rejected PSAL flag, and the
    rejected salinities include 0.00, 65.53 and 134.12 PSU.

    Six levels, one per case:
      0  PRES 1  TEMP 1  PSAL 1   both good
      1  PRES 1  TEMP 1  PSAL 4   good temperature, REJECTED salinity
      2  PRES 1  TEMP 4  PSAL 1   REJECTED temperature, good salinity
      3  PRES 1  TEMP 3  PSAL 3   both dubious, both rejected
      4  PRES 4  TEMP 1  PSAL 1   no usable pressure: the level has no depth
      5  PRES 1  TEMP 2  PSAL 2   probably-good, which Argo accepts
    """
    path = tmp_path / "argo_mixed_qc.nc"
    n_prof, n_lev = 1, 6

    pres = np.array([[5.0, 10.0, 20.0, 50.0, 100.0, 200.0]], dtype="float32")
    temp = np.array([[29.10, 29.05, 28.90, 27.10, 22.40, 15.20]], dtype="float32")
    # The impossible values sit on the levels whose PSAL flag rejects them, so a
    # leak is unmistakable rather than plausible.
    psal = np.array([[34.50, 134.12, 35.10, 65.53, 34.90, 34.80]], dtype="float32")

    pres_qc = np.array([list("111141")], dtype="S1")
    temp_qc = np.array([list("114312")], dtype="S1")
    psal_qc = np.array([list("141312")], dtype="S1")

    with NCDataset(path, "w") as nc:
        nc.createDimension("N_PROF", n_prof)
        nc.createDimension("N_LEVELS", n_lev)
        nc.createDimension("STRING8", 8)

        pn = nc.createVariable("PLATFORM_NUMBER", "S1", ("N_PROF", "STRING8"))
        pn[0, :] = np.array(list("1902367 "), dtype="S1")

        j = nc.createVariable("JULD", "f8", ("N_PROF",))
        j.units = "days since 1950-01-01 00:00:00 UTC"
        j[:] = np.array([27969.0], dtype="float64")

        for name, value, unit in (
            ("LATITUDE", 5.70, "degree_north"),
            ("LONGITUDE", 88.18, "degree_east"),
        ):
            v = nc.createVariable(name, "f8", ("N_PROF",))
            v.units = unit
            v[:] = np.array([value], dtype="float64")

        p = nc.createVariable("PRES", "f4", ("N_PROF", "N_LEVELS"))
        p.units = "decibar"
        p[:] = pres

        t = nc.createVariable("TEMP", "f4", ("N_PROF", "N_LEVELS"))
        t.units = "degree_Celsius"
        t[:] = temp

        s = nc.createVariable("PSAL", "f4", ("N_PROF", "N_LEVELS"))
        s.units = "psu"
        s[:] = psal

        for name, src in (("PRES_QC", pres_qc), ("TEMP_QC", temp_qc), ("PSAL_QC", psal_qc)):
            q = nc.createVariable(name, "S1", ("N_PROF", "N_LEVELS"))
            q[:] = src

    return path


@pytest.fixture
def argo_bgc_like_nc(tmp_path):
    """Argo BGC synthetic-profile (Sprof) look-alike.

    Reproduces the three properties of the REAL files that decide whether any
    biogeochemistry reaches the screen, all three verified against float
    1902367 in `data/raw/argo_bgc`:

      1. The raw parameter QC is flag 3 on EVERY level, and only the ADJUSTED
         product carries an accepted flag. On the real float that is 13,934
         raw CHLA levels at flag 3 with nothing at 1 or 2, against 13,688
         CHLA_ADJUSTED levels at flag 2. A reader that ignored the adjusted
         product would therefore serve NO chlorophyll at all, which looks like
         a broken pipe rather than a policy.
      2. Raw values are not physical before adjustment: negative chlorophyll
         from fluorometer dark-offset drift, and a pH of -381.
      3. Parameters sample DIFFERENT levels. A BGC sensor runs sparsely
         compared with the CTD, so oxygen exists at levels where temperature
         does not and vice versa.

    Four levels. CHLA is measured on levels 0 and 2 only, DOXY on 1 and 3.
    """
    path = tmp_path / "argo_bgc_like.nc"
    n_prof, n_lev = 1, 4
    nan = np.nan

    pres = np.array([[5.0, 50.0, 150.0, 400.0]], dtype="float32")
    temp = np.array([[28.50, 26.10, 18.20, 10.60]], dtype="float32")
    psal = np.array([[31.90, 34.33, 34.98, 35.03]], dtype="float32")

    # Raw: physically impossible, and flagged 3 throughout.
    chla_raw = np.array([[-0.993, nan, 1.971, nan]], dtype="float32")
    doxy_raw = np.array([[nan, 189.26, -50.0, nan]], dtype="float32")
    ph_raw = np.array([[-381.62, nan, 157.63, nan]], dtype="float32")

    # Adjusted: the values a scientist would actually use.
    chla_adj = np.array([[0.081, nan, 0.412, nan]], dtype="float32")
    doxy_adj = np.array([[nan, 186.40, 1.71, nan]], dtype="float32")
    ph_adj = np.array([[8.021, nan, 7.607, nan]], dtype="float32")

    with NCDataset(path, "w") as nc:
        nc.createDimension("N_PROF", n_prof)
        nc.createDimension("N_LEVELS", n_lev)
        nc.createDimension("STRING8", 8)

        pn = nc.createVariable("PLATFORM_NUMBER", "S1", ("N_PROF", "STRING8"))
        pn[0, :] = np.array(list("2903831 "), dtype="S1")

        j = nc.createVariable("JULD", "f8", ("N_PROF",))
        j.units = "days since 1950-01-01 00:00:00 UTC"
        # A value whose nanosecond tail is float noise: this is what produced
        # the timestamp 14:13:48.001520640 on the real float.
        j[:] = np.array([27967.59291666667], dtype="float64")

        for name, value, unit in (
            ("LATITUDE", 18.09, "degree_north"),
            ("LONGITUDE", 89.84, "degree_east"),
        ):
            v = nc.createVariable(name, "f8", ("N_PROF",))
            v.units = unit
            v[:] = np.array([value], dtype="float64")

        def write(name, values, unit):
            v = nc.createVariable(name, "f4", ("N_PROF", "N_LEVELS"), fill_value=np.float32(99999.0))
            v.units = unit
            v[:] = values

        write("PRES", pres, "decibar")
        write("TEMP", temp, "degree_Celsius")
        write("PSAL", psal, "psu")
        write("CHLA", chla_raw, "mg/m3")
        write("CHLA_ADJUSTED", chla_adj, "mg/m3")
        write("DOXY", doxy_raw, "micromole/kg")
        write("DOXY_ADJUSTED", doxy_adj, "micromole/kg")
        write("PH_IN_SITU_TOTAL", ph_raw, "dimensionless")
        write("PH_IN_SITU_TOTAL_ADJUSTED", ph_adj, "dimensionless")

        good = np.full((n_prof, n_lev), b"1", dtype="S1")
        dubious = np.full((n_prof, n_lev), b"3", dtype="S1")
        accepted = np.full((n_prof, n_lev), b"2", dtype="S1")
        for name, src in (
            ("PRES_QC", good), ("TEMP_QC", good), ("PSAL_QC", good),
            # Raw BGC flags: dubious everywhere, exactly as the real files.
            ("CHLA_QC", dubious), ("DOXY_QC", dubious), ("PH_IN_SITU_TOTAL_QC", dubious),
            # Adjusted flags: accepted.
            ("CHLA_ADJUSTED_QC", accepted),
            ("DOXY_ADJUSTED_QC", good),
            ("PH_IN_SITU_TOTAL_ADJUSTED_QC", accepted),
        ):
            q = nc.createVariable(name, "S1", ("N_PROF", "N_LEVELS"))
            q[:] = src

    return path


@pytest.fixture
def shipped_currents_client(monkeypatch):
    """Pointed at the REAL cube, for the claims that are about real currents.

    Skips rather than passing vacuously when the Copernicus cube is absent: it
    needs an account, and a checkout without one is a normal state that should
    not read as a failure.
    """
    import pathlib

    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    root = pathlib.Path(__file__).resolve().parents[3] / "data" / "cube"
    if not (root / "glorys12_cur_bob.zarr").is_dir():
        pytest.skip(
            "no Copernicus currents cube; needs COPERNICUS_USERNAME and "
            "COPERNICUS_PASSWORD in .env, then tools/fetch_sample.py"
        )

    monkeypatch.setenv("SAGAR_CUBE", str(root))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    clear_caches()
