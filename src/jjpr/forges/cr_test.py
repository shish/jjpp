from unittest.mock import Mock

import httpx

from . import cr


class TestTitle:
    def test_str(self) -> None:
        t = cr.Title(text="Hello", url=None)
        assert str(t) == "Hello"

    def test_rich_without_url(self) -> None:
        t = cr.Title(text="Hello", url=None)
        assert t.__rich__() == "Hello"

    def test_rich_with_url(self) -> None:
        t = cr.Title(text="[x] Hello", url=httpx.URL("https://example.com"))
        assert t.__rich__() == "[link=https://example.com]\\[x] Hello[/link]"


class TestBlocker:
    def test_rich_without_color_or_url(self) -> None:
        b = cr.Blocker(name="Blocker[x]", color=None, url=None)
        assert "Blocker\\[x]" == b.__rich__()

    def test_rich_with_color_and_url(self) -> None:
        url = httpx.URL("https://example.com")
        b = cr.Blocker(name="Blocker1", color="red", url=url)
        rich_output = b.__rich__()
        assert "[red]" in rich_output
        assert "[link=https://example.com]" in rich_output


class TestState:
    def test_str(self) -> None:
        s = cr.State(name="Open", color=None, url=None)
        assert "Open" in str(s)

    def test_rich_without_color_or_url(self) -> None:
        s = cr.State(name="Open", color=None, url=None)
        assert s.__rich__() == "Open"

    def test_rich_with_color_and_url(self) -> None:
        url = httpx.URL("https://example.com")
        s = cr.State(name="Open", color="green", url=url)
        rich_output = s.__rich__()
        assert "[green]" in rich_output
        assert "[link=https://example.com]" in rich_output


class TestCodeReview:
    def test_as_dict_with_extra(self) -> None:
        forge_mock = Mock()
        forge_mock.asdict.return_value = {"name": "github"}

        title = cr.Title(text="Fix bug", url=None)
        state = cr.State(name="Open", color=None, url=None)
        blockers = []

        code_review = cr.CodeReview(
            forge=forge_mock,
            cr_id="456",
            title=title,
            state=state,
            blockers=blockers,
            extra={"author": "alice", "branch": "feature/x"},
        )

        result = code_review.as_dict()
        assert result["extra"]["author"] == "alice"
        assert result["extra"]["branch"] == "feature/x"
