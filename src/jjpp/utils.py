import logging
import subprocess
from typing import Optional

log = logging.getLogger(__name__)


class UserError(Exception):
    """Exception raised for user errors (no stack trace)."""

    pass


def run(cmd: list[str], dry_run: bool = False) -> str:
    if dry_run:
        log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        return ""
    else:
        log.debug(f"Executing command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_git_remote_url(remote_name: str = "origin") -> Optional[str]:
    try:
        return run(["git", "config", "--get", f"remote.{remote_name}.url"])
    except Exception as e:
        log.debug(f"Failed to get git remote URL for '{remote_name}': {e}")
        return None


def get_merge_target(remote: str = "origin") -> str:
    # Output format: ref: refs/heads/main	HEAD
    output = run(["git", "ls-remote", "--symref", remote, "HEAD"])
    if output.startswith("ref:"):
        # Extract the branch name from "ref: refs/heads/main	HEAD"
        ref_path = output.split()[1]  # "refs/heads/main"
        if ref_path.startswith("refs/heads/"):
            return ref_path[len("refs/heads/") :]
    raise Exception("Could not parse git ls-remote output")  # pragma: no cover


def unique_branch_name(name: str) -> str:
    """Generate a unique branch name by appending a number if the branch already exists."""
    counter = 1
    unique_name = name
    while True:
        result = subprocess.run(["git", "show-ref", "--quiet", unique_name])
        if result.returncode != 0:
            break
        unique_name = f"{name}-{counter}"
        counter += 1
    return unique_name
