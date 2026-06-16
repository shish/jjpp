"""Tests for jjpp.utils module."""

import os
import subprocess
from pathlib import Path

import pytest

from jjpp import utils

from .conftest import run_cmd


class TestRun:
    """Tests for utils.run() function."""

    def test_run_basic_command(self):
        """Test running a basic shell command."""
        output = utils.run(["echo", "hello"])
        assert output == "hello"

    def test_run_with_output(self):
        """Test command that produces output."""
        output = utils.run(["echo", "test output"])
        assert "test output" in output

    def test_run_command_failure_raises_error(self):
        """Test that failed commands raise CalledProcessError."""
        with pytest.raises(subprocess.CalledProcessError):
            utils.run(["false"])

    def test_run_strips_whitespace(self):
        """Test that output is stripped of whitespace."""
        output = utils.run(["echo", "  spaced  "])
        assert output == "spaced"


class TestGetMergeTarget:
    """Tests for utils.get_merge_target() function."""

    def test_get_merge_target_with_remote(
        self, git_repo_with_remote: tuple[Path, Path]
    ):
        """Test getting merge target from remote."""
        local_repo, remote_repo = git_repo_with_remote
        os.chdir(local_repo)

        # Git HEAD symref should point to main
        result = run_cmd("git", "ls-remote", "--symref", "origin", "HEAD")
        assert "refs/heads/main" in result

    def test_get_merge_target_parses_correctly(
        self, git_repo_with_remote: tuple[Path, Path]
    ):
        """Test that get_merge_target parses symref correctly."""
        local_repo, remote_repo = git_repo_with_remote
        os.chdir(local_repo)

        target = utils.get_merge_target("origin")
        assert target == "main"

    def test_get_merge_target_invalid_remote(self, tmp_jj_repo: Path):
        """Test that invalid remote raises exception."""
        os.chdir(tmp_jj_repo)
        with pytest.raises(Exception):
            utils.get_merge_target("nonexistent")


class TestGetGitRemoteUrl:
    """Tests for utils.get_git_remote_url() function."""

    def test_get_git_remote_url_with_configured_remote(
        self, git_repo_with_remote: tuple[Path, Path]
    ):
        """Test getting URL of configured remote."""
        local_repo, remote_repo = git_repo_with_remote
        os.chdir(local_repo)

        url = utils.get_git_remote_url("origin")
        assert url is not None
        assert str(remote_repo) in url

    def test_get_git_remote_url_nonexistent_remote(self, tmp_jj_repo: Path):
        """Test getting URL of non-existent remote returns None."""
        os.chdir(tmp_jj_repo)
        url = utils.get_git_remote_url("nonexistent")
        assert url is None

    def test_get_git_remote_url_default_remote(
        self, git_repo_with_remote: tuple[Path, Path]
    ):
        """Test getting default 'origin' remote URL."""
        local_repo, remote_repo = git_repo_with_remote
        os.chdir(local_repo)

        url = utils.get_git_remote_url()
        assert url is not None


class TestUniqueBranchName:
    """Tests for utils.unique_branch_name() function."""

    def test_unique_branch_name_non_existent(self, tmp_jj_repo: Path):
        """Test generating unique name for non-existent branch."""
        os.chdir(tmp_jj_repo)
        name = utils.unique_branch_name("new-branch")
        assert name == "new-branch"

    def test_unique_branch_name_existing_appends_number(
        self, git_repo_with_commits: Path
    ):
        """Test that existing branch names get numbers appended."""
        os.chdir(git_repo_with_commits)

        # Create a branch
        run_cmd("git", "checkout", "-b", "feature")

        # Request unique name for same branch
        name = utils.unique_branch_name("feature")
        assert name == "feature-1"

    def test_unique_branch_name_multiple_existing(self, git_repo_with_commits: Path):
        """Test with multiple existing branches with same base name."""
        os.chdir(git_repo_with_commits)

        # Create multiple branches
        run_cmd("git", "checkout", "-b", "feature")
        run_cmd("git", "checkout", "-b", "feature-1")

        # Request unique name
        name = utils.unique_branch_name("feature")
        # Should skip feature-1 and go to feature-2
        assert name == "feature-2"

    def test_unique_branch_name_incrementally_finds_gap(
        self, git_repo_with_commits: Path
    ):
        """Test that unique_branch_name finds first available number."""
        os.chdir(git_repo_with_commits)

        # Create branches
        run_cmd("git", "checkout", "-b", "test")
        run_cmd("git", "checkout", "-b", "test-1")
        # Don't create test-2, so test-2 should be available

        name = utils.unique_branch_name("test")
        assert name == "test-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
