import logging
from typing import Optional

from .. import jj
from .base import Forge

log = logging.getLogger(__name__)


class GerritForge(Forge):
    def push(self, ref: Optional[str], pre_commit: bool) -> None:
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=True)
        )
        for change_id in changes:
            with jj.with_edit(change_id):
                log.info(f"Pushing change {change_id} (pre-commit={pre_commit})")
                if pre_commit:
                    self.pre_commit(change_id)
                log.warning(f"[TODO] Pushing {change_id}")
                # jj.run('gerrit', 'push', '-r', change_id)

    def pull(self, identifier: Optional[str] = None) -> None:
        log.warning("[TODO] Pull CR")
        if identifier:
            log.warning(f"  CR ID: {identifier}")

    def list(self) -> None:
        log.warning("[TODO] Listing CRs")
