import os
import random
import string
import typing as t
from pathlib import Path

import httpx
import pytest

from ...conftest import run_cmd, tmp_cwd
from ...utils import netrc
from .client import GerritClient


@pytest.fixture(scope="class")
def url() -> httpx.URL:
    """Get the Gerrit URL from the environment variable or use a default."""
    return httpx.URL(os.getenv("JJPR_TEST_GERRIT_URL", "http://gerrit.localhost:8080"))


@pytest.fixture(scope="class")
def session(
    tmp_home: Path,
    url: httpx.URL,
) -> t.Generator[GerritClient, None, None]:
    # configure .netrc
    gerrit_token = os.getenv("JJPR_TEST_GERRIT_API_TOKEN")
    if not gerrit_token:
        pytest.skip("JJPR_TEST_GERRIT_API_TOKEN not set, skipping tests")

    netrc.write(url.host, "admin", gerrit_token)

    client = GerritClient(url)

    try:
        # check that the client works
        try:
            client.get(url)
        except Exception as e:
            pytest.skip(f"Gerrit server seems broken, skipping tests: {e}")
        yield client
    finally:
        client.close()


@pytest.fixture
def repo(
    url: httpx.URL,
    session: GerritClient,
) -> t.Generator[httpx.URL, None, None]:
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    repo_name = f"ztst-gerr-{rand}"
    try:
        session.put(
            f"projects/{repo_name}",
            json={"create_empty_commit": True},
        )
    except Exception as e:
        pytest.skip(f"Gerrit repo creation error: {url}: {e}")

    try:
        yield url.join(f"/{repo_name}.git")
    finally:
        try:
            # Delete all outstanding changes before deleting the project
            changes = session.get(
                "changes",
                params={"q": f"status:open project:{repo_name}"},
            ).json()
            for change in changes:
                change_id = change["id"]
                session.delete(f"changes/{change_id}")

            # Delete the project
            session.delete(f"projects/{repo_name}")
        except Exception as e:
            pytest.fail(f"Gerrit repo deletion error: {url}: {e}")


@pytest.fixture
def clone(repo: httpx.URL) -> t.Generator[Path, None, None]:
    with tmp_cwd() as tmp_dir:
        run_cmd("jj", "git", "clone", str(repo), ".")
        yield tmp_dir
