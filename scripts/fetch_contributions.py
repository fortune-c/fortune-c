"""
fetch_contributions.py – Scrape GitHub contribution data without a token.

Strategy
--------
GitHub renders each user's public contribution calendar at:

    https://github.com/users/<username>/contributions

The response is an HTML fragment (not a full page) containing an SVG-like
table of ``<td>`` elements with ``data-date`` and ``data-level`` attributes.
No authentication is required.

Computed statistics
-------------------
- total_contributions: sum of all counts in the past year
- longest_streak: longest run of consecutive days with ≥ 1 contribution
- current_streak: number of consecutive days ending today with ≥ 1 contribution
- busiest_day: date with the highest single-day count
- monthly_totals: dict mapping "YYYY-MM" → total for that month

Output
------
Saves to ``data/contributions.json`` (path configurable).

Usage
-----
    python scripts/fetch_contributions.py
    python scripts/fetch_contributions.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:
    sys.exit(
        f"[fetch_contributions] Missing dependency: {exc}.\n"
        "Run: pip install -r scripts/requirements.txt"
    )

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import load_config


# ═══════════════════════════════════════════════════════════════════════════════
#  Scraping
# ═══════════════════════════════════════════════════════════════════════════════

_CONTRIBUTIONS_URL = "https://github.com/users/{username}/contributions"

_HEADERS = {
    "Accept": "text/html, application/xhtml+xml",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_raw_html(username: str) -> str:
    """Fetch the raw HTML fragment from GitHub's contributions endpoint.

    Args:
        username: GitHub username (no ``@``).

    Returns:
        Raw HTML string.

    Raises:
        SystemExit: If the request fails or returns a non-200 status.
    """
    url = _CONTRIBUTIONS_URL.format(username=username)
    print(f"[fetch] GET {url}")
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(f"[fetch] HTTP request failed: {exc}")
    return resp.text


def parse_contributions(html: str) -> list[dict]:
    """Parse the contribution calendar HTML into a list of day records.

    Each ``<td>`` with a ``data-date`` attribute represents one calendar day.
    GitHub currently uses ``data-level`` (0–4) for the contribution intensity
    and ``data-count`` or a tooltip ``title`` attribute for the exact count.

    Args:
        html: Raw HTML fragment from the contributions endpoint.

    Returns:
        List of dicts with keys ``date`` (ISO string), ``level`` (int 0–4),
        ``count`` (int ≥ 0).
    """
    soup = BeautifulSoup(html, "html.parser")

    days: list[dict] = []

    # GitHub renders contribution squares as <td> with data-date attributes.
    # Some older versions used <rect> inside an SVG – we try both.
    cells = soup.find_all("td", attrs={"data-date": True})
    if not cells:
        # Fallback: try <rect> elements (older GitHub markup)
        cells = soup.find_all("rect", attrs={"data-date": True})

    if not cells:
        print("[fetch] WARNING: No contribution cells found. The page structure may have changed.")
        return []

    for cell in cells:
        date_str: str = cell.get("data-date", "")
        if not date_str:
            continue

        # Level: 0 = no contributions, 4 = maximum
        level_str: str = cell.get("data-level", "0")
        try:
            level = int(level_str)
        except ValueError:
            level = 0

        # Count: try data-count first, then parse title attribute
        count_str: str = cell.get("data-count", "")
        if count_str.isdigit():
            count = int(count_str)
        else:
            # Parse from title like "3 contributions on January 15, 2024"
            title: str = cell.get("title", "") or cell.get("aria-label", "")
            count = _parse_count_from_title(title)

        days.append({"date": date_str, "level": level, "count": count})

    # Sort chronologically
    days.sort(key=lambda d: d["date"])
    print(f"[fetch] Parsed {len(days)} days of contribution data")
    return days


def _parse_count_from_title(title: str) -> int:
    """Extract contribution count from a tooltip title string.

    Examples:
        "3 contributions on January 15, 2024" → 3
        "No contributions on January 15, 2024" → 0
        "1 contribution on February 3, 2024" → 1

    Args:
        title: Tooltip text.

    Returns:
        Integer count, 0 if not parseable.
    """
    import re
    if not title:
        return 0
    m = re.match(r"(\d+)\s+contribution", title, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
#  Statistics computation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_stats(days: list[dict]) -> dict:
    """Compute aggregate statistics from the parsed contribution data.

    Args:
        days: Sorted list of day records (from :func:`parse_contributions`).

    Returns:
        Dict with keys:
            - ``total_contributions`` (int)
            - ``longest_streak`` (int)  – in days
            - ``current_streak`` (int)  – in days
            - ``busiest_day`` (dict with ``date`` and ``count`` keys)
            - ``monthly_totals`` (dict mapping ``"YYYY-MM"`` → int)
    """
    if not days:
        return {
            "total_contributions": 0,
            "longest_streak": 0,
            "current_streak": 0,
            "busiest_day": {"date": "", "count": 0},
            "monthly_totals": {},
        }

    total = sum(d["count"] for d in days)

    # Build a date → count lookup for streak computation
    lookup: dict[str, int] = {d["date"]: d["count"] for d in days}

    # Longest streak
    longest_streak = 0
    current_run = 0

    for d in days:
        if d["count"] > 0:
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 0

    # Current streak (walk backwards from today)
    today = date.today()
    current_streak = 0
    check_date = today
    for _ in range(366):
        date_str = check_date.isoformat()
        count = lookup.get(date_str, 0)
        if count > 0:
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Busiest day
    busiest = max(days, key=lambda d: d["count"])

    # Monthly totals
    monthly: dict[str, int] = {}
    for d in days:
        month_key = d["date"][:7]  # "YYYY-MM"
        monthly[month_key] = monthly.get(month_key, 0) + d["count"]

    return {
        "total_contributions": total,
        "longest_streak": longest_streak,
        "current_streak": current_streak,
        "busiest_day": {"date": busiest["date"], "count": busiest["count"]},
        "monthly_totals": monthly,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Fetch and save contribution data.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the saved JSON file.
    """
    cfg = load_config(config_path)
    username: str = cfg["github_username"]

    html = fetch_raw_html(username)
    days = parse_contributions(html)
    stats = compute_stats(days)

    payload = {
        "username": username,
        "fetched_at": date.today().isoformat(),
        "days": days,
        "stats": stats,
    }

    output_path = _PROJECT_ROOT / "data" / "contributions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"[fetch] Saved {len(days)} days → {output_path}")
    print(f"[fetch] Stats: total={stats['total_contributions']}, "
          f"longest_streak={stats['longest_streak']}, "
          f"current_streak={stats['current_streak']}")
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch GitHub contribution data (no token required)."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
