import json
from pathlib import Path

from ...conftest import run_cmd
from .forge import Phabricator


class TestMeta:
    def test_meta(self, tmp_home: Path, tmp_repo: Path):
        r = "https://phab.mycorp.com/source/my-repo.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        arcrc = {
            "hosts": {
                "https://phab.mycorp.com/api/": {
                    "token": "api-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                }
            }
        }
        (tmp_home / ".arcrc").write_text(json.dumps(arcrc))
        arcconfig = {
            "phabricator.uri": "https://phab.mycorp.com",
            "repository.callsign": "TESTREPO",
            "arc.land.onto.default": "main",
        }
        (tmp_repo / ".arcconfig").write_text(json.dumps(arcconfig))
        f = Phabricator("origin")
        assert f.remote_url == r
        assert f.forge_url == "https://phab.mycorp.com"
        assert f.project_id == "TESTREPO"
        assert f.merge_target == "main"


class TestSubmit:
    def test_push_one_head(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "-vv", "submit", "-m", "Test push 1")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_cwd(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit", "-m", "Test push 1")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_push_one_then_two(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit", "-m", "Test push 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "submit", "-m", "Test push 2")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[0]["title"] == "Test commit 2"
        assert js[1]["title"] == "Test commit 1"
        # todo: assert two has one as a parent

    def test_push_two_at_once(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "submit", "-m", "Test push 1+2")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[0]["title"] == "Test commit 2"
        assert js[1]["title"] == "Test commit 1"
        # todo: assert two has one as a parent


class TestLog:
    def test_log(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "submit")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output
        assert "Needs Review" in log_output
