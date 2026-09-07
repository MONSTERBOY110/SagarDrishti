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


# --- colour parity between the server and the browser -----------------------
#
# ADR-0005 (accepted 2026-09-07) chose colour parity over following TRD M2's
# "matplotlib colormaps server-side" wording. The reason is not cosmetic: a
# forecaster can open the same field twice, as a WMS layer in QGIS and as a
# slice in our own scene, and if those disagree about which colour 26 degrees
# is, the colorbar stops being a measuring instrument, which is the one thing
# PRD F4 insists it must remain.
#
# The ADR's first draft justified that by saying there is ONE lookup table.
# There are TWO: `PALETTE_STOPS` in app/colormap.py and `STOPS` in
# apps/web/lib/colormap.ts. They are byte-identical today, and they agree
# because somebody kept them in step by hand, which is not a guarantee.
# Generating one from the other would need a build step in a project whose
# whole posture is that the demo runs from a clean checkout with the network
# off, so the tables stay duplicated and these tests are what make a
# divergence a failing build instead of a wrong colour on stage.

#: Repo-relative, resolved by walking up rather than by counting "..", because
#: counting levels is how this test first failed.
WEB_COLORMAP = "apps/web/lib/colormap.ts"


def _client_colormap_path():
    import pathlib

    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / WEB_COLORMAP
        if candidate.is_file():
            return candidate
    raise AssertionError(
        f"could not find {WEB_COLORMAP} above {__file__}. If the client moved, this "
        "test must move with it: it is the only thing keeping the browser's palette "
        "and the server's palette in step (ADR-0005)."
    )


def _stops_from_typescript() -> dict[str, list[tuple[int, int, int]]]:
    """Parse the STOPS table out of apps/web/lib/colormap.ts.

    Deliberately a parse of the real client source rather than a copy of it: a
    copy would be a third table to keep in step, and it would pass while the
    browser did something else entirely.
    """
    import re

    source = _client_colormap_path()
    text = source.read_text(encoding="utf-8")

    block = re.search(
        r"const STOPS:\s*Record<Palette,\s*\[number,\s*number,\s*number\]\[\]>\s*=\s*\{(.*?)\n\};",
        text,
        re.DOTALL,
    )
    assert block, "could not find the STOPS table; has the client colormap been restructured?"

    out: dict[str, list[tuple[int, int, int]]] = {}
    # `name: [ [r, g, b], [r, g, b], ... ],` possibly spread over several lines.
    for name, body in re.findall(r"(\w+):\s*\[(.*?)\]\s*,\s*(?=\w+:|\Z)", block.group(1), re.DOTALL):
        triples = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", body)
        assert triples, f"palette {name} parsed with no stops"
        out[name] = [(int(r), int(g), int(b)) for r, g, b in triples]
    return out


def test_the_client_and_the_server_declare_the_same_palette_stops():
    """The anchor stops must match exactly, palette for palette, stop for stop.

    This is the failure that would actually happen: someone tunes a ramp in one
    file and forgets the other, and the WMS tile and the browser slice then
    disagree about what a value looks like.
    """
    from app.colormap import PALETTE_STOPS

    web = _stops_from_typescript()

    assert set(web) == set(PALETTE_STOPS), (
        f"palette names differ: client has {sorted(set(web) - set(PALETTE_STOPS))} extra, "
        f"server has {sorted(set(PALETTE_STOPS) - set(web))} extra"
    )
    for name, server_stops in PALETTE_STOPS.items():
        assert web[name] == [tuple(s) for s in server_stops], (
            f"palette {name!r} differs between the client and the server:\n"
            f"  server: {server_stops}\n  client: {web[name]}"
        )


def test_the_two_rounding_rules_cannot_produce_a_different_colour():
    """numpy and JavaScript round halves DIFFERENTLY, and both build the LUT.

    `np.round` is round-half-to-EVEN, so 126.5 becomes 126. `Math.round` in the
    browser is round-half-AWAY-FROM-ZERO, so the same 126.5 becomes 127. Any LUT
    entry whose interpolated channel lands exactly on a half would therefore be
    one least-significant bit apart between the tile and the slice.

    No current palette hits such a tie, which is why the parity claim holds
    today. This test is what turns "does not happen to hit one" into "cannot
    ship one": add a palette whose stops interpolate onto a half and it fails
    here rather than in front of a judge with a colour picker.
    """
    from app.colormap import LUT_SIZE, PALETTES, PALETTE_STOPS

    def javascript_lut(stops: list[tuple[int, int, int]]) -> np.ndarray:
        """The client's `lut()` reimplemented exactly, Math.round included."""
        n = len(stops)
        out = np.zeros((LUT_SIZE, 3), dtype="int64")
        for i in range(LUT_SIZE):
            t = i / (LUT_SIZE - 1)
            seg = t * (n - 1)
            a = min(int(np.floor(seg)), n - 2)
            f = seg - a
            for c in range(3):
                value = stops[a][c] + (stops[a + 1][c] - stops[a][c]) * f
                out[i, c] = int(np.floor(value + 0.5))   # Math.round
        return out

    for name, stops in PALETTE_STOPS.items():
        server = PALETTES[name].astype("int64")
        client = javascript_lut(stops)
        delta = np.abs(server - client)
        worst = int(delta.max())
        if worst:
            i, c = (int(v) for v in np.argwhere(delta > 0)[0])
            raise AssertionError(
                f"palette {name!r} renders differently on the server and in the browser: "
                f"lut[{i}] channel {c} is {server[i, c]} server-side and {client[i, c]} "
                f"client-side, because the interpolated value lands on a rounding tie. "
                f"{int((delta > 0).sum())} channel value(s) differ. Nudge a stop by one "
                f"so the interpolation misses the tie, or make both sides round the same way."
            )


def test_a_named_temperature_reads_the_same_colour_on_both_sides():
    """The concrete version of the claim, at the value the demo talks about.

    26 degrees is the isotherm the D26 plugin computes and the number a cyclone
    forecaster cares about, so it is the value most likely to be checked with a
    colour picker against a QGIS layer.
    """
    from app.colormap import LUT_SIZE, PALETTE_STOPS, map_to_rgba

    vmin, vmax, value = 2.0, 30.0, 26.0
    served = map_to_rgba(np.array([[value]], dtype="float64"), vmin, vmax, "thermal")[0, 0]

    # What the browser computes for the same value: normalize, then index.
    t = (value - vmin) / (vmax - vmin)
    index = min(LUT_SIZE - 1, max(0, int(np.floor(t * (LUT_SIZE - 1) + 0.5))))
    stops = PALETTE_STOPS["thermal"]
    seg = (index / (LUT_SIZE - 1)) * (len(stops) - 1)
    a = min(int(np.floor(seg)), len(stops) - 2)
    f = seg - a
    client = [
        int(np.floor(stops[a][c] + (stops[a + 1][c] - stops[a][c]) * f + 0.5)) for c in range(3)
    ]

    assert list(served[:3]) == client, (
        f"26 degC is rgb{tuple(served[:3])} in a WMS tile and rgb{tuple(client)} in the "
        "browser. ADR-0005 exists to make these the same number."
    )
    assert served[3] == 255
