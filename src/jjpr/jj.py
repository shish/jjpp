import logging
import shlex
import subprocess
from contextlib import contextmanager
from typing import Literal, overload

from . import utils

log = logging.getLogger(__name__)

# Type aliases
ChangeID = str
RevSet = str


class JjError(Exception):
    pass


@overload
def run(*args: str, cap: Literal[True]) -> str: ...


@overload
def run(*args: str, cap: Literal[False]) -> None: ...


@overload
def run(*args: str) -> str: ...


def run(*args: str, cap: bool = True) -> str | None:
    try:
        return utils.run(["jj"] + list(args), cap=cap)
    except subprocess.CalledProcessError as e:
        raise JjError(f"Failed to run {shlex.join(['jj'] + list(args))!r}") from e


#######################################################################
# Direct mappings to jj commands


def bookmark_advance(name: str, to: RevSet) -> None:
    run("bookmark", "advance", name, "--to", to, cap=False)


def bookmark_create(name: str, r: RevSet) -> None:
    run("bookmark", "create", name, "-r", r, cap=False)


def describe(r: ChangeID, m: str) -> None:
    run("describe", "-r", r, "-m", m)


def gerrit_upload(
    r: str,
    wip: bool = False,
    message: str | None = None,
    remote_branch: str | None = None,
) -> None:
    args = ["gerrit", "upload", "-r", r]
    if wip:
        args.append("--wip")
    if message:
        args.extend(["--message", message])
    if remote_branch:
        args.extend(["--remote-branch", remote_branch])
    run(*args, cap=False)


def git_fetch(remote: str) -> None:
    run("git", "fetch", "--remote", remote, cap=False)


def git_push(remote: str, bookmark: str) -> None:
    run("git", "push", "--remote", remote, "--bookmark", bookmark, cap=False)


def rebase(d: RevSet, r: RevSet) -> None:
    run("rebase", "--skip-emptied", "-d", d, "-r", r, cap=False)


def root() -> str:
    return run("root", cap=True)


#######################################################################
# Extra helpers


def change_ids(r: RevSet) -> list[ChangeID]:
    lines = run(
        "log",
        "-r",
        r,
        "--no-graph",
        "--reversed",
        "-T",
        'self.change_id().short() ++ "\\n"',
        cap=True,
    ).split("\n")
    return [line for line in lines if line]


def change_id(revset: RevSet) -> ChangeID:
    cs = change_ids(revset)
    if len(cs) != 1:
        raise ValueError(f"Revset {revset} did not resolve to a single change ID")
    return cs[0]


def closest_work() -> ChangeID:
    return change_id("heads(::@ & mutable() & (~empty() | merges()))")


def specified_or_stack(
    rev: RevSet | None,
    require_description: bool = False,
) -> list[ChangeID]:
    if rev:
        return [change_id(rev)]
    else:
        return current_stack(require_description=require_description)


def current_stack(require_description: bool = False) -> list[ChangeID]:
    if require_description:
        stack = 'trunk()..heads(::@ & mutable() & ~description(exact:"") & (~empty() | merges()))'
    else:
        stack = "trunk()..heads(::@ & mutable() & (~empty() | merges()))"
    return change_ids(stack)


def change_info(change_id: ChangeID, t: str) -> str:
    return run("log", "-r", change_id, "--no-graph", "-T", t)


def parents_of(change_id: ChangeID) -> list[ChangeID]:
    output = change_info(
        change_id, 'parents.map(|p| p.change_id().short()).join("\\n")'
    )
    return [p for p in output.split("\n") if p]


def files_in(change_id: ChangeID) -> list[str]:
    output = change_info(change_id, 'self.diff().files().map(|f| f.path()).join("\\n")')
    return [f for f in output.split("\n") if f]


def branches_pointing_to(change_id: ChangeID, prefix: str = "") -> list[str]:
    output = change_info(change_id, 'self.bookmarks().map(|b| b.name()).join("\\n")')
    return [b for b in output.split("\n") if b and b.startswith(prefix)]


def description_of(change_id: ChangeID) -> str:
    output = change_info(change_id, "self.description()")
    return output.strip()


@contextmanager
def with_edit(rev: RevSet, new: bool = False):
    """Context manager to temporarily switch to a change and reset on exit.

    If the target ref is already the current commit, does nothing.
    If the current change is empty, creates a new empty commit with the same parent.
    """
    orig_change_id = change_id("@")
    orig_parents = parents_of(orig_change_id)
    targ_change_id = change_id(rev)

    if not new and orig_change_id == targ_change_id:
        log.debug(f"Already on target change {targ_change_id}, no edit needed.")
        yield
        return

    is_empty = files_in(orig_change_id) == []
    try:
        co = "child of " if new else ""
        log.debug(f"Switching from {orig_change_id} to {co}{targ_change_id}.")
        run("new" if new else "edit", targ_change_id)
        yield
    finally:
        if is_empty:
            log.debug(f"Resetting to empty change with parents {orig_parents}.")
            run("new", *orig_parents)
        else:
            log.debug(f"Resetting back to original change {orig_change_id}.")
            run("edit", orig_change_id)


@contextmanager
def with_new(rev: RevSet):
    with with_edit(rev, new=True):
        yield
