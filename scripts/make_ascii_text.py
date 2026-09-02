"""
make_ascii_text.py – Convert a pre-processed portrait to plain ASCII text.

Unlike make_ascii_svg.py which generates an animated SVG, this outputs a
simple text file that can be embedded in README.md inside a <pre> block.

Usage
-----
    python scripts/make_ascii_text.py
    python scripts/make_ascii_text.py --config path/to/config.yaml
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
        f"[make_ascii_text] Missing dependency: {exc}.\n"
        "Run: pip install -r scripts/requirements.txt"
    )

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import load_config


def image_to_ascii_grid(
    img_path: Path,
    brightness_ramp: str,
) -> list[str]:
    """Convert a greyscale image to a 2-D grid of ASCII characters.

    The image is **inverted** before conversion so that the white background
    maps to the space character, while the dark portrait subject maps to the
    denser characters at the end of the ramp.
    """
    img = Image.open(img_path).convert("L")
    img = ImageOps.invert(img)
    pixels = np.array(img, dtype=np.uint8)

    ramp = brightness_ramp
    n = len(ramp) - 1

    rows: list[str] = []
    for row in pixels:
        chars = "".join(ramp[int(p / 255 * n)] for p in row)
        rows.append(chars)

    max_len = max(len(r) for r in rows)
    rows = [r.ljust(max_len) for r in rows]
    return rows


def run(config_path: Path | None = None) -> Path:
    """Run the ASCII text generator.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the generated text file.
    """
    cfg = load_config(config_path)
    portrait_cfg = cfg["portrait"]

    cleaned_path = _PROJECT_ROOT / portrait_cfg["cleaned_path"]
    if not cleaned_path.exists():
        sys.exit(
            f"[make_ascii_text] Cleaned image not found: {cleaned_path}\n"
            "Run 'python scripts/prep_photo.py' first."
        )

    brightness_ramp = portrait_cfg["brightness_ramp"]
    ascii_width = int(portrait_cfg["ascii_width_chars"])

    print(f"[make_ascii_text] Converting {cleaned_path} → ASCII text …")

    # Open image and resize to target width
    img = Image.open(cleaned_path).convert("L")
    aspect_ratio = img.height / img.width
    new_height = int(ascii_width * aspect_ratio * 0.55)  # char height ratio
    img = img.resize((ascii_width, new_height))

    # Invert and convert
    img = ImageOps.invert(img)
    pixels = np.array(img, dtype=np.uint8)

    ramp = brightness_ramp
    n = len(ramp) - 1

    rows: list[str] = []
    for row in pixels:
        chars = "".join(ramp[int(p / 255 * n)] for p in row)
        rows.append(chars.rstrip())

    # Strip leading empty rows
    while rows and not rows[0].strip():
        rows.pop(0)

    print(f"[make_ascii_text] Grid: {len(rows)} rows × {ascii_width} cols")

    output_path = _PROJECT_ROOT / "generated" / "ascii-art.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write("\n".join(rows))

    print(f"[make_ascii_text] Wrote {output_path}")
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate plain ASCII text from a portrait photo."
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
