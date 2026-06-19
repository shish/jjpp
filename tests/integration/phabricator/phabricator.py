from pathlib import Path

from jjpr.main import main

from ...conftest import run_cmd


class TestPhabricator:
    def test_import(self):
        # otherwise pytest complains that nothing touched jjpr
        assert main is not None

    def test_clone(self, phabricator_clone: Path):
        remote_url = run_cmd("git", "config", "--get", "remote.origin.url").strip()
        assert remote_url.startswith("http://phab.localhost:8081/")
