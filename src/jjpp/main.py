import logging
import os
import shlex
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import jj, utils
from .forges import get_forge
from .forges.base import CRListItem

app = typer.Typer(help="Unified CLI for multiple code review forges")
log = logging.getLogger(__name__)


class Repo:
    def __init__(self, spec: str):
        # spec = /path/to/repo:remote:forge where remote and forge are optional
        parts = spec.split(":")
        self.path = Path(parts[0]).resolve()
        remote = parts[1] if len(parts) > 1 else "origin"
        forge_type = parts[2] if len(parts) > 2 else None
        forge = get_forge(forge_type, remote)
        if forge is None:
            log.error(
                f"Could not determine forge for remote '{remote}' in repo '{self.path}'"
            )
            raise typer.Exit(code=1)
        self.forge = forge

    @contextmanager
    def with_chdir(self):
        """Context manager to temporarily change the working directory."""
        original_dir = Path.cwd()
        try:
            os.chdir(self.path)
            yield
        finally:
            os.chdir(original_dir)


class GlobalOptions:
    def __init__(self, repos: list[Repo]) -> None:
        self.repos = repos

    @property
    def repo(self) -> Repo:
        if len(self.repos) == 1:
            return self.repos[0]
        elif len(self.repos) == 0:
            raise utils.UserError("No repositories specified.")
        else:
            raise utils.UserError("Too many repositories specified.")


@app.callback(invoke_without_command=False)
def main(
    ctx: typer.Context,
    repos: list[str] = typer.Option([], "--repo"),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
        count=True,
    ),
) -> None:
    """Integrate JJ with multiple code review forges."""
    log_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    logging.basicConfig(level=log_level)

    repo_objs = [Repo(spec) for spec in repos] or [Repo(jj.run("root"))]

    ctx.obj = GlobalOptions(repo_objs)


@app.command("push")
def push_command(
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
    r = opts.repo
    with r.with_chdir():
        if pre_commit:
            _pre_commit_stack(ref)
        r.forge.push(ref)


@app.command("checkout")
def checkout_command(
    ctx: typer.Context,
    identifier: str = typer.Argument(None, help="PR/Diff/CR ID"),
) -> None:
    """Checkout changes from the forge."""
    opts: GlobalOptions = ctx.obj
    r = opts.repo
    with r.with_chdir():
        r.forge.checkout(identifier)


def _display_list(items: List[CRListItem]) -> None:
    """Display a list of code review items in a formatted table."""
    console = Console()

    all_extra_keys = set()
    for item in items:
        all_extra_keys.update(item.extra.keys())

    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    for key in sorted(all_extra_keys):
        table.add_column(key.title(), style="yellow")

    for item in items:
        table.add_row(
            item.identifier,
            f"[link={item.url}]{item.title}[/link]",
            *[
                item.extra[key] if key in item.extra else ""
                for key in sorted(all_extra_keys)
            ],
        )

    console.print(table)


@app.command("list")
def list_command(
    ctx: typer.Context,
) -> None:
    """List items on the forge."""
    opts: GlobalOptions = ctx.obj
    r = opts.repo
    with r.with_chdir():
        items = r.forge.list()
        if items:
            _display_list(items)
        else:
            print("No items found.")


def _pre_commit_stack(ref: Optional[str]) -> None:
    """Run pre-commit hooks on a stack of changes."""
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


@app.command("pre-commit")
def pre_commit_command(
    ctx: typer.Context,
    ref: Optional[str] = typer.Argument(None, help="Ref to check"),
) -> None:
    """Run pre-commit hooks."""
    opts: GlobalOptions = ctx.obj
    r = opts.repo
    with r.with_chdir():
        _pre_commit_stack(ref)


@app.command("pull")
def pull_command(
    ctx: typer.Context,
    all: bool = typer.Option(
        False,
        "--all",
        help="Rebase all local branches; if not set, only rebase the current branch",
    ),
) -> None:
    """Pull from remote and rebase local branches"""
    opts: GlobalOptions = ctx.obj
    r = opts.repo
    with r.with_chdir():
        jj.run("git", "fetch", "--remote", r.forge.remote)
        if all:
            range = "mutable()"
        else:
            range = "trunk()..@"
        jj.run("rebase", "--skip-emptied", "-d", "trunk()", "-r", range)


def run() -> None:
    """Entry point for the CLI application."""
    try:
        app()
    except utils.UserError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
