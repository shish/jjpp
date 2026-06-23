from pathlib import Path
from unittest import mock

import pytest

from .. import exc
from ..conftest import run_cmd
from . import git


class TestGetMergeTarget:
    def test_with_remote(self, tmp_repo: Path):
        result = run_cmd("git", "ls-remote", "--symref", "origin", "HEAD")
        assert "refs/heads/main" in result

    def test_parses_correctly(self, tmp_repo: Path):
        target = git.get_merge_target("origin")
        assert target == "main"

    def test_invalid_remote(self, tmp_repo: Path):
        with pytest.raises(exc.UserError):
            git.get_merge_target("nonexistent")

    def test_unparsable_output(self, tmp_repo: Path):
        with mock.patch("jjpr.utils.exec.run", return_value="invalid output"):
            with pytest.raises(exc.UserError):
                git.get_merge_target("origin")


class TestGetGitRemoteUrl:
    def test_with_configured_remote(self, tmp_repo: Path):
        url = git.get_remote_url("origin")
        assert url is not None

    def test_nonexistent_remote(self, tmp_repo: Path):
        with pytest.raises(exc.UserError):
            git.get_remote_url("nonexistent")

    def test_with_scp_style_remote(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "git@github.com:user/repo.git")
        url = git.get_remote_url("origin")
        assert url == "ssh://git@github.com/user/repo.git"

    def test_default_remote(self, tmp_repo: Path):
        url = git.get_remote_url()
        assert url is not None

    def test_default_no_remote(self, tmp_repo: Path):
        run_cmd("git", "remote", "remove", "origin")
        with pytest.raises(exc.UserError):
            git.get_remote_url()


class TestUniqueBranchName:
    def test_non_existent(self, tmp_repo: Path):
        name = git.unique_branch_name("new-branch")
        assert name == "new-branch"

    def test_existing_appends_number(self, repo_with_commits: Path):
        run_cmd("git", "checkout", "-b", "feature")
        name = git.unique_branch_name("feature")
        assert name == "feature-1"

    def test_multiple_existing(self, repo_with_commits: Path):
        run_cmd("git", "checkout", "-b", "feature")
        run_cmd("git", "checkout", "-b", "feature-1")
        name = git.unique_branch_name("feature")
        assert name == "feature-2"

    def test_incrementally_finds_gap(self, repo_with_commits: Path):
        run_cmd("git", "checkout", "-b", "test")
        run_cmd("git", "checkout", "-b", "test-2")
        name = git.unique_branch_name("test")
        assert name == "test-1"
