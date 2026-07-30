"""
shared.py – Shared utilities for the animated GitHub profile SVG pipeline.

All generators import from this module. It provides:
  - Config loading
  - Catppuccin Mocha color palette dataclass
  - SVG building helpers (elements, groups, filters)
  - SMIL / CSS animation helpers
  - Terminal window chrome renderer
  - Typography constants
  - Cursor blink animation builder
  - Timing utilities
"""

from __future__ import annotations

import math
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

# ─── Project root (directory containing this file's parent) ──────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPTS_DIR.parent


# ═══════════════════════════════════════════════════════════════════════════════
#  Config loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and return the YAML configuration dictionary.

    Args:
        path: Optional explicit path.  Defaults to ``<project_root>/config.yaml``.

    Returns:
        Parsed config as a plain Python dict.
    """
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ═══════════════════════════════════════════════════════════════════════════════
#  Theme / palette
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Palette:
    """Typed wrapper around the ``theme`` section of ``config.yaml``."""

    background:  str = "#1e1e2e"
    surface:     str = "#313244"
    surface_alt: str = "#45475a"
    overlay:     str = "#6c7086"
    muted:       str = "#585b70"
    text:        str = "#cdd6f4"
    subtext:     str = "#a6adc8"
    blue:        str = "#89b4fa"
    green:       str = "#a6e3a1"
    pink:        str = "#f5c2e7"
    lavender:    str = "#b4befe"
    peach:       str = "#fab387"
    red:         str = "#f38ba8"
    yellow:      str = "#f9e2af"
    teal:        str = "#94e2d5"
    sky:         str = "#89dceb"
    mauve:       str = "#cba6f7"
    sapphire:    str = "#74c7ec"

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Palette":
        theme = cfg.get("theme", {})
        kwargs = {k: v for k, v in theme.items() if k in cls.__dataclass_fields__}
        return cls(**kwargs)


def get_palette(cfg: dict[str, Any]) -> Palette:
    """Convenience wrapper – returns a :class:`Palette` from a loaded config."""
    return Palette.from_config(cfg)


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG element helpers
# ═══════════════════════════════════════════════════════════════════════════════

NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", NS)
ET.register_namespace("xlink", XLINK_NS)


def svg_root(
    width: int | float,
    height: int | float,
    *,
    extra_attrs: dict[str, str] | None = None,
) -> ET.Element:
    """Create an ``<svg>`` root element with standard attributes.

    Args:
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        extra_attrs: Additional XML attributes to set on the root element.

    Returns:
        An :class:`xml.etree.ElementTree.Element` ready to be populated.
    """
    attrs: dict[str, str] = {
        "xmlns": NS,
        "xmlns:xlink": XLINK_NS,
        "width": str(int(width)),
        "height": str(int(height)),
        "viewBox": f"0 0 {int(width)} {int(height)}",
        "role": "img",
    }
    if extra_attrs:
        attrs.update(extra_attrs)
    return ET.Element("svg", attrs)


def el(
    tag: str,
    parent: ET.Element | None = None,
    **attrs: str,
) -> ET.Element:
    """Create an SVG element, optionally attaching it to *parent*.

    Args:
        tag: Local tag name (e.g. ``"rect"``, ``"text"``).
        parent: If given, the new element is appended to this element.
        **attrs: XML attributes as keyword arguments.
            Underscores in keys are NOT replaced – pass exact XML names
            or use ``attrib`` dict for names with hyphens/colons.

    Returns:
        The created :class:`ET.Element`.
    """
    elem = ET.SubElement(parent, tag, attrs) if parent is not None else ET.Element(tag, attrs)
    return elem


def group(
    parent: ET.Element | None = None,
    **attrs: str,
) -> ET.Element:
    """Create a ``<g>`` group element."""
    return el("g", parent, **attrs)


def rect(
    parent: ET.Element,
    x: int | float,
    y: int | float,
    w: int | float,
    h: int | float,
    *,
    fill: str = "none",
    rx: int | float = 0,
    ry: int | float | None = None,
    stroke: str | None = None,
    stroke_width: float | None = None,
    **extra: str,
) -> ET.Element:
    """Append a ``<rect>`` to *parent*."""
    attrs: dict[str, str] = {
        "x": str(x),
        "y": str(y),
        "width": str(w),
        "height": str(h),
        "fill": fill,
        "rx": str(rx),
    }
    if ry is not None:
        attrs["ry"] = str(ry)
    if stroke is not None:
        attrs["stroke"] = stroke
    if stroke_width is not None:
        attrs["stroke-width"] = str(stroke_width)
    attrs.update(extra)
    return el("rect", parent, **attrs)


def text_el(
    parent: ET.Element,
    content: str,
    x: int | float,
    y: int | float,
    *,
    fill: str = "#cdd6f4",
    font_family: str = "monospace",
    font_size: int | float = 13,
    font_weight: str = "normal",
    text_anchor: str = "start",
    dominant_baseline: str = "auto",
    opacity: float = 1.0,
    **extra: str,
) -> ET.Element:
    """Append a ``<text>`` element to *parent*.

    Args:
        content: Text string to display.
        x, y: Position in SVG user units.
        fill: Text colour.
        font_family: Font stack string.
        font_size: Font size in px.
        font_weight: CSS font-weight value.
        text_anchor: SVG text-anchor attribute.
        dominant_baseline: SVG dominant-baseline attribute.
        opacity: Initial opacity (used for fade animations).
        **extra: Additional XML attributes.

    Returns:
        The ``<text>`` element.
    """
    attrs: dict[str, str] = {
        "x": str(x),
        "y": str(y),
        "fill": fill,
        "font-family": font_family,
        "font-size": str(font_size),
        "font-weight": font_weight,
        "text-anchor": text_anchor,
        "dominant-baseline": dominant_baseline,
        "opacity": str(opacity),
    }
    attrs.update(extra)
    elem = el("text", parent, **attrs)
    elem.text = content
    return elem


def tspan(
    parent: ET.Element,
    content: str,
    *,
    fill: str | None = None,
    font_weight: str | None = None,
    **extra: str,
) -> ET.Element:
    """Append a ``<tspan>`` inside a ``<text>`` element."""
    attrs: dict[str, str] = {}
    if fill:
        attrs["fill"] = fill
    if font_weight:
        attrs["font-weight"] = font_weight
    attrs.update(extra)
    t = el("tspan", parent, **attrs)
    t.text = content
    return t


def line_el(
    parent: ET.Element,
    x1: float, y1: float,
    x2: float, y2: float,
    *,
    stroke: str = "#585b70",
    stroke_width: float = 1.0,
    **extra: str,
) -> ET.Element:
    """Append a ``<line>`` element to *parent*."""
    return el(
        "line", parent,
        x1=str(x1), y1=str(y1),
        x2=str(x2), y2=str(y2),
        stroke=stroke,
        **{"stroke-width": str(stroke_width)},
        **extra,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG <defs> helpers
# ═══════════════════════════════════════════════════════════════════════════════

def make_defs(parent: ET.Element) -> ET.Element:
    """Append and return a ``<defs>`` block."""
    return el("defs", parent)


def glow_filter(
    defs: ET.Element,
    filter_id: str,
    blur: float = 8,
    color: str = "#89b4fa",
) -> str:
    """Add a soft glow filter to *defs* and return the filter id.

    The filter uses a Gaussian blur flood-composite approach to produce a
    single-colour glow compatible with all SVG renderers (including GitHub's).

    Args:
        defs: The ``<defs>`` element to append to.
        filter_id: Unique ``id`` for the ``<filter>`` element.
        blur: Standard deviation for the Gaussian blur (controls spread).
        color: Hex colour of the glow.

    Returns:
        The ``filter_id`` string, for use in ``filter="url(#...)"`` attributes.
    """
    filt = el("filter", defs, id=filter_id, x="-30%", y="-30%", width="160%", height="160%")
    el("feGaussianBlur", filt, **{"in": "SourceGraphic", "stdDeviation": str(blur), "result": "blur"})
    el("feFlood", filt, **{"flood-color": color, "flood-opacity": "0.6", "result": "color"})
    el("feComposite", filt, **{"in": "color", "in2": "blur", "operator": "in", "result": "glow"})
    el("feMerge", filt)
    merge = filt.find("feMerge")
    assert merge is not None
    el("feMergeNode", merge, **{"in": "glow"})
    el("feMergeNode", merge, **{"in": "SourceGraphic"})
    return filter_id


def drop_shadow_filter(
    defs: ET.Element,
    filter_id: str,
    dx: float = 0,
    dy: float = 2,
    blur: float = 4,
    color: str = "#000000",
    opacity: float = 0.4,
) -> str:
    """Add a drop-shadow filter and return the filter id."""
    filt = el("filter", defs, id=filter_id, x="-20%", y="-20%", width="140%", height="140%")
    el(
        "feDropShadow", filt,
        dx=str(dx), dy=str(dy),
        **{"stdDeviation": str(blur), "flood-color": color, "flood-opacity": str(opacity)},
    )
    return filter_id


# ═══════════════════════════════════════════════════════════════════════════════
#  SMIL animation helpers
# ═══════════════════════════════════════════════════════════════════════════════

def animate(
    parent: ET.Element,
    attribute_name: str,
    from_val: str,
    to_val: str,
    *,
    begin: str = "0s",
    dur: str = "0.4s",
    fill: str = "freeze",
    calc_mode: str | None = None,
    key_times: str | None = None,
    values: str | None = None,
    **extra: str,
) -> ET.Element:
    """Append a SMIL ``<animate>`` element.

    Args:
        parent: The element being animated.
        attribute_name: SVG attribute to animate (e.g. ``"opacity"``).
        from_val: Start value.
        to_val: End value.
        begin: SMIL begin time string.
        dur: SMIL duration string.
        fill: SMIL fill mode (``"freeze"`` keeps the end value).
        **extra: Additional SMIL attributes.

    Returns:
        The ``<animate>`` element.
    """
    attrs: dict[str, str] = {
        "attributeName": attribute_name,
        "from": from_val,
        "to": to_val,
        "begin": begin,
        "dur": dur,
        "fill": fill,
    }
    if calc_mode:
        attrs["calcMode"] = calc_mode
    if key_times:
        attrs["keyTimes"] = key_times
    if values:
        attrs["values"] = values
        attrs.pop("from", None)
        attrs.pop("to", None)
    attrs.update(extra)
    return el("animate", parent, **attrs)


def animate_transform(
    parent: ET.Element,
    transform_type: str,
    from_val: str,
    to_val: str,
    *,
    begin: str = "0s",
    dur: str = "0.4s",
    fill: str = "freeze",
    add_itive: str = "replace",
    **extra: str,
) -> ET.Element:
    """Append a SMIL ``<animateTransform>`` element."""
    attrs: dict[str, str] = {
        "attributeName": "transform",
        "type": transform_type,
        "from": from_val,
        "to": to_val,
        "begin": begin,
        "dur": dur,
        "fill": fill,
        "additive": add_itive,
    }
    attrs.update(extra)
    return el("animateTransform", parent, **attrs)


def set_attr(
    parent: ET.Element,
    attribute_name: str,
    to_val: str,
    *,
    begin: str = "0s",
    fill: str = "freeze",
) -> ET.Element:
    """Append a SMIL ``<set>`` element (instant attribute change)."""
    return el(
        "set", parent,
        attributeName=attribute_name,
        to=to_val,
        begin=begin,
        fill=fill,
    )


def ms_to_smil(ms: int | float) -> str:
    """Convert milliseconds to a SMIL time string (e.g. ``"1.23s"``)."""
    return f"{ms / 1000:.3f}s"


# ═══════════════════════════════════════════════════════════════════════════════
#  Cursor animation
# ═══════════════════════════════════════════════════════════════════════════════

def cursor_blink_rect(
    parent: ET.Element,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = "#cdd6f4",
    blink_period_ms: int = 530,
    begin_ms: int = 0,
    blink_forever: bool = True,
) -> ET.Element:
    """Append a blinking block cursor ``<rect>`` to *parent*.

    The cursor appears at *begin_ms* and then blinks indefinitely (or stops
    after one period if *blink_forever* is False).

    Args:
        x, y: Top-left corner.
        w, h: Width / height (typically 1 character cell).
        fill: Cursor colour.
        blink_period_ms: Full on-off cycle length in ms.
        begin_ms: Delay before the cursor first appears.
        blink_forever: If True, blink indefinitely; if False, blink once.

    Returns:
        The ``<rect>`` element.
    """
    cur = rect(parent, x, y, w, h, fill=fill, opacity="0")

    period_s = blink_period_ms / 1000
    half_s = period_s / 2
    begin_s = begin_ms / 1000

    repeat = "indefinite" if blink_forever else "1"

    # Appear at begin_ms
    set_attr(cur, "opacity", "1", begin=f"{begin_s:.3f}s")

    # Then blink: 1 → 0 → 1 …
    animate(
        cur,
        "opacity",
        "1",
        "0",
        begin=f"{begin_s:.3f}s",
        dur=f"{half_s:.3f}s",
        **{"repeatCount": repeat, "calcMode": "discrete"},
        values="1;0;1",
        key_times="0;0.5;1",
    )
    return cur


# ═══════════════════════════════════════════════════════════════════════════════
#  Terminal window chrome
# ═══════════════════════════════════════════════════════════════════════════════

TRAFFIC_LIGHT_COLORS = ("#f38ba8", "#f9e2af", "#a6e3a1")  # red, yellow, green


def draw_terminal_chrome(
    parent: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    palette: Palette,
    corner_radius: float = 10,
    border_width: float = 1.5,
    title: str = "",
    font_family: str = "monospace",
    font_size: float = 12,
    title_bar_height: float = 36,
    glow_filter_id: str | None = None,
) -> ET.Element:
    """Draw a macOS-style terminal window chrome and return the content ``<g>``.

    Creates:
      - Background rect with rounded corners
      - Title bar gradient rect
      - Three traffic-light dots
      - Optional title text in the centre of the title bar
      - A separator line below the title bar
      - An optional glow filter reference on the outer border

    Args:
        parent: SVG element to append chrome elements to.
        x, y: Position of the terminal window.
        width, height: Outer dimensions.
        palette: Colour palette instance.
        corner_radius: Border radius.
        border_width: Stroke width of the outer border.
        title: Text to display in the title bar.
        font_family: Font for title text.
        font_size: Font size for title text.
        title_bar_height: Height of the title bar area.
        glow_filter_id: If provided, apply ``filter="url(#...)"`` to the border.

    Returns:
        A ``<g>`` element positioned at the content area (below the title bar).
    """
    g = group(parent)

    # Outer border / window background
    border_attrs: dict[str, str] = {
        "stroke": palette.surface_alt,
        "stroke-width": str(border_width),
    }
    if glow_filter_id:
        border_attrs["filter"] = f"url(#{glow_filter_id})"

    rect(g, x, y, width, height, fill=palette.background, rx=corner_radius, **border_attrs)

    # Title bar
    rect(
        g, x, y, width, title_bar_height,
        fill=palette.surface,
        rx=corner_radius,
    )
    # Bottom of title bar (square the bottom corners)
    rect(
        g,
        x,
        y + title_bar_height / 2,
        width,
        title_bar_height / 2,
        fill=palette.surface,
    )

    # Traffic lights
    dot_y = y + title_bar_height / 2
    dot_r = 6.0
    for i, colour in enumerate(TRAFFIC_LIGHT_COLORS):
        cx = x + 20 + i * 20
        el("circle", g, cx=str(cx), cy=str(dot_y), r=str(dot_r), fill=colour)

    # Title text
    if title:
        text_el(
            g, title,
            x + width / 2, y + title_bar_height / 2,
            fill=palette.subtext,
            font_family=font_family,
            font_size=font_size,
            text_anchor="middle",
            dominant_baseline="middle",
        )

    # Separator line
    line_el(
        g,
        x, y + title_bar_height,
        x + width, y + title_bar_height,
        stroke=palette.muted,
        stroke_width=border_width * 0.5,
    )

    # Return a positioned content group
    content_g = group(g, transform=f"translate({x}, {y + title_bar_height})")
    return content_g


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG serialisation
# ═══════════════════════════════════════════════════════════════════════════════

def _indent_tree(elem: ET.Element, level: int = 0) -> None:
    """Recursively indent an ElementTree in-place (pretty-print helper)."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_tree(child, level + 1)
        if not child.tail or not child.tail.strip():  # type: ignore[reportPossiblyUnbound]
            child.tail = indent  # type: ignore[reportPossiblyUnbound]
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def write_svg(root: ET.Element, output_path: str | Path) -> None:
    """Serialise *root* to *output_path* with an XML declaration.

    Args:
        root: The ``<svg>`` root element.
        output_path: Destination file path (created / overwritten).
    """
    _indent_tree(root)
    tree = ET.ElementTree(root)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(fh, encoding="utf-8", xml_declaration=False)
    print(f"[shared] Written → {out}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Colour utilities
# ═══════════════════════════════════════════════════════════════════════════════

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a ``#rrggbb`` string to an (R, G, B) integer tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(hex_color: str) -> float:
    """Compute relative luminance [0–1] of a hex colour (sRGB).

    Uses the WCAG 2.1 formula for perceptual luminance, useful when
    choosing text colour for a given background.
    """
    r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def css_style_block(svg_root: ET.Element, css: str) -> ET.Element:
    """Inject a ``<style>`` element with CDATA-wrapped CSS into *svg_root*.

    The CDATA wrapper prevents XML parsers from choking on ``<`` ``>`` ``&``
    inside CSS rules.

    Args:
        svg_root: The ``<svg>`` element (prepended, not appended).
        css: Raw CSS string.

    Returns:
        The ``<style>`` element.
    """
    style = ET.Element("style")
    style.text = f"\n{textwrap.dedent(css)}\n"
    # Prepend so it comes before all visual elements
    svg_root.insert(0, style)
    return style
