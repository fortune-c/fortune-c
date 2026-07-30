"""
make_spotify_svg.py – Generate a Spotify "Now Playing" placeholder SVG.

When ``spotify.vercel_url`` is set in config.yaml the README uses the live
novatorem embed directly (no SVG needed).  When it is empty this script
produces a styled placeholder card instructing the user to connect Spotify.

Usage
-----
    python scripts/make_spotify_svg.py
    python scripts/make_spotify_svg.py --config path/to/config.yaml
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
    el,
    get_palette,
    group,
    load_config,
    make_defs,
    ms_to_smil,
    rect,
    set_attr,
    svg_root,
    text_el,
    write_svg,
    line_el,
    glow_filter,
)

# Spotify brand green
_SPOTIFY_GREEN = "#1DB954"
# Musical note unicode path approximated as text
_NOTE = "♫"


def build_spotify_placeholder(cfg: dict) -> ET.Element:
    """Build a 'Connect Spotify' placeholder card SVG.

    The card pulses the Spotify logo colour subtly to draw attention.
    All text explains how to activate the live widget.

    Args:
        cfg: Loaded config dict.

    Returns:
        The ``<svg>`` root element.
    """
    palette = get_palette(cfg)
    fonts = cfg["fonts"]
    sans = fonts["sans"]
    mono = fonts["mono"]

    width, height = 350, 80
    corner_r = 10

    root = svg_root(width, height, extra_attrs={"aria-label": "Spotify not connected"})
    defs = make_defs(root)
    glow_filter(defs, "spot-glow", blur=6, color=_SPOTIFY_GREEN)

    # Background
    rect(root, 0, 0, width, height,
         fill=palette.surface, rx=corner_r,
         stroke=palette.surface_alt, **{"stroke-width": "1"})

    # Left accent bar in Spotify green
    rect(root, 0, 0, 4, height, fill=_SPOTIFY_GREEN, rx=corner_r)

    # Musical note icon (pulsing opacity)
    note_g = group(root)
    note_el = text_el(
        note_g, _NOTE,
        22, height / 2,
        fill=_SPOTIFY_GREEN,
        font_family=sans,
        font_size=28,
        text_anchor="middle",
        dominant_baseline="middle",
    )
    # Subtle pulse: opacity 1 → 0.4 → 1, indefinite
    animate(
        note_el, "opacity", "1", "0.4",
        begin="0s", dur="1.8s",
        **{"repeatCount": "indefinite", "calcMode": "ease-in-out"},
        values="1;0.4;1",
        key_times="0;0.5;1",
    )

    # Main label
    text_el(
        root, "Spotify — Not Connected",
        42, height * 0.38,
        fill=palette.text,
        font_family=sans,
        font_size=13,
        font_weight="bold",
        dominant_baseline="middle",
    )

    # Sub-label
    text_el(
        root, "Set spotify.vercel_url in config.yaml",
        42, height * 0.68,
        fill=palette.subtext,
        font_family=mono,
        font_size=10,
        dominant_baseline="middle",
    )

    return root


def run(config_path: Path | None = None) -> Path:
    """Generate (or skip) the Spotify placeholder SVG.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG (placeholder).
    """
    cfg = load_config(config_path)
    vercel_url = cfg.get("spotify", {}).get("vercel_url", "")

    output_path = _PROJECT_ROOT / "generated" / "spotify.svg"

    if vercel_url:
        print(f"[spotify] Live URL configured: {vercel_url}")
        print("[spotify] No placeholder SVG needed – README uses embed URL directly.")
        return output_path  # README will embed the live URL, not this file

    print("[spotify] No vercel_url set – generating placeholder SVG.")
    svg_el = build_spotify_placeholder(cfg)
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Spotify placeholder SVG (or skip if live URL is set)."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
