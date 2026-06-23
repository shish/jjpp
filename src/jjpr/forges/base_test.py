from unittest import mock

import httpx

from ..utils import git
from . import base, cr


class DummyForge(base.Forge):
    def __init__(self) -> None:
        with mock.patch.object(
            git,
            "get_remote_url",
            return_value=httpx.URL("https://example.com/dummy.git"),
        ):
            super().__init__("https://example.com/dummy.git")

    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None: ...

    def checkout_cr(self, identifier: str) -> None: ...

    def list_crs(self, all_projects: bool = False) -> list[cr.CodeReview]:
        return []

    def log(self, args: list[str]) -> str:
        return ""


class TestForge:
    def test_str(self) -> None:
        f = DummyForge()
        str(f)
        f.__rich__()
        f.asdict()

    def test_log(self) -> None:
        f = DummyForge()
        txt = f._log([], '"D123"', {"D123": cr.State("OPEN")})
        assert "OPEN" in txt
        assert "D123" not in txt
