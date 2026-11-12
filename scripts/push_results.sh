#!/usr/bin/env bash
# Commit the JSON run records, figures and tables and push them to the current branch.
#   bash scripts/push_results.sh "E3 sweep, 3 seeds"
set -euo pipefail
cd "$(dirname "$0")/.."
MSG=${1:-"Add run records and figures ($(date -u +%Y-%m-%dT%H:%MZ))"}
git add -f results/**/*.json figures/ docs/ logs/*.log 2>/dev/null || true
git add -A
git commit -m "$MSG" || echo "nothing to commit"
git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
