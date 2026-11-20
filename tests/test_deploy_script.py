"""The deploy never restarts the bot when a restart would repeat a nightly post."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "deploy.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="deploy.sh runs on the Linux VPS",
)


def _check(day_and_time: str) -> int:
    env = dict(os.environ, PETER_DEPLOY_NOW=day_and_time, PETER_DEPLOY_CHECK_ONLY="1")
    env.pop("PETER_DEPLOY_COPY", None)
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True).returncode


def test_script_has_no_syntax_errors():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


@pytest.mark.parametrize("now", ["20 1910", "20 1915", "20 2000", "20 2130", "20 2205", "01 0955", "01 1000", "01 1105"])
def test_quiet_hours_stop_the_deploy(now):
    assert _check(now) == 75


@pytest.mark.parametrize("now", ["20 1600", "20 1909", "20 2206", "20 0900", "02 1000", "01 0954", "01 1106", "08 0830"])
def test_other_times_go_ahead(now):
    assert _check(now) == 0


LAUNCHER = SCRIPT.parent / "deploy-launcher.sh"


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_launcher_has_no_syntax_errors():
    assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0


def test_launcher_runs_the_deploy_script_from_main_not_the_old_copy(tmp_path):
    origin = tmp_path / "origin.git"
    server = tmp_path / "server"
    _git("init", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    _git("clone", str(origin), str(server), cwd=tmp_path)
    _git("config", "user.email", "t@t", cwd=server)
    _git("config", "user.name", "t", cwd=server)
    (server / "scripts").mkdir()
    deploy = server / "scripts" / "deploy.sh"

    deploy.write_text("echo OLD $PETER_REPO_DIR\n")
    _git("add", ".", cwd=server)
    _git("commit", "-m", "old", cwd=server)
    _git("push", "origin", "HEAD:main", cwd=server)

    # main moves on. The server's copy on disk stays OLD.
    other = tmp_path / "other"
    _git("clone", str(origin), str(other), cwd=tmp_path)
    _git("config", "user.email", "t@t", cwd=other)
    _git("config", "user.name", "t", cwd=other)
    (other / "scripts" / "deploy.sh").write_text("echo NEW $PETER_REPO_DIR\n")
    _git("commit", "-am", "new", cwd=other)
    _git("push", "origin", "HEAD:main", cwd=other)

    env = dict(os.environ, PETER_REPO_DIR=str(server))
    env.pop("PETER_DEPLOY_COPY", None)
    run = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)

    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == f"NEW {server}"
    assert deploy.read_text() == "echo OLD $PETER_REPO_DIR\n"
