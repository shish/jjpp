import logging
from pathlib import Path

import httpx
import pytest

from .client import GerritClient, _get_auth

log = logging.getLogger(__name__)


class TestGerritClient:
    def test_init(self, tmp_home: Path) -> None:
        with pytest.raises(Exception):
            GerritClient(httpx.URL("https://example.com/a/project"))
        Path(".netrc").write_text("machine example.com\nlogin user\npassword pass\n")
        Path(".netrc").chmod(0o600)
        GerritClient(httpx.URL("https://example.com/a/project"))


class TestGetAuth:
    def test_auth(self, tmp_home: Path) -> None:
        assert _get_auth("example.com") is None
        Path(".netrc").write_text("machine example.com login user password pass\n")
        Path(".netrc").chmod(0o600)
        assert _get_auth("example.com") == ("user", "pass")
        Path(".netrc").write_text("machine example.com login user password pass\n")
        assert _get_auth("tastycake.com") is None
        Path(".netrc").write_text("machine example.com login user\n")
        assert _get_auth("example.com") is None
