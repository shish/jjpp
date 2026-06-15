import logging
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from .. import jj, utils

log = logging.getLogger(__name__)


class CRListItem:
    """Represents an item in a code review list."""

    def __init__(
        self,
        identifier: str,
        title: str,
        url: Optional[str],
        extra: Optional[str] = None,
    ):
        self.identifier = identifier
        self.title = title
        self.url = url
        self.extra = extra

    def __str__(self) -> str:
        title_link = utils.hyperlink(self.url, self.title) if self.url else self.title
        return f"{self.identifier}: {title_link} {self.extra}".strip()


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str, remote_url: str):
        self.remote = remote
        self.remote_url = remote_url

    @abstractmethod
    def push(self, ref: Optional[str]) -> None:
        """Push changes to the forge."""
        pass

    @abstractmethod
    def checkout(self, identifier: str) -> None:
        """Checkout changes from the forge."""
        pass

    @abstractmethod
    def list(self) -> None:
        """List items on the forge."""
        pass

    def pre_commit_stack(self, ref: Optional[str]) -> None:
        if not Path(".git/hooks/pre-commit").exists():
            log.info("No .git/hooks/pre-commit found, skipping pre-commit hooks")
            return
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=False)
        )
        log.info("Pre-commit checking all changes in the stack")
        for change_id in changes:
            try:
                self.pre_commit(change_id)
            except Exception:
                raise utils.UserError(f"Pre-commit failed for change {change_id}")

    def pre_commit(self, change_id: jj.ChangeID) -> None:
        if not Path(".git/hooks/pre-commit").exists():
            log.info("No .git/hooks/pre-commit found, skipping pre-commit hooks")
            return
        with jj.with_edit(change_id):
            files = jj.files_in(change_id)
            log.info(f"Running pre-commit on {change_id} ({shlex.join(files)})")
            subprocess.run(["pre-commit", "run", "--files", *files], check=True)

    def display_list(self, items: List[CRListItem]) -> None:
        if not items:
            print("No items found on the forge")
            return
        print("Items on the forge:")
        for item in items:
            print(f"  {item}")
