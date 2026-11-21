#!/usr/bin/env bash
# Nightly off-site backup of everything GitHub does not already hold.
#
#   founder_ops.db   every score, goal, and equity record (SQLite snapshot)
#   .env             bot tokens and keys
#   service file     how systemd runs the bot
#   deploy launcher  /root/bin/peter-deploy
#
# The bundle goes to an rclone "crypt" remote, so it is encrypted on the
# server before upload. Google Drive only ever stores scrambled files.
#
# Keeps 30 days of nightly backups, plus every 1st-of-month backup forever.
# On any failure it posts one alert card to Discord and exits non-zero.
#
# Setup and restore: docs/BACKUP.md

# -E: the failure trap below also fires inside functions.
set -Eeuo pipefail

# Everything runs inside main(). Bash reads a whole function before running
# it, so a deploy that rewrites this file mid-backup cannot break it.
main() {
    local repo="${BACKUP_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
    local remote="${BACKUP_REMOTE:-peter-backup:}"
    local python="${BACKUP_PYTHON:-$repo/venv/bin/python}"
    local keep_days="${BACKUP_KEEP_DAYS:-30}"
    local extras="${BACKUP_EXTRA_FILES:-/etc/systemd/system/peter-thiel.service /root/bin/peter-deploy}"

    cd "$repo"

    if command -v flock >/dev/null 2>&1; then
        exec 8>"/tmp/peter-thiel-backup.lock"
        flock -n 8 || { say "Another backup is running. Skipped."; return 0; }
    fi

    local stamp name
    # Not local: the cleanup trap runs after main() returns.
    work="$(mktemp -d /tmp/peter-backup.XXXXXX)"
    trap 'rm -rf "${work:-}"' EXIT
    stamp="$(TZ=Asia/Kolkata date +%Y%m%d-%H%M)"
    name="peter-thiel-$stamp.tar.gz"
    mkdir -p "$work/bundle"

    # 1. Snapshot the database. SQLite's own backup is safe while the bot writes.
    #    Then prove the snapshot is readable before trusting it.
    "$python" - "$work/bundle/founder_ops.db" <<'PY'
import os, sqlite3, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(".env")
src = Path(os.getenv("DATA_DIR", ".")) / "founder_ops.db"
if not src.exists():
    sys.exit(f"Database not found at {src}")
with sqlite3.connect(src) as a, sqlite3.connect(sys.argv[1]) as b:
    a.backup(b)
with sqlite3.connect(sys.argv[1]) as b:
    result = b.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    sys.exit(f"Snapshot failed integrity check: {result}")
PY
    say "Database snapshot is healthy."

    # 2. Secrets and server config. A missing extra is a warning, not a failure.
    cp .env "$work/bundle/.env"
    local f
    for f in $extras; do
        if [[ -f "$f" ]]; then
            cp "$f" "$work/bundle/$(basename "$f")"
        else
            say "Warning: $f not found, not included."
        fi
    done
    git rev-parse HEAD > "$work/bundle/COMMIT" 2>/dev/null || true

    tar -czf "$work/$name" -C "$work/bundle" .

    # 3. Upload, then confirm the remote copy has the same size.
    rclone copyto "$work/$name" "$remote$name"
    local local_size remote_size
    local_size="$(wc -c < "$work/$name" | tr -d ' ')"
    remote_size="$(rclone lsl "$remote$name" | awk '{print $1}')"
    if [[ "$local_size" != "$remote_size" ]]; then
        fail "Uploaded size $remote_size does not match local size $local_size for $name"
    fi
    say "Uploaded $name ($local_size bytes)."

    # 4. Retention. Nightly copies older than $keep_days days go. 1st-of-month copies stay.
    # Filter rules apply in order: protect monthlies, then match nightlies, then nothing else.
    rclone delete "$remote" --min-age "${keep_days}d" \
        --filter "- peter-thiel-??????01-*.tar.gz" \
        --filter "+ peter-thiel-*.tar.gz" \
        --filter "- *"
    say "Backup done."
}

say() {
    echo "[backup] $*"
    command -v logger >/dev/null 2>&1 && logger -t peter-backup -- "$*" || true
}

fail() {
    say "FAILED: $*"
    alert "$*"
    exit 1
}

# One Discord card. Its title is in SYSTEM_EMBED_TITLES, so it is never scored.
alert() {
    [[ "${BACKUP_NO_ALERT:-}" == "1" ]] && return 0
    local python="${BACKUP_PYTHON:-${BACKUP_REPO_DIR:-.}/venv/bin/python}"
    "$python" - "$1" <<'PY' || true
import json, os, sys, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")
token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
channel = os.getenv("BACKUP_ALERT_CHANNEL_ID", "1508293104371896330")  # dev-updates
if not token:
    sys.exit(0)
body = {"embeds": [{
    "title": "⚠️ Backup Alert",
    "description": f"Last night's server backup did not finish.\n\n`{sys.argv[1][:900]}`\n\nCheck: journalctl -u peter-backup -n 50",
    "color": 0xE74C3C,
}]}
req = urllib.request.Request(
    f"https://discord.com/api/v10/channels/{channel}/messages",
    data=json.dumps(body).encode(),
    headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
)
urllib.request.urlopen(req, timeout=15)
PY
}

# Any command that fails without calling fail() still alerts.
trap 'fail "Step failed at line $LINENO (exit $?)"' ERR

main "$@"
exit 0
