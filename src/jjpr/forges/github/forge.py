import json
import logging
import re
import typing as t

import httpx

from ...utils import exec, git, jj
from ..base import CRListItem, Forge

log = logging.getLogger(__name__)


class GitHub(Forge):
    def __init__(self, remote: str):
        super().__init__(remote)

        s = self.remote_url.scheme
        self.forge_url = self.remote_url.copy_with(
            scheme=s if s == "http" else "https", path="/"
        )

        if match := re.match("/([^/]+?/[^/]+?)(\\.git)?", self.remote_url.path):
            self.project_id = match.group(1)
        else:
            raise ValueError(
                f"Invalid GitHub remote URL format: {self.remote_url}. Expected format: owner/repo"
            )

    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        changes = jj.change_id(ref) if ref else jj.pushable_stack()

        # if a change in the stack has a branch name that starts with "pr/":
        branches = [jj.branches_pointing_to(change, prefix="pr/") for change in changes]
        branches = [list(b)[0] for b in branches if b]
        if branches:
            # - advance that branch to the current change
            # - force-push the branch to the remote
            pr_branch = branches[-1]
            log.info(f"Updating existing PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.bookmark_advance(pr_branch, to=changes[-1])
                jj.git_push(remote=self.remote, bookmark=pr_branch)
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
            pr_branch = git.unique_branch_name(f"pr/{sanitized_title}")
            log.info(f"Creating new PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.bookmark_create(pr_branch, r=changes[-1])
                jj.git_push(remote=self.remote, bookmark=pr_branch)
                base = git.get_merge_target()
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
                exec.run(args)

    def checkout_cr(self, identifier: str) -> None:
        log.info(f"Checking out PR {identifier} from {self.remote_url}")
        exec.run(
            [
                "gh",
                "pr",
                "checkout",
                identifier,
                "--repo",
                str(self.remote_url),
            ]
        )

    def list_crs(self, all_projects: bool = False) -> list[CRListItem]:
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
        prs = json.loads(exec.run(cmd))
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
                    state=_colour_state(is_draft=is_draft, reviews=reviews),
                    blockers=blockers,
                )
            )
        return crs


def _colour_state(is_draft: bool = False, reviews: list[t.Any] | None = None) -> str:
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
