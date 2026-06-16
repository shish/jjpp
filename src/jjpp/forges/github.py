import json
import logging
import re
from typing import Optional

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class GitHub(Forge):
    def push(self, ref: Optional[str]) -> None:
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=True)
        )

        # if a change between the base and current change has
        # a branch name that starts with "pr/":
        branches = [jj.branches_pointing_to(change, prefix="pr/") for change in changes]
        branches = [b[0] for b in branches if b]
        if branches:
            # - advance that branch to the current change
            # - force-push the branch to the remote
            pr_branch = branches[-1]
            log.info(f"Updating existing PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.run("bookmark", "advance", pr_branch, "--to", changes[-1])
                jj.run(
                    "git",
                    "push",
                    "--remote",
                    self.remote,
                    "--bookmark",
                    pr_branch,
                    cap=False,
                )
        else:
            # - create a new branch named "pr/<sanitized-title>" where
            #   <sanitized-title> is a name based on the description of
            #   the last change in the stack
            # - push that branch to the remote
            # - create a PR on GitHub with the new branch as the source
            #   and the merge target as the destination
            description = jj.description_of(changes[-1])
            if not description:
                raise ValueError(f"No description found for change {changes[-1]}")
            title = description.splitlines()[0]
            sanitized_title = re.sub(r"[^a-zA-Z0-9\-]+", "-", title).strip("-").lower()
            pr_branch = utils.unique_branch_name(f"pr/{sanitized_title}")
            log.info(f"Creating new PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.run("bookmark", "create", pr_branch, "-r", changes[-1])
                jj.run(
                    "git",
                    "push",
                    "--remote",
                    self.remote,
                    "--bookmark",
                    pr_branch,
                    cap=False,
                )
                base = utils.get_merge_target()
                utils.run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--fill",
                        "--head",
                        pr_branch,
                        "--base",
                        base,
                    ]
                )

    def checkout(self, identifier: str) -> None:
        log.info(f"Checking out PR {identifier} from {self.remote_url}")
        utils.run(
            [
                "gh",
                "pr",
                "checkout",
                identifier,
                "--repo",
                self.remote_url,
            ]
        )

    def list(self, all_projects: bool = False) -> list[CRListItem]:
        if all_projects:
            log.warning("Listing PRs for all projects is not supported for GitHub.")
        log.info(
            f"Listing PRs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )
        cmd = [
            "gh",
            "pr",
            "list",
            "--repo",
            self.remote_url,
            "--json",
            "number,title,state,url,statusCheckRollup",
        ]
        prs = json.loads(utils.run(cmd))
        crs: list[CRListItem] = []
        for pr in prs:
            # Merge status checks into a blockers string
            checks = pr.get("statusCheckRollup", [])
            blockers = ", ".join(
                f"{check['name']}: {check['conclusion']}"
                for check in checks
                if check.get("conclusion") != "SUCCESS"
            )
            crs.append(
                CRListItem(
                    forge_name="GitHub",
                    forge_url=self.forge_url,
                    project_id=self.project_id,
                    identifier=str(pr["number"]),
                    title=pr["title"],
                    url=pr["url"],
                    extra={
                        "state": pr["state"],
                        "blockers": blockers,
                    },
                )
            )
        return crs
