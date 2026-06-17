import base64
import os
import random
import shutil
import string
import tempfile
import urllib.parse
from netrc import netrc
from pathlib import Path
from typing import Generator

import pytest
import requests

from ..conftest import run_cmd


@pytest.fixture(scope="session")
def gerrit_url() -> str:
    """Get the Gerrit URL from the environment variable or use a default."""
    return os.getenv("GERRIT_URL", "http://gerrit.localhost:8080")


@pytest.fixture(scope="session")
def gerrit_session(
    tmp_home: Path,
    gerrit_url: str,
) -> Generator[requests.Session, None, None]:
    # configure .netrc
    gerrit_token = os.getenv("GERRIT_API_TOKEN")
    if gerrit_token:
        url = urllib.parse.urlparse(gerrit_url)
        rc = Path(tmp_home) / ".netrc"
        rc.write_text(f"machine {url.hostname}\nlogin admin\npassword {gerrit_token}\n")
        rc.chmod(0o600)

    # configure http session with persistent auth headers
    session = requests.Session()
    try:
        rc = netrc()
        parsed = urllib.parse.urlparse(gerrit_url)
        hostname = parsed.hostname or "fail"
        login, _, password = rc.authenticators(hostname) or (None, None, None)
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        session.headers.update({"Authorization": f"Basic {credentials}"})
    except Exception as e:
        pytest.skip(f"Failed to read credentials from .netrc: {e}")

    # check that the session works
    try:
        response = session.get(f"{gerrit_url}/")
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit server error: {e}")

    yield session


@pytest.fixture
def gerrit_repo(
    gerrit_url: str,
    gerrit_session: requests.Session,
) -> Generator[str, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-gerr-{rand}"
    try:
        response = gerrit_session.put(
            f"{gerrit_url}/a/projects/{repo_name}",
            json={"create_empty_commit": True},
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit repo creation error: {gerrit_url}: {e}")

    yield repo_name

    try:
        response = gerrit_session.delete(f"{gerrit_url}/a/projects/{repo_name}")
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit repo deletion error: {gerrit_url}: {e}")


@pytest.fixture
def gerrit_clone(
    gerrit_url: str,
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
