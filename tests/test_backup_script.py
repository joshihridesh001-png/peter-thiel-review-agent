"""The nightly backup runs end to end against a fake rclone, and fails loudly."""

import fnmatch
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from config import SYSTEM_EMBED_TITLES

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "backup.sh"

on_linux = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="backup.sh runs on the Linux VPS",
)

# Stands in for rclone. "fake:" maps to $FAKE_REMOTE on disk.
FAKE_RCLONE = r"""#!/usr/bin/env bash
set -e
echo "$*" >> "$FAKE_LOG"
cmd="$1"; shift
to_path() { echo "$FAKE_REMOTE/${1#fake:}"; }
case "$cmd" in
  copyto) cp "$1" "$(to_path "$2")" ;;
  lsl)
    size=$(wc -c < "$(to_path "$1")" | tr -d ' ')
    [ "${FAKE_BAD_SIZE:-}" = "1" ] && size=1
    echo "$size 2026-11-21 23:30:00.000 ${1#fake:}" ;;
  delete) : ;;
  *) echo "unexpected rclone $cmd" >&2; exit 2 ;;
esac
"""


def _setup(tmp_path, db_ok=True):
    repo = tmp_path / "repo"
    remote = tmp_path / "remote"
    fakebin = tmp_path / "bin"
    for d in (repo, remote, fakebin):
        d.mkdir()
    (repo / ".env").write_text("DISCORD_BOT_TOKEN=test\n", encoding="utf-8")
    db = repo / "founder_ops.db"
    if db_ok:
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE daily_scores (founder_key TEXT, final_score REAL)")
            conn.execute("INSERT INTO daily_scores VALUES ('harsh', 4.5)")
    else:
        db.write_bytes(b"this is not a database" * 100)
    rclone = fakebin / "rclone"
    rclone.write_text(FAKE_RCLONE, encoding="utf-8")
    rclone.chmod(0o755)
    log = tmp_path / "rclone.log"
    env = dict(
        os.environ,
        PATH=f"{fakebin}{os.pathsep}{os.environ['PATH']}",
        BACKUP_REPO_DIR=str(repo),
        BACKUP_REMOTE="fake:",
        BACKUP_PYTHON=sys.executable,
        BACKUP_EXTRA_FILES="",
        BACKUP_NO_ALERT="1",
        FAKE_REMOTE=str(remote),
        FAKE_LOG=str(log),
    )
    return repo, remote, log, env


def _run(env):
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


@on_linux
def test_script_has_no_syntax_errors():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


@on_linux
def test_a_backup_uploads_the_database_and_env(tmp_path):
    _repo, remote, log, env = _setup(tmp_path)
    run = _run(env)
    assert run.returncode == 0, run.stdout + run.stderr

    archives = list(remote.glob("peter-thiel-*.tar.gz"))
    assert len(archives) == 1
    out = tmp_path / "restored"
    with tarfile.open(archives[0]) as tar:
        tar.extractall(out)
    with sqlite3.connect(out / "founder_ops.db") as conn:
        assert conn.execute("SELECT * FROM daily_scores").fetchall() == [("harsh", 4.5)]
    assert (out / ".env").read_text(encoding="utf-8") == "DISCORD_BOT_TOKEN=test\n"

    calls = log.read_text(encoding="utf-8")
    assert "--min-age 30d" in calls
    assert "- peter-thiel-??????01-*.tar.gz" in calls


@on_linux
def test_a_corrupt_database_is_not_uploaded(tmp_path):
    _repo, remote, _log, env = _setup(tmp_path, db_ok=False)
    run = _run(env)
    assert run.returncode != 0
    assert list(remote.iterdir()) == []


@on_linux
def test_a_short_upload_fails_the_backup(tmp_path):
    _repo, _remote, log, env = _setup(tmp_path)
    env["FAKE_BAD_SIZE"] = "1"
    run = _run(env)
    assert run.returncode != 0
    assert "does not match" in run.stdout
    # Nothing old is deleted after a bad upload.
    assert "delete" not in log.read_text(encoding="utf-8")


def test_monthly_backups_are_protected_and_nightlies_are_not():
    monthly = "peter-thiel-??????01-*.tar.gz"
    assert fnmatch.fnmatch("peter-thiel-20261101-2330.tar.gz", monthly)
    assert fnmatch.fnmatch("peter-thiel-20270101-2334.tar.gz", monthly)
    assert not fnmatch.fnmatch("peter-thiel-20261121-2330.tar.gz", monthly)
    assert not fnmatch.fnmatch("peter-thiel-20261110-2330.tar.gz", monthly)


def test_backup_alert_cards_are_never_scored():
    from cogs.tracker import TrackerCog

    assert "Backup Alert" in SYSTEM_EMBED_TITLES

    class Embed:
        title = "⚠️ Backup Alert"

    class Message:
        embeds = [Embed()]

    assert TrackerCog(bot=None)._is_system_message(Message()) is True


def _alert_code() -> str:
    import re

    text = SCRIPT.read_text(encoding="utf-8")
    blocks = re.findall(r"<<'PY'[^\n]*\n(.*?)\nPY\n", text, re.DOTALL)
    assert len(blocks) == 2, "expected the snapshot block and the alert block"
    return blocks[1]


def test_alert_code_is_valid_python():
    compile(_alert_code(), "backup-alert", "exec")


def test_alert_without_a_token_exits_quietly(tmp_path):
    (tmp_path / ".env").write_text("TZ=Asia/Kolkata\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "DISCORD_BOT_TOKEN"}
    run = subprocess.run(
        [sys.executable, "-", "disk full"],
        input=_alert_code(),
        text=True,
        # The alert holds an emoji. Windows would otherwise encode stdin as cp1252 and fail.
        encoding="utf-8",
        timeout=30,
        cwd=tmp_path,
        env=env,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr


def test_alert_title_matches_the_skip_list():
    assert '"⚠️ Backup Alert"' in SCRIPT.read_text(encoding="utf-8")
