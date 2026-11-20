#!/usr/bin/env bash
# Pull the latest main onto the VPS and restart Peter Thiel.
#
# GitHub runs this over SSH after the tests pass on main. The deploy key
# on the VPS is locked to this one script (see docs/DEPLOY.md).
#
# It stops, and changes nothing, when:
#   - it is a time when a restart would repeat a nightly post
#   - someone edited a tracked file by hand on the server
#   - the update is not a clean fast-forward
# If the bot does not come back after the restart, it rolls back.

set -euo pipefail

# The pull below rewrites this file. Bash reads a script as it runs, so run
# from a copy and leave the real file free to change.
if [[ -z "${PETER_DEPLOY_COPY:-}" ]]; then
    PETER_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    COPY="$(mktemp /tmp/peter-deploy.XXXXXX.sh)"
    cp "${BASH_SOURCE[0]}" "$COPY"
    export PETER_REPO_DIR PETER_DEPLOY_COPY="$COPY"
    exec bash "$COPY" "$@"
fi
trap 'rm -f "$PETER_DEPLOY_COPY"' EXIT

REPO_DIR="$PETER_REPO_DIR"
SERVICE="peter-thiel.service"
BACKUP_DIR="$REPO_DIR/backups"
KEEP_BACKUPS=14
TRY_LATER=75

say() {
    echo "[deploy] $*"
    command -v logger >/dev/null 2>&1 && logger -t peter-deploy -- "$*" || true
}

# ── 1. Quiet hours ────────────────────────────────────────────────────────────
# The scheduler remembers in memory what it already posted today. A restart
# forgets, so restarting at these times posts the same thing twice.
#   19:10–22:05 IST every day: 7:15 check, 8:00 card, 9:00 goals, 9:30 nudge
#   09:55–11:05 IST on the 1st: monthly equity post
in_quiet_hours() {
    local now day hhmm
    now="${PETER_DEPLOY_NOW:-$(TZ=Asia/Kolkata date +'%d %H%M')}"
    day="${now%% *}"
    hhmm="${now##* }"
    day=$((10#$day))
    hhmm=$((10#$hhmm))
    if (( hhmm >= 1910 && hhmm <= 2205 )); then
        return 0
    fi
    if (( day == 1 && hhmm >= 955 && hhmm <= 1105 )); then
        return 0
    fi
    return 1
}

if in_quiet_hours; then
    say "Quiet hours (nightly posts or monthly equity). Nothing changed. Re-run the deploy after 22:05 IST."
    exit "$TRY_LATER"
fi
if [[ "${PETER_DEPLOY_CHECK_ONLY:-}" == "1" ]]; then
    say "Not quiet hours. A deploy would go ahead."
    exit 0
fi

cd "$REPO_DIR"

# Only one deploy at a time.
exec 9>"/tmp/peter-thiel-deploy.lock"
if ! flock -n 9; then
    say "Another deploy is running. Nothing changed."
    exit "$TRY_LATER"
fi

# ── 2. Hand edits block the pull ──────────────────────────────────────────────
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    say "Files were edited by hand on the server. Nothing changed:"
    git status --short --untracked-files=no
    say "Fix: git stash push -m 'server edits' <file>, then re-run the deploy."
    exit 1
fi

BEFORE="$(git rev-parse HEAD)"
git fetch --quiet origin main
TARGET="$(git rev-parse origin/main)"

if [[ "$BEFORE" == "$TARGET" ]]; then
    say "Already on ${TARGET:0:7}. Nothing to do."
    exit 0
fi

if ! git merge-base --is-ancestor "$BEFORE" "$TARGET"; then
    say "Server commit ${BEFORE:0:7} is not behind origin/main. Nothing changed."
    exit 1
fi

# ── 3. Back up the database ───────────────────────────────────────────────────
# SQLite's own backup is safe even while the bot is writing.
mkdir -p "$BACKUP_DIR"
STAMP="$(TZ=Asia/Kolkata date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/founder_ops-$STAMP-${BEFORE:0:7}.db"
venv/bin/python - "$BACKUP_FILE" <<'PY'
import os, sqlite3, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
src = Path(os.getenv("DATA_DIR", ".")) / "founder_ops.db"
if not src.exists():
    sys.exit(f"Database not found at {src}")
with sqlite3.connect(src) as a, sqlite3.connect(sys.argv[1]) as b:
    a.backup(b)
PY
ls -1t "$BACKUP_DIR"/founder_ops-*.db 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm -f
say "Database backed up to $BACKUP_FILE"

# ── 4. Update and restart ─────────────────────────────────────────────────────
restart_and_check() {
    venv/bin/pip install --quiet -r requirements.txt
    systemctl restart "$SERVICE"
    local port
    port="$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '"' || true)"
    port="${port:-10000}"
    # Discord can take a few seconds to connect.
    for _ in $(seq 1 30); do
        sleep 3
        if systemctl is-active --quiet "$SERVICE" \
            && curl -fsS "http://localhost:$port/healthz" 2>/dev/null | grep -q '"bot_online": true'; then
            return 0
        fi
    done
    return 1
}

git merge --ff-only --quiet "$TARGET"
say "Updated ${BEFORE:0:7} -> ${TARGET:0:7}. Restarting."

if restart_and_check; then
    say "Deployed ${TARGET:0:7}. Bot is online."
    exit 0
fi

# ── 5. Roll back ──────────────────────────────────────────────────────────────
say "Bot did not come back on ${TARGET:0:7}. Rolling back to ${BEFORE:0:7}."
journalctl -u "$SERVICE" -n 40 --no-pager || true
git reset --hard --quiet "$BEFORE"
if restart_and_check; then
    say "Rolled back to ${BEFORE:0:7}. Bot is online. The new code needs a fix."
else
    say "Rollback also failed. Bot may be down. Check: journalctl -u $SERVICE -n 100"
fi
exit 1
