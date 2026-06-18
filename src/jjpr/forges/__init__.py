import logging
from typing import Literal, Optional

import httpx

from .. import utils
from .base import Forge
from .gerrit import Gerrit
from .github import GitHub
from .phabricator import Phabricator

log = logging.getLogger(__name__)

ForgeName = Literal["github", "phabricator", "gerrit"]


def detect_forge_from_url(url: httpx.URL) -> Optional[ForgeName]:
    if not url:
        return None

    domain = url.host.lower() if url.host else ""

    # Remove 'www.' prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    if "github.com" in domain:
        return "github"
    elif "phab" in domain:
        return "phabricator"
    elif "gerrit" in domain:
        return "gerrit"

    return None


def get_forge(forge: Optional[ForgeName], remote: str) -> Forge:
    remote_url = utils.get_git_remote_url(remote)

    # If forge is explicitly specified, use that
    if not forge:
        forge = detect_forge_from_url(remote_url)
    if forge == "github":
        return GitHub(remote, remote_url)
    elif forge == "phabricator":
        return Phabricator(remote, remote_url)
    elif forge == "gerrit":
        return Gerrit(remote, remote_url)

    raise utils.UserError(
        f"Could not detect forge from remote URL: {remote_url}. "
        "Please specify --forge explicitly (github, phabricator, gerrit)."
    )


__all__ = [
    "Forge",
    "GitHub",
    "Phabricator",
    "Gerrit",
    "get_forge",
]
