import logging
import os
from typing import Optional

import typer

from . import jj
from .cli import GlobalOptions
from .utils import get_forge_or_die

app = typer.Typer(help="Unified CLI for multiple code review forges")
log = logging.getLogger(__name__)


@app.callback(invoke_without_command=False)
def main(
    ctx: typer.Context,
    forge: Optional[str] = typer.Option(
        None,
        "--forge",
        help="Specify the forge (auto-detects from git remote if not provided)",
    ),
    remote: str = typer.Option("origin", "--remote", help="Git remote to use"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    """Integrate JJ with multiple code review forges."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    try:
        jj_root = jj.run("root")
        os.chdir(jj_root)
    except jj.JjError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    ctx.obj = GlobalOptions(forge=forge, remote=remote)


@app.command()
def push(
    ctx: typer.Context,
    ref: Optional[str] = typer.Argument(None, help="Ref to push"),
    pre_commit: bool = typer.Option(
        True,
        "--pre-commit/--no-pre-commit",
        help="Run or skip pre-commit hooks",
    ),
) -> None:
    """Push changes to the forge."""
    opts: GlobalOptions = ctx.obj
    f = get_forge_or_die(opts)
    f.push(ref, pre_commit)


@app.command()
def pull(
    ctx: typer.Context,
    identifier: Optional[str] = typer.Argument(None, help="PR/Diff/CR ID"),
) -> None:
    """Pull changes from the forge."""
    opts: GlobalOptions = ctx.obj
    f = get_forge_or_die(opts)
    f.pull(identifier)


@app.command()
def list(
    ctx: typer.Context,
) -> None:
    """List items on the forge."""
    opts: GlobalOptions = ctx.obj
    f = get_forge_or_die(opts)
    f.list()


@app.command("pre-commit")
def pre_commit_command(
    ctx: typer.Context,
    ref: Optional[str] = typer.Argument(None, help="Ref to check"),
) -> None:
    """Run pre-commit hooks."""
    opts: GlobalOptions = ctx.obj
    f = get_forge_or_die(opts)
    changes = (
        [jj.revset_to_changeid(ref)]
        if ref
        else jj.current_stack(require_description=False)
    )
    for change_id in changes:
        f.pre_commit(change_id)


@app.command("sync")
def sync_command(ctx: typer.Context) -> None:
    """Pull from remote and rebase local branches"""
    opts: GlobalOptions = ctx.obj
    jj.run("git", "fetch", "--remote", opts.remote)
    jj.run("rebase", "--skip-emptied", "-d", "trunk()", "-r", "mutable()")


def run() -> None:
    """Entry point for the CLI application."""
    app()
