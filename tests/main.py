from typing import List

import pytest

from jjpp.forges.base import CRListItem
from jjpp.main import _display_list


@pytest.fixture
def dummy_cr_list_items() -> List[CRListItem]:
    return [
        CRListItem(
            forge_name="DummyForge",
            forge_url="https://example.com",
            project_id="dummy-project",
            identifier="123",
            title="Fix bug",
            url="https://example.com/repo/123",
            extra={"Author": "Alice"},
        ),
        CRListItem(
            forge_name="DummyForge",
            forge_url="https://example.com",
            project_id="dummy-project",
            identifier="124",
            title="Add feature",
            url="https://example.com/repo/124",
            extra={"Author": "Bob"},
        ),
    ]


class TestBase:
    def test_display_list(self, dummy_cr_list_items: list[CRListItem]):
        _display_list(dummy_cr_list_items)

    def test_display_list_empty(self):
        _display_list([])
