#!/usr/bin/env bash
# run_all.sh – Regenerate GitHub profile assets.
#
# Usage:
#   ./run_all.sh              # full pipeline (includes photo prep)
#   ./run_all.sh --skip-photo # skip photo prep (faster; uses cached profile_clean.png)
#
# The script exits immediately if any step fails.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SKIP_PHOTO=false
for arg in "$@"; do
  [[ "$arg" == "--skip-photo" ]] && SKIP_PHOTO=true
done

# Activate virtual environment if it exists
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "⚠  No .venv found. Install dependencies with:"
  echo "   python -m venv .venv && source .venv/bin/activate"
  echo "   pip install -r scripts/requirements.txt"
  exit 1
fi

echo "══════════════════════════════════════════"
echo "  GitHub Profile – Regenerate README"
echo "══════════════════════════════════════════"

if [[ "$SKIP_PHOTO" == "false" ]]; then
  echo ""
  echo "▶ Step 1/3 – Pre-process portrait photo …"
  python scripts/prep_photo.py
else
  echo ""
  echo "▶ Step 1/3 – Skipping photo prep (--skip-photo)"
fi

echo ""
echo "▶ Step 2/3 – Generate ASCII art text …"
python scripts/make_ascii_text.py

echo ""
echo "▶ Step 3/3 – Generate README.md …"
python scripts/make_readme.py

echo ""
echo "══════════════════════════════════════════"
echo "  ✓ README.md generated successfully!"
echo "══════════════════════════════════════════"
