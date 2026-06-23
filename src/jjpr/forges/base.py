import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

import httpx

from ..utils import git

log = logging.getLogger(__name__)


@dataclass
class CRListItem:
    """Represents an item in a code review list."""

    forge_name: str
    forge_url: httpx.URL
    project_id: str
    identifier: str
    title: str
    url: httpx.URL
    state: str
    blockers: str
    extra: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["forge_url"] = str(self.forge_url)
        d["url"] = str(self.url)
        return d


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str) -> None:
        self.remote = remote
        self.remote_url = git.get_remote_url(remote)

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
    def list_crs(self, all_projects: bool = False) -> list[CRListItem]:
        """List items on the forge, returning a list of CRListItem objects."""
