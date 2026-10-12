"""Avoid pytest's chmod(0700) temp dirs, unreadable in this Windows sandbox."""
from pathlib import Path
import uuid
import pytest


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1]/'output'/'test_runs'/uuid.uuid4().hex
    path.mkdir(parents=True)
    return path
