import logging
import subprocess
from typing import Literal, Optional, overload

log = logging.getLogger(__name__)


class UserError(Exception):
    """Exception raised for user errors (no stack trace)."""

    pass


@overload
def run(cmd: list[str], cap: Literal[True]) -> str: ...


@overload
def run(cmd: list[str], cap: Literal[False]) -> None: ...


@overload
def run(cmd: list[str]) -> str: ...


def run(cmd: list[str], cap: bool = True) -> str | None:
    log.debug(f"Executing command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=cap,
            text=True,
            check=True,
        )
        if cap:
            log.debug(f"Command output: {result.stdout.strip()}")
            return result.stdout.strip()
        else:
            return None
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: {' '.join(cmd)}")
        log.error(f"Return code: {e.returncode}")
        log.error(f"stdout: {e.stdout}")
        log.error(f"stderr: {e.stderr}")
        raise


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
