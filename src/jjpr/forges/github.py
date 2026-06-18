import json
import logging
import re
from typing import Any, List, Optional

import httpx

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class GitHub(Forge):
    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
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
                args = [
                    "gh",
                    "pr",
                    "create",
                    "--fill",
                    "--head",
                    pr_branch,
                    "--base",
                    base,
                ]
                if draft:
                    args.append("--draft")
                if message:
                    args.extend(["-b", message])
                utils.run(args)

    def checkout(self, identifier: str) -> None:
        log.info(f"Checking out PR {identifier} from {self.remote_url}")
        utils.run(
            [
                "gh",
                "pr",
                "checkout",
                identifier,
                "--repo",
                str(self.remote_url),
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
            str(self.remote_url),
            "--json",
            "number,title,state,url,statusCheckRollup,isDraft,reviews",
        ]
        prs = json.loads(utils.run(cmd))
        crs: list[CRListItem] = []
        c2c = {
            "SUCCESS": "green",
            "PENDING": "yellow",
            "FAILURE": "red",
        }
        for pr in prs:
            # Merge status checks into a blockers string
            checks = pr.get("statusCheckRollup", [])
            blockers = ", ".join(
                f"[{c2c.get(check['conclusion'], 'normal')}][link={check['detailsUrl']}]{check['name']}[/link][/]"
                for check in checks
                if check.get("conclusion") != "SUCCESS"
            )

            # Determine PR state based on draft status and reviews
            is_draft = pr.get("isDraft", False)
            reviews = pr.get("reviews", [])

            crs.append(
                CRListItem(
                    forge_name="GitHub",
                    forge_url=self.forge_url,
                    project_id=self.project_id,
                    identifier=str(pr["number"]),
                    title=pr["title"],
                    url=httpx.URL(pr["url"]),
                    state=self._colour_state(
                        pr["state"], is_draft=is_draft, reviews=reviews
                    ),
                    blockers=blockers,
                )
            )
        return crs

    def _colour_state(
        self, state: str, is_draft: bool = False, reviews: Optional[List[Any]] = None
    ) -> str:
        if reviews is None:
            reviews = []

        # Determine display state based on draft and review status
        if is_draft:
            display_state = "Draft"
            color = "cyan"
        else:
            # Check review status
            has_approved = any(r.get("state") == "APPROVED" for r in reviews)
            has_rejected = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)

            if has_rejected:
                display_state = "Rejected"
                color = "red"
            elif has_approved:
                display_state = "Accepted"
                color = "green"
            else:
                display_state = "Needs Review"
                color = "yellow"

        return f"[{color}]{display_state}[/{color}]"
