import json
import logging
from pathlib import Path

import pytest

from .. import exc
from ..conftest import run_cmd
from ..utils import netrc
from . import detect

log = logging.getLogger(__name__)


class TestGetForgeFromConfig:
    def test_detect_github(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "github")
        assert detect._get_forge_from_config() == "github"

    def test_detect_phabricator(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "phabricator")
        assert detect._get_forge_from_config() == "phabricator"

    def test_detect_gerrit(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "gerrit")
        assert detect._get_forge_from_config() == "gerrit"

    def test_detect_no_config(self, tmp_repo: Path):
        assert detect._get_forge_from_config() is None


class TestGetForgeFromRemoteName:
    def test_detect_github(self):
        assert detect._get_forge_from_remote_name("github") == "github"

    def test_detect_phabricator(self):
        assert detect._get_forge_from_remote_name("phabricator") == "phabricator"

    def test_detect_gerrit(self):
        assert detect._get_forge_from_remote_name("gerrit") == "gerrit"

    def test_detect_unknown_remote(self):
        assert detect._get_forge_from_remote_name("unknown") is None


class TestGetForgeFromRemoteUrl:
    def test_detect_github(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://github.com/foo/bar")
        assert detect._get_forge_from_remote_url("origin") == "github"

    def test_detect_phabricator(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://phab.foo.com/foo/bar")
        assert detect._get_forge_from_remote_url("origin") == "phabricator"

    def test_detect_gerrit(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://gerrit.foo.com/foo/bar")
        assert detect._get_forge_from_remote_url("origin") == "gerrit"

    def test_detect_unknown_forge(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://unknown.com/foo/bar")
        assert detect._get_forge_from_remote_url("origin") is None


class TestGetForge:
    def test_detect_github(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "github")
        f = detect.get_forge("origin")
        assert f is not None
        assert f.__class__.__name__ == "GitHub"

    def test_detect_phabricator(self, tmp_repo: Path):
        rc = Path.home() / ".arcrc"
        rc.write_text(
            json.dumps({"hosts": {"https://phab.foo.com": {"token": "test_token"}}})
        )
        arcconfig = {"repository.callsign": "TEST", "arc.land.onto.default": "main"}
        (tmp_repo / ".arcconfig").write_text(json.dumps(arcconfig))
        run_cmd("git", "remote", "set-url", "origin", "https://phab.foo.com/foo/bar")
        f = detect.get_forge("origin")
        assert f is not None
        assert f.__class__.__name__ == "Phabricator"

    def test_detect_gerrit(self, tmp_repo: Path):
        netrc.write("gerrit.foo.com", "l", "p")
        run_cmd("jj", "config", "set", "--repo", "gerrit.default-remote-branch", "main")
        run_cmd("git", "remote", "set-url", "origin", "https://gerrit.foo.com/foo/bar")
        f = detect.get_forge("origin")
        assert f is not None
        assert f.__class__.__name__ == "Gerrit"

    def test_detect_unknown_forge(self, tmp_repo: Path):
        run_cmd("git", "remote", "set-url", "origin", "https://unknown.com/foo/bar")
        with pytest.raises(exc.UserError):
            detect.get_forge("origin")
