import logging
from typing import List, Optional

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class Phabricator(Forge):
    def push(
        self, ref: Optional[str], draft: bool = False, message: Optional[str] = None
    ) -> None:
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=True)
        )
        for change_id in changes:
            with jj.with_new(change_id):
                log.warning(f"[TODO] Pushing {change_id}")
                args = ["arc", "diff", "HEAD^"]
                if draft:
                    args.append("--draft")
                if message:
                    args.extend(["--message", message])
                utils.run(args, cap=False)

    def checkout(self, identifier: str) -> None:
        log.warning(f"[TODO] Checkout diff {identifier}")

    def list(self, all_projects: bool = False) -> List[CRListItem]:
        log.warning(
            f"Listing diffs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )
        return []
