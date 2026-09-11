"""SIG0: potential density anomaly referenced to the surface, as a derived product.

Density is the variable that actually stratifies the ocean. Temperature and
salinity are what we measure; density is what decides whether a column mixes
or holds, where the mixed layer ends, which water mass a parcel belongs to,
and how much energy a storm has to spend to stir cold water up to the surface.
An oceanographer reads it third, after T and S, and reads it constantly.

It is also NEVER MEASURED. There is no density sensor on an Argo float or a
CTD rosette. The quantity is computed from temperature, salinity and pressure
through an equation of state, which makes it the second honest demonstration
of the derived-product extension point beside D26: the field is new, the store
on disk is not, and PS requirement F6's "ML-derived products" clause is
answered with something a reviewer can check rather than something they have
to believe.

WHICH STANDARD, BECAUSE IT MATTERS
----------------------------------
TEOS-10, the Thermodynamic Equation of Seawater 2010 (IOC, SCOR and IAPSO,
2010), through the `gsw` Gibbs SeaWater toolbox. That is the international
standard, adopted in 2009 and the one INCOIS and Argo both work in. The older
EOS-80 (Fofonoff and Millard, 1983) is still widely used and disagrees by
order 0.01 kg/m3 in the open ocean, which is small and is not nothing when the
whole vertical range of the anomaly is about 7 kg/m3.

`gsw` is not a new dependency. app/argo.py already uses it to turn Argo's
pressure into depth, so the same library that defines our vertical coordinate
defines our density, and the two cannot disagree about what a decibar is.

The chain, and every step of it changes the answer:

    depth, latitude        -> pressure            gsw.p_from_z
    practical salinity, p  -> Absolute Salinity   gsw.SA_from_SP
    in-situ temperature    -> Conservative Temp   gsw.CT_from_t
    SA, CT                 -> sigma-0             gsw.sigma0

Skipping the two conversions in the middle and feeding practical salinity and
in-situ temperature straight into the density function is the commonest
shortcut in this calculation. It produces numbers that look entirely
reasonable on a colour map and are wrong in the second decimal.

WHAT IS SERVED IS SIGMA-0, AND THE REFERENCE IS A CHOICE
--------------------------------------------------------
Sigma-0 is the potential density anomaly referenced to 0 dbar: the density a
parcel would have if moved adiabatically to the surface, minus 1000 kg/m3.
The subtraction is convention, and it is why the served numbers run about 20
to 28 rather than about 1020 to 1028.

The reference level is load-bearing. Sigma-0 is the right variable for the
upper ocean and the WRONG one in the deep, where seawater's compressibility
makes it misrank water masses; below roughly 1000 m an oceanographer switches
to sigma-2 or sigma-4. Our cube reaches 2000 m, so that caveat applies to the
bottom third of it and is served with the field rather than left for someone
to remember.

WHAT IT REFUSES TO TIDY UP
--------------------------
The Bay of Bengal is the freshest large bay in the world: the Ganges,
Brahmaputra and Irrawaddy put a warm fresh lid on it, and the INCOIS analysis
resolves that lid. At 15.5 N, 88.5 E on 2026-07-30 the analysis puts water at
10 m that is both warmer and fresher than the water at 5 m, so it is lighter,
sitting underneath. That column is statically unstable in its top 20 m.

That is a real property of a smoothed 10-day, 1-degree gridded analysis, not
an error in this code, and a gridded analysis is under no obligation to be
statically stable. So the field is served exactly as the equation of state
gives it, and the count of unstable columns travels with it in the notes. The
alternative, sorting each column into stable order, would replace a fact about
INCOIS's product with a number we invented.
"""

from __future__ import annotations

import numpy as np

#: The reference pressure, in decibars. 0 dbar is the surface: sigma-0.
REFERENCE_DBAR = 0.0

STANDARD = "TEOS-10 (IOC, SCOR and IAPSO, 2010) via the gsw Gibbs SeaWater toolbox"

METHOD = (
    "potential density anomaly referenced to 0 dbar (sigma-0), TEOS-10: "
    "pressure from depth and latitude (gsw.p_from_z), practical to Absolute "
    "Salinity (gsw.SA_from_SP), in-situ to Conservative Temperature "
    "(gsw.CT_from_t), then gsw.sigma0; a cell needs BOTH temperature and "
    "salinity, and columns are never sorted into stable order"
)

REFERENCE_NOTE = (
    "Referenced to 0 dbar. Sigma-0 compares water masses correctly in the "
    "upper ocean and misranks them in the deep, where compressibility "
    "dominates; below roughly 1000 m an oceanographer would use sigma-2 or "
    "sigma-4 instead. This cube reaches 2000 m."
)


def sigma0_field(temp, sal, depth, lat, lon) -> np.ndarray:
    """Sigma-0 on a (depth, lat, lon) grid, NaN wherever it is not defined.

    `temp` is in-situ temperature in degC and `sal` is PRACTICAL salinity,
    both shaped (depth, lat, lon) with NaN for missing. `depth` is metres
    positive down; `lat` and `lon` are the grid's own coordinate vectors, in
    degrees.

    A cell needs both temperature and salinity to be finite. Density from one
    of them is not a partial answer, it is a different quantity.
    """
    import gsw

    temp = np.asarray(temp, dtype="float64")
    sal = np.asarray(sal, dtype="float64")
    depth = np.asarray(depth, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")

    if temp.shape != sal.shape:
        raise ValueError(f"TEMP {temp.shape} and SAL {sal.shape} must be the same grid")
    if temp.ndim != 3:
        raise ValueError(f"expected (depth, lat, lon); got {temp.shape}")
    nz, ny, nx = temp.shape
    if (depth.size, lat.size, lon.size) != (nz, ny, nx):
        raise ValueError(
            f"coordinates {depth.size, lat.size, lon.size} do not match the "
            f"field {temp.shape}"
        )

    # Broadcast the coordinates onto the grid. Latitude down axis 1 and
    # longitude along axis 2, which is the whole content of the
    # transposed-broadcast bug: getting it backwards puts the northern
    # latitude on the eastern column and nothing downstream looks wrong.
    depth3 = depth.reshape(nz, 1, 1)
    lat3 = lat.reshape(1, ny, 1)
    lon3 = lon.reshape(1, 1, nx)

    # Pressure from depth AND latitude, because gravity varies with latitude
    # and the demo box spans 5 N to 25 N. At 2000 m the difference between
    # metres and decibars is about 21 dbar, an error that is small, confident
    # and undetectable downstream. This is the exact inverse of the conversion
    # app/argo.py applies to Argo pressure, deliberately: one library, one
    # definition of a decibar.
    pressure = np.broadcast_to(
        gsw.p_from_z(-depth3, np.broadcast_to(lat3, (nz, ny, 1))), (nz, ny, nx)
    )

    # Only finite cells enter the equation of state. An infinity would not be
    # excluded by NaN propagation: it would travel through the polynomial and
    # emerge as a finite-looking absurdity or as a warning we acted on by
    # accident rather than by rule.
    usable = np.isfinite(temp) & np.isfinite(sal)
    out = np.full(temp.shape, np.nan, dtype="float64")
    if not usable.any():
        return out

    t_ok = temp[usable]
    s_ok = sal[usable]
    p_ok = pressure[usable]
    lat_ok = np.broadcast_to(lat3, temp.shape)[usable]
    lon_ok = np.broadcast_to(lon3, temp.shape)[usable]

    absolute_salinity = gsw.SA_from_SP(s_ok, p_ok, lon_ok, lat_ok)
    conservative_temperature = gsw.CT_from_t(absolute_salinity, t_ok, p_ok)
    out[usable] = gsw.sigma0(absolute_salinity, conservative_temperature)
    return out


#: Below this depth an inversion is no longer attributable to the surface
#: freshwater lens. Chosen from the field itself rather than from taste: in
#: our 2026-07-30 cube the inversions cluster at 5 to 30 m (208 of 213
#: columns) and thin out sharply beneath, which is the monsoon river plume.
SURFACE_LAYER_M = 50.0


def stability_census(sigma0, depth=None) -> dict:
    """How many columns are statically unstable, WHERE, and by how much.

    A column is unstable where a deeper level is LIGHTER than the level above
    it. In a real ocean that overturns within minutes, so finding it in a
    gridded analysis means the analysis is smoothed rather than that the sea
    is upside down.

    THE DEPTH SPLIT IS THE POINT. In our own Bay of Bengal cube 213 of 225 wet
    columns are unstable somewhere, which on its own reads as a broken field.
    208 of those are in the top 30 m, which is the Ganges and Brahmaputra
    plume sitting warm and fresh on the bay in July, and it is the single most
    characteristic feature of this basin. Reporting one number without the
    other would turn the correct answer into an alarming one.

    Adjacent PAIRS only, both finite. Comparing across a missing level would
    manufacture inversions on sparse columns.
    """
    sigma0 = np.asarray(sigma0, dtype="float64")
    finite = np.isfinite(sigma0)
    upper, lower = sigma0[:-1], sigma0[1:]
    pair = finite[:-1] & finite[1:]

    # Positive where the deeper level is lighter: an inversion.
    deficit = np.where(pair, upper - lower, np.nan)
    unstable = np.nan_to_num(deficit, nan=-np.inf) > 0

    wet = finite.any(axis=0)
    flat = unstable.reshape(unstable.shape[0], -1)
    per_column = flat.sum(axis=0)
    worst = float(np.nanmax(deficit)) if np.isfinite(deficit).any() else 0.0

    out = {
        "columns_total": int(wet.size),
        "columns_wet": int(wet.sum()),
        "columns_unstable": int((per_column >= 1).sum()),
        "max_inversion_kg_m3": round(max(worst, 0.0), 4),
    }

    if depth is not None:
        depth = np.asarray(depth, dtype="float64")
        # A pair is identified by its UPPER level, so pair k spans
        # depth[k] to depth[k+1].
        below = depth[:-1] >= SURFACE_LAYER_M
        deep = flat[below]
        out["surface_layer_m"] = SURFACE_LAYER_M
        out["columns_unstable_below_surface_layer"] = int(
            (deep.sum(axis=0) >= 1).sum()
        ) if deep.size else 0
        rows = np.flatnonzero(unstable.reshape(unstable.shape[0], -1).any(axis=1))
        out["inversion_depth_range_m"] = (
            [float(depth[rows[0]]), float(depth[rows[-1] + 1])] if rows.size else None
        )
    return out


def compute(ds):
    """The derived-product entry point: (values, notes)."""
    temp = ds["TEMP"].values
    sal = ds["SAL"].values
    values = sigma0_field(
        temp, sal, ds["depth"].values, ds["lat"].values, ds["lon"].values
    )

    notes = dict(stability_census(values, ds["depth"].values))
    notes["standard"] = STANDARD
    notes["reference"] = REFERENCE_NOTE
    if notes["columns_unstable"]:
        deep = notes.get("columns_unstable_below_surface_layer", 0)
        notes["stability_note"] = (
            f"{notes['columns_unstable']} of {notes['columns_wet']} wet columns "
            f"are statically unstable somewhere, by up to "
            f"{notes['max_inversion_kg_m3']:g} kg/m3, and {deep} of them below "
            f"{SURFACE_LAYER_M:g} m. The shallow ones are the monsoon river "
            "plume sitting warm and fresh on the bay, which is this basin's "
            "defining feature; a smoothed 10-day gridded analysis is under no "
            "obligation to be statically stable. The field is served as the "
            "equation of state gives it and columns are never sorted."
        )
    return values, notes


def register(registry) -> None:
    registry.register_derived_product(
        name="SIG0",
        label="Potential density anomaly (sigma-0)",
        units="kg m-3",
        requires={"TEMP": "degC", "SAL": "1"},
        compute=compute,
        output="column",
        canonical="sea_water_sigma_theta",
        method=METHOD,
        params={"reference_pressure_dbar": REFERENCE_DBAR, "standard": "TEOS-10"},
    )
