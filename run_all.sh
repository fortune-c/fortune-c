#!/usr/bin/env bash
# run_all.sh – Regenerate every profile art asset in one command.
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
echo "  Animated GitHub Profile – Full Rebuild"
echo "══════════════════════════════════════════"

if [[ "$SKIP_PHOTO" == "false" ]]; then
echo ""
echo "▶ Step 1/6 – Pre-process portrait photo …"
python scripts/prep_photo.py
else
  echo ""
  echo "▶ Step 1/6 – Skipping photo prep (--skip-photo)"
fi

echo ""
echo "▶ Step 2/6 – Render ASCII portrait …"
python scripts/make_ascii_svg.py

echo ""
echo "▶ Step 3/6 – Render info card …"
python scripts/make_info_card.py

echo ""
echo "▶ Step 4/6 – Render animated banner …"
python scripts/make_banner_svg.py

echo ""
echo "▶ Step 5/6 – Render tech stack card …"
python scripts/make_tech_stack_svg.py

echo ""
echo "▶ Step 6/6 – Render Spotify card …"
python scripts/make_spotify_svg.py

echo ""
echo "══════════════════════════════════════════"
echo "  ✓ All assets generated in generated/"
echo "══════════════════════════════════════════"
