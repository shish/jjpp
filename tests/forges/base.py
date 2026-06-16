"""Tests for jjpp.forge module."""

import logging
import os
from pathlib import Path

from jjpp.forges.base import CRListItem, Forge

log = logging.getLogger(__name__)


class DummyForge(Forge):
    def push(self, ref: str | None) -> None:
        log.info(f"DummyForge: push called with ref={ref}")

    def checkout(self, identifier: str) -> None:
        log.info(f"DummyForge: checkout called with identifier={identifier}")

    def list(self) -> None:
        self.display_list(
            [
                CRListItem(
                    "123",
                    "Fix bug",
                    "https://example.com/repo/123",
                    {"Author": "Alice"},
                ),
                CRListItem(
                    "124",
                    "Add feature",
                    "https://example.com/repo/124",
                    {"Author": "Bob"},
                ),
            ]
        )


class TestBase:
    def test_display_list(self, tmp_jj_repo: Path):
        os.chdir(tmp_jj_repo)
        f = DummyForge("origin", "https://example.com/repo.git")
        f.list()

    def test_display_list_empty(self, tmp_jj_repo: Path):
        os.chdir(tmp_jj_repo)
        f = DummyForge("origin", "https://example.com/repo.git")
        f.display_list([])


class TestForgeProperties:
    def test_forge_url_https(self):
        f = DummyForge("origin", "https://gerrit.mycompany.com/a/project")
        assert f.forge_url == "https://gerrit.mycompany.com"
        assert f.project_id == "project"

    def test_forge_url_ssh(self):
        f = DummyForge("origin", "git@gerrit.mycompany.com:project")
        assert f.forge_url == "https://gerrit.mycompany.com"
        assert f.project_id == "project"

    def test_forge_url_github(self):
        f = DummyForge("origin", "https://github.com/owner/repo.git")
        assert f.forge_url == "https://github.com"
        assert f.project_id == "owner/repo"

    def test_project_id_https_github_no_git_suffix(self):
        f = DummyForge("origin", "https://github.com/owner/repo")
        assert f.project_id == "owner/repo"

    def test_project_id_ssh_github(self):
        f = DummyForge("origin", "git@github.com:owner/repo.git")
        assert f.project_id == "owner/repo"
