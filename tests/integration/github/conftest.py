import os
import random
import shutil
import string
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import requests

from ..conftest import run_cmd


@pytest.fixture(scope="session")
def github_url() -> str:
    """Get the GitHub URL from the environment variable or use a default."""
    return os.getenv("GITHUB_URL", "https://github.com")


@pytest.fixture(scope="session")
def github_session(
    github_url: str,
) -> Generator[requests.Session, None, None]:
    """Create and validate a GitHub API session."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN environment variable not set")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            # "X-GitHub-Api-Version: 2026-03-10",
        }
    )

    # Determine the API URL based on GitHub URL
    if github_url == "https://github.com":
        api_url = "https://api.github.com"
    else:
        # For GitHub Enterprise, API is at {github_url}/api/v3
        api_url = f"{github_url}/api/v3"

    # Check that the session works
    try:
        response = session.get(f"{api_url}/user")
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"GitHub API error or invalid token: {e}")

    yield session


@pytest.fixture
def github_repo(
    github_url: str,
    github_session: requests.Session,
) -> Generator[str, None, None]:
    """Create and cleanup a test repository on GitHub."""
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-ghub-{rand}"

    # Determine the API URL based on GitHub URL
    if github_url == "https://github.com":
        api_url = "https://api.github.com"
    else:
        api_url = f"{github_url}/api/v3"

    # Get the current username from the API
    try:
        user_response = github_session.get(f"{api_url}/user")
        user_response.raise_for_status()
        github_username = user_response.json()["login"]
    except Exception as e:
        pytest.skip(f"Failed to get GitHub username: {e}")

    try:
        response = github_session.post(
            f"{api_url}/user/repos",
            json={
                "name": repo_name,
                "description": "Test repository for jj-pr integration tests",
                "private": True,
                "auto_init": True,
            },
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"GitHub repo creation error: {github_url}: {e}")

    # import time
    # time.sleep(60)
    yield f"{github_username}/{repo_name}"

    try:
        response = github_session.delete(
            f"{api_url}/repos/{github_username}/{repo_name}"
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"GitHub repo deletion error: {github_url}: {e}")


@pytest.fixture
def github_clone(
    github_url: str,
    github_repo: str,
) -> Generator[Path, None, None]:
    """Clone a test GitHub repository and initialize it with jj."""
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_ghub_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{github_url}/{github_repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)
