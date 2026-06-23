import logging
import typing as t

import httpx

from .. import exc
from ..utils import git
from .base import Forge
from .gerrit.forge import Gerrit
from .github.forge import GitHub
from .phabricator.forge import Phabricator

log = logging.getLogger(__name__)

ForgeName = t.Literal["github", "phabricator", "gerrit"]


def detect_forge_from_url(url: httpx.URL) -> ForgeName | None:
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


def get_forge(forge: ForgeName | None, remote: str) -> Forge:
    remote_url = git.get_remote_url(remote)

    # If forge is explicitly specified, use that
    if not forge:
        forge = detect_forge_from_url(remote_url)
    if forge == "github":
        return GitHub(remote)
    elif forge == "phabricator":
        return Phabricator(remote)
    elif forge == "gerrit":
        return Gerrit(remote)

    raise exc.UserError(
        f"Could not detect forge from remote URL: {remote_url}. "
        "Please specify --forge explicitly (github, phabricator, gerrit)."
    )
