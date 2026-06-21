import json
from pathlib import Path

from ...conftest import run_cmd


class TestGithubPush:
    def test_push_one_head(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_cwd(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_then_two(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_two_at_once(self, clone: Path):
        # github is branch-based, so pushing two commits at once will
        # only create a PR for the top commit
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 2"
