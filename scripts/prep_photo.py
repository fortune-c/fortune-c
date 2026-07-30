"""
prep_photo.py – Portrait pre-processing pipeline.

Steps
-----
1. Remove background using rembg (U²-Net model).
2. Convert to grayscale.
3. Apply CLAHE (Contrast Limited Adaptive Histogram Equalisation) for
   dramatic tonal contrast without clipping highlights.
4. Composite the alpha-masked greyscale image on a solid white background.
5. Resize to the width configured in ``config.yaml`` (preserving aspect ratio).
6. Save to ``assets/profile_clean.png``.

Usage
-----
    python scripts/prep_photo.py
    python scripts/prep_photo.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Graceful import errors with helpful messages ──────────────────────────────
try:
    import cv2  # type: ignore
    import numpy as np
    from PIL import Image
    from rembg import remove  # type: ignore
except ImportError as exc:
    sys.exit(
        f"[prep_photo] Missing dependency: {exc}.\n"
        "Run: pip install -r scripts/requirements.txt"
    )

# Locate project root relative to this script
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from shared import load_config


# ═══════════════════════════════════════════════════════════════════════════════
#  Core pipeline steps
# ═══════════════════════════════════════════════════════════════════════════════

def remove_background(image_path: Path) -> Image.Image:
    """Remove the background of an image using rembg (U²-Net).

    Args:
        image_path: Path to the source portrait (JPEG, PNG, …).

    Returns:
        A PIL :class:`Image` in RGBA mode with the background made transparent.
    """
    print(f"[prep_photo] Removing background from {image_path} …")
    with image_path.open("rb") as fh:
        raw = fh.read()
    result_bytes = remove(raw)
    img = Image.open(__import__("io").BytesIO(result_bytes)).convert("RGBA")
    print(f"[prep_photo] Background removed – size {img.size}")
    return img


def to_grayscale_clahe(rgba_img: Image.Image) -> Image.Image:
    """Convert RGBA image to enhanced greyscale using CLAHE.

    Workflow:
      RGBA  →  RGB  →  LAB  →  CLAHE on L channel  →  Merge  →  grey RGBA

    Args:
        rgba_img: Source image in RGBA mode.

    Returns:
        A PIL image in RGBA mode; colour channels are all-equal (greyscale)
        but the original alpha channel is preserved so background removal is
        kept intact.
    """
    print("[prep_photo] Applying CLAHE …")
    # Separate alpha for later
    r, g, b, a = rgba_img.split()
    rgb = Image.merge("RGB", (r, g, b))

    # OpenCV expects BGR uint8 ndarray
    bgr = cv2.cvtColor(np.array(rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)

    # Convert to LAB to operate on luminance only
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)

    # CLAHE: clipLimit 3.0, tileGridSize 8×8 – strong but not over-sharpened
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_ch)

    # Merge back and convert to greyscale via luminance
    lab_enhanced = cv2.merge([l_enhanced, a_ch, b_ch])
    bgr_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    grey_bgr = cv2.cvtColor(bgr_enhanced, cv2.COLOR_BGR2GRAY)

    # Back to PIL
    grey_pil = Image.fromarray(grey_bgr, mode="L")
    # Re-create RGBA using the enhanced grey for R/G/B and original alpha
    rgba_grey = Image.merge("RGBA", (grey_pil, grey_pil, grey_pil, a))
    print("[prep_photo] CLAHE applied")
    return rgba_grey


def composite_on_white(rgba_img: Image.Image) -> Image.Image:
    """Flatten an RGBA image onto a pure-white background.

    Args:
        rgba_img: Source RGBA image (subject already extracted).

    Returns:
        A PIL image in RGB mode (no alpha channel).
    """
    white_bg = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
    white_bg.paste(rgba_img, mask=rgba_img.split()[3])
    return white_bg.convert("RGB")


def resize_image(img: Image.Image, target_width_chars: int, char_height_ratio: float) -> Image.Image:
    """Resize image to fit the ASCII art canvas dimensions.

    The *target_width_chars* is the number of character columns in the output
    ASCII art.  Each character cell is taller than wide (roughly 2:1 in most
    terminals), so the image must be pre-compressed vertically to prevent the
    ASCII output from appearing vertically stretched.

    Args:
        img: Source RGB image.
        target_width_chars: Number of character columns.
        char_height_ratio: Height-to-width ratio of one character cell
            (e.g. 0.55 means characters are ~55% as tall as they are wide).

    Returns:
        Resized PIL image.
    """
    orig_w, orig_h = img.size
    target_w = target_width_chars
    target_h = int(orig_h * (target_width_chars / orig_w) * char_height_ratio)
    resized = img.resize((target_w, target_h), Image.LANCZOS)
    print(f"[prep_photo] Resized to {resized.size} for ASCII ({target_width_chars} cols)")
    return resized


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(config_path: Path | None = None) -> Path:
    """Execute the full portrait pre-processing pipeline.

    Args:
        config_path: Optional path to ``config.yaml``.

    Returns:
        Path to the cleaned output image.
    """
    cfg = load_config(config_path)
    portrait_cfg = cfg["portrait"]

    source_path = _PROJECT_ROOT / portrait_cfg["source_path"]
    cleaned_path = _PROJECT_ROOT / portrait_cfg["cleaned_path"]
    ascii_width = int(portrait_cfg["ascii_width_chars"])
    char_ratio = float(portrait_cfg["char_height_ratio"])

    if not source_path.exists():
        sys.exit(f"[prep_photo] Source image not found: {source_path}")

    # Pipeline
    rgba = remove_background(source_path)
    rgba_grey = to_grayscale_clahe(rgba)
    rgb = composite_on_white(rgba_grey)
    rgb_resized = resize_image(rgb, ascii_width, char_ratio)

    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    rgb_resized.save(str(cleaned_path), "PNG")
    print(f"[prep_photo] Saved cleaned image → {cleaned_path}")
    return cleaned_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-process a portrait photo for ASCII art generation."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: <project_root>/config.yaml)",
    )
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
