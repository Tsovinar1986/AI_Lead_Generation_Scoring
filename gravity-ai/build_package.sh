#!/usr/bin/env bash
# Assembles the Gravity AI submission zip.
#
# Gravity AI expects a single self-contained project (gravityai-build.json at
# the root, entry script + its dependencies under src/). This repo's scoring
# logic lives in backend/app/ and is shared with the interactive FastAPI
# service, so rather than forking a duplicate copy that drifts out of sync,
# this script copies just the modules score_leads.py actually imports into
# a dist/ folder shaped the way Gravity AI expects, then zips it.
#
# Usage: ./build_package.sh
# Output: dist/gravity-ai-lead-scoring.zip

set -euo pipefail
cd "$(dirname "$0")"

ROOT="$(cd .. && pwd)"
DIST="$(pwd)/dist"
PKG="$DIST/package"

rm -rf "$DIST"
mkdir -p "$PKG/src/app/services" "$PKG/src/app/llm"

cp gravityai-build.json requirements.txt test_input.csv "$PKG/"
cp src/score_leads.py "$PKG/src/"

cp "$ROOT/backend/app/__init__.py" "$PKG/src/app/"
cp "$ROOT/backend/app/config.py" "$PKG/src/app/"
cp "$ROOT/backend/app/models.py" "$PKG/src/app/"
cp "$ROOT/backend/app/llm/__init__.py" "$PKG/src/app/llm/"
cp "$ROOT/backend/app/llm/client.py" "$PKG/src/app/llm/"
cp "$ROOT/backend/app/services/__init__.py" "$PKG/src/app/services/"
cp "$ROOT/backend/app/services/ingestion.py" "$PKG/src/app/services/"
cp "$ROOT/backend/app/services/enrichment.py" "$PKG/src/app/services/"
cp "$ROOT/backend/app/services/scoring.py" "$PKG/src/app/services/"
cp "$ROOT/backend/app/services/outreach.py" "$PKG/src/app/services/"

find "$PKG" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

(cd "$PKG" && zip -r -q "$DIST/gravity-ai-lead-scoring.zip" .)

echo "Built $DIST/gravity-ai-lead-scoring.zip"
