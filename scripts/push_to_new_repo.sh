#!/usr/bin/env bash
# After creating an EMPTY GitHub repo (e.g. ParallelWeightedA-), run from repo root:
#   bash scripts/push_to_new_repo.sh [NEW_REPO_NAME]
#
# Default NEW_REPO_NAME=ParallelWeightedA-
# Creates/updates remote "origin" to https://github.com/jpark9013/<name>.git and pushes main.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

USER="${GITHUB_USER:-jpark9013}"
NEW_NAME="${1:-ParallelWeightedA-}"
NEW_URL="https://github.com/${USER}/${NEW_NAME}.git"

if git remote get-url origin >/dev/null 2>&1; then
  echo "Removing old origin: $(git remote get-url origin)"
  git remote remove origin
fi

echo "Adding origin -> $NEW_URL"
git remote add origin "$NEW_URL"

echo "Pushing main..."
git push -u origin main

echo "Done. Default branch on GitHub should be main; set repo description on the website if needed."
