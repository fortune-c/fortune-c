"""
make_banner_svg.py – Generate an animated typing banner SVG.

The banner renders:
  Line 1 – greeting ("Hi, I'm Fortunate") typed character-by-character
             with a blinking cursor trailing each character.
  Line 2 – subtitle that fades in after the greeting finishes.

The cursor blinks indefinitely after typing ends.
No JavaScript. Pure SVG + SMIL.

Usage
-----
    python scripts/make_banner_svg.py
    python scripts/make_banner_svg.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import (
    animate,
    cursor_blink_rect,
    el,
    get_palette,
    glow_filter,
    group,
    line_el,
    load_config,
    make_defs,
    ms_to_smil,
    rect,
    set_attr,
    svg_root,
    text_el,
    tspan,
    write_svg,
)


# ─── Character width multiplier for monospace font ────────────────────────────
_MONO_CHAR_RATIO = 0.602   # empirically matches JetBrains Mono at any size


def build_banner_svg(cfg: dict) -> ET.Element:
    """Construct the animated greeting banner SVG.

    Animation sequence
    ------------------
    1. Each character of the greeting appears one by one via individual
       ``<tspan>`` elements, each hidden with ``opacity="0"`` and revealed
       with a SMIL ``<set>`` timed at ``char_index * typing_delay_ms``.
    2. A cursor rect tracks the end of the typed text.
    3. After the greeting finishes, the subtitle fades in over
       ``subtitle_fade_ms``.
    4. The cursor blinks indefinitely.

    Args:
        cfg: Loaded config dict.

    Returns:
        The ``<svg>`` root element.
    """
    banner_cfg = cfg["banner"]
    palette = get_palette(cfg)
    fonts = cfg["fonts"]

    width         = int(banner_cfg["width"])
    height        = int(banner_cfg["height"])
    greeting      = str(banner_cfg["greeting"])
    subtitle      = str(banner_cfg["subtitle"])
    fs_greet      = float(banner_cfg["font_size_greeting"])
    fs_sub        = float(banner_cfg["font_size_subtitle"])
    corner_r      = float(banner_cfg["corner_radius"])
    type_delay_ms = float(banner_cfg["typing_delay_ms"])
    sub_fade_ms   = float(banner_cfg["subtitle_fade_ms"])
    sub_delay_ms  = float(banner_cfg["subtitle_delay_ms"])
    glow_blur     = float(banner_cfg["glow_blur"])
    mono          = fonts["mono"]
    sans          = fonts["sans"]

    # ── Geometry ──────────────────────────────────────────────────────────────
    pad_x = 40.0
    greet_y = height * 0.52    # vertical centre for greeting baseline
    sub_y   = height * 0.80    # vertical centre for subtitle baseline

    char_w = fs_greet * _MONO_CHAR_RATIO  # width of one monospace character

    # ── Root + defs ───────────────────────────────────────────────────────────
    root = svg_root(
        width, height,
        extra_attrs={"aria-label": f"Animated greeting: {greeting}"},
    )
    defs = make_defs(root)

    # Glow filter – applied to the greeting text group
    glow_filter(defs, "banner-glow", blur=glow_blur, color=palette.lavender)

    # ── Background ────────────────────────────────────────────────────────────
    rect(root, 0, 0, width, height, fill=palette.background, rx=corner_r)

    # Subtle top-edge accent bar (3px, full width, lavender)
    rect(root, 0, 0, width, 3, fill=palette.lavender, rx=0)

    # Subtle separator line between greeting and subtitle
    sep_y = (greet_y + sub_y) / 2 - 4
    line_el(root, pad_x, sep_y, width - pad_x, sep_y,
            stroke=palette.surface_alt, stroke_width=1.0)

    # ── Greeting: per-character typing animation ───────────────────────────────
    # We place a single <text> element and use individual <tspan> children,
    # each starting invisible and revealed via <set> at the appropriate time.
    greet_g = group(root, **{"filter": "url(#banner-glow)"})

    greet_text = el(
        "text", greet_g,
        x=str(pad_x),
        y=str(greet_y),
        **{
            "font-family": mono,
            "font-size": str(fs_greet),
            "font-weight": "bold",
            "fill": palette.lavender,
            "dominant-baseline": "auto",
        },
    )

    total_dur_ms = 0.0
    for i, char in enumerate(greeting):
        begin_s = ms_to_smil(i * type_delay_ms)
        span = tspan(greet_text, char, **{"opacity": "0"})
        set_attr(span, "opacity", "1", begin=begin_s)
        total_dur_ms = (i + 1) * type_delay_ms

    # ── Blinking cursor ────────────────────────────────────────────────────────
    # Positioned at the end of the greeting text.
    cursor_x = pad_x + len(greeting) * char_w + 2
    cursor_y = greet_y - fs_greet        # top of the char cell
    cursor_h = fs_greet * 1.1
    cursor_w = char_w * 0.85

    blink_ms = int(cfg["animation"]["ascii_cursor_blink_ms"])
    cursor_blink_rect(
        root,
        cursor_x, cursor_y,
        cursor_w, cursor_h,
        fill=palette.green,
        blink_period_ms=blink_ms,
        begin_ms=int(total_dur_ms),
        blink_forever=True,
    )

    # ── Subtitle: fade in after greeting + extra delay ────────────────────────
    sub_begin_ms = total_dur_ms + sub_delay_ms

    sub_g = group(root, opacity="0")
    animate(
        sub_g, "opacity", "0", "1",
        begin=ms_to_smil(sub_begin_ms),
        dur=ms_to_smil(sub_fade_ms),
    )

    text_el(
        sub_g, subtitle,
        pad_x, sub_y,
        fill=palette.subtext,
        font_family=sans,
        font_size=fs_sub,
        dominant_baseline="auto",
    )

    return root


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Generate the banner SVG.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG.
    """
    cfg = load_config(config_path)
    svg_el = build_banner_svg(cfg)

    output_path = _PROJECT_ROOT / "generated" / "banner.svg"
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an animated typing banner SVG."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
