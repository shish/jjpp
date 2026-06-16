import json
import logging
from typing import List, Optional
from urllib.request import urlopen

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class Gerrit(Forge):
    def push(
        self, ref: Optional[str], draft: bool = False, message: Optional[str] = None
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
        jj.run(*args, cap=False)

    def checkout(self, identifier: str) -> None:
        log.info(f"Fetching Gerrit change {identifier}")
        # Query API to get the latest patch set number
        url = f"{self.forge_url}/a/changes/{identifier}?o=CURRENT_REVISION"
        with urlopen(url) as response:
            result = response.read().decode("utf-8")
        # Gerrit API returns a magic prefix that needs to be stripped
        if result.startswith(")]}'"):
            result = result[5:]
        change_data = json.loads(result)

        # Get the latest patch set revision
        current_rev = change_data.get("current_revision")
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
        # Query Gerrit REST API for current user's open changes
        # 'owner:self' filters to current user, 'status:open' shows only open changes
        # DETAILED_LABELS shows reviewer votes and blocking votes
        query = "owner:self+status:open"
        if not all_projects:
            query += f"+project:{self.project_id}"
        url = f"{self.forge_url}/a/changes/?q={query}&o=DETAILED_LABELS&o=MESSAGES"
        with urlopen(url) as response:
            result = response.read().decode("utf-8")
        # Gerrit API returns a magic prefix that needs to be stripped
        if result.startswith(")]}'"):
            result = result[5:]
        changes = json.loads(result)

        if not changes:
            return []

        crs: List[CRListItem] = []
        for change in changes:
            number = change.get("_number", "N/A")
            subject = change.get("subject", "N/A")
            status = change.get("status", "N/A")

            # Check for blockers
            blockers = []
            labels = change.get("labels", {})
            for label_name, label_data in labels.items():
                votes = label_data.get("all", [])
                for vote in votes:
                    value = vote.get("value")
                    # Check for blocking votes (-2) or negative votes (-1)
                    if value == -2:
                        blocker_name = vote.get("name", "Unknown")
                        blockers.append(f"Blocked by {blocker_name} ({label_name})")
                    elif value == -1:
                        blocker_name = vote.get("name", "Unknown")
                        blockers.append(f"{label_name}: {blocker_name}")

            blocker_str = f" [{', '.join(blockers)}]" if blockers else ""
            change_url = f"{self.forge_url}/c/{number}" if number != "N/A" else ""
            crs.append(
                CRListItem(
                    forge_name="Gerrit",
                    forge_url=self.forge_url,
                    project_id=self.project_id,
                    identifier=str(number),
                    title=subject,
                    url=change_url,
                    extra={"status": status, "blockers": blocker_str},
                )
            )

        return crs
