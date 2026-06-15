import logging
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .. import jj

log = logging.getLogger(__name__)


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str, remote_url: str):
        self.remote = remote
        self.remote_url = remote_url

    @abstractmethod
    def push(self, ref: Optional[str], pre_commit: bool) -> None:
        """Push changes to the forge."""
        pass

    @abstractmethod
    def pull(self, identifier: Optional[str] = None) -> None:
        """Pull changes from the forge."""
        pass

    @abstractmethod
    def list(self) -> None:
        """List items on the forge."""
        pass

    def pre_commit(self, change_id: jj.ChangeID) -> None:
        if not Path(".git/hooks/pre-commit").exists():
            log.info("No .git/hooks/pre-commit found, skipping pre-commit hooks")
            return
        with jj.with_edit(change_id):
            files = jj.files_in(change_id)
            log.info(f"Running pre-commit on {change_id} ({shlex.join(files)})")
            subprocess.run(["pre-commit", "run", "--files", *files], check=True)
