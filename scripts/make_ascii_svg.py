"""
make_ascii_svg.py – Convert a pre-processed portrait to an animated ASCII SVG.

The output SVG uses SMIL animations to type each character one at a time,
left-to-right, top-to-bottom.  A blinking block cursor trails the typing.
After all characters are placed the cursor continues to blink forever —
everything else freezes.

No GIF.  No canvas.  No JavaScript.  Pure SVG + SMIL.

Usage
-----
    python scripts/make_ascii_svg.py
    python scripts/make_ascii_svg.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
    import numpy as np
except ImportError as exc:
    sys.exit(
        f"[make_ascii_svg] Missing dependency: {exc}.\n"
        "Run: pip install -r scripts/requirements.txt"
    )

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import (
    animate,
    cursor_blink_rect,
    el,
    get_palette,
    group,
    glow_filter,
    load_config,
    make_defs,
    ms_to_smil,
    rect,
    set_attr,
    svg_root,
    text_el,
    write_svg,
    css_style_block,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  ASCII conversion
# ═══════════════════════════════════════════════════════════════════════════════

def image_to_ascii_grid(
    img_path: Path,
    brightness_ramp: str,
) -> list[str]:
    """Convert a greyscale image to a 2-D grid of ASCII characters.

    The image is **inverted** before conversion so that the white background
    (produced by ``prep_photo.py``'s white composite step) maps to the space
    character (index 0 in the ramp), while the dark portrait subject maps to
    the denser characters at the end of the ramp.

    Args:
        img_path: Path to the pre-processed greyscale PNG.
        brightness_ramp: String of characters ordered dark-to-light.
            After inversion, dark pixels (formerly bright background) become
            space, and bright pixels (formerly dark subject tones) become
            dense characters.

    Returns:
        A list of strings, one per row, each of equal length.
    """
    img = Image.open(img_path).convert("L")
    # Invert: white background (255) → 0 (space), dark subject → 255 (dense char)
    img = ImageOps.invert(img)
    pixels = np.array(img, dtype=np.uint8)

    ramp = brightness_ramp
    n = len(ramp) - 1

    rows: list[str] = []
    for row in pixels:
        chars = "".join(ramp[int(p / 255 * n)] for p in row)
        rows.append(chars)

    # Ensure all rows are the same length (they should be, but guard anyway)
    max_len = max(len(r) for r in rows)
    rows = [r.ljust(max_len) for r in rows]
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG geometry calculations
# ═══════════════════════════════════════════════════════════════════════════════

def compute_canvas(
    rows: list[str],
    font_size: float,
    line_height_multiplier: float,
    padding: float = 12,
) -> tuple[float, float, float, float]:
    """Return (canvas_width, canvas_height, cell_w, cell_h).

    Monospace fonts have a character width that is approximately 0.6× their
    font-size.  Line height is font_size × line_height_multiplier.

    Args:
        rows: ASCII rows (all same length).
        font_size: Font size in SVG user units.
        line_height_multiplier: Line height as a fraction of font size.
        padding: Extra padding added on all sides.

    Returns:
        Tuple of (canvas_w, canvas_h, char_cell_w, char_cell_h).
    """
    num_cols = len(rows[0]) if rows else 0
    num_rows = len(rows)

    char_cell_w = font_size * 0.602  # empirically good for monospace
    char_cell_h = font_size * line_height_multiplier

    canvas_w = num_cols * char_cell_w + padding * 2
    canvas_h = num_rows * char_cell_h + padding * 2
    return canvas_w, canvas_h, char_cell_w, char_cell_h


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG generation
# ═══════════════════════════════════════════════════════════════════════════════

def build_ascii_svg(
    rows: list[str],
    cfg: dict,
) -> "ET.Element":  # noqa: F821 – avoid circular import at type-check time
    """Build the complete animated ASCII SVG element tree.

    Each character is placed as an individual ``<text>`` element with an
    initial ``opacity="0"`` that flips to ``1`` via a SMIL ``<set>`` timed
    so that characters appear one by one from left to right, row by row.

    A block cursor rect is rendered at the current typing position and follows
    the last typed character.  After typing finishes the cursor continues to
    blink indefinitely.

    Args:
        rows: ASCII character grid.
        cfg: Loaded config dict.

    Returns:
        The ``<svg>`` root :class:`ET.Element`.
    """
    from xml.etree import ElementTree as ET  # local import to avoid circular

    portrait_cfg = cfg["portrait"]
    anim_cfg = cfg["animation"]
    theme_cfg = cfg["theme"]
    fonts_cfg = cfg["fonts"]
    palette = get_palette(cfg)

    font_size = float(portrait_cfg["svg_font_size_px"])
    line_height_mult = float(portrait_cfg["svg_line_height"])
    padding = 12.0
    char_delay_ms = int(anim_cfg["ascii_char_delay_ms"])
    blink_ms = int(anim_cfg["ascii_cursor_blink_ms"])
    brightness_ramp = portrait_cfg["brightness_ramp"]
    font_family = fonts_cfg["mono"]

    canvas_w, canvas_h, cell_w, cell_h = compute_canvas(rows, font_size, line_height_mult, padding)

    # Force integer canvas dimensions for clean pixel layout
    canvas_w = int(canvas_w) + 1
    canvas_h = int(canvas_h) + 1

    root = svg_root(canvas_w, canvas_h, extra_attrs={"aria-label": "ASCII portrait animation"})
    defs = make_defs(root)

    # Subtle glow for the overall ASCII art
    glow_filter(defs, "ascii-glow", blur=3, color=palette.text)

    # Background
    rect(root, 0, 0, canvas_w, canvas_h, fill=palette.background, rx=0)

    art_group = group(root, **{"filter": "url(#ascii-glow)"})

    # Pre-compute timing
    total_chars = sum(len(r.rstrip()) for r in rows)
    current_char_index = 0
    last_char_x = padding
    last_char_y = padding + cell_h

    for row_idx, row_text in enumerate(rows):
        stripped = row_text.rstrip()
        if not stripped:
            current_char_index += len(row_text.rstrip()) or 0
            continue

        row_y = padding + (row_idx + 1) * cell_h  # baseline y

        for col_idx, char in enumerate(stripped):
            if char == " ":
                current_char_index += 1
                continue

            char_x = padding + col_idx * cell_w
            begin_s = ms_to_smil(current_char_index * char_delay_ms)

            # Each character starts invisible
            t = text_el(
                art_group,
                char,
                char_x,
                row_y,
                fill=palette.text,
                font_family=font_family,
                font_size=font_size,
                opacity="0",
            )
            # Reveal via SMIL <set>
            set_attr(t, "opacity", "1", begin=begin_s)

            last_char_x = char_x + cell_w
            last_char_y = row_y - cell_h  # top of cursor

            current_char_index += 1

    # Total animation duration
    total_dur_ms = total_chars * char_delay_ms

    # Blinking cursor that trails typing and then blinks forever
    cursor_w = cell_w * 0.85
    cursor_h = cell_h * 0.9
    cursor_blink_rect(
        root,
        last_char_x,
        last_char_y,
        cursor_w,
        cursor_h,
        fill=palette.text,
        blink_period_ms=blink_ms,
        begin_ms=total_dur_ms,
        blink_forever=True,
    )

    return root


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Run the ASCII SVG generator.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG file.
    """
    cfg = load_config(config_path)
    portrait_cfg = cfg["portrait"]

    cleaned_path = _PROJECT_ROOT / portrait_cfg["cleaned_path"]
    if not cleaned_path.exists():
        sys.exit(
            f"[make_ascii_svg] Cleaned image not found: {cleaned_path}\n"
            "Run 'python scripts/prep_photo.py' first."
        )

    brightness_ramp = portrait_cfg["brightness_ramp"]
    print(f"[make_ascii_svg] Converting {cleaned_path} → ASCII …")
    rows = image_to_ascii_grid(cleaned_path, brightness_ramp)
    print(f"[make_ascii_svg] Grid: {len(rows)} rows × {len(rows[0])} cols")

    svg_el = build_ascii_svg(rows, cfg)

    output_path = _PROJECT_ROOT / "generated" / "avi-ascii.svg"
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an animated ASCII art SVG from a portrait photo."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
