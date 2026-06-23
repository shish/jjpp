import logging
import re
from abc import ABC, abstractmethod

from ..utils import git, jj, text
from . import cr

log = logging.getLogger(__name__)


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str) -> None:
        self.remote = remote
        self.remote_url = git.get_remote_url(remote)
        self.forge_url = self.remote_url
        self.project_id = "unknown"

    def asdict(self) -> dict:
        return {
            "name": self.__class__.__name__,
            "remote": self.remote,
            "remote_url": str(self.remote_url),
            "forge_url": str(self.forge_url),
            "project_id": self.project_id,
        }

    def __rich__(self) -> str:
        return f"[link={self.forge_url}]{self.__class__.__name__}[/link]"

    @abstractmethod
    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        """Push changes to the forge."""

    @abstractmethod
    def checkout_cr(self, identifier: str) -> None:
        """Checkout changes from the forge."""

    @abstractmethod
    def list_crs(self, all_projects: bool = False) -> list[cr.CodeReview]:
        """List items on the forge, returning a list of CRListItem objects."""

    def _log(
        self, args: list[str], template: str, id_to_state: dict[str, cr.State]
    ) -> str:
        """Helper to run `jj log` with an extra template for CR IDs, and then
        replace those IDs with the current CR status"""
        logdata = jj.log_(
            "--color",
            "always",
            "--config",
            f"template-aliases.\"format_commit_labels(commit)\"='''\"JJPR:\"++{template}++\":JJPR\"'''",
            *args,
        )
        log.debug(f"Updating log output with PRs: {id_to_state}")
        logdata = re.sub(
            r"JJPR:([^:]*):JJPR",
            lambda x: str(id_to_state.get(text.remove_ansi(x.group(1)), "")),
            logdata,
        )
        return logdata

    @abstractmethod
    def log(self, args: list[str]) -> str:
        """Run `jj log` with annotated extra output for the forge."""
