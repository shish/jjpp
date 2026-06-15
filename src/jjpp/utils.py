import logging
import subprocess
from typing import Optional
from urllib.parse import urlparse

import typer

from .cli import GlobalOptions
from .forges import Forge, GerritForge, GitHubForge, PhabricatorForge

log = logging.getLogger(__name__)


def run(cmd: list[str], dry_run: bool = False) -> str:
    """Run a command and return stdout.

    Args:
        cmd: List of command arguments to execute.
        dry_run: If True, log the command without executing it.

    Returns:
        The stdout output of the command, or empty string if dry_run=True.

    Raises:
        subprocess.CalledProcessError: If the command fails.
        FileNotFoundError: If the command is not found.
    """
    if dry_run:
        log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        return ""
    else:
        log.debug(f"Executing command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise e
    except FileNotFoundError as e:
        raise e


def get_merge_target(remote: str = "origin") -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", remote, "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output format: ref: refs/heads/main	HEAD
        output = result.stdout.strip()
        if output.startswith("ref:"):
            # Extract the branch name from "ref: refs/heads/main	HEAD"
            ref_path = output.split()[1]  # "refs/heads/main"
            if ref_path.startswith("refs/heads/"):
                return ref_path[len("refs/heads/") :]
        raise Exception("Could not parse git ls-remote output")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to get merge target: {e}")
    except (FileNotFoundError, IndexError) as e:
        raise Exception(f"Error getting merge target: {e}")


def get_git_remote_url(remote_name: str = "origin") -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "config", "--get", f"remote.{remote_name}.url"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def detect_forge_from_url(url: str) -> Optional[str]:
    if not url:
        return None

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove 'www.' prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    if "github.com" in domain:
        return "github"
    elif "phabricator" in domain:
        return "phabricator"
    elif "gerrit" in domain:
        return "gerrit"

    return None


def get_forge(forge: Optional[str], remote: str) -> Optional[Forge]:
    # If forge is explicitly specified, use that
    if forge:
        remote_url = get_git_remote_url(remote)
        if not remote_url:
            typer.echo(f"Error: Could not find git remote '{remote}'", err=True)
            return None

        if forge == "github":
            return GitHubForge(remote, remote_url)
        elif forge == "phabricator":
            return PhabricatorForge(remote, remote_url)
        elif forge == "gerrit":
            return GerritForge(remote, remote_url)

    # Auto-detect from remote URL
    remote_url = get_git_remote_url(remote)
    if not remote_url:
        typer.echo(
            f"Error: Could not find git remote '{remote}'. "
            "Please specify --forge explicitly.",
            err=True,
        )
        return None

    detected_forge = detect_forge_from_url(remote_url)
    if not detected_forge:
        typer.echo(
            f"Error: Could not detect forge from remote URL: {remote_url}. "
            "Please specify --forge explicitly (github, phabricator, gerrit).",
            err=True,
        )
        return None

    if detected_forge == "github":
        return GitHubForge(remote, remote_url)
    elif detected_forge == "phabricator":
        return PhabricatorForge(remote, remote_url)
    elif detected_forge == "gerrit":
        return GerritForge(remote, remote_url)

    return None


def get_forge_or_die(opts: GlobalOptions) -> Forge:
    forge = get_forge(opts.forge, opts.remote)
    if forge is None:
        raise typer.Exit(code=1)
    return forge


def hyperlink(url: str, text: Optional[str] = None) -> str:
    """Return a string that will be rendered as a hyperlink in supported terminals."""
    if text is None:
        text = url
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


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
