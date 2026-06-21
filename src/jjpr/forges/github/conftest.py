import os
import random
import shutil
import string
from pathlib import Path
from typing import Generator

import httpx
import pytest

from ...conftest import run_cmd, tmp_cwd


@pytest.fixture(scope="class")
def url() -> httpx.URL:
    """Get the GitHub URL from the environment variable or use a default."""
    return httpx.URL(os.getenv("JJPR_TEST_GITHUB_URL", "https://github.com"))


@pytest.fixture(scope="class")
def api_url(url: httpx.URL) -> httpx.URL:
    """Get the GitHub API URL based on the GitHub URL."""
    if url.host == "github.com":
        return httpx.URL("https://api.github.com")
    else:
        # For GitHub Enterprise, API is at {url}/api/v3
        return url.join("/api/v3/")


@pytest.fixture(scope="class")
def session(
    api_url: httpx.URL,
) -> Generator[httpx.Client, None, None]:
    """Create and validate a GitHub API session."""
    token = os.getenv("JJPR_TEST_GITHUB_API_TOKEN")
    if not token:
        pytest.skip("JJPR_TEST_GITHUB_API_TOKEN not set, skipping tests")

    client = httpx.Client(
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            # "X-GitHub-Api-Version: 2026-03-10",
        }
    )

    try:
        # Check that the client works
        if not shutil.which("gh"):
            pytest.skip("`gh` command not found, skipping tests")
        try:
            response = client.get(api_url.join("user"))
            response.raise_for_status()
        except Exception as e:
            pytest.skip(f"GitHub server seems broken, skipping tests: {e}")
        yield client
    finally:
        client.close()


@pytest.fixture
def repo(
    url: httpx.URL,
    api_url: httpx.URL,
    session: httpx.Client,
) -> Generator[httpx.URL, None, None]:
    """Create and cleanup a test repository on GitHub."""
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-ghub-{rand}"

    # Get the current username from the API
    try:
        user_response = session.get(api_url.join("user"))
        user_response.raise_for_status()
        github_username = user_response.json()["login"]
    except Exception as e:
        pytest.skip(f"Failed to get GitHub username: {e}")

    try:
        response = session.post(
            api_url.join("user/repos"),
            json={
                "name": repo_name,
                "description": "Test repository for jj-pr integration tests",
                "private": True,
                "auto_init": True,
            },
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"GitHub repo creation error: {url}: {e}")

    # import time
    # time.sleep(60)
    try:
        yield url.join(f"{github_username}/{repo_name}")
    finally:
        response = session.delete(api_url.join(f"repos/{github_username}/{repo_name}"))
        response.raise_for_status()


@pytest.fixture
def clone(repo: httpx.URL) -> Generator[Path, None, None]:
    with tmp_cwd() as tmp_dir:
        run_cmd("jj", "git", "clone", str(repo), ".")
        yield tmp_dir
