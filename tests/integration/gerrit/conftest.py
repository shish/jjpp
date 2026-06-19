import base64
import os
import random
import shutil
import string
import tempfile
from netrc import netrc
from pathlib import Path
from typing import Generator

import httpx
import pytest

from ...conftest import run_cmd


@pytest.fixture(scope="session")
def gerrit_url() -> httpx.URL:
    """Get the Gerrit URL from the environment variable or use a default."""
    return httpx.URL(os.getenv("GERRIT_URL", "http://gerrit.localhost:8080"))


@pytest.fixture(scope="session")
def gerrit_session(
    tmp_home: Path,
    gerrit_url: httpx.URL,
) -> Generator[httpx.Client, None, None]:
    # configure .netrc
    gerrit_token = os.getenv("GERRIT_API_TOKEN")
    if gerrit_token:
        rc = Path(tmp_home) / ".netrc"
        rc.write_text(
            f"machine {gerrit_url.host}\nlogin admin\npassword {gerrit_token}\n"
        )
        rc.chmod(0o600)

    # configure http client with persistent auth headers
    headers = {}
    try:
        rc = netrc()
        hostname = gerrit_url.host or "fail"
        login, _, password = rc.authenticators(hostname) or (None, None, None)
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        headers.update({"Authorization": f"Basic {credentials}"})
    except Exception as e:
        pytest.skip(f"Failed to read credentials from .netrc: {e}")

    client = httpx.Client(headers=headers)

    # check that the client works
    try:
        response = client.get(gerrit_url)
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit server error: {e}")

    yield client
    client.close()


@pytest.fixture
def gerrit_repo(
    gerrit_url: httpx.URL,
    gerrit_session: httpx.Client,
) -> Generator[str, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-gerr-{rand}"
    try:
        response = gerrit_session.put(
            gerrit_url.join(f"/a/projects/{repo_name}"),
            json={"create_empty_commit": True},
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit repo creation error: {gerrit_url}: {e}")

    yield repo_name

    try:
        response = gerrit_session.delete(gerrit_url.join(f"/a/projects/{repo_name}"))
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit repo deletion error: {gerrit_url}: {e}")


@pytest.fixture
def gerrit_clone(
    gerrit_url: httpx.URL,
    gerrit_repo: str,
) -> Generator[Path, None, None]:
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_gerrit_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{gerrit_url}/{gerrit_repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)
