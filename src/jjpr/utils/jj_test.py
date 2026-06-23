import logging
import os
from pathlib import Path
from unittest import mock

import pytest

from ..conftest import run_cmd
from . import jj

log = logging.getLogger(__name__)


class TestRun:
    def test_basic_command(self, tmp_repo: Path):
        output = jj.run("log", "-r", "@", "--no-graph", "-T", "''")
        assert output is not None
        assert isinstance(output, str)

    def test_invalid_command(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.run("invalid-command-xyz")


class TestBasicCommands:
    def test_bookmark_create_and_advance(self, repo_with_commits: Path):
        change_id = jj.change_id("@-")
        bookmark_name = "test-bookmark"

        # Create a bookmark pointing to the previous change
        jj.bookmark_create(bookmark_name, change_id)
        bookmarks = jj.bookmarks()
        assert bookmark_name in bookmarks

        # Advance the bookmark to the current change
        change_id = jj.change_id("@")
        jj.bookmark_advance(bookmark_name, change_id)
        bookmarks_after_advance = jj.bookmarks()
        assert bookmark_name in bookmarks_after_advance

    def test_config_get(self, repo_with_commits: Path):
        # Set a config value
        jj.run("config", "set", "--repo", "test.key", "test_value")
        value = jj.config_get("test.key")
        assert value == "test_value"

        # Test getting a non-existent config key
        non_existent_value = jj.config_get("non.existent.key")
        assert non_existent_value is None

    def test_describe(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        new_description = "Updated description"
        jj.describe(change_id, new_description)
        description = jj.description_of(change_id)
        assert new_description in description

    def test_root(self, repo_with_commits: Path):
        assert os.getcwd() == str(jj.root())

    def test_git_fetch(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.git_fetch("origin")
            mock_run.assert_called_once_with(
                "git", "fetch", "--remote", "origin", cap=False
            )

    def test_git_push(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.git_push("origin", "main")
            mock_run.assert_called_once_with(
                "git", "push", "--remote", "origin", "--bookmark", "main", cap=False
            )

    def test_rebase(self, repo_with_commits: Path):
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.rebase(d="trunk()", r="@")
            mock_run.assert_called_once_with(
                "rebase", "--skip-emptied", "-d", "trunk()", "-r", "@", cap=False
            )


class TestGerritUpload:
    def test_gerrit_upload_basic(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        with mock.patch("jjpr.utils.jj.run"):
            jj.gerrit_upload(change_id)

    def test_gerrit_upload_with_all_options(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        with mock.patch("jjpr.utils.jj.run") as mock_run:
            jj.gerrit_upload(
                change_id, wip=True, message="Test", remote_branch="refs/for/main"
            )
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "--wip" in args
            assert "--message" in args
            assert "Test" in args
            assert "--remote-branch" in args
            assert "refs/for/main" in args


class TestChangeId:
    def test_current(self, repo_with_commits: Path):
        change_id = jj.change_id("@")
        assert len(change_id) > 0
        # Change IDs are short hashes
        assert isinstance(change_id, str)

    def test_root(self, repo_with_commits: Path):
        change_id = jj.change_id("root()")
        assert change_id == "zzzzzzzzzzzz"

    def test_invalid_revset(self, tmp_repo: Path):
        with pytest.raises(jj.JjError):
            jj.change_id("invalid::revset:::xyz")

    def test_multiple_matches(self, repo_with_commits: Path):
        with pytest.raises(ValueError):
            jj.change_id("trunk()..@")


class TestClosestWork:
    def test_multiple_commits(self, repo_with_commits: Path):
        change_id = jj.closest_work()
        assert change_id
        assert isinstance(change_id, str)

    def test_no_work(self, tmp_repo: Path):
        run_cmd("jj", "new", "trunk()")
        with pytest.raises(ValueError):  # "@ does not resolve to a single change ID"
            jj.closest_work()


class TestCheckableStack:
    def test_with_commits(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        assert isinstance(stack, list)
        assert len(stack) >= 3


class TestPushableStack:
    def test_require_description(self, repo_with_commits: Path):
        stack = jj.pushable_stack()
        assert isinstance(stack, list)
        assert len(stack) >= 3


class TestBookmarks:
    def test_bookmarks_basic(self, repo_with_commits: Path):
        bookmarks = jj.bookmarks()
        assert isinstance(bookmarks, dict)
        assert "main" in bookmarks

    def test_bookmarks_with_remote(self, repo_with_commits: Path):
        # remote bookmarks only show up when they differ from local?
        jj.bookmark_create("mywork", r="root()+")
        jj.git_push("origin", "mywork")
        jj.bookmark_advance("mywork", "@-")
        bookmarks = jj.bookmarks()
        assert "mywork@origin" in bookmarks


class TestParentsOf:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        assert len(stack) > 1
        assert jj.parents_of(stack[1]) == {stack[0]}

    def test_root_has_no_parents(self, repo_with_commits: Path):
        assert jj.parents_of(jj.change_id("root()")) == set()


class TestFilesIn:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        change_id = stack[1]
        files = jj.files_in(change_id)
        assert files == {"file2.txt"}

    def test_files_in_commit_no_files(self, repo_with_commits: Path):
        run_cmd("jj", "new")
        assert jj.files_in(jj.change_id("@")) == set()


class TestBranchesPointingTo:
    def test_with_bookmarks(self, repo_with_commits: Path):
        c = jj.change_id("feat/commit-2")
        branches = jj.branches_pointing_to(c)
        assert branches == {"feat/commit-2"}

    def test_with_prefix(self, repo_with_commits: Path):
        c = jj.change_id("feat/commit-2")
        branches = jj.branches_pointing_to(c, prefix="feat/")
        assert branches == {"feat/commit-2"}
        branches = jj.branches_pointing_to(c, prefix="pr/")
        assert branches == set()

    def test_branches_pointing_to_no_branches(self, tmp_repo: Path):
        current = jj.change_id("root()")
        branches = jj.branches_pointing_to(current)
        assert branches == set()


class TestDescriptionOf:
    def test_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        change_id = stack[0]
        description = jj.description_of(change_id)
        assert "Commit" in description or "Initial" in description


class TestWithEdit:
    def test_no_op_when_already_on_target(self, repo_with_commits: Path):
        # be on a commit
        original = jj.change_id("@")

        # edit itself
        with jj.with_edit(original):
            during = jj.change_id("@")
            assert during == original

        # still on itself
        after = jj.change_id("@")
        assert after == original

    def test_switches_to_commit(self, repo_with_commits: Path):
        # start from a non-empty commit in the middle of the stack
        stack = jj.pushable_stack()
        assert len(stack) >= 3
        run_cmd("jj", "edit", stack[-2])
        original = jj.change_id("@")

        # edit a different part of the stack
        target = stack[-1]
        with jj.with_edit(target):
            assert jj.change_id("@") == target

        # return to the original part of the stack
        assert jj.change_id("@") == original

    def test_preserves_empty_commit(self, repo_with_commits: Path):
        # start from an empty fork off of a non-empty commit in the middle of the stack
        stack = jj.pushable_stack()
        assert len(stack) >= 3
        run_cmd("jj", "edit", stack[-2])
        run_cmd("jj", "new")
        original = jj.change_id("@")
        assert jj.description_of(original) == ""
        assert jj.files_in(original) == set()
        original_parents = jj.parents_of(original)

        # edit some other part of the stack
        target = stack[-1]
        with jj.with_edit(target):
            assert jj.change_id("@") == target

        # return to a new empty forked off of the same point
        replacement = jj.change_id("@")
        assert replacement != original
        assert jj.description_of(replacement) == ""
        assert jj.files_in(replacement) == set()  # Ensure we return to empty
        assert jj.parents_of(replacement) == original_parents


class TestWithNew:
    def test_creates_new_commit(self, repo_with_commits: Path):
        stack = jj.checkable_stack()
        original_parents = jj.parents_of("@")

        assert len(stack) > 1
        target = stack[0]
        with jj.with_new(target):
            assert jj.parents_of("@") == {target}

        assert jj.parents_of("@") == original_parents
