"""Tests for jjpp.forge module."""

import logging
import os
from pathlib import Path

from jjpp import forges

from ..conftest import run_cmd

log = logging.getLogger(__name__)


class TestDetectForgeFromUrl:
    """Tests for utils.detect_forge_from_url() function."""

    def test_detect_github(self):
        """Test detecting GitHub forge."""
        result = forges.detect_forge_from_url("https://github.com/user/repo.git")
        assert result == "github"

    def test_detect_github_with_www(self):
        """Test detecting GitHub with www prefix."""
        result = forges.detect_forge_from_url("https://www.github.com/user/repo.git")
        assert result == "github"

    def test_detect_phabricator(self):
        """Test detecting Phabricator forge."""
        result = forges.detect_forge_from_url(
            "https://phabricator.example.com/repo/name"
        )
        assert result == "phabricator"

    def test_detect_gerrit(self):
        """Test detecting Gerrit forge."""
        result = forges.detect_forge_from_url("https://gerrit.example.com/repo")
        assert result == "gerrit"

    def test_detect_unknown_forge(self):
        """Test detecting unknown forge returns None."""
        result = forges.detect_forge_from_url("https://unknown.example.com/repo")
        assert result is None

    def test_detect_forge_empty_url(self):
        """Test detecting forge with empty URL returns None."""
        result = forges.detect_forge_from_url("")
        assert result is None

    def test_detect_forge_case_insensitive(self):
        """Test that forge detection is case-insensitive."""
        result = forges.detect_forge_from_url("https://GITHUB.COM/user/repo")
        assert result == "github"


class TestGetForge:
    """Tests for utils.get_forge() function."""

    def test_get_forge_explicit(self, repo_with_remote: tuple[Path, Path]):
        """Test getting forge with explicit specification."""
        local_repo, remote_repo = repo_with_remote
        os.chdir(local_repo)

        # Add GitHub URL as remote
        run_cmd("git", "remote", "add", "github", "https://github.com/user/repo.git")

        forge = forges.get_forge("github", "github")
        assert forge is not None
        assert forge.__class__.__name__ == "GitHub"

        forge = forges.get_forge("gerrit", "github")
        assert forge is not None
        assert forge.__class__.__name__ == "Gerrit"

        forge = forges.get_forge("phabricator", "github")
        assert forge is not None
        assert forge.__class__.__name__ == "Phabricator"

    def test_get_forge_auto_detect_github(self, repo_with_remote: tuple[Path, Path]):
        """Test auto-detecting GitHub forge."""
        local_repo, remote_repo = repo_with_remote
        os.chdir(local_repo)

        # Add GitHub URL as origin
        run_cmd("git", "remote", "remove", "origin")
        run_cmd("git", "remote", "add", "origin", "https://github.com/user/repo.git")

        forge = forges.get_forge(None, "origin")
        assert forge is not None
        assert forge.__class__.__name__ == "GitHub"

    def test_get_forge_nonexistent_remote(self, tmp_repo: Path):
        """Test that nonexistent remote returns None."""
        os.chdir(tmp_repo)
        forge = forges.get_forge(None, "nonexistent")
        assert forge is None

    def test_get_forge_no_auto_detect_no_forge_specified(self, tmp_repo: Path):
        """Test that unknown URL without explicit forge returns None."""
        os.chdir(tmp_repo)
        run_cmd("git", "remote", "add", "origin", "https://unknown.example.com/repo")

        forge = forges.get_forge(None, "origin")
        assert forge is None
