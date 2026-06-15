from typing import Optional

import typer

from .base import Forge


class PhabricatorForge(Forge):
    def push(self, ref: str) -> None:
        """Push changes to Phabricator."""
        typer.echo(f"[TODO] Phabricator: Pushing {ref} to Phabricator")

    def pull(self, identifier: Optional[str] = None) -> None:
        """Pull diff from Phabricator."""
        typer.echo("[TODO] Phabricator: Pulling from Phabricator")
        if identifier:
            typer.echo(f"  Diff ID: {identifier}")

    def list(self) -> None:
        """List Phabricator diffs."""
        typer.echo("[TODO] Phabricator: Listing Phabricator diffs")
