"""Tests for jjpp.forge module."""

import logging

from jjpp.forges.base import CRListItem, Forge

log = logging.getLogger(__name__)


class DummyForge(Forge):
    def push(self, ref: str | None) -> None:
        log.info(f"DummyForge: push called with ref={ref}")

    def checkout(self, identifier: str) -> None:
        log.info(f"DummyForge: checkout called with identifier={identifier}")

    def list(self) -> list[CRListItem]:
        log.info("DummyForge: list called")
        return []


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
