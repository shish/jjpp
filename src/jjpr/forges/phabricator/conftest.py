import json
import os
import random
import shutil
import string
import typing as t
from pathlib import Path

import httpx
import pytest
import tenacity as tc

from ...conftest import run_cmd, tmp_cwd
from ...utils import netrc
from .client import PhabricatorClient


@pytest.fixture(scope="class")
def url() -> httpx.URL:
    """Get the Phabricator URL from the environment variable or use a default."""
    return httpx.URL(
        os.getenv("JJPR_TEST_PHABRICATOR_URL", "http://phab.localhost:8081")
    )


@pytest.fixture(scope="class")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> t.Generator[PhabricatorClient, None, None]:
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

    netrc.write(url.host, "admin", vcs_password)

    # configure http client with persistent token
    client = PhabricatorClient(url)

    # check that the client works
    if not shutil.which("arc"):
        pytest.skip("`arc` command not found, skipping tests")
    try:
        data = client.call("user.whoami")
        assert data["userName"] == "admin"
    except Exception as e:
        pytest.skip(f"Phabricator server seems broken, skipping tests: {e}")
    yield client


@pytest.fixture
def repo(
    url: httpx.URL,
    session: PhabricatorClient,
) -> t.Generator[httpx.URL, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-phab-{rand}"
    try:
        session.call(
            "diffusion.repository.edit",
            transactions=[
                {"type": "name", "value": repo_name},
                {"type": "vcs", "value": "git"},
                {"type": "callsign", "value": f"ZTST{rand.upper()}"},
                {"type": "status", "value": "active"},
                {"type": "shortName", "value": repo_name},
            ],
        )
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
                stop=tc.stop_after_attempt(60),
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
        response = session.call(
            "diffusion.repository.search",
            constraints={"shortNames": [repo_name]},
        )
        session.call(
            "diffusion.repository.edit",
            objectIdentifier=response["data"][0]["phid"],
            transactions=[{"type": "status", "value": "inactive"}],
        )


@pytest.fixture
def clone(repo: httpx.URL) -> t.Generator[Path, None, None]:
    with tmp_cwd() as tmp_dir:
        run_cmd("jj", "git", "clone", str(repo), ".")
        yield tmp_dir
