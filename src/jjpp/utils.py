import subprocess
from typing import Optional
from urllib.parse import urlparse

import typer

from .cli import GlobalOptions
from .forges import Forge, GerritForge, GitHubForge, PhabricatorForge


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
            return GitHubForge(remote_url)
        elif forge == "phabricator":
            return PhabricatorForge(remote_url)
        elif forge == "gerrit":
            return GerritForge(remote_url)

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
        return GitHubForge(remote_url)
    elif detected_forge == "phabricator":
        return PhabricatorForge(remote_url)
    elif detected_forge == "gerrit":
        return GerritForge(remote_url)

    return None


def get_forge_or_die(opts: GlobalOptions) -> Forge:
    forge = get_forge(opts.forge, opts.remote)
    if forge is None:
        raise typer.Exit(code=1)
    return forge
