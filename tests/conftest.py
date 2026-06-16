"""Pytest configuration and shared fixtures for testing jjpp."""

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, Union

import pytest

log = logging.getLogger(__name__)


def run_cmd(*args: str, cwd: Union[str, None] = None, text: bool = True) -> str:
    log.info(f"Running test-setup command: {shlex.join(args)} in {cwd or os.getcwd()}")
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=text,
            cwd=cwd,
        )
        return result.stdout.strip() if text else result.stdout
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: {shlex.join(args)}")
        log.error(f"Return code: {e.returncode}")
        log.error(f"stdout: {e.stdout}")
        log.error(f"stderr: {e.stderr}")
        raise


@pytest.fixture
def tmp_jj_repo() -> Generator[Path, None, None]:
    """Create a temporary jj (Jujutsu) repository with git backend.

    Yields:
        Path to the temporary jj repository.
    """
    tmp_dir = tempfile.mkdtemp(prefix="jjpp_jj_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        # Initialize git repo first
        run_cmd("git", "init")
        run_cmd("git", "config", "user.email", "test@example.com")
        run_cmd("git", "config", "user.name", "Test User")
        run_cmd("git", "branch", "-m", "main")
        # Initialize jj repo using git backend
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def jj_repo_with_commits(tmp_jj_repo: Path) -> Generator[Path, None, None]:
    """Create a jj repository with initial commits and branches.

    Creates:
    - Initial commit on main/trunk
    - 3 commits in a stack

    Yields:
        Path to the jj repository with commits.
    """
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_jj_repo)

        # Create initial commit - jj auto-tracks changes
        Path("file1.txt").write_text("initial content")
        run_cmd("jj", "commit", "-m", "Initial commit")
        log.debug(
            "Commit 0: "
            + run_cmd("jj", "log", "-r", "@-", "--no-graph", "-T", "change_id.short()")
        )

        # Create commit 1
        Path("file2.txt").write_text("commit 1 content")
        run_cmd("jj", "commit", "-m", "Commit 1")
        log.debug(
            "Commit 1: "
            + run_cmd("jj", "log", "-r", "@-", "--no-graph", "-T", "change_id.short()")
        )

        # Create commit 2
        Path("file3.txt").write_text("commit 2 content")
        run_cmd("jj", "commit", "-m", "Commit 2")
        log.debug(
            "Commit 2: "
            + run_cmd("jj", "log", "-r", "@-", "--no-graph", "-T", "change_id.short()")
        )

        # Create commit 3
        Path("file4.txt").write_text("commit 3 content")
        run_cmd("jj", "commit", "-m", "Commit 3")
        log.debug(
            "Commit 3: "
            + run_cmd("jj", "log", "-r", "@-", "--no-graph", "-T", "change_id.short()")
        )

        log.debug(
            "Commit N: "
            + run_cmd("jj", "log", "-r", "@", "--no-graph", "-T", "change_id.short()")
        )

        yield tmp_jj_repo
    finally:
        os.chdir(original_dir)


@pytest.fixture
def jj_repo_with_branches(tmp_jj_repo: Path) -> Generator[Path, None, None]:
    """Create a jj repository with commits and bookmarks (branches).

    Creates:
    - Initial commit
    - feature-1 bookmark
    - feature-2 bookmark

    Yields:
        Path to the jj repository with bookmarks.
    """
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_jj_repo)

        # Create initial commit
        Path("base.txt").write_text("base content")
        run_cmd("jj", "commit", "-m", "Base commit")

        # Get current change id
        base_change_id = run_cmd(
            "jj", "log", "-r", "@", "--no-graph", "-T", "change_id.short()"
        )

        # Create feature-1 with bookmark
        Path("feature1.txt").write_text("feature 1 content")
        run_cmd("jj", "commit", "-m", "Feature 1")
        run_cmd("jj", "bookmark", "create", "feature-1")

        # Move back to base and create feature-2
        run_cmd("jj", "edit", base_change_id)
        Path("feature2.txt").write_text("feature 2 content")
        run_cmd("jj", "commit", "-m", "Feature 2")
        run_cmd("jj", "bookmark", "create", "feature-2")

        yield tmp_jj_repo
    finally:
        os.chdir(original_dir)


@pytest.fixture
def jj_repo_with_empty_commit(tmp_jj_repo: Path) -> Generator[Path, None, None]:
    """Create a jj repository with an empty commit.

    Creates:
    - Initial commit
    - One empty commit

    Yields:
        Path to the jj repository with empty commit.
    """
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_jj_repo)

        # Create initial commit
        Path("file.txt").write_text("initial")
        run_cmd("jj", "commit", "-m", "Initial")

        # Create empty commit
        run_cmd("jj", "commit", "-m", "Empty commit")

        yield tmp_jj_repo
    finally:
        os.chdir(original_dir)


@pytest.fixture
def git_repo_with_commits(tmp_jj_repo: Path) -> Generator[Path, None, None]:
    """Create a git repository with some commits.

    Creates:
    - Initial commit on main
    - 2 additional commits

    Yields:
        Path to the git repository with commits.
    """
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_jj_repo)

        # Create initial commit
        Path("file1.txt").write_text("initial content")
        run_cmd("git", "add", "file1.txt")
        run_cmd("git", "commit", "-m", "Initial commit")

        # Create second commit
        Path("file2.txt").write_text("second content")
        run_cmd("git", "add", "file2.txt")
        run_cmd("git", "commit", "-m", "Second commit")

        # Set main as default branch
        run_cmd("git", "symbolic-ref", "HEAD", "refs/heads/main")

        yield tmp_jj_repo
    finally:
        os.chdir(original_dir)


@pytest.fixture
def git_repo_with_remote(
    tmp_jj_repo: Path,
) -> Generator[tuple[Path, Path], None, None]:
    """Create a git repository with a configured remote.

    Creates:
    - Local git repository
    - Remote git repository
    - Remote configured as 'origin'

    Yields:
        Tuple of (local_repo_path, remote_repo_path).
    """
    original_dir = os.getcwd()

    remote_dir = None
    try:
        # Create remote repository
        remote_dir = tempfile.mkdtemp(prefix="jjpp_remote_")
        os.chdir(remote_dir)
        run_cmd("git", "init", "--bare")

        # Configure local repo with remote
        os.chdir(tmp_jj_repo)
        run_cmd("git", "remote", "add", "origin", remote_dir)

        # Create and push initial commit
        Path("file.txt").write_text("content")
        run_cmd("git", "add", "file.txt")
        run_cmd("git", "commit", "-m", "Initial")
        run_cmd("git", "push", "-u", "origin", "main")

        yield (tmp_jj_repo, Path(remote_dir))
    finally:
        os.chdir(original_dir)
        if remote_dir:
            shutil.rmtree(remote_dir, ignore_errors=True)
