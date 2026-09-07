"""Colorbar mapping (TRD §9, PS requirement F4).

The colorbar is a scientific instrument, not decoration: if a fill cell paints
as a real colour, or a log scale silently clamps, a forecaster reads a number
off the globe that is not there.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.colormap import map_to_rgba


# --- Test 8: colorbar mapping -----------------------------------------------

def test_nan_is_fully_transparent():
    """Land and fill values must never receive a colour."""
    vals = np.array([[20.0, np.nan], [np.nan, 30.0]], dtype="float32")

    rgba = map_to_rgba(vals, vmin=20.0, vmax=30.0, palette="thermal", scale="linear")

    assert rgba.shape == (2, 2, 4)
    assert rgba[0, 1, 3] == 0, "NaN must have alpha 0"
    assert rgba[1, 0, 3] == 0
    assert rgba[0, 0, 3] == 255, "real values must be opaque"
    # a transparent pixel must also be black, so no colour bleeds under blending
    assert tuple(rgba[0, 1, :3]) == (0, 0, 0)


def test_out_of_range_values_clamp_not_wrap():
    vals = np.array([[-5.0, 15.0, 99.0]], dtype="float32")

    rgba = map_to_rgba(vals, vmin=10.0, vmax=20.0, palette="thermal", scale="linear")

    lo = map_to_rgba(np.array([[10.0]], dtype="float32"), 10.0, 20.0, "thermal", "linear")
    hi = map_to_rgba(np.array([[20.0]], dtype="float32"), 10.0, 20.0, "thermal", "linear")
    np.testing.assert_array_equal(rgba[0, 0], lo[0, 0])
    np.testing.assert_array_equal(rgba[0, 2], hi[0, 0])
    assert rgba[0, 0, 3] == 255, "a clamped value is still a value"


def test_linear_mapping_is_monotonic_and_centred():
    vals = np.linspace(10.0, 20.0, 11, dtype="float32").reshape(1, -1)

    rgba = map_to_rgba(vals, vmin=10.0, vmax=20.0, palette="thermal", scale="linear")

    luma = rgba[0, :, :3].astype("f8").sum(axis=1)
    assert np.all(np.diff(luma) >= 0) or np.all(np.diff(luma) <= 0), "palette is not monotonic"
    mid = map_to_rgba(np.array([[15.0]], dtype="float32"), 10.0, 20.0, "thermal", "linear")
    np.testing.assert_array_equal(rgba[0, 5], mid[0, 0])


def test_log_scale_differs_from_linear_and_rejects_nonpositive_range():
    """Chlorophyll is read on a log scale; that is the reason the option exists."""
    vals = np.array([[0.01, 0.1, 1.0, 10.0]], dtype="float32")

    lin = map_to_rgba(vals, 0.01, 10.0, "thermal", "linear")
    log = map_to_rgba(vals, 0.01, 10.0, "thermal", "log")
    assert not np.array_equal(lin, log)

    # The GEOMETRIC mean of the range must land on the palette midpoint:
    # sqrt(0.01 * 10) = 0.3162, and log10 puts that exactly halfway.
    geo = map_to_rgba(np.array([[0.31623]], dtype="float32"), 0.01, 10.0, "thermal", "log")
    half = map_to_rgba(np.array([[0.5]], dtype="float32"), 0.0, 1.0, "thermal", "linear")
    np.testing.assert_allclose(geo[0, 0].astype(int), half[0, 0].astype(int), atol=2)

    with pytest.raises(ValueError, match="positive"):
        map_to_rgba(vals, vmin=0.0, vmax=10.0, palette="thermal", scale="log")


def test_reverse_flips_the_ramp():
    vals = np.array([[10.0, 20.0]], dtype="float32")

    fwd = map_to_rgba(vals, 10.0, 20.0, "thermal", "linear")
    rev = map_to_rgba(vals, 10.0, 20.0, "thermal", "linear", reverse=True)

    np.testing.assert_array_equal(fwd[0, 0], rev[0, 1])
    np.testing.assert_array_equal(fwd[0, 1], rev[0, 0])


def test_degenerate_range_is_rejected():
    """vmin == vmax would divide by zero and paint the whole ocean one colour."""
    with pytest.raises(ValueError, match="vmin"):
        map_to_rgba(np.zeros((2, 2), dtype="float32"), 5.0, 5.0, "thermal", "linear")


def test_oceanographic_palettes_are_available():
    """cmocean/crameri-style names per TRD M3. thermal for temperature, haline
    for salinity -- perceptually uniform, which matters for reading gradients."""
    from app.colormap import PALETTES

    assert {"thermal", "haline", "balance", "deep"} <= set(PALETTES)
    for name in PALETTES:
        out = map_to_rgba(np.array([[0.5]], dtype="float32"), 0.0, 1.0, name, "linear")
        assert out.shape == (1, 1, 4) and out[0, 0, 3] == 255
