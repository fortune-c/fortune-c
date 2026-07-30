"""
render_heatmap_svg.py – Generate an animated GitHub contribution heatmap SVG.

Layout (53 weeks wide × 7 days tall)
--------------------------------------
The grid follows GitHub's calendar convention:
  - Columns = ISO weeks (Sunday…Saturday or Monday…Sunday depending on locale).
  - Row 0 = Sunday (or Monday), row 6 = Saturday.
  - Missing days at the start/end of the 53-week window are left empty.

Animation
---------
Squares are revealed in a diagonal wave (top-left → bottom-right).
Each square on the same anti-diagonal appears simultaneously.
A SMIL ``<set>`` flips ``opacity`` from ``0`` → ``1`` at the computed time.
After all squares are revealed the SVG freezes.

Stats section
-------------
Below (or beside) the grid:
  - Total contributions this year
  - Current streak
  - Longest streak
  - Busiest day

Usage
-----
    python scripts/render_heatmap_svg.py
    python scripts/render_heatmap_svg.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import (
    animate,
    css_style_block,
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


# ═══════════════════════════════════════════════════════════════════════════════
#  Calendar grid helpers
# ═══════════════════════════════════════════════════════════════════════════════

NUM_WEEKS = 53
DAYS_IN_WEEK = 7

DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_date_grid(days_data: list[dict]) -> list[list[dict | None]]:
    """Arrange contribution days into a 53×7 calendar grid.

    Column 0 is the oldest week; column 52 is the newest (or current) week.
    Row 0 = Sunday, row 6 = Saturday.

    Args:
        days_data: List of ``{"date": "YYYY-MM-DD", "level": 0-4, "count": int}``
            dicts sorted chronologically.

    Returns:
        A ``list[col][row]`` grid where each cell is either ``None`` (empty)
        or a day dict.
    """
    # Build lookup
    lookup: dict[str, dict] = {d["date"]: d for d in days_data}

    # End = today; start = 53 weeks ago adjusted to the first Sunday
    today = date.today()
    # Find the Sunday of the current week
    days_since_sunday = today.weekday() + 1  # Monday=0 so +1 for Sunday=0
    if today.weekday() == 6:  # today is Sunday
        days_since_sunday = 0
    week_start_sunday = today - timedelta(days=days_since_sunday % 7)

    grid_end = week_start_sunday + timedelta(days=6)  # Saturday of current week
    grid_start = grid_end - timedelta(weeks=NUM_WEEKS) + timedelta(days=1)

    # Adjust grid_start to the nearest Sunday on or before it
    while grid_start.weekday() != 6:  # 6 = Sunday in Python (Mon=0)
        grid_start -= timedelta(days=1)

    # Populate grid: grid[col][row]
    grid: list[list[dict | None]] = [[None] * DAYS_IN_WEEK for _ in range(NUM_WEEKS)]

    current = grid_start
    col = 0
    while col < NUM_WEEKS:
        for row in range(DAYS_IN_WEEK):
            d = current + timedelta(days=row)
            if d > today:
                pass  # leave as None (future)
            else:
                date_str = d.isoformat()
                grid[col][row] = lookup.get(date_str, {"date": date_str, "level": 0, "count": 0})
        current += timedelta(weeks=1)
        col += 1

    return grid


def month_label_positions(
    grid: list[list[dict | None]],
    cell_size: float,
    cell_gap: float,
    pad_left: float,
) -> list[tuple[str, float]]:
    """Return (month_name, x_position) tuples for month column labels.

    Scans the grid for week columns whose first valid day starts a new month,
    and records the x-position for that column's label.

    Args:
        grid: 53×7 calendar grid.
        cell_size: Square cell size in px.
        cell_gap: Gap between cells in px.
        pad_left: Left padding (space reserved for day labels).

    Returns:
        List of ``(month_abbreviation, x_pixel)`` tuples.
    """
    labels: list[tuple[str, float]] = []
    step = cell_size + cell_gap
    last_month = -1

    for col_idx, week_col in enumerate(grid):
        # First non-None day in this column
        first_day = next((d for d in week_col if d is not None), None)
        if first_day is None:
            continue
        d = date.fromisoformat(first_day["date"])
        if d.month != last_month:
            x = pad_left + col_idx * step
            labels.append((MONTH_ABBR[d.month - 1], x))
            last_month = d.month

    return labels


# ═══════════════════════════════════════════════════════════════════════════════
#  SVG builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_heatmap_svg(cfg: dict, contributions: dict) -> ET.Element:
    """Build the fully animated heatmap SVG.

    Diagonal reveal animation
    ~~~~~~~~~~~~~~~~~~~~~~~~
    For each cell at (col, row), the anti-diagonal index is ``col + row``.
    The maximum anti-diagonal is ``(NUM_WEEKS - 1) + (DAYS_IN_WEEK - 1) = 58``.
    Each diagonal fires ``stagger_ms`` later than the previous one.
    Each cell fades from opacity 0 → 1 over ``reveal_duration_ms``.

    Args:
        cfg: Loaded config dict.
        contributions: Parsed contributions JSON (from ``data/contributions.json``).

    Returns:
        The ``<svg>`` root element.
    """
    hm_cfg = cfg["heatmap"]
    fonts = cfg["fonts"]
    palette = get_palette(cfg)
    heatmap_colors: list[str] = cfg["heatmap_colors"]

    cell = float(hm_cfg["cell_size"])
    gap = float(hm_cfg["cell_gap"])
    rx = float(hm_cfg["corner_radius"])
    pad_top = float(hm_cfg["padding_top"])
    pad_bot = float(hm_cfg["padding_bottom"])
    pad_left = float(hm_cfg["padding_left"])
    pad_right = float(hm_cfg["padding_right"])
    fs_label = float(hm_cfg["font_size_label"])
    fs_title = float(hm_cfg["font_size_title"])
    fs_stats = float(hm_cfg["font_size_stats"])
    title_text = str(hm_cfg["title"])
    stagger_ms = float(hm_cfg["stagger_ms"])
    reveal_ms = float(hm_cfg["reveal_duration_ms"])
    glow_blur = float(hm_cfg["glow_blur"])
    mono = fonts["mono"]
    sans = fonts["sans"]

    step = cell + gap  # pixels per cell (width + gap)

    # Canvas dimensions
    grid_w = NUM_WEEKS * step - gap
    grid_h = DAYS_IN_WEEK * step - gap

    canvas_w = int(pad_left + grid_w + pad_right)
    canvas_h = int(pad_top + grid_h + pad_bot)

    # ── Root & defs ──────────────────────────────────────────────────────────
    root = svg_root(canvas_w, canvas_h, extra_attrs={"aria-label": "GitHub contribution heatmap"})
    defs = make_defs(root)
    glow_filter(defs, "heatmap-glow", blur=glow_blur, color=palette.green)

    # Background
    rect(root, 0, 0, canvas_w, canvas_h, fill=palette.background, rx=10)

    # ── Title ────────────────────────────────────────────────────────────────
    title_y = pad_top * 0.45
    text_el(
        root, title_text,
        canvas_w / 2, title_y,
        fill=palette.text,
        font_family=sans,
        font_size=fs_title,
        font_weight="bold",
        text_anchor="middle",
        dominant_baseline="middle",
    )

    # ── Month labels ─────────────────────────────────────────────────────────
    days_data: list[dict] = contributions.get("days", [])
    grid = build_date_grid(days_data)
    month_labels = month_label_positions(grid, cell, gap, pad_left)

    month_y = pad_top - fs_label - 4
    for month_name, mx in month_labels:
        text_el(
            root, month_name,
            mx, month_y,
            fill=palette.subtext,
            font_family=sans,
            font_size=fs_label,
        )

    # ── Day-of-week labels (Sun Mon … Sat) ──────────────────────────────────
    for row_idx, day_name in enumerate(DAY_LABELS):
        # Only label Sun, Wed, Fri to avoid clutter
        if row_idx not in (0, 2, 4, 6):
            continue
        lx = pad_left - 4
        ly = pad_top + row_idx * step + cell / 2
        text_el(
            root, day_name,
            lx, ly,
            fill=palette.subtext,
            font_family=sans,
            font_size=fs_label,
            text_anchor="end",
            dominant_baseline="middle",
        )

    # ── Grid cells ───────────────────────────────────────────────────────────
    grid_g = group(root)

    for col_idx, week_col in enumerate(grid):
        for row_idx, day_data in enumerate(week_col):
            if day_data is None:
                continue

            level = int(day_data.get("level", 0))
            count = int(day_data.get("count", 0))
            color = heatmap_colors[min(level, len(heatmap_colors) - 1)]

            cx = pad_left + col_idx * step
            cy = pad_top + row_idx * step

            # Anti-diagonal index drives the stagger
            diag = col_idx + row_idx
            begin_ms = diag * stagger_ms

            # Each cell starts invisible
            cell_el = rect(
                grid_g,
                cx, cy, cell, cell,
                fill=color,
                rx=rx,
                opacity="0",
            )

            # Tooltip
            cell_el.set("aria-label", f"{count} contributions on {day_data['date']}")

            # Apply glow filter only for high-activity cells (level ≥ 3)
            if level >= 3:
                cell_el.set("filter", "url(#heatmap-glow)")

            # Diagonal reveal: opacity 0 → 1
            animate(
                cell_el, "opacity", "0", "1",
                begin=ms_to_smil(begin_ms),
                dur=ms_to_smil(reveal_ms),
            )

    # ── Legend ───────────────────────────────────────────────────────────────
    legend_y = pad_top + grid_h + (pad_bot * 0.35)
    legend_x_start = canvas_w - pad_right - (len(heatmap_colors) * (cell + 3))

    text_el(
        root, "Less",
        legend_x_start - 34, legend_y + cell / 2,
        fill=palette.subtext,
        font_family=sans,
        font_size=fs_label,
        dominant_baseline="middle",
    )
    for i, color in enumerate(heatmap_colors):
        lx = legend_x_start + i * (cell + 3)
        rect(root, lx, legend_y, cell, cell, fill=color, rx=rx)
    text_el(
        root, "More",
        legend_x_start + len(heatmap_colors) * (cell + 3) + 4,
        legend_y + cell / 2,
        fill=palette.subtext,
        font_family=sans,
        font_size=fs_label,
        dominant_baseline="middle",
    )

    # ── Stats strip ──────────────────────────────────────────────────────────
    stats: dict = contributions.get("stats", {})
    total = stats.get("total_contributions", 0)
    longest = stats.get("longest_streak", 0)
    current_s = stats.get("current_streak", 0)
    busiest: dict = stats.get("busiest_day", {})
    busiest_str = f"{busiest.get('date', 'N/A')} ({busiest.get('count', 0)})"

    stats_items = [
        (str(total), "contributions"),
        (str(current_s), "day streak"),
        (str(longest), "longest streak"),
        (busiest_str, "busiest day"),
    ]

    stats_y_val = pad_top + grid_h + pad_bot * 0.65
    stats_y_lbl = stats_y_val + fs_stats + 3
    n_stats = len(stats_items)
    for i, (val, lbl) in enumerate(stats_items):
        sx = pad_left + (grid_w / (n_stats)) * (i + 0.5)
        text_el(
            root, val,
            sx, stats_y_val,
            fill=palette.green,
            font_family=mono,
            font_size=fs_stats,
            font_weight="bold",
            text_anchor="middle",
        )
        text_el(
            root, lbl,
            sx, stats_y_lbl,
            fill=palette.subtext,
            font_family=sans,
            font_size=fs_stats - 1,
            text_anchor="middle",
        )

    return root


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def load_contributions(cfg: dict) -> dict:
    """Load contribution data from the JSON file.

    Falls back to an empty scaffold if the file doesn't exist yet so the
    heatmap can still be generated (all cells will be level 0).

    Args:
        cfg: Loaded config dict.

    Returns:
        Contributions dict.
    """
    path = _PROJECT_ROOT / "data" / "contributions.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    print("[heatmap] WARNING: contributions.json not found – using empty data.")
    return {"days": [], "stats": {}}


def run(config_path: Path | None = None) -> Path:
    """Generate the heatmap SVG.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated SVG.
    """
    cfg = load_config(config_path)
    contributions = load_contributions(cfg)

    svg_el = build_heatmap_svg(cfg, contributions)

    output_path = _PROJECT_ROOT / "generated" / "contrib-heatmap.svg"
    write_svg(svg_el, output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate an animated contribution heatmap SVG."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
