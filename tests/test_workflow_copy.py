"""Development's copy of workflow 04 must match main's, which is the live one."""

import subprocess
from pathlib import Path

import pytest

from daioe_regions.config import PATHS

WORKFLOW = ".github/workflows/04_development_to_main.yml"


def main_copy() -> str | None:
    """Workflow 04 as it exists on origin/main, or None when it cannot be read."""
    try:
        result = subprocess.run(
            ["git", "show", f"origin/main:{WORKFLOW}"],
            cwd=PATHS.root,
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError, subprocess.CalledProcessError:
        return None
    return result.stdout


def test_development_copy_matches_main() -> None:
    expected = main_copy()
    if expected is None:
        pytest.skip("origin/main is not available")
    actual = Path(PATHS.root / WORKFLOW).read_text()
    assert actual == expected, (
        "development's copy of workflow 04 differs from origin/main's. "
        "Push the main edit first; the sync job copies main's file onto "
        "development after every run."
    )
