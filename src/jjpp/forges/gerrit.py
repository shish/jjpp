from typing import Optional

import typer

from .base import Forge


class GerritForge(Forge):
    def push(self, ref: str) -> None:
        """Push changes to Gerrit."""
        typer.echo(f"[TODO] Gerrit: Pushing {ref} to Gerrit")

    def pull(self, identifier: Optional[str] = None) -> None:
        """Pull CR from Gerrit."""
        typer.echo("[TODO] Gerrit: Pulling from Gerrit")
        if identifier:
            typer.echo(f"  CR ID: {identifier}")

    def list(self) -> None:
        """List Gerrit changes."""
        typer.echo("[TODO] Gerrit: Listing Gerrit changes")
