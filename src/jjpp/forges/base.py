import logging
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table

from .. import jj, utils

log = logging.getLogger(__name__)


class CRListItem:
    """Represents an item in a code review list."""

    def __init__(
        self,
        identifier: str,
        title: str,
        url: Optional[str],
        extra: Optional[dict[str, str]] = None,
    ):
        self.identifier = identifier
        self.title = title
        self.url = url
        self.extra = extra or {}


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
    def push(self, ref: Optional[str]) -> None:
        """Push changes to the forge."""

    @abstractmethod
    def checkout(self, identifier: str) -> None:
        """Checkout changes from the forge."""

    @abstractmethod
    def list(self) -> None:
        """List items on the forge."""

    def pre_commit_stack(self, ref: Optional[str]) -> None:
        if not Path(".git/hooks/pre-commit").exists():
            log.info("No .git/hooks/pre-commit found, skipping pre-commit hooks")
            return

        pc_cmd = None
        for cmd in ["prek", "pre-commit"]:
            if shutil.which(cmd):
                pc_cmd = cmd
                break
        if not pc_cmd:
            log.info("No pre-commit command found, skipping pre-commit hooks")
            return

        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=False)
        )
        log.debug("Pre-commit checking all changes in the stack")
        for change_id in changes:
            with jj.with_edit(change_id):
                files = jj.files_in(change_id)
                descr = (jj.description_of(change_id).splitlines() or ["(untitled)"])[0]
                if ref is None:
                    print("=" * 80)
                    print(f'Running {pc_cmd} on "{descr}" ({change_id})')
                    print(f"Affected files: {shlex.join(files)}")
                else:
                    log.debug(f"Running {pc_cmd} on {change_id} ({shlex.join(files)})")
                try:
                    files = [f for f in files if Path(f).exists()]
                    subprocess.run([pc_cmd, "run", "--files", *files], check=True)
                except FileNotFoundError:
                    raise
                except Exception:
                    raise utils.UserError(f"Pre-commit failed for change {change_id}")

    def display_list(self, items: List[CRListItem]) -> None:
        console = Console()

        title = self.__class__.__name__
        url = self.remote_url
        if not items:
            console.print(f"[green]No reviews on [link={url}]{title}[/link][/green]")
            return

        all_extra_keys = set()
        for item in items:
            all_extra_keys.update(item.extra.keys())

        table = Table(title=f"Reviews on [link={url}]{title}[/link]")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="magenta")
        for key in sorted(all_extra_keys):
            table.add_column(key.title(), style="yellow")

        for item in items:
            if item.url:
                title_link = f"[link={item.url}]{item.title}[/link]"
            else:
                title_link = item.title
            table.add_row(
                item.identifier,
                title_link,
                *[
                    item.extra[key] if key in item.extra else ""
                    for key in sorted(all_extra_keys)
                ],
            )

        console.print(table)
