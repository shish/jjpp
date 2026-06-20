import os
import random
import shutil
import string
import tempfile
from pathlib import Path
from typing import Generator

import httpx
import pytest

from jjpr.forges.gerrit import GerritClient

from ...conftest import run_cmd


@pytest.fixture(scope="session")
def url() -> httpx.URL:
    """Get the Gerrit URL from the environment variable or use a default."""
    return httpx.URL(os.getenv("JJPR_TEST_GERRIT_URL", "http://gerrit.localhost:8080"))


@pytest.fixture(scope="session")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> Generator[GerritClient, None, None]:
    # configure .netrc
    gerrit_token = os.getenv("JJPR_TEST_GERRIT_API_TOKEN")
    if gerrit_token:
        rc = Path(tmp_home) / ".netrc"
        rc.write_text(f"machine {url.host}\nlogin admin\npassword {gerrit_token}\n")
        rc.chmod(0o600)

    client = GerritClient(url)

    # check that the client works
    try:
        client.get(url)
    except Exception as e:
        pytest.skip(f"Gerrit server error: {e}")

    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def repo(
    url: httpx.URL,
    session: GerritClient,
) -> Generator[str, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-gerr-{rand}"
    try:
        session.put(
            url.join(f"/a/projects/{repo_name}"),
            json={"create_empty_commit": True},
        )
    except Exception as e:
        pytest.skip(f"Gerrit repo creation error: {url}: {e}")

    try:
        yield repo_name
    finally:
        session.delete(url.join(f"/a/projects/{repo_name}"))


@pytest.fixture
def clone(
    url: httpx.URL,
    repo: str,
) -> Generator[Path, None, None]:
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_gerrit_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{url}/{repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)
