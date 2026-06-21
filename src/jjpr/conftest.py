import contextlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from filelock import FileLock
from typer.testing import CliRunner

from . import main

log = logging.getLogger(__name__)


def run_cmd(*args: str, text: bool = True) -> str:
    log.info(f"Setup command: {shlex.join(args)} in {os.getcwd()}")

    # Handle jj-pr commands by calling main.py directly
    if len(args) >= 2 and args[0] == "jj" and args[1] == "pr":
        return _run_jjpr_cmd(args[2:])

    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=text,
        )
        return result.stdout.strip() if text else result.stdout
    except subprocess.CalledProcessError as e:
        raise Exception(
            f"""
Command failed: {shlex.join(args)}
Return code: {e.returncode}
stdout: {e.stdout}
stderr: {e.stderr}
        """.strip()
        ) from None


def _run_jjpr_cmd(args: tuple[str, ...]) -> str:
    """Run jj-pr command directly via main.py instead of subprocess."""

    runner = CliRunner()
    result = runner.invoke(main.app, args)
    if result.exit_code != 0:
        raise subprocess.CalledProcessError(
            returncode=result.exit_code,
            cmd=["jj", "pr"] + list(args),
            output=result.output,
        )
    return result.output.strip()


@contextlib.contextmanager
def tmp_cwd() -> Generator[Path, None, None]:
    """Create a temporary working directory for tests."""
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_cwd_")
    original_dir = os.getcwd()
    os.chdir(tmp_dir)
    try:
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _create_dotfiles() -> None:
    # configure .gitrc
    run_cmd("git", "config", "set", "--global", "user.email", "test@example.com")
    run_cmd("git", "config", "set", "--global", "user.name", "Test User")

    # configure jj
    run_cmd("jj", "config", "set", "--user", "user.email", "test@example.com")
    run_cmd("jj", "config", "set", "--user", "user.name", "Test User")
    run_cmd(
        "jj",
        "config",
        "set",
        "--user",
        "aliases.pr",
        json.dumps(["util", "exec", "--", shutil.which("jj-pr")]),
    )


@pytest.fixture(scope="class")
def tmp_home() -> Generator[Path, None, None]:
    """Create a temporary home directory for tests, with git & jj configured."""
    original_home = os.environ.get("HOME", "")
    with tmp_cwd() as tmp_dir:
        try:
            os.environ["HOME"] = str(tmp_dir)
            os.environ["GIT_TERMINAL_PROMPT"] = "0"  # Disable git credential prompts
            home_lock = Path(tmp_dir) / ".jjpr-lock"
            with FileLock(home_lock):
                _create_dotfiles()

            yield Path(tmp_dir)
        finally:
            os.environ["HOME"] = original_home


@pytest.fixture
def tmp_repo(tmp_home: Path) -> Generator[Path, None, None]:
    with tmp_cwd() as remote_dir:
        run_cmd("git", "init", "--bare", "-b", "main")
        with tmp_cwd() as tmp_dir:
            run_cmd("git", "clone", str(remote_dir), ".")
            # a commit needs to exist before remote:HEAD exists
            run_cmd("git", "commit", "--allow-empty", "-m", "Initial commit")
            run_cmd("git", "push", "origin", "HEAD:main")
            run_cmd("jj", "git", "init", ".")
            run_cmd("jj", "bookmark", "track", "main", "--remote=origin")
            yield Path(tmp_dir)


@pytest.fixture
def repo_with_commits(tmp_repo: Path) -> Generator[Path, None, None]:
    # Create initial commit - jj auto-tracks changes
    Path("file1.txt").write_text("initial content")
    run_cmd("jj", "commit", "-m", "Initial commit")

    # Create commit 1
    Path("file2.txt").write_text("commit 1 content")
    run_cmd("jj", "commit", "-m", "Commit 1")

    # Create commit 2
    Path("file3.txt").write_text("commit 2 content")
    run_cmd("jj", "commit", "-m", "Commit 2")
    run_cmd("jj", "bookmark", "create", "feat/commit-2")

    # Create commit 3
    Path("file4.txt").write_text("commit 3 content")
    run_cmd("jj", "commit", "-m", "Commit 3")
    run_cmd("jj", "bookmark", "create", "feat/commit-3")

    yield tmp_repo
