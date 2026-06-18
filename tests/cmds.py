from typing import List

import httpx
import pytest

from jjpr.cmds import display_list
from jjpr.forges.base import CRListItem


@pytest.fixture
def dummy_cr_list_items() -> List[CRListItem]:
    return [
        CRListItem(
            forge_name="DummyForge",
            forge_url=httpx.URL("https://example.com"),
            project_id="dummy-project",
            identifier="123",
            title="Fix bug",
            url=httpx.URL("https://example.com/repo/123"),
            state="Open",
            blockers="",
        ),
        CRListItem(
            forge_name="DummyForge",
            forge_url=httpx.URL("https://example.com"),
            project_id="dummy-project",
            identifier="124",
            title="Add feature",
            url=httpx.URL("https://example.com/repo/124"),
            state="In Review",
            blockers="Needs approval",
        ),
    ]


class TestBase:
    def test_display_list_multi(self, dummy_cr_list_items: list[CRListItem]):
        display_list(dummy_cr_list_items, multi=True)

    def test_display_list_empty(self):
        display_list([], multi=False)
