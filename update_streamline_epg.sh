#!/usr/bin/env bash
set -euo pipefail

python3 generate_streamline_epg.py

git add --all --force "StreamLine_epg.xml.gz"

if git diff --cached --quiet; then
  echo "No StreamLine EPG changes to commit."
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

DATE=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
git commit -m "chore: update StreamLine EPG ($DATE)"
git push origin HEAD:${GITHUB_REF_NAME:-main}
