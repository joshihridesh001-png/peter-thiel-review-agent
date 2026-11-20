"""The database backup inside deploy.sh runs the way the VPS runs it: code piped into python."""

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "deploy.sh"


def _backup_code() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"<<'PY'\n(.*?)\nPY\n", text, re.DOTALL)
    assert match, "backup block not found in deploy.sh"
    return match.group(1)


def test_backup_copies_the_database_when_piped_into_python(tmp_path):
    db = tmp_path / "founder_ops.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE scores (who TEXT)")
        conn.execute("INSERT INTO scores VALUES ('harsh')")
    (tmp_path / ".env").write_text("TZ=Asia/Kolkata\n", encoding="utf-8")
    out = tmp_path / "backup.db"

    run = subprocess.run(
        [sys.executable, "-", str(out)],
        input=_backup_code(),
        text=True,
        cwd=tmp_path,
        capture_output=True,
    )

    assert run.returncode == 0, run.stderr
    with sqlite3.connect(out) as conn:
        assert conn.execute("SELECT who FROM scores").fetchone() == ("harsh",)


def test_backup_follows_data_dir_from_env(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "founder_ops.db") as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
    (tmp_path / ".env").write_text(f"DATA_DIR={data}\n", encoding="utf-8")
    out = tmp_path / "backup.db"

    run = subprocess.run(
        [sys.executable, "-", str(out)],
        input=_backup_code(),
        text=True,
        cwd=tmp_path,
        capture_output=True,
    )

    assert run.returncode == 0, run.stderr
    assert out.exists()
