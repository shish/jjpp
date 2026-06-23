import subprocess

import httpx

from .. import exc
from . import exec


def get_remote_url(remote_name: str = "origin") -> httpx.URL:
    try:
        url = exec.run(["git", "config", "--get", f"remote.{remote_name}.url"])
        if "://" not in url:
            if url.startswith("/"):
                url = "file://" + url
            else:
                url = "ssh://" + url.replace(":", "/", 1)
        return httpx.URL(url)
    except Exception as e:
        raise exc.UserError(f"Failed to get git remote URL for '{remote_name}': {e}")


def get_merge_target(remote: str = "origin") -> str:
    """Find the default branch of the remote repository."""
    # Output format: ref: refs/heads/main	HEAD
    try:
        output = exec.run(["git", "ls-remote", "--symref", remote, "HEAD"])
        if output.startswith("ref:"):
            # Extract the branch name from "ref: refs/heads/main	HEAD"
            ref_path = output.split()[1]  # "refs/heads/main"
            if ref_path.startswith("refs/heads/"):
                return ref_path[len("refs/heads/") :]
        raise Exception(f"Could not parse git ls-remote output: {output}")
    except Exception as e:
        raise exc.UserError(f"Failed to find HEAD in remote {remote}: {e}")


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
