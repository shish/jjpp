import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

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


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str, remote_url: httpx.URL):
        self.remote = remote
        self.remote_url = remote_url

    @property
    def forge_url(self) -> httpx.URL:
        """Extract the forge API base URL from remote_url.

        Converts URLs like:
        - https://gerrit.mycompany.com/a/project -> https://gerrit.mycompany.com
        - https://github.com/owner/repo.git -> https://github.com
        """
        return httpx.URL(f"{self.remote_url.scheme}://{self.remote_url.host}")

    @property
    def project_id(self) -> str:
        """Extract the project path from remote_url.

        Converts URLs like:
        - https://gerrit.mycompany.com/a/project -> project
        - https://github.com/owner/repo.git -> owner/repo
        """
        # Handle HTTPS URLs
        path = self.remote_url.path

        # Remove leading/trailing slashes and .git suffix
        path = path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]

        # Remove Gerrit API prefix /a/ if present
        if path.startswith("a/"):
            path = path[2:]

        return path

    @abstractmethod
    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        """Push changes to the forge."""

    @abstractmethod
    def checkout(self, identifier: str) -> None:
        """Checkout changes from the forge."""

    @abstractmethod
    def list(self, all_projects: bool = False) -> List[CRListItem]:
        """List items on the forge, returning a list of CRListItem objects."""
