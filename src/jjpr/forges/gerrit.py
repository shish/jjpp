import base64
import json
import logging
import re
from netrc import NetrcParseError, netrc
from typing import List, Optional, Union

import httpx

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class Gerrit(Forge):
    def _get_auth_header(self) -> Optional[dict]:
        try:
            rc = netrc()
        except (FileNotFoundError, NetrcParseError) as e:
            log.warning(f"Could not get creds from netrc file: {e}")
            return None

        # Extract hostname from forge_url (e.g., "gerrit.example.com" from "https://gerrit.example.com")
        hostname = self.forge_url.host

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

    def _request(self, url: httpx.URL) -> Union[dict, list]:
        auth_header = self._get_auth_header()

        try:
            log.debug(f"Making request to {url}")
            response = httpx.get(url, headers=auth_header or {})
            response.raise_for_status()
            result = response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise utils.UserError(
                    f"Authentication failed for {url}. Check your netrc credentials."
                )
            raise

        # Gerrit API returns a magic prefix that needs to be stripped
        result = result.lstrip(")]}':\n")

        try:
            result = json.loads(result)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON from {url} ({result[:20]!r}): {e}")
            raise
        log.debug(f"Response from {url}:\n{json.dumps(result)}")
        return result

    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        if ref:
            change_id = jj.revset_to_changeid(ref)
            range = f"{change_id}::{change_id}"
        else:
            range = jj.closest_work()
        log.info(f"Pushing {range} to gerrit")
        args = ["gerrit", "upload", "-r", range]
        if draft:
            args.append("--wip")
        if message:
            args.extend(["--message", message])
        args.extend(["--remote-branch", utils.get_merge_target()])
        jj.run(*args, cap=False)

    def checkout(self, identifier: str) -> None:
        log.info(f"Fetching Gerrit change {identifier}")
        # Query API to get the latest patch set number
        url = self.forge_url.join(f"/a/changes/{identifier}?o=CURRENT_REVISION")
        change_data_response = self._request(url)

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
        url = self.forge_url.join(
            f"/a/changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=DETAILED_ACCOUNTS"
        )
        changes_response = self._request(url)

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
                    state=self._colour_state(
                        is_private=change.get("is_private", False),
                        work_in_progress=change.get("work_in_progress", False),
                        blockers=len(blockers) > 0,
                    ),
                    blockers=", ".join(blockers),
                )
            )

        return crs

    def _colour_state(
        self,
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
