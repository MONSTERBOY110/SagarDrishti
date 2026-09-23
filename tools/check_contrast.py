"""Every contrast ratio the stylesheet claims is the ratio it actually has.

WHY THIS EXISTS. On 22 September the panel ground inverted from warm manila to
cool slate, and a sweep of the surface found sixty-five sites that the token
change alone would not reach. Two of them would have shipped: an opaque paper
raster whose mean colour was the OLD plate, so the sheet would have stayed
manila whatever `--plate` said, and `--caution-ink`, which every honesty
surface in this build is printed in, falling from 5.1:1 to 1.4:1 while the
figures it qualifies stayed bright.

Both were caught by a human reading carefully. `tools/check_dashes.py` exists
because reading carefully does not scale to the next paragraph somebody types,
and the same is true here: `globals.css` states a measured ratio in a comment
beside almost every colour it defines, and a stated measurement that nobody
re-runs is a claim, not a measurement.

WHAT IT CHECKS

1. Every token below carries a `N.N:1` claim in its own comment.
2. That claim is the real WCAG 2.1 contrast ratio against the ground the token
   is used on, to within a tenth.
3. The ratio clears the floor for what the token does: 4.5:1 where it sets
   text, 3:1 where it draws a mark that carries meaning.

WHAT IT DOES NOT CHECK, said plainly rather than implied: a colour written
inline in a component, a translucent wash composited over something, or a
raster. Those are found by reading, and the note above is about how well that
scales. This covers the tokens, which is where a palette change starts.

Run:  python tools/check_contrast.py
Exit: 0 clean, 1 with every failure named and the correct figure given.
"""

from __future__ import annotations

import pathlib
import re
import sys

CSS = pathlib.Path(__file__).resolve().parents[1] / "apps" / "web" / "app" / "globals.css"

#: token -> (ground token, floor, what it does)
#:
#: The ground matters more than the value. `--caution-stamp` is a perfectly
#: legible colour that would fail on the plate and passes on the water, which
#: is exactly why the reserved ink is kept in two values and why reading a
#: ratio without knowing what it was measured against tells you nothing.
CHECKS: dict[str, tuple[str, float, str]] = {
    "ink": ("plate", 4.5, "labels and values, on the plate"),
    "ink-soft": ("plate", 4.5, "secondary print, on the plate"),
    "ink-faint": ("plate", 4.5, "tertiary print, on the plate"),
    "rule": ("plate", 3.0, "the ruling ink: a mark, never text"),
    "caution": ("plate", 3.0, "reserved ink for rules and marks"),
    "caution-ink": ("plate", 4.5, "reserved ink where it carries TEXT"),
    "caution-stamp": ("abyss", 4.5, "reserved ink on the water"),
}

#: Floors, named once so a failure can quote the rule rather than a number.
FLOOR_TEXT = "WCAG 2.1 AA, 4.5:1 for body text"
FLOOR_MARK = "WCAG 2.1 AA, 3:1 for a non-text mark that carries meaning"


def relative_luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def read_tokens(src: str) -> dict[str, tuple[str, float | None, int]]:
    """Every `--name: #hex;` in the file, with the ratio its comment claims.

    The comment may sit on the same line or on the line before, because the
    file uses both: a one-line token carries its figure inline, and a token
    with a paragraph of reasoning above it carries the figure at the end of
    that paragraph."""
    out: dict[str, tuple[str, float | None, int]] = {}
    lines = src.splitlines()
    for i, line in enumerate(lines):
        m = re.search(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{3,6})\s*;", line)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        claim = re.search(r"([0-9]+(?:\.[0-9]+)?):1", line)
        if not claim:
            # look back over an immediately preceding comment block
            j = i - 1
            while j >= 0 and ("*" in lines[j] or lines[j].strip().startswith("/*")):
                found = re.search(r"([0-9]+(?:\.[0-9]+)?):1", lines[j])
                if found:
                    claim = found
                    break
                j -= 1
        out[name] = (value, float(claim.group(1)) if claim else None, i + 1)
    return out


def main() -> int:
    if not CSS.is_file():
        print(f"no stylesheet at {CSS}")
        return 1
    tokens = read_tokens(CSS.read_text(encoding="utf-8"))

    missing = [t for t in ("plate", "abyss") if t not in tokens]
    if missing:
        print(f"globals.css defines no --{' and no --'.join(missing)}; nothing to measure against")
        return 1

    failures: list[str] = []
    for name, (ground_name, floor, what) in CHECKS.items():
        if name not in tokens:
            failures.append(f"--{name} is gone from globals.css, but {what} still needs a colour")
            continue
        value, claimed, line = tokens[name]
        ground = tokens[ground_name][0]
        actual = ratio(value, ground)
        where = f"{CSS.name}:{line}"

        if claimed is None:
            failures.append(
                f"{where}  --{name} states no measured ratio.\n"
                f"    It is {what}, and against --{ground_name} it measures "
                f"{actual:.1f}:1. Put that in the comment."
            )
            continue
        if abs(actual - claimed) > 0.1:
            failures.append(
                f"{where}  --{name} claims {claimed}:1 and measures {actual:.2f}:1 "
                f"against --{ground_name} ({ground}).\n"
                f"    A stated measurement nobody re-runs is a claim. Correct it to "
                f"{actual:.1f}:1, or change the colour."
            )
        if actual < floor:
            rule = FLOOR_TEXT if floor >= 4.5 else FLOOR_MARK
            failures.append(
                f"{where}  --{name} is {actual:.2f}:1 against --{ground_name}, under {floor}:1.\n"
                f"    It is {what}. {rule}."
            )

    if failures:
        print(f"{len(failures)} contrast problem(s):\n")
        for f in failures:
            print(f"  {f}\n")
        return 1

    lines = ", ".join(
        f"--{n} {ratio(tokens[n][0], tokens[g][0]):.1f}:1" for n, (g, _, _) in CHECKS.items()
    )
    print(f"clean: {len(CHECKS)} tokens measured against their own ground ({lines})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
