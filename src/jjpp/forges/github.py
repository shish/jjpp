import logging
import re
from typing import Optional

from .. import jj, utils
from .base import Forge

log = logging.getLogger(__name__)


class GitHubForge(Forge):
    def push(self, ref: Optional[str], pre_commit: bool) -> None:
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=True)
        )
        if pre_commit:
            log.info("Pre-commit checking all changes in the stack")
            for change_id in changes:
                self.pre_commit(change_id)

        # if a change between the base and current change has
        # a branch name that starts with "pr/":
        # - advance that branch to the current change
        # - force-push the branch to the remote
        # else:
        # - create a new branch named "pr/<sanitized-title>" where
        #   <sanitized-title> is a name based on the description of
        #   the last change in the stack
        # - push that branch to the remote
        # - create a PR on GitHub with the new branch as the source
        #   and the merge target as the destination

        branches = [jj.branches_pointing_to(change, prefix="pr/") for change in changes]
        branches = [b[0] for b in branches if b]
        if branches:
            pr_branch = branches[-1]
            log.info(f"Found existing PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                jj.run("bookmark", "advance", pr_branch, "--to", changes[-1])
                utils.run(
                    [
                        "git",
                        "push",
                        "--force",
                        self.remote,
                        f"{pr_branch}:{pr_branch}",
                        "--force-with-lease",
                    ],
                )
        else:
            description = jj.description_of(changes[-1])
            if not description:
                raise ValueError(f"No description found for change {changes[-1]}")
            title = description.splitlines()[0]
            sanitized_title = re.sub(r"[^a-zA-Z0-9\-]+", "-", title).strip("-").lower()
            pr_branch = f"pr/{sanitized_title}"
            log.info(f"Creating new PR branch: {pr_branch}")
            with jj.with_new(changes[-1]):
                utils.run(["git", "checkout", "-b", pr_branch])
                utils.run(["git", "push", self.remote, f"{pr_branch}:{pr_branch}"])
                base = utils.get_merge_target()
                utils.run(["gh", "pr", "create", "--fill", "--base", base])

    def pull(self, identifier: Optional[str] = None) -> None:
        log.warning("[TODO] Pull PR")
        if identifier:
            pr_number = int(identifier)
            log.warning(f"  PR: #{pr_number}")

    def list(self) -> None:
        log.warning("[TODO] Listing PRs")
