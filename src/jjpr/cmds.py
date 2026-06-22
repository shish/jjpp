import logging
import os
import shlex
import shutil
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import exc
from .forges import detect
from .forges.base import CRListItem
from .utils import exec, jj

log = logging.getLogger(__name__)


class Repo:
    def __init__(
        self,
        path: Path,
        remote: str | None,
        forge_type: detect.ForgeName | None,
    ):
        # spec = /path/to/repo:remote:forge where remote and forge are optional
        # eg ~/Projects/jjpp:origin
        self.path = path.resolve()
        with self.chdir():
            default_remote = exec.run(["git", "remote"]).splitlines()[0]
            forge = detect.get_forge(forge_type, remote or default_remote)
        self.forge = forge

    @contextmanager
    def chdir(self):
        """Context manager to temporarily change the working directory."""
        original_dir = Path.cwd()
        try:
            os.chdir(self.path)
            yield
        finally:
            os.chdir(original_dir)


def _get_pc_command() -> str | None:
    pc_configured = Path(".git/hooks/pre-commit").exists()
    if not pc_configured:
        return None

    pc_cmd = None
    for cmd in ["prek", "pre-commit"]:
        if pc_cmd := shutil.which(cmd):
            break
    if pc_configured and not pc_cmd:
        log.info("pre-commit hook found, but no pre-commit or prek binary")

    return pc_cmd


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
            if pc_cmd:
                exec.run([pc_cmd, "run", "--files", *files], cap=False)
            if arc_cmd:
                exec.run([arc_cmd, "lint", "--apply-patches"], cap=False)
        except Exception:
            raise exc.UserError(f"pre-commit checks failed for change {change_id}")


def display_list(items: list[CRListItem], multi: bool) -> None:
    """Display a list of code review items in a formatted table."""
    console = Console()

    all_forge_urls = set(item.forge_url for item in items)
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
            row.append(f"[link={item.forge_url}]{item.forge_name}[/link]")
        if multi:
            row.append(item.project_id)
        row.append(item.identifier)
        row.append(f"[link={item.url}]{item.title}[/link]")
        row.append(item.state)
        row.append(item.blockers)
        table.add_row(
            *row,
            *[
                item.extra[key] if key in item.extra else ""
                for key in sorted(all_extra_keys)
            ],
        )

    console.print(table)
