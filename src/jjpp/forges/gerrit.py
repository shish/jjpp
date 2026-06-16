import base64
import json
import logging
import re
from netrc import NetrcParseError, netrc
from typing import List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class Gerrit(Forge):
    def _get_auth_header(self) -> Optional[dict]:
        try:
            rc = netrc()
        except (FileNotFoundError, NetrcParseError) as e:
            log.warning(f"Could not read netrc file: {e}")
            return None

        # Extract hostname from forge_url (e.g., "gerrit.example.com" from "https://gerrit.example.com")

        parsed = urlparse(self.forge_url)
        hostname = parsed.hostname

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

    def _request(self, url: str) -> Union[dict, list]:
        auth_header = self._get_auth_header()

        req = Request(url)
        if auth_header:
            for key, value in auth_header.items():
                req.add_header(key, value)

        try:
            log.debug(f"Making request to {url}")
            with urlopen(req) as response:
                result = response.read().decode("utf-8")
        except HTTPError as e:
            if e.code == 401:
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
        url = f"{self.forge_url}/a/changes/{identifier}?o=CURRENT_REVISION"
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
        url = f"{self.forge_url}/a/changes/?q={query}&o=SUBMIT_REQUIREMENTS&o=MESSAGES"
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
                    url=f"{self.forge_url}/c/{change['_number']}",
                    extra={
                        "state": change["status"],
                        "blockers": ", ".join(blockers),
                    },
                )
            )

        return crs
