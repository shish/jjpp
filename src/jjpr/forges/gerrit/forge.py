import logging
import re

import httpx

from ...utils import exec, git, jj
from ..base import CRListItem, Forge
from .client import GerritClient

log = logging.getLogger(__name__)


class Gerrit(Forge):
    def __init__(self, remote: str):
        super().__init__(remote)
        if conf := jj.config_get("gerrit.review-url"):
            self.forge_url = httpx.URL(conf)
        else:
            s = self.remote_url.scheme
            self.forge_url = self.remote_url.copy_with(
                scheme=s if s == "http" else "https", path="/"
            )
        if match := re.match(r"^/(a/)?(.*?)(\.git)?$", self.remote_url.path):
            self.project_id = match.group(2)
        if conf := jj.config_get("gerrit.default-remote-branch"):
            self.merge_target = conf
        else:
            self.merge_target = git.get_merge_target()

        self.client = GerritClient(self.forge_url)

    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
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
            remote_branch=self.merge_target,
        )

    def checkout_cr(self, identifier: str) -> None:
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
        exec.run(["git", "fetch", self.remote, f"{current_rev}:{remote_id}"])
        exec.run(["git", "checkout", remote_id])

    def list_crs(self, all_projects: bool = False) -> list[CRListItem]:
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

        crs: list[CRListItem] = []
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
