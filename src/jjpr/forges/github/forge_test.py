import json
from pathlib import Path

from ...conftest import run_cmd
from .forge import GitHub


class TestMeta:
    def test_meta(self, tmp_home: Path, tmp_repo: Path):
        r = "git@github.com:example/repo.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        f = GitHub("origin")
        assert f.remote_url == "ssh://git@github.com/example/repo.git"
        assert f.forge_url == "https://github.com"
        assert f.project_id == "example/repo"


class TestSubmit:
    def test_push_one_head(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_cwd(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_then_two(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "submit")

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

        run_cmd("jj", "pr", "submit")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 2"


class TestLog:
    def test_log(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output
        assert "Needs Review" in log_output
