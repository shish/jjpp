import base64
import logging
import netrc

import httpx

from ... import exc

log = logging.getLogger(__name__)


class GerritClient(httpx.Client):
    """Custom httpx.Client for Gerrit.

    - Loads credentials from ~/.netrc.
    - Adds HTTP Basic Auth header to requests.
    - Strips Gerrit's magic prefix from JSON responses.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL) -> None:
        auth = _get_auth(str(base_url.host))
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
        log.debug(
            f"API call:\n"
            f"  {response.request.method} {response.request.url} = {response.status_code}\n"
            # f"  <- {parse_qs(response.request.content.decode())}\n"
            f"  -> {response.text}"
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
        return response


def _get_auth(hostname: str) -> tuple[str, str] | None:
    try:
        rc = netrc.netrc()
    except (FileNotFoundError, netrc.NetrcParseError) as e:
        log.warning(f"Could not get creds from netrc file: {e}")
        return None

    auth = rc.authenticators(hostname)
    if not auth:
        log.warning(f"No credentials found in netrc for {hostname}")
        return None

    login, _, password = auth
    if not password:
        log.warning(f"Empty password in netrc for {hostname}")
        return None

    return (login, password)
