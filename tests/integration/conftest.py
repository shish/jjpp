import base64
import json
import os
import shutil
import tempfile
import urllib.parse
from netrc import netrc
from pathlib import Path
from typing import Generator

import pytest
import requests

from ..conftest import run_cmd


@pytest.fixture
def gerrit_url() -> str:
    """Get the Gerrit URL from the environment variable or use a default."""
    return os.getenv("GERRIT_URL", "http://gerrit.localhost:8080")


@pytest.fixture
def phabricator_url() -> str:
    """Get the Phabricator URL from the environment variable or use a default."""
    return os.getenv("PHABRICATOR_URL", "http://phab.localhost:8081")


@pytest.fixture
def tmp_home(gerrit_url: str, phabricator_url: str) -> Generator[Path, None, None]:
    """Create a temporary home directory for tests."""
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_home_")
    original_home = os.environ.get("HOME", "")
    os.environ["HOME"] = tmp_dir
    try:
        # configure .gitrc
        run_cmd("git", "config", "user.email", "test@example.com")
        run_cmd("git", "config", "user.name", "Test User")

        # configure .netrc
        gerrit_token = os.getenv("GERRIT_API_TOKEN")
        if gerrit_token:
            url = urllib.parse.urlparse(gerrit_url)
            rc = Path(tmp_dir) / ".netrc"
            rc.write_text(
                f"machine {url.hostname}\nlogin admin\npassword {gerrit_token}\n"
            )
            rc.chmod(0o600)

        # configure .arcrc
        phabricator_token = os.getenv("PHABRICATOR_API_TOKEN")
        if phabricator_token:
            rc = Path(tmp_dir) / ".arcrc"
            rc.write_text(
                json.dumps({"hosts": {phabricator_url: {"token": phabricator_token}}})
            )
            rc.chmod(0o600)

        yield Path(tmp_dir)
    finally:
        os.environ["HOME"] = original_home
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def tmp_gerrit_repo(
    tmp_home: Path,
    gerrit_url: str,
) -> Generator[Path, None, None]:
    gerrit_test_repo = "test-repo-g"

    if not (tmp_home / ".netrc").exists():
        pytest.skip("Didn't create .netrc (GERRIT_API_TOKEN env var not set?)")

    try:
        rc = netrc()
        parsed = urllib.parse.urlparse(gerrit_url)
        hostname = parsed.hostname or "fail"
        login, _, password = rc.authenticators(hostname) or (None, None, None)
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
    except Exception as e:
        pytest.skip(f"Failed to read credentials from .netrc: {e}")

    try:
        response = requests.get(f"{gerrit_url}/", headers=headers)
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit server error: {e}")

    try:
        response = requests.get(
            f"{gerrit_url}/a/projects/{gerrit_test_repo}", headers=headers
        )
        response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Gerrit repo error: {gerrit_url}: {e}")

    tmp_dir = tempfile.mkdtemp(prefix="jjpr_gerrit_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{gerrit_url}/{gerrit_test_repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def tmp_phabricator_repo(
    tmp_home: Path,
    phabricator_url: str,
) -> Generator[Path, None, None]:
    phabricator_test_repo = "test-repo-p"

    if not (tmp_home / ".arcrc").exists():
        pytest.skip("Didn't create .arcrc (PHABRICATOR_API_TOKEN env var not set?)")
    data = json.loads((tmp_home / ".arcrc").read_text())
    phabricator_token = data.get("hosts", {}).get(phabricator_url, {}).get("token")
    if not phabricator_token:
        pytest.skip("Failed to read token from generated .arcrc")

    try:
        response = requests.get(phabricator_url)
        response.raise_for_status()
        response = requests.post(f"{phabricator_url}/api/conduit.ping")
        response.raise_for_status()
        data = response.json()
        assert "result" in data or "error_code" in data
    except Exception as e:
        pytest.skip(f"Phabricator server error: {phabricator_url}: {e}")

    response = requests.post(
        f"{phabricator_url}/api/user.whoami",
        data={"api.token": phabricator_token},
    )
    try:
        response.raise_for_status()
        data = response.json()
        assert data["result"]["userName"] == "admin"
    except Exception as e:
        pytest.skip(f"Invalid Phabricator API token or unable to authenticate: {e}")

    tmp_dir = tempfile.mkdtemp(prefix="jjpr_phab_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{phabricator_url}/{phabricator_test_repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)
