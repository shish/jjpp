import base64
import json
import logging

import httpx

from ... import exc
from ...utils import netrc

log = logging.getLogger(__name__)


class GerritClient(httpx.Client):
    """Custom httpx.Client for Gerrit.

    - Loads credentials from ~/.netrc.
    - Adds HTTP Basic Auth header to requests.
    - Strips Gerrit's magic prefix from JSON responses.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL) -> None:
        auth = netrc.read(str(base_url.host))
        if not auth:
            raise exc.UserError(
                f"Could not find credentials for {base_url.host} in ~/.netrc"
            )
        cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        super().__init__(
            base_url=base_url.copy_with(path="/a/"),
            headers={"Authorization": f"Basic {cred}"},
        )

    def request(self, *args, **kwargs) -> httpx.Response:
        response = super().request(*args, **kwargs)
        request = response.request
        log.debug(
            f"API call: {request.method} {request.url.path} = {response.status_code}\n"
            f"  <- {json.dumps(dict(request.url.params))}\n"
            f"  -> " + response.text.lstrip(")]}':\n")
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise exc.UserError(
                    "Authentication failed. Check your ~/.netrc credentials."
                )
            e.add_note(e.response.text)
            raise
        # Gerrit API returns a magic prefix that needs to be stripped
        cleaned_text = response.text.lstrip(")]}':\n")
        # Replace the response text with cleaned content
        response._content = cleaned_text.encode()
        del response._text  # Remove the cached property to force re-evaluation
        return response
