import json
import os
import random
import shutil
import string
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import requests

from jjpr.forges.phabricator import PhabricatorSession

from ..conftest import run_cmd


@pytest.fixture(scope="session")
def phabricator_url() -> str:
    """Get the Phabricator URL from the environment variable or use a default."""
    return os.getenv("PHABRICATOR_URL", "http://phab.localhost:8081")


@pytest.fixture(scope="session")
def phabricator_session(
    tmp_home: Path,
    phabricator_url: str,
) -> Generator[requests.Session, None, None]:
    # configure .arcrc
    phabricator_token = os.getenv("PHABRICATOR_API_TOKEN")
    if not phabricator_token:
        pytest.skip("PHABRICATOR_API_TOKEN environment variable not set")
    data = {"hosts": {phabricator_url: {"token": phabricator_token}}}
    rc = Path(tmp_home) / ".arcrc"
    rc.write_text(json.dumps(data))
    rc.chmod(0o600)

    # configure http session with persistent token
    session = PhabricatorSession(phabricator_token)

    # check that the session works
    try:
        response = session.post(f"{phabricator_url}/api/user.whoami")
        response.raise_for_status()
        data = response.json()
        assert data["result"]["userName"] == "admin"
    except Exception as e:
        pytest.skip(f"Invalid Phabricator API token or unable to authenticate: {e}")

    yield session


@pytest.fixture
def phabricator_repo(
    phabricator_url: str,
    phabricator_session: requests.Session,
) -> Generator[str, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-phab-{rand}"
    try:
        response = phabricator_session.post(
            f"{phabricator_url}/api/diffusion.repository.edit",
            data={
                "transactions": [
                    {"type": "name", "value": repo_name},
                    {"type": "vcs", "value": "git"},
                    {"type": "callsign", "value": f"ZTST{rand.upper()}"},
                    {"type": "status", "value": "active"},
                    {"type": "shortName", "value": repo_name},
                ]
            },
        )
        response.raise_for_status()
        result = response.json()
        if result.get("error_code"):
            raise Exception(
                f"Phabricator API error: {result['error_code']} - {result.get('error_info')}"
            )
    except Exception as e:
        pytest.skip(f"Phabricator repo creation error: {phabricator_url}: {e}")

    yield repo_name

    try:
        response = phabricator_session.post(
            f"{phabricator_url}/api/diffusion.repository.search",
            data={"constraints": {"shortNames": [repo_name]}},
        )
        response.raise_for_status()
        result = response.json()
        if result.get("error_code"):
            raise Exception(
                f"Phabricator API error: {result['error_code']} - {result.get('error_info')}"
            )

        repos = result.get("result", {}).get("data", [])
        if repos:
            repo_phid = repos[0]["phid"]
            response = phabricator_session.post(
                f"{phabricator_url}/api/diffusion.repository.edit",
                data={
                    "objectIdentifier": repo_phid,
                    "transactions": [{"type": "status", "value": "inactive"}],
                },
            )
            response.raise_for_status()
    except Exception as e:
        pytest.skip(f"Phabricator repo deletion error: {phabricator_url}: {e}")


@pytest.fixture
def phabricator_clone(
    phabricator_url: str,
    phabricator_repo: str,
) -> Generator[Path, None, None]:
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_phab_")
    original_dir = os.getcwd()

    try:
        os.chdir(tmp_dir)
        run_cmd("git", "clone", f"{phabricator_url}/{phabricator_repo}.git", ".")
        run_cmd("jj", "git", "init", ".")
        data = {
            "phabricator.uri": phabricator_url,
            "repository.callsign": f"ZTST{phabricator_repo[-4:].upper()}",
        }
        Path(".arcconfig").write_text(json.dumps(data))
        run_cmd("jj", "commit", "-m", "Initial commit with .arcconfig")
        yield Path(tmp_dir)
    finally:
        os.chdir(original_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)
