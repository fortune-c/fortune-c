"""
make_readme.py – Generate a terminal-style README.md for the GitHub profile.

Creates a single README.md with:
- Left side: ASCII art portrait
- Right side: Terminal-style info card with system info, languages, and stats

Usage
-----
    python scripts/make_readme.py
    python scripts/make_readme.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import load_config


def generate_readme(cfg: dict, ascii_art: str) -> str:
    """Generate the README.md content.

    Args:
        cfg: Loaded config dict.
        ascii_art: Plain text ASCII art string.

    Returns:
        Complete README.md content as a string.
    """
    github = cfg["github_username"]
    name = cfg["display_name"]
    info_rows = cfg["info_rows"]
    links = cfg["links"]

    # Build the info rows for the terminal card
    info_lines = []
    for row in info_rows:
        label = row["label"]
        value = row["value"]
        info_lines.append(f"  {label + ':':<18} {value}")

    info_card = "\n".join(info_lines)

    # GitHub stats badges using shields.io
    stats_badges = f"""[![Repos](https://img.shields.io/badge/Repos-{get_repos_count(github)}-blue?style=flat-square&logo=github)](https://github.com/{github}?tab=repositories)
[![Stars](https://img.shields.io/github/stars/{github}?style=flat-square&logo=github&color=yellow)](https://github.com/{github}/stargazers)
[![Followers](https://img.shields.io/github/followers/{github}?style=flat-square&logo=github&color=purple)](https://github.com/{github}?tab=followers)"""

    readme = f"""<!-- README.md – {name}'s GitHub Profile -->

<table>
  <tr>
    <td valign="top" width="50%">
      <pre>
{ascii_art}
      </pre>
    </td>
    <td valign="top" width="50%">
      <pre>
{cfg["terminal_prompt"]}
{info_card}
      </pre>
      <hr>
      <b>GitHub Stats</b>
      <br>
      {stats_badges}
      <hr>
      <b>Connect</b>
      <ul>
        <li><b>GitHub:</b> <a href="{links["github"]}">{github}</a></li>
        <li><b>Twitter/X:</b> <a href="{links["twitter"]}">@fortunevm</a></li>
        <li><b>LinkedIn:</b> <a href="{links["linkedin"]}">linkedin.com/in/fortune-c</a></li>
      </ul>
    </td>
  </tr>
</table>

---

<div align="center">

![Profile Views](https://komarev.com/ghpvc/?username={github}&color=blueviolet&style=flat-square)

</div>
"""
    return readme


def get_repos_count(username: str) -> str:
    """Get repo count from GitHub API or return placeholder."""
    try:
        import urllib.request
        import json

        url = f"https://api.github.com/users/{username}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return str(data.get("public_repos", "?"))
    except Exception:
        return "?"


def run(config_path: Path | None = None) -> Path:
    """Run the README generator.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated README.md.
    """
    cfg = load_config(config_path)

    ascii_path = _PROJECT_ROOT / "generated" / "ascii-art.txt"
    if not ascii_path.exists():
        sys.exit(
            f"[make_readme] ASCII art not found: {ascii_path}\n"
            "Run 'python scripts/make_ascii_text.py' first."
        )

    print(f"[make_readme] Reading ASCII art from {ascii_path} …")
    ascii_art = ascii_path.read_text()

    readme_content = generate_readme(cfg, ascii_art)

    output_path = _PROJECT_ROOT / "README.md"
    output_path.write_text(readme_content)
    print(f"[make_readme] Wrote {output_path}")
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a terminal-style README.md for GitHub profile."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
