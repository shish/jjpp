import logging
import os
import shlex
import shutil
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import exc
from .forges import cr, detect
from .utils import exec, jj

log = logging.getLogger(__name__)


class Repo:
    def __init__(
        self,
        path: Path,
        remote: str | None,
    ):
        self.path = path.resolve()
        with self.chdir():
            default_remote = exec.run(["git", "remote"]).splitlines()[0]
            forge = detect.get_forge(remote or default_remote)
        self.remote = forge

    @contextmanager
    def chdir(self):
        """Context manager to temporarily change the working directory
        to the root of the checked-out repository."""
        original_dir = Path.cwd()
        try:
            os.chdir(self.path)
            yield
        finally:
            os.chdir(original_dir)


def _get_pc_command() -> str | None:
    pch = Path(".git/hooks/pre-commit")
    if pch.exists():
        return str(pch)
    return None


def _get_arc_command() -> str | None:
    arc_configured = Path(".arclint").exists()
    if not arc_configured:
        return None

    arc_bin = shutil.which("arc")
    if arc_configured and not arc_bin:
        log.info(".arclint found, but no arc binary")

    return arc_bin


def pre_commit_stack(ref: str | None) -> None:
    """Run pre-commit hooks on a stack of changes."""
    pc_cmd = _get_pc_command()
    arc_cmd = _get_arc_command()
    if not pc_cmd and not arc_cmd:
        log.info("No pre-commit configuration found, skipping")
        return

    changes = jj.change_ids(ref) if ref else jj.checkable_stack()
    for n, change_id in enumerate(changes):
        if n > 0:
            print("=" * 80)
        pre_commit_change(change_id, pc_cmd, arc_cmd)


def pre_commit_change(change_id: str, pc_cmd: str | None, arc_cmd: str | None) -> None:
    with jj.with_edit(change_id):
        files = jj.files_in(change_id)
        files = [f for f in files if Path(f).exists()]
        descr = (jj.description_of(change_id).splitlines() or ["(untitled)"])[0]
        print(f'Checking "{descr}" ({change_id})')
        print(f"Affected files: {shlex.join(files)}")
        try:
            if arc_cmd:
                exec.run([arc_cmd, "lint", "--apply-patches"], cap=False)
            exec.run(["git", "add", "--all"], cap=False)
            if pc_cmd:
                exec.run([pc_cmd], cap=False)
        except Exception:
            raise exc.UserError(f"pre-commit checks failed for change {change_id}")


def display_list(items: list[cr.CodeReview], multi: bool) -> None:
    """Display a list of code review items in a formatted table."""
    console = Console()

    all_forge_urls = set(item.forge.forge_url for item in items)
    all_extra_keys = set()
    for item in items:
        all_extra_keys.update(item.extra.keys())

    table = Table()
    if len(all_forge_urls) > 1:
        table.add_column("Forge", style="blue")
    if multi:
        table.add_column("Project", style="blue")
    table.add_column("ID", style="blue")
    table.add_column("Title", style="green")
    table.add_column("State")
    table.add_column("Blockers")
    for key in sorted(all_extra_keys):
        table.add_column(key.title(), style="magenta")

    for item in items:
        row = []
        if len(all_forge_urls) > 1:
            row.append(item.forge)
        if multi:
            row.append(item.forge.project_id)
        row.append(item.cr_id)
        row.append(item.title)
        row.append(item.state)
        row.append(", ".join(b.__rich__() for b in item.blockers))
        table.add_row(
            *row,
            *[item.extra.get(key, "") for key in sorted(all_extra_keys)],
        )

    console.print(table)
