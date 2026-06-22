import json
import logging
import typing as t
from pathlib import Path

import httpx

from ... import exc

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class PhabricatorClient:
    """Custom client for Phabricator.

    - Loads api.token from ~/.arcrc for the given base_url.
    - Adds api.token to POST request data.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL):
        self.client = httpx.Client(base_url=base_url.copy_with(path="/api/"))

        token = None
        arc_conf = Path.home() / ".arcrc"
        if arc_conf.exists():
            with open(arc_conf) as f:
                data = json.load(f)
            for url, config in data.get("hosts", {}).items():
                if httpx.URL(url).host == base_url.host:
                    token = config.get("token")
                    break
        if not token:
            raise exc.UserError(f"API token for {base_url.host} not found in ~/.arcrc")
        self.token = token

    def call(self, method: str, **kwargs: t.Any) -> dict[str, t.Any]:
        response = self.client.post(
            method,
            data={
                "params": json.dumps(
                    {
                        "__conduit__": {"api.token": self.token},
                        **kwargs,
                    }
                ),
                "output": "json",
                "__conduit__": True,
            },
        )
        log.debug(f"API call: {method}({json.dumps(kwargs)})\n  -> {response.text}")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            e.add_note(e.response.text)
            raise
        js = response.json()
        if js.get("error_code"):
            raise Exception(
                f"Phabricator API error: {js['error_code']} - {js.get('error_info')}"
            )
        return response.json()["result"]
