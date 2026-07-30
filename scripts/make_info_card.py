"""
make_info_card.py – Generate an animated terminal info-card SVG.

The card resembles a neofetch / macOS terminal window.  Each row fades in and
slides up from below the card edge, staggered so the card "types itself" into
existence.  After all rows appear every element freezes – no looping.

A blinking cursor sits at the end of the header prompt line forever.

Visual structure
----------------
  ┌──────────────────────────────────────────────────────┐
  │  ● ● ●     fortune@github:~$                         │  ← title bar
  ├──────────────────────────────────────────────────────┤
  │                                                      │
  │  username@github ──────────────────────────────────  │  ← prompt row
  │                                                      │
  │  OS          Arch Linux (btw)                        │  ← info rows
  │  Shell        zsh + starship                         │
  │  …                                                   │
  │                                                      │
  └──────────────────────────────────────────────────────┘

Usage
-----
    python scripts/make_info_card.py
    python scripts/make_info_card.py --config path/to/config.yaml
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
    css_style_block,
    cursor_blink_rect,
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
    tspan,
    write_svg,
)


# ─── Label colour cycle (cycling through palette accents) ────────────────────
_LABEL_COLOURS = [
    "blue", "green", "peach", "pink", "lavender",
    "teal", "yellow", "sky", "mauve", "sapphire",
]


def _label_colour(palette, index: int) -> str:
    """Return a cycling accent colour for info row labels."""
    attr = _LABEL_COLOURS[index % len(_LABEL_COLOURS)]
    return getattr(palette, attr)


# ═══════════════════════════════════════════════════════════════════════════════
#  Row geometry helper
# ═══════════════════════════════════════════════════════════════════════════════

def _total_card_height(cfg: dict) -> int:
    """Compute the total outer SVG canvas height.

    Args:
        cfg: Loaded config dict.

    Returns:
        Integer pixel height.
    """
    card_cfg = cfg["info_card"]
    info_rows = cfg["info_rows"]
    rows = len(info_rows)

    header_h = int(card_cfg["header_height"])
    title_bar_h = 36  # matches draw_terminal_chrome default
    row_h = int(card_cfg["row_height"])
    padding = int(card_cfg["padding"])

    # prompt row + separator + all info rows + top/bottom padding
    content_height = (
        padding            # gap after title bar
        + row_h            # prompt/username header row
        + padding // 2     # gap
        + row_h            # separator
        + rows * row_h     # info rows
        + padding          # bottom gap
    )
    return title_bar_h + content_height


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_info_card_svg(cfg: dict) -> ET.Element:
    """Construct the complete animated info-card SVG.

    Each info row is an invisible ``<g>`` group that:
      1. Starts with ``opacity="0"`` and a downward ``translateY`` offset.
      2. Uses a SMIL ``<animate>`` to fade in and an ``<animateTransform>``
         to slide upward – both starting at the same time with a stagger.
      3. Both animations use ``fill="freeze"`` so the row stays visible
         after its animation finishes.

    Args:
        cfg: Loaded config dict.

    Returns:
        The ``<svg>`` root element.
    """
    card_cfg = cfg["info_card"]
    anim_cfg = cfg["animation"]
    fonts_cfg = cfg["fonts"]
    palette = get_palette(cfg)

    info_rows: list[dict] = cfg["info_rows"]
    prompt_text: str = cfg["terminal_prompt"]
    github_username: str = cfg["github_username"]
    display_name: str = cfg["display_name"]

    width = int(card_cfg["width"])
    padding = int(card_cfg["padding"])
    row_h = int(card_cfg["row_height"])
    title_bar_h = 36  # hard-coded to match draw_terminal_chrome
    corner_r = int(card_cfg["corner_radius"])
    border_w = float(card_cfg["border_width"])
    font_body = float(card_cfg["font_size_body"])
    font_header = float(card_cfg["font_size_header"])
    font_prompt = float(card_cfg["font_size_prompt"])
    label_w = int(card_cfg["label_width"])
    glow_blur = float(card_cfg["glow_blur"])
    mono = fonts_cfg["mono"]

    stagger_ms = int(anim_cfg["card_row_stagger_ms"])
    duration_ms = int(anim_cfg["card_row_duration_ms"])
    initial_delay_ms = int(anim_cfg["card_initial_delay_ms"])
    blink_ms = int(cfg["animation"]["ascii_cursor_blink_ms"])

    total_height = _total_card_height(cfg)

    root = svg_root(width, total_height, extra_attrs={"aria-label": "Terminal info card"})
    defs = make_defs(root)

    # Clip path to hide rows that slide in from below
    clip = el("clipPath", defs, id="card-clip")
    rect(clip, 0, title_bar_h, width, total_height - title_bar_h, fill="white")

    # Glow filter for the window border
    glow_filter(defs, "card-glow", blur=glow_blur, color=palette.blue)

    # Terminal chrome (draws background + title bar + traffic lights, returns content <g>)
    content_g = draw_terminal_chrome(
        root,
        x=0, y=0,
        width=width,
        height=total_height,
        palette=palette,
        corner_radius=corner_r,
        border_width=border_w,
        title=prompt_text,
        font_family=mono,
        font_size=float(card_cfg["font_size_prompt"]),
        title_bar_height=title_bar_h,
        glow_filter_id="card-glow",
    )

    # Apply clip to content group so slide-in rows don't overflow window bounds
    content_g.set("clip-path", "url(#card-clip)")

    # ── Prompt / username header row ────────────────────────────────────────
    header_y = padding + row_h
    prompt_g = group(content_g, opacity="0")
    set_attr(prompt_g, "opacity", "1", begin=ms_to_smil(initial_delay_ms))
    animate(prompt_g, "opacity", "0", "1",
            begin=ms_to_smil(initial_delay_ms),
            dur=ms_to_smil(duration_ms))

    # Green user@host portion
    user_t = text_el(
        prompt_g, "",
        padding, header_y,
        fill=palette.green,
        font_family=mono,
        font_size=font_header,
        font_weight="bold",
    )
    tspan(user_t, f"{github_username}@github", fill=palette.green, font_weight="bold")
    tspan(user_t, "  —  ", fill=palette.muted)
    tspan(user_t, display_name, fill=palette.text)

    # Horizontal separator after header
    sep_y = header_y + row_h * 0.6
    sep_line_g = group(content_g, opacity="0")
    set_attr(sep_line_g, "opacity", "1", begin=ms_to_smil(initial_delay_ms + stagger_ms))
    animate(sep_line_g, "opacity", "0", "1",
            begin=ms_to_smil(initial_delay_ms + stagger_ms),
            dur=ms_to_smil(duration_ms))
    line_el(sep_line_g, padding, sep_y, width - padding, sep_y,
            stroke=palette.surface_alt, stroke_width=1.0)

    # ── Info rows ────────────────────────────────────────────────────────────
    row_start_y = sep_y + row_h * 0.6

    for i, row_data in enumerate(info_rows):
        label: str = row_data["label"]
        value: str = row_data["value"]

        delay_ms = initial_delay_ms + (i + 2) * stagger_ms
        row_y = row_start_y + i * row_h

        # Slide-up wrapper: starts invisible + shifted down 10px
        slide_g = group(content_g, opacity="0", transform="translate(0, 10)")

        # Fade in
        animate(slide_g, "opacity", "0", "1",
                begin=ms_to_smil(delay_ms), dur=ms_to_smil(duration_ms))

        # Slide up (translate Y 10 → 0)
        animate_transform(
            slide_g, "translate",
            from_val="0 10", to_val="0 0",
            begin=ms_to_smil(delay_ms), dur=ms_to_smil(duration_ms),
        )

        label_colour = _label_colour(palette, i)

        # Label
        text_el(
            slide_g, label,
            padding, row_y,
            fill=label_colour,
            font_family=mono,
            font_size=font_body,
            font_weight="bold",
        )

        # Value – starts at label_width offset
        text_el(
            slide_g, value,
            padding + label_w, row_y,
            fill=palette.text,
            font_family=mono,
            font_size=font_body,
        )

    # ── Blinking cursor after the prompt in the title bar ───────────────────
    # Approximate x position: end of prompt text + 1 char
    prompt_approx_end_x = (
        len(prompt_text) * font_prompt * 0.602  # monospace char width
        + (width / 2 - len(prompt_text) * font_prompt * 0.602 / 2)  # centred
        + font_prompt * 0.7
    )
    cursor_h = font_prompt + 2
    cursor_y = title_bar_h / 2 - cursor_h / 2
    # Cursor lives in root (not content_g, which is translated)
    cursor_blink_rect(
        root,
        prompt_approx_end_x, cursor_y,
        font_prompt * 0.55, cursor_h,
        fill=palette.green,
        blink_period_ms=blink_ms,
        begin_ms=initial_delay_ms,
        blink_forever=True,
    )

    return root


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Generate the info-card SVG.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG.
    """
    cfg = load_config(config_path)
    svg_el = build_info_card_svg(cfg)

    output_path = _PROJECT_ROOT / "generated" / "info-card.svg"
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an animated terminal info-card SVG."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
