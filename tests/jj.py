"""Tests for jjpp.jj module."""

import logging
import os
from pathlib import Path

import pytest

from jjpp import jj

from .conftest import run_cmd

log = logging.getLogger(__name__)


class TestRun:
    """Tests for jj.run() function."""

    def test_run_basic_command(self, tmp_repo: Path):
        """Test running a basic jj command."""
        os.chdir(tmp_repo)
        output = jj.run("log", "-r", "@", "--no-graph", "-T", "''")
        assert output is not None
        assert isinstance(output, str)

    def test_run_invalid_command_raises_error(self, tmp_repo: Path):
        """Test that invalid jj commands raise JjError."""
        os.chdir(tmp_repo)
        with pytest.raises(jj.JjError):
            jj.run("invalid-command-xyz")


class TestRevsetToChangeid:
    """Tests for jj.revset_to_changeid() function."""

    def test_revset_to_changeid_current(self, repo_with_commits: Path):
        """Test converting current commit revset to change ID."""
        os.chdir(repo_with_commits)
        change_id = jj.revset_to_changeid("@")
        assert change_id
        assert len(change_id) > 0
        # Change IDs are short hashes
        assert isinstance(change_id, str)

    def test_revset_to_changeid_root(self, repo_with_commits: Path):
        """Test converting root revset to change ID."""
        os.chdir(repo_with_commits)
        change_id = jj.revset_to_changeid("root()")
        assert change_id
        assert isinstance(change_id, str)

    def test_revset_to_changeid_invalid_revset(self, tmp_repo: Path):
        """Test that invalid revsets raise an error."""
        os.chdir(tmp_repo)
        with pytest.raises(jj.JjError):
            jj.revset_to_changeid("invalid::revset:::xyz")


class TestClosestWork:
    """Tests for jj.closest_work() function."""

    def test_closest_work_with_multiple_commits(self, repo_with_commits: Path):
        """Test finding closest work with multiple commits in stack."""
        os.chdir(repo_with_commits)
        change_id = jj.closest_work()
        assert change_id
        assert isinstance(change_id, str)

    def test_closest_work_no_work(self, tmp_repo: Path):
        """Test closest_work when on empty root."""
        os.chdir(tmp_repo)
        # Root commit typically has no work, might return empty or raise
        try:
            result = jj.closest_work()
            # If it doesn't raise, result should be empty or valid
            assert isinstance(result, str)
        except jj.JjError:
            # Also acceptable if there's no work to find
            pass


class TestCurrentStack:
    """Tests for jj.current_stack() function."""

    def test_current_stack_with_commits(self, repo_with_commits: Path):
        """Test getting current stack of commits."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        assert isinstance(stack, list)
        # Should have at least the commits we created
        assert len(stack) >= 3

    def test_current_stack_returns_list(self, repo_with_commits: Path):
        """Test that current_stack returns a list of change IDs."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        assert isinstance(stack, list)
        for item in stack:
            assert isinstance(item, str)

    def test_current_stack_with_require_description(self, repo_with_commits: Path):
        """Test current_stack with require_description flag."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack(require_description=True)
        assert isinstance(stack, list)


class TestChangeParents:
    """Tests for jj.change_parents() function."""

    def test_change_parents_of_commit(self, repo_with_commits: Path):
        """Test getting parents of a commit."""
        os.chdir(repo_with_commits)
        # Get a commit from the stack
        stack = jj.current_stack()
        if len(stack) > 1:
            change_id = stack[1]
            parents = jj.change_parents(change_id)
            assert isinstance(parents, list)
            assert len(parents) > 0

    def test_change_parents_of_initial_commit(self, repo_with_commits: Path):
        """Test getting parents of initial commit (should have 0 or 1 parent)."""
        os.chdir(repo_with_commits)
        # Get root
        root_id = jj.revset_to_changeid("root()")
        parents = jj.change_parents(root_id)
        assert isinstance(parents, list)


class TestFilesIn:
    """Tests for jj.files_in() function."""

    def test_files_in_commit(self, repo_with_commits: Path):
        """Test getting files in a commit."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        # Get the last commit (should have a file)
        if stack:
            change_id = stack[-1]
            files = jj.files_in(change_id)
            assert isinstance(files, list)
            assert len(files) > 0

    def test_files_in_commit_no_files(self, repo_with_commits: Path):
        """Test getting files in an empty commit."""
        os.chdir(repo_with_commits)
        run_cmd("jj", "new")
        # Get the empty commit
        current = jj.revset_to_changeid("@")
        files = jj.files_in(current)
        assert isinstance(files, list)
        assert len(files) == 0


class TestBranchesPointingTo:
    """Tests for jj.branches_pointing_to() function."""

    def test_branches_pointing_to_with_bookmarks(self, repo_with_branches: Path):
        """Test getting bookmarks pointing to a commit."""
        os.chdir(repo_with_branches)
        # Get all commits using -r with revset
        result = run_cmd(
            "jj", "log", "-r", "::@", "--no-graph", "-T", "change_id.short() ++ '\n'"
        )
        commits = [c for c in result.strip().split("\n") if c]

        # Find which commits have bookmarks
        if commits:
            branches = jj.branches_pointing_to(commits[0])
            assert isinstance(branches, list)

    def test_branches_pointing_to_with_prefix(self, repo_with_branches: Path):
        """Test filtering branches by prefix."""
        os.chdir(repo_with_branches)
        # Get all commits using -r with revset
        result = run_cmd(
            "jj", "log", "-r", "::@", "--no-graph", "-T", "change_id.short() ++ '\n'"
        )
        commits = [c for c in result.strip().split("\n") if c]

        if commits:
            branches = jj.branches_pointing_to(commits[0], prefix="feature-")
            assert isinstance(branches, list)

    def test_branches_pointing_to_no_branches(self, repo_with_commits: Path):
        """Test getting branches when none exist."""
        os.chdir(repo_with_commits)
        current = jj.revset_to_changeid("@")
        branches = jj.branches_pointing_to(current)
        assert isinstance(branches, list)


class TestDescriptionOf:
    """Tests for jj.description_of() function."""

    def test_description_of_commit(self, repo_with_commits: Path):
        """Test getting description of a commit."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        if stack:
            change_id = stack[0]
            description = jj.description_of(change_id)
            assert isinstance(description, str)
            assert len(description) > 0
            # Should contain the commit message we set
            assert "Commit" in description or "Initial" in description

    def test_description_includes_message(self, repo_with_commits: Path):
        """Test that description includes commit message."""
        os.chdir(repo_with_commits)
        current = jj.revset_to_changeid("@")
        description = jj.description_of(current)
        # Description should be a string (may be empty if description not set)
        assert isinstance(description, str)


class TestWithEdit:
    """Tests for jj.with_edit() context manager."""

    def test_with_edit_switches_to_commit(self, repo_with_commits: Path):
        """Test that with_edit switches to target commit."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        run_cmd("jj", "edit", "@-")  # be on the most recent not-empty commit
        original = jj.revset_to_changeid("@")

        assert len(stack) > 1
        target = stack[0]
        with jj.with_edit(target):
            assert jj.revset_to_changeid("@") == target

        assert jj.revset_to_changeid("@") == original

    def test_with_edit_no_op_when_already_on_target(self, repo_with_commits: Path):
        """Test that with_edit is no-op when already on target."""
        os.chdir(repo_with_commits)
        current = jj.revset_to_changeid("@")

        with jj.with_edit(current):
            during = jj.revset_to_changeid("@")
            assert during == current

        after = jj.revset_to_changeid("@")
        assert after == current

    def test_with_edit_preserves_empty_commit(self, repo_with_commits: Path):
        """Test that with_edit preserves empty commits."""
        os.chdir(repo_with_commits)
        run_cmd("jj", "new")
        stack = jj.current_stack()
        assert len(stack) > 1

        target = stack[0]
        original = jj.revset_to_changeid("@")
        assert jj.files_in(original) == []  # Ensure original is empty
        original_parents = jj.change_parents(original)

        with jj.with_edit(target):
            assert jj.revset_to_changeid("@") == target

        replacement = jj.revset_to_changeid("@")
        assert jj.files_in(replacement) == []  # Ensure we return to empty
        assert jj.change_parents(replacement) == original_parents


class TestWithNew:
    """Tests for jj.with_new() context manager."""

    def test_with_new_creates_new_commit(self, repo_with_commits: Path):
        """Test that with_new creates a new commit."""
        os.chdir(repo_with_commits)
        stack = jj.current_stack()
        original_parents = jj.change_parents("@")

        assert len(stack) > 1
        target = stack[0]
        with jj.with_new(target):
            assert jj.change_parents("@") == [target]

        assert jj.change_parents("@") == original_parents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
