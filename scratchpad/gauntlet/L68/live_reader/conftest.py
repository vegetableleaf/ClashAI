"""Hermetic tests: live_play's parallel-instance guard (other_live_plays) must not see a REAL live_play running on this
machine during a test run (it would refuse every main() test). Tests of the guard pass their own process list."""
import pytest


@pytest.fixture(autouse=True)
def _no_real_processes(monkeypatch):
    import psutil
    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: iter(()))
