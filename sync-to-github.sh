#!/usr/bin/env bash
# One-command sync of THIS local folder to a NEW GitHub repo for the OKX paid esports API.
# Run on your own Mac, inside this folder:
#   bash sync-to-github.sh                         # uses the default repo below
#   bash sync-to-github.sh <git-remote-url>        # or pass your own repo URL
#   bash sync-to-github.sh <git-remote-url> "msg"  # + custom commit message
set -e
cd "$(dirname "$0")"

# CHANGE this to the repo you create on GitHub for the OKX paid version:
REPO="${1:-https://github.com/ForegatePrediction/FG-esports-prediction-okx.git}"
MSG="${2:-Esports prediction API + x402 pay-per-call gate (OKX A2MCP ASP)}"

rm -f .git/index.lock 2>/dev/null || true
[ -d .git ] || git init
git branch -M main 2>/dev/null || true
git config user.name  "$(git config user.name  || echo Dave)" >/dev/null 2>&1 || true
git config user.email "$(git config user.email || echo davewell@gphtech.com)" >/dev/null 2>&1 || true
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO"

git add -A
echo "=== Changes to be pushed (raw data + .env stay gitignored) ==="
git status --short
echo

git commit -m "$MSG" || echo "(nothing to commit)"

# Overwrite GitHub with this local version (local is the source of truth).
git push -u origin main --force

echo
echo "Done. Repo: $REPO"
echo "Next: create a NEW Render web service from this repo (render.yaml is included),"
echo "      set PAY_TO_ADDRESS + OKX_API_KEY/SECRET/PASSPHRASE in the dashboard,"
echo "      flip PAYWALL_ENABLED=true when ready to charge."
