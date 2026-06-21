import logging
from typing import Optional

import httpx

from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class DummyForge(Forge):
    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        log.info(f"DummyForge: push called with ref={ref}")

    def checkout(self, identifier: str) -> None:
        log.info(f"DummyForge: checkout called with identifier={identifier}")

    def list(self, all_projects: bool = False) -> list[CRListItem]:
        log.info("DummyForge: list called")
        return []


class TestForgeProperties:
    def test_forge_url_https(self):
        f = DummyForge("origin", httpx.URL("https://gerrit.mycompany.com/a/project"))
        assert str(f.forge_url) == "https://gerrit.mycompany.com"
        assert f.project_id == "project"

    def test_forge_url_github(self):
        f = DummyForge("origin", httpx.URL("https://github.com/owner/repo.git"))
        assert str(f.forge_url) == "https://github.com"
        assert f.project_id == "owner/repo"

    def test_project_url_ssh(self):
        f = DummyForge("origin", httpx.URL("ssh://git@github.com/owner/repo.git"))
        assert str(f.forge_url) == "https://github.com"
        assert f.project_id == "owner/repo"
