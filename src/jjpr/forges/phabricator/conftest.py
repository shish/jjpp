import json
import os
import random
import shutil
import string
from pathlib import Path
from typing import Generator

import httpx
import pytest
import tenacity as tc

from ...conftest import run_cmd, tmp_cwd
from .client import PhabricatorClient


@pytest.fixture(scope="session")
def url() -> httpx.URL:
    """Get the Phabricator URL from the environment variable or use a default."""
    return httpx.URL(
        os.getenv("JJPR_TEST_PHABRICATOR_URL", "http://phab.localhost:8081")
    )


@pytest.fixture(scope="session")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> Generator[httpx.Client, None, None]:
    # configure .arcrc
    phabricator_token = os.getenv("JJPR_TEST_PHABRICATOR_API_TOKEN")
    if not phabricator_token:
        pytest.skip("JJPR_TEST_PHABRICATOR_API_TOKEN not set, skipping tests")

    data = {"hosts": {str(url) + "/api/": {"token": phabricator_token}}}
    rc = Path(tmp_home) / ".arcrc"
    rc.write_text(json.dumps(data))
    rc.chmod(0o600)

    vcs_password = os.getenv("JJPR_TEST_PHABRICATOR_VCS_PASSWORD")
    if not vcs_password:
        pytest.skip("JJPR_TEST_PHABRICATOR_VCS_PASSWORD not set, skipping tests")

    rc = Path(tmp_home) / ".netrc"
    rc.open("a").write(f"machine {url.host}\nlogin admin\npassword {vcs_password}\n\n")
    rc.chmod(0o600)

    # configure http client with persistent token
    client = PhabricatorClient(url)

    # check that the client works
    try:
        if not shutil.which("arc"):
            pytest.skip("`arc` command not found, skipping tests")
        try:
            data = client.post("user.whoami").json()["result"]
            assert data["userName"] == "admin"
        except Exception as e:
            pytest.skip(f"Phabricator server seems broken, skipping tests: {e}")
        yield client
    finally:
        client.close()


@pytest.fixture
def repo(
    url: httpx.URL,
    session: httpx.Client,
) -> Generator[httpx.URL, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-phab-{rand}"
    try:
        response = session.post(
            "diffusion.repository.edit",
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
        response.json()
    except Exception as e:
        pytest.skip(f"Phabricator repo creation error: {url}: {e}")

    try:
        callsign = f"ZTST{rand.upper()}"
        repo_url = url.join(f"/source/{repo_name}.git")
        # jj can't tell which branch is trunk() if we clone a totally bare repo,
        # and arc gets confused if .arcconfig is missing, so let's pre-populate
        # those as part of the repo creation process.
        with tmp_cwd():
            for attempt in tc.Retrying(
                stop=tc.stop_after_attempt(30),
                wait=tc.wait_fixed(2),
                reraise=True,
            ):
                with attempt:
                    run_cmd("git", "clone", str(repo_url), ".")
            data = {
                "phabricator.uri": str(url),
                "repository.callsign": callsign,
            }
            Path(".arcconfig").write_text(json.dumps(data))
            run_cmd("git", "add", ".arcconfig")
            run_cmd("git", "commit", "-m", "Initial commit with .arcconfig")
            run_cmd("git", "push")

        yield repo_url
    finally:
        response = session.post(
            "diffusion.repository.search",
            data={"constraints": {"shortNames": [repo_name]}},
        )
        result = response.json()
        repos = result.get("result", {}).get("data", [])
        if repos:
            repo_phid = repos[0]["phid"]
            session.post(
                "diffusion.repository.edit",
                data={
                    "objectIdentifier": repo_phid,
                    "transactions": [{"type": "status", "value": "inactive"}],
                },
            )


@pytest.fixture
def clone(repo: httpx.URL) -> Generator[Path, None, None]:
    with tmp_cwd() as tmp_dir:
        run_cmd("jj", "git", "clone", str(repo), ".")
        yield tmp_dir
