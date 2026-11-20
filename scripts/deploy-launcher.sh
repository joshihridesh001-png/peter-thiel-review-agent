#!/usr/bin/env bash
# Runs the newest scripts/deploy.sh from origin/main, not the copy on disk.
#
# Install once on the VPS OUTSIDE the repo, so a pull never changes it:
#   cp scripts/deploy-launcher.sh /root/bin/peter-deploy
# The deploy key's forced command points at /root/bin/peter-deploy.
#
# Why: if deploy.sh has a bug, the old copy on the server can't pull the
# fix. Taking deploy.sh from main means a fixed script is used right away.
#
# Keep this file tiny. A bug here needs a manual fix on the server.

set -euo pipefail

REPO="${PETER_REPO_DIR:-/root/peter-thiel-review-agent}"
cd "$REPO"
git fetch --quiet origin main
SCRIPT="$(mktemp /tmp/peter-deploy.XXXXXX.sh)"
git show origin/main:scripts/deploy.sh > "$SCRIPT"
PETER_REPO_DIR="$REPO" PETER_DEPLOY_COPY="$SCRIPT" exec bash "$SCRIPT" "$@"
