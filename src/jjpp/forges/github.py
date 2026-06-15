import json
import logging
import re
from typing import Optional

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class GitHubForge(Forge):
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
            log.info(f"Found existing PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.run("bookmark", "advance", pr_branch, "--to", changes[-1])
                jj.run("git", "push", "--remote", self.remote, "--bookmark", pr_branch)
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
                jj.run("git", "push", "--remote", self.remote, "--bookmark", pr_branch)
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

    def list(self) -> None:
        cmd = [
            "gh",
            "pr",
            "list",
            "--repo",
            self.remote_url,
            "--json",
            "number,title,state,url",
        ]
        prs = json.loads(utils.run(cmd))
        crs = []
        for pr in prs:
            crs.append(
                CRListItem(
                    identifier=str(pr["number"]),
                    title=pr["title"],
                    url=pr["url"],
                    extra=f"[{pr['state']}]",
                )
            )
        self.display_list(crs)
