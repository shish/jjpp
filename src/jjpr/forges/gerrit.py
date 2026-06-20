import base64
import logging
import re
from netrc import NetrcParseError, netrc
from typing import List, Optional

import httpx

from .. import git, jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class GerritClient(httpx.Client):
    """Custom httpx.Client for Gerrit.

    - Loads credentials from ~/.netrc.
    - Adds HTTP Basic Auth header to requests.
    - Strips Gerrit's magic prefix from JSON responses.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL) -> None:
        headers = _get_auth_header(base_url.host)
        if not headers:
            raise utils.UserError(
                f"Could not find credentials for {base_url.host} in ~/.netrc"
            )
        super().__init__(
            base_url=base_url.copy_with(path="/a/"),
            headers=headers,
        )

    def request(self, *args, **kwargs) -> httpx.Response:
        response = super().request(*args, **kwargs)
        log.debug(
            f"{response.request.method}({response.request.url}) -> {response.text}"
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise utils.UserError(
                    "Authentication failed. Check your ~/.netrc credentials."
                )
            e.add_note(e.response.text)
            raise
        # Gerrit API returns a magic prefix that needs to be stripped
        cleaned_text = response.text.lstrip(")]}':\n")
        # Replace the response text with cleaned content
        response._content = cleaned_text.encode()
        return response


class Gerrit(Forge):
    def __init__(self, remote: str, remote_url: httpx.URL):
        super().__init__(remote, remote_url)
        self.client = GerritClient(self.forge_url)

    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        if ref:
            change_id = jj.change_id(ref)
            range = f"{change_id}::{change_id}"
        else:
            range = jj.closest_work()
        log.info(f"Pushing {range} to gerrit")
        jj.gerrit_upload(
            r=range,
            wip=draft,
            message=message,
            remote_branch=git.get_merge_target(),
        )

    def checkout(self, identifier: str) -> None:
        log.info(f"Fetching Gerrit change {identifier}")
        # Query API to get the latest patch set number
        change_data_response = self.client.get(
            f"changes/{identifier}?o=CURRENT_REVISION"
        ).json()

        # Ensure response is a dict
        if not isinstance(change_data_response, dict):
            log.error(f"Invalid response type for change {identifier}")
            return

        # Get the latest patch set revision
        current_rev = change_data_response.get("current_revision")
        if not current_rev:
            log.error(f"Could not determine current revision for change {identifier}")
            return

        # Fetch the latest patch set
        remote_id = f"refs/remotes/{self.remote}/change-{identifier}"
        utils.run(["git", "fetch", self.remote, f"{current_rev}:{remote_id}"])
        utils.run(["git", "checkout", remote_id])

    def list(self, all_projects: bool = False) -> List[CRListItem]:
        """List the user's open changes in Gerrit, showing any blockers."""
        log.info(
            f"Listing open changes from {self.forge_url} ({'*' if all_projects else self.project_id})"
        )
        query = "owner:self+status:open"
        if not all_projects:
            query += f"+project:{self.project_id}"
        changes_response = self.client.get(
            f"changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
        ).json()

        crs: List[CRListItem] = []
        for change in changes_response:
            blockers = []
            for req in change.get("submit_requirements", []):
                if req["status"] not in {"SATISFIED", "NOT_APPLICABLE"}:
                    req_name = re.sub("[^A-Z]+", "", req["name"])
                    blockers.append(req_name)

            crs.append(
                CRListItem(
                    forge_name="Gerrit",
                    forge_url=self.forge_url,
                    project_id=self.project_id,
                    identifier=str(change["_number"]),
                    title=change["subject"],
                    url=self.forge_url.join(f"/c/{change['_number']}"),
                    state=_colour_state(
                        is_private=change.get("is_private", False),
                        work_in_progress=change.get("work_in_progress", False),
                        blockers=len(blockers) > 0,
                    ),
                    blockers=", ".join(blockers),
                )
            )

        return crs


def _get_auth_header(hostname: str | None) -> Optional[dict]:
    try:
        rc = netrc()
    except (FileNotFoundError, NetrcParseError) as e:
        log.warning(f"Could not get creds from netrc file: {e}")
        return None

    if not hostname:
        log.warning("Could not determine hostname from forge_url")
        return None

    auth = rc.authenticators(hostname)
    if not auth:
        log.warning(f"No credentials found in netrc for {hostname}")
        return None

    login, _, password = auth
    if not password:
        log.warning(f"Empty password in netrc for {hostname}")
        return None

    credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def _colour_state(
    is_private: bool = False,
    work_in_progress: bool = False,
    blockers: bool = False,
) -> str:
    if is_private:
        state = "Private"
        color = "cyan"
    elif work_in_progress:
        state = "Draft"
        color = "cyan"
    elif blockers:
        state = "Blocked"
        color = "yellow"
    else:
        state = "Accepted"
        color = "green"

    return f"[{color}]{state}[/{color}]"
