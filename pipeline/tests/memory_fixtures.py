"""Workspace-inherited ACLs for temp files in the restricted Windows worktree."""
import shutil
import uuid
from pathlib import Path
import pytest


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[2] / 'scratchpad' / ('memory_test_'+uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)
