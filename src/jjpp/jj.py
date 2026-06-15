import logging
from contextlib import contextmanager

from . import utils

log = logging.getLogger(__name__)

# Type aliases
ChangeID = str
RevSet = str


class JjError(Exception):
    pass


def run(*args: str, dry_run: bool = False) -> str:
    """Run a jj command and return stdout.

    Args:
        *args: Arguments to pass to jj command.
        dry_run: If True, log the command without executing it.

    Returns:
        The stdout output of the jj command, or empty string if dry_run=True.

    Raises:
        JjError: If the jj command fails or is not found.
    """
    try:
        return utils.run(["jj"] + list(args), dry_run=dry_run)
    except Exception as e:
        if isinstance(e, JjError):
            raise
        raise JjError(f"jj command failed: {' '.join(args)}") from e


def revset_to_changeid(revset: RevSet) -> ChangeID:
    return run("log", "-r", revset, "--no-graph", "-T", "self.change_id().short()")


def closest_work() -> ChangeID:
    return revset_to_changeid("heads(::@ & mutable() & (~empty() | merges()))")


def current_stack(require_description: bool = False) -> list[ChangeID]:
    if require_description:
        stack = 'trunk()..heads(::@ & mutable() & ~description(exact:"") & (~empty() | merges()))'
    else:
        stack = "trunk()..heads(::@ & mutable() & (~empty() | merges()))"
    output = run(
        "log",
        "-r",
        stack,
        "--no-graph",
        "--reversed",
        "-T",
        'self.change_id().short() ++ "\n"',
    )
    return [c for c in output.split("\n") if c]


def change_parents(change_id: ChangeID) -> list[ChangeID]:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "parents.map(|p| p.change_id().short()).join('\\n')",
    )
    return [p for p in output.split("\n") if p]


def files_in(change_id: ChangeID) -> list[str]:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "self.diff().files().map(|f| f.path()).join('\n')",
    )
    return [f for f in output.split("\n") if f]


def branches_pointing_to(change_id: ChangeID, prefix: str = "") -> list[str]:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "self.bookmarks().map(|b| b.name()).join('\n')",
    )
    return [b for b in output.split("\n") if b and b.startswith(prefix)]


def description_of(change_id: ChangeID) -> str:
    output = run(
        "log",
        "-r",
        change_id,
        "--no-graph",
        "-T",
        "self.description()",
    )
    return output.strip()


@contextmanager
def with_edit(rev: RevSet, new: bool = False):
    """Context manager to temporarily switch to a change and reset on exit.

    If the target ref is already the current commit, does nothing.
    If the current change is empty, creates a new empty commit with the same parent.
    """
    original_change_id = revset_to_changeid("@")
    original_parents = change_parents(original_change_id)
    target_change_id = revset_to_changeid(rev)

    if original_change_id == target_change_id:
        log.debug(f"Already on target change {target_change_id}, no edit needed.")
        yield
        return

    is_empty = files_in(original_change_id) == []
    try:
        log.debug(f"Switching from change {original_change_id} to {target_change_id}.")
        run("new" if new else "edit", target_change_id)
        yield
    finally:
        if is_empty:
            log.debug(f"Creating new empty change with parents {original_parents}.")
            run("new", *original_parents)
        else:
            log.debug(f"Resetting back to original change {original_change_id}.")
            run("edit", original_change_id)


@contextmanager
def with_new(rev: RevSet):
    yield with_edit(rev, new=True)
