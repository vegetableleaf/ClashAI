"""Avoid pytest's mode-0700 temp directories on the managed Windows filesystem."""
from pathlib import Path
import shutil
import uuid
import pytest


@pytest.fixture
def tmp_path():
    root = Path(__file__).resolve().parent / '.test_work'
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        assert path.resolve().parent == root.resolve()
        shutil.rmtree(path)
