import json
import logging
import sys
import typing as t
from pathlib import Path

import typer

from . import cmds, exc
from .forges import detect
from .utils import jj

app = typer.Typer(
    help="Unified CLI for multiple code review forges",
    add_completion=False,
)
log = logging.getLogger(__name__)

OutputFormat = t.Literal["table", "json"]


class GlobalOptions:
    def __init__(self, repo: cmds.Repo, format: OutputFormat) -> None:
        self.repo = repo
        self.format = format


@app.callback(invoke_without_command=False)
def main(
    ctx: typer.Context,
    path: Path | None = typer.Option(
        None,
        "--repo",
        help="Path to locally checked out repo",
    ),
    remote: str | None = typer.Option(
        None, "--remote", help="Which remote to work with"
    ),
    forge: detect.ForgeName | None = typer.Option(
        None, "--forge", help="Which forge backend to use"
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
        count=True,
    ),
    format: OutputFormat = typer.Option(
        "table",
        "--format",
        help="Output format (only works with some commands)",
    ),
) -> None:
    log_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    logging.basicConfig(level=log_level)
    # we can log our own HTTP I/O
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)

    if not path:
        try:
            path = Path(jj.root())
        except Exception as e:
            raise exc.UserError(f"Can't detect current repository: {e}")

    ctx.obj = GlobalOptions(cmds.Repo(path, remote, forge), format)


@app.command("push")
def push_command(
    ctx: typer.Context,
    ref: str | None = typer.Argument(None, help="Ref to push"),
    pre_commit: bool = typer.Option(
        True,
        "--pre-commit/--no-pre-commit",
        help="Run or skip pre-commit hooks",
    ),
    draft: bool = typer.Option(
        False,
        "--draft",
        help="Create as a draft/WIP",
    ),
    message: str | None = typer.Option(
        None,
        "-m",
        "--message",
        help="Commit/PR message",
    ),
) -> None:
    """Push current stack to the forge."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        if pre_commit:
            cmds.pre_commit_stack(ref)
        r.forge.push_cr(ref, draft=draft, message=message)


@app.command("pull")
def pull_command(
    ctx: typer.Context,
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Rebase all local branches; if not set, only rebase the current branch",
    ),
) -> None:
    """Pull from remote and rebase current stack."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        jj.git_fetch(remote=r.forge.remote)
        jj.rebase(d="trunk()", r="mutable()" if all else "trunk()..@")


@app.command("checkout")
def checkout_command(
    ctx: typer.Context,
    identifier: str = typer.Argument(None, help="PR/Diff/CR ID"),
) -> None:
    """Check out a PR/CR/Diff from the forge."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        r.forge.checkout_cr(identifier)


@app.command("list")
def list_command(
    ctx: typer.Context,
    all_projects: bool = typer.Option(
        False,
        "--all-projects",
        help="List reviews for all projects on the forge",
    ),
    extra_repos: list[str] = typer.Option(
        [], "--extra-repo", help="List reviews for this other repo at the same time"
    ),
) -> None:
    """List my open PRs/CRs/Diffs for the current project."""
    gos = t.cast(GlobalOptions, ctx.obj)
    rs = [gos.repo]

    for extra in extra_repos:
        path, remote, forge = (extra.split(":") + [None, None, None])[:3]
        assert path is not None
        if forge is not None:
            assert forge in t.get_args(detect.ForgeName)
            forge = t.cast(detect.ForgeName, forge)
        rs.append(cmds.Repo(Path(path), remote, forge))

    items = []
    for r in rs:
        with r.chdir():
            items.extend(r.forge.list_crs(all_projects))
    if gos.format == "json":
        print(json.dumps([item.as_dict() for item in items], indent=4))
    else:
        if items:
            cmds.display_list(items, multi=all_projects or len(rs) > 1)
        else:
            print("No items found.")


@app.command("pre-commit")
def pre_commit_command(
    ctx: typer.Context,
    ref: str | None = typer.Argument(None, help="Ref to check"),
) -> None:
    """Run pre-commit hooks."""
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        cmds.pre_commit_stack(ref)


@app.command("log")
def log_command(
    ctx: typer.Context,
) -> None:
    r = t.cast(GlobalOptions, ctx.obj).repo
    with r.chdir():
        print(r.forge.log(ctx.args))


def run() -> None:
    try:
        app()
    except exc.UserError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
