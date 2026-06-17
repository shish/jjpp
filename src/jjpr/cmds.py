import logging
import os
import shlex
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from . import forges, jj, utils
from .forges.base import CRListItem

log = logging.getLogger(__name__)


class Repo:
    def __init__(
        self, path: Path, remote: Optional[str], forge_type: Optional[forges.ForgeName]
    ):
        # spec = /path/to/repo:remote:forge where remote and forge are optional
        # eg ~/Projects/jjpp:origin
        self.path = path.resolve()
        with self.chdir():
            default_remote = utils.run(["git", "remote"]).splitlines()[0]
            forge = forges.get_forge(forge_type, remote or default_remote)
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


def pre_commit(ref: Optional[str]) -> None:
    """Run pre-commit hooks on a stack of changes."""
    if not Path(".git/hooks/pre-commit").exists():
        log.info("No .git/hooks/pre-commit found, skipping pre-commit hooks")
        return

    pc_apps = ["prek", "pre-commit"]
    pc_cmd = None
    for cmd in pc_apps:
        if shutil.which(cmd):
            pc_cmd = cmd
            break
    if not pc_cmd:
        log.info(f"No pre-commit app found ({', '.join(pc_apps)}), skipping pre-commit")
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
                utils.run([pc_cmd, "run", "--files", *files], cap=False)
            except FileNotFoundError:
                raise
            except Exception:
                raise utils.UserError(f"Pre-commit failed for change {change_id}")


def display_list(items: List[CRListItem], multi: bool) -> None:
    """Display a list of code review items in a formatted table."""
    console = Console()

    all_forge_urls = set(item.forge_url for item in items)
    all_extra_keys = set()
    for item in items:
        all_extra_keys.update(item.extra.keys())

    table = Table()
    if len(all_forge_urls) > 1:
        table.add_column("Forge", style="green")
    if multi:
        table.add_column("Project", style="blue")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    for key in sorted(all_extra_keys):
        table.add_column(key.title(), style="yellow")

    for item in items:
        row = []
        if len(all_forge_urls) > 1:
            row.append(f"[link={item.forge_url}]{item.forge_name}[/link]")
        if multi:
            row.append(item.project_id)
        row.append(item.identifier)
        row.append(f"[link={item.url}]{item.title}[/link]")
        table.add_row(
            *row,
            *[
                item.extra[key] if key in item.extra else ""
                for key in sorted(all_extra_keys)
            ],
        )

    console.print(table)
