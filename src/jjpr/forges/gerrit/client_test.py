import logging
from pathlib import Path
from unittest import mock

import httpx
import pytest

from ... import exc
from ...utils import netrc
from .client import GerritClient

log = logging.getLogger(__name__)


class TestGerritClient:
    def test_init(self, tmp_home: Path) -> None:
        with pytest.raises(Exception):
            GerritClient(httpx.URL("https://example.com/a/project"))

        netrc.write("example.com", "user", "pass")
        GerritClient(httpx.URL("https://example.com/a/project"))

    def test_request_success(self, tmp_home: Path) -> None:
        netrc.write("example.com", "user", "pass")
        client = GerritClient(httpx.URL("https://example.com"))

        # Mock the parent request to return a response with Gerrit magic prefix
        gerrit_response_text = ')]}\'\n{"key": "value"}'
        mock_response = httpx.Response(
            status_code=200,
            text=gerrit_response_text,
            request=httpx.Request("GET", "https://example.com/a/test"),
        )

        with mock.patch.object(httpx.Client, "request", return_value=mock_response):
            response = client.request("GET", "https://example.com/a/test")

        # Verify the magic prefix was stripped
        assert response.text == '{"key": "value"}'
        assert response.status_code == 200
        client.close()

    def test_request_error_401(self, tmp_home: Path) -> None:
        netrc.write("example.com", "user", "pass")
        client = GerritClient(httpx.URL("https://example.com"))

        # Mock the parent request to return 401
        mock_response = httpx.Response(
            status_code=401,
            text="Unauthorized",
            request=httpx.Request("GET", "https://example.com/a/test"),
        )

        with mock.patch.object(httpx.Client, "request", return_value=mock_response):
            with pytest.raises(exc.UserError) as exc_info:
                client.request("GET", "https://example.com/a/test")

        assert "Authentication failed" in str(exc_info.value)
        assert "~/.netrc" in str(exc_info.value)
        client.close()

    def test_request_error_500(self, tmp_home: Path) -> None:
        netrc.write("example.com", "user", "pass")
        client = GerritClient(httpx.URL("https://example.com"))

        # Mock the parent request to return 500
        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://example.com/a/test"),
        )

        with mock.patch.object(httpx.Client, "request", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.request("GET", "https://example.com/a/test")

        # Verify that the error note contains the response text
        assert "Internal Server Error" in str(exc_info.value.__notes__)
        client.close()
