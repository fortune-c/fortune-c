"""
make_tech_stack_svg.py – Generate an animated tech-stack SVG card.

Renders two side-by-side panels inside a terminal-chrome window:
  • Left panel:   "Languages"  – items listed vertically with coloured dots
  • Right panel:  "Tools & Environment" – same style

Each item fades in and slides up with staggered timing, matching the
info-card animation style.

Usage
-----
    python scripts/make_tech_stack_svg.py
    python scripts/make_tech_stack_svg.py --config path/to/config.yaml
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
    animate_transform,
    draw_terminal_chrome,
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
    write_svg,
)


# ─── Accent colours for the item dots (cycling through palette) ──────────────

_DOT_COLOURS = [
    "blue", "green", "peach", "pink", "lavender",
    "teal", "yellow", "sky", "mauve", "sapphire",
]


def _dot_colour(palette, index: int) -> str:
    """Return a cycling accent colour for tech item dots."""
    attr = _DOT_COLOURS[index % len(_DOT_COLOURS)]
    return getattr(palette, attr)


# ═════════════════════════════════════════════════════════════════════════════
#  SVG builder
# ═════════════════════════════════════════════════════════════════════════════

def build_tech_stack_svg(cfg: dict) -> ET.Element:
    """Construct the complete animated tech-stack SVG.

    Args:
        cfg: Loaded config dict.

    Returns:
        The ``<svg>`` root element.
    """
    ts_cfg = cfg.get("tech_stack", {})
    fonts_cfg = cfg["fonts"]
    palette = get_palette(cfg)

    languages: list[str] = ts_cfg.get("languages", [])
    tools: list[str] = ts_cfg.get("tools", [])

    width = int(ts_cfg.get("width", 860))
    padding = int(ts_cfg.get("padding", 24))
    row_height = int(ts_cfg.get("row_height", 30))
    corner_r = int(ts_cfg.get("corner_radius", 10))
    border_w = float(ts_cfg.get("border_width", 1.5))
    font_size_heading = float(ts_cfg.get("font_size_heading", 15))
    font_size_item = float(ts_cfg.get("font_size_item", 13))
    glow_blur = float(ts_cfg.get("glow_blur", 8))
    dot_r = float(ts_cfg.get("dot_radius", 4))

    stagger_ms = int(ts_cfg.get("stagger_ms", 100))
    duration_ms = int(ts_cfg.get("duration_ms", 400))
    initial_delay_ms = int(ts_cfg.get("initial_delay_ms", 200))

    mono = fonts_cfg["mono"]

    title_bar_h = 36
    max_items = max(len(languages), len(tools))

    # heading row + all items + padding top/bottom
    content_h = (
        padding
        + row_height           # heading
        + padding // 2         # gap after heading
        + max_items * row_height  # items
        + padding              # bottom
    )
    total_h = title_bar_h + content_h

    root = svg_root(width, total_h, extra_attrs={"aria-label": "Tech stack card"})
    defs = make_defs(root)

    # Glow filter
    glow_filter(defs, "stack-glow", blur=glow_blur, color=palette.blue)

    # Terminal chrome
    content_g = draw_terminal_chrome(
        root,
        x=0, y=0,
        width=width,
        height=total_h,
        palette=palette,
        corner_radius=corner_r,
        border_width=border_w,
        title="fortune@github:~$ neofetch --stack",
        font_family=mono,
        font_size=12,
        title_bar_height=title_bar_h,
        glow_filter_id="stack-glow",
    )

    half_w = width / 2
    col_left_x = padding
    col_right_x = half_w + padding // 2

    # ── Vertical divider ─────────────────────────────────────────────────
    divider_g = group(content_g, opacity="0")
    animate(divider_g, "opacity", "0", "1",
            begin=ms_to_smil(initial_delay_ms),
            dur=ms_to_smil(duration_ms))
    line_el(
        divider_g,
        half_w, padding * 0.5,
        half_w, content_h - padding * 0.5,
        stroke=palette.surface_alt,
        stroke_width=1.0,
    )

    # ── Helper: draw a column of items ────────────────────────────────────
    def _draw_column(
        items: list[str],
        heading: str,
        heading_colour: str,
        start_x: float,
        anim_offset: int,
    ) -> None:
        heading_y = padding + row_height * 0.8
        delay = initial_delay_ms + anim_offset * stagger_ms

        # Heading
        h_g = group(content_g, opacity="0", transform="translate(0, 8)")
        animate(h_g, "opacity", "0", "1",
                begin=ms_to_smil(delay), dur=ms_to_smil(duration_ms))
        animate_transform(h_g, "translate", "0 8", "0 0",
                          begin=ms_to_smil(delay), dur=ms_to_smil(duration_ms))

        text_el(
            h_g, heading,
            start_x, heading_y,
            fill=heading_colour,
            font_family=mono,
            font_size=font_size_heading,
            font_weight="bold",
        )

        # Separator under heading
        sep_y = heading_y + row_height * 0.35
        sep_g = group(content_g, opacity="0")
        animate(sep_g, "opacity", "0", "1",
                begin=ms_to_smil(delay + stagger_ms),
                dur=ms_to_smil(duration_ms))
        line_el(
            sep_g,
            start_x, sep_y,
            start_x + half_w - padding * 1.5, sep_y,
            stroke=palette.surface_alt,
            stroke_width=0.8,
        )

        # Items
        items_start_y = sep_y + row_height * 0.7
        for i, item in enumerate(items):
            item_delay = delay + (i + 2) * stagger_ms
            item_y = items_start_y + i * row_height

            item_g = group(content_g, opacity="0", transform="translate(0, 10)")
            animate(item_g, "opacity", "0", "1",
                    begin=ms_to_smil(item_delay), dur=ms_to_smil(duration_ms))
            animate_transform(item_g, "translate", "0 10", "0 0",
                              begin=ms_to_smil(item_delay),
                              dur=ms_to_smil(duration_ms))

            # Coloured dot
            dot_colour = _dot_colour(palette, i + anim_offset)
            el("circle", item_g,
               cx=str(start_x + dot_r),
               cy=str(item_y - font_size_item * 0.3),
               r=str(dot_r),
               fill=dot_colour)

            # Item text
            text_el(
                item_g, item,
                start_x + dot_r * 2 + 12, item_y,
                fill=palette.text,
                font_family=mono,
                font_size=font_size_item,
            )

    # ── Draw both columns ─────────────────────────────────────────────────
    _draw_column(languages, "🔧 Languages", palette.blue, col_left_x, anim_offset=0)
    _draw_column(tools, "⚙️  Tools & Environment", palette.peach, col_right_x, anim_offset=len(languages) + 2)

    return root


# ═════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Generate the tech-stack SVG.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG.
    """
    cfg = load_config(config_path)
    svg_el = build_tech_stack_svg(cfg)

    output_path = _PROJECT_ROOT / "generated" / "tech-stack.svg"
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an animated tech-stack SVG card."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
