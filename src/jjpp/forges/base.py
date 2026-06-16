import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)


@dataclass
class CRListItem:
    """Represents an item in a code review list."""

    forge_name: str
    forge_url: str
    project_id: str
    identifier: str
    title: str
    url: str
    extra: dict[str, str] = field(default_factory=dict)


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote: str, remote_url: str):
        self.remote = remote
        self.remote_url = remote_url

    @property
    def forge_url(self) -> str:
        """Extract the forge API base URL from remote_url.

        Converts URLs like:
        - https://gerrit.mycompany.com/a/project -> https://gerrit.mycompany.com
        - git@gerrit.mycompany.com:project -> https://gerrit.mycompany.com
        """
        parsed = urlparse(self.remote_url)

        # Handle SSH URLs (git@host:project)
        if parsed.scheme in ("", "ssh") or "@" in self.remote_url:
            # Extract host from git@host:project format
            host = self.remote_url.split("@")[1].split(":")[0]
            return f"https://{host}"

        # Handle HTTPS URLs
        if parsed.scheme in ("http", "https"):
            return f"{parsed.scheme}://{parsed.netloc}"

        raise ValueError(f"Cannot parse forge URL from remote: {self.remote_url}")

    @property
    def project_id(self) -> str:
        """Extract the project path from remote_url.

        Converts URLs like:
        - https://gerrit.mycompany.com/a/project -> project
        - git@gerrit.mycompany.com:project -> project
        - https://github.com/owner/repo.git -> owner/repo
        """
        parsed = urlparse(self.remote_url)

        # Handle SSH URLs (git@host:project)
        if parsed.scheme in ("", "ssh") or "@" in self.remote_url:
            # Extract path from git@host:project format
            path = self.remote_url.split(":")[1]
        else:
            # Handle HTTPS URLs
            path = parsed.path

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
