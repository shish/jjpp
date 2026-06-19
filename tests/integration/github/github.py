from pathlib import Path

from jjpr.main import main

from ...conftest import run_cmd


class TestGithub:
    def test_import(self):
        # otherwise pytest complains that nothing touched jjpr
        assert main is not None

    def test_clone(self, github_clone: Path):
        remote_url = run_cmd("git", "config", "--get", "remote.origin.url").strip()
        assert remote_url.startswith("https://github.com/")
