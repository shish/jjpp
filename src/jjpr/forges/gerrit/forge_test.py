import json
from pathlib import Path

from ...conftest import run_cmd
from .forge import Gerrit


class TestMeta:
    def test_meta(self, tmp_home: Path, tmp_repo: Path):
        r = "ssh://git@gerrit.mycorp.com:29418/example/repo.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        run_cmd("jj", "config", "set", "--repo", "gerrit.default-remote-branch", "main")
        (tmp_home / ".netrc").write_text(
            "machine gerrit.mycorp.com\nlogin testuser\npassword testtoken\n"
        )
        (tmp_home / ".netrc").chmod(0o600)
        f = Gerrit("origin")
        assert f.remote_url == r
        assert f.forge_url == "https://gerrit.mycorp.com"
        assert f.project_id == "example/repo"
        assert f.merge_target == "main"


class TestPush:
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
        assert len(js) == 2
        assert js[0]["title"] == "Test commit 2"
        assert js[1]["title"] == "Test commit 1"

    def test_push_two_at_once(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[0]["title"] == "Test commit 2"
        assert js[1]["title"] == "Test commit 1"


class TestLog:
    def test_log(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output
        assert "Blocked" in log_output  # blocked on code review approval
