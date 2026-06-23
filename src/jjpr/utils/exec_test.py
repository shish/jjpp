import subprocess

import pytest

from . import exec


class TestRun:
    def test_run_basic_command(self):
        output = exec.run(["echo", "hello"])
        assert output == "hello"

    def test_run_with_output(self):
        output = exec.run(["echo", "test output"])
        assert "test output" in output

    def test_run_skipping_output(self):
        output = exec.run(["echo", "test output"], cap=False)
        assert output is None

    def test_run_command_failure_raises_error(self):
        with pytest.raises(subprocess.CalledProcessError):
            exec.run(["false"])

    def test_run_strips_whitespace(self):
        output = exec.run(["echo", "  spaced  "])
        assert output == "spaced"
