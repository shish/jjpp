import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from ..conftest import run_cmd


@pytest.fixture(scope="session")
def tmp_home() -> Generator[Path, None, None]:
    """Create a temporary home directory for tests."""
    tmp_dir = tempfile.mkdtemp(prefix="jjpr_home_")
    original_home = os.environ.get("HOME", "")
    os.environ["HOME"] = tmp_dir
    try:
        # configure .gitrc
        run_cmd("git", "config", "user.email", "test@example.com")
        run_cmd("git", "config", "user.name", "Test User")

        yield Path(tmp_dir)
    finally:
        os.environ["HOME"] = original_home
        shutil.rmtree(tmp_dir, ignore_errors=True)
