from typing import Optional

import typer

from .base import Forge


class GitHubForge(Forge):
    def push(self, ref: str) -> None:
        """Push changes to GitHub."""
        typer.echo(f"[TODO] GitHub: Pushing {ref} to GitHub")

    def pull(self, identifier: Optional[str] = None) -> None:
        """Pull PR from GitHub."""
        typer.echo("[TODO] GitHub: Pulling from GitHub")
        if identifier:
            pr_number = int(identifier)
            typer.echo(f"  PR: #{pr_number}")

    def list(self) -> None:
        """List GitHub PRs."""
        typer.echo("[TODO] GitHub: Listing GitHub PRs")
