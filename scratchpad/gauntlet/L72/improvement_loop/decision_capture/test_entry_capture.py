"""Real source splice and OFF/real-call/warmup separation, no live launch."""
import ast
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from entry import CANONICAL, transformed_source, dispatch


def test_exact_real_source_splice_preserves_all_other_text():
    original = CANONICAL.read_text(encoding='utf-8')
    changed = transformed_source(original)
    assert changed.replace('            d = capture_actual_decision(pilot, f)\n',
                           '            d = pilot.decide(f)\n') == original
    ast.parse(changed)
    assert changed.count('                    pilot.decide(f)\n') == 1
    with pytest.raises(ValueError):
        transformed_source(original.replace('            d = pilot.decide(f)\n', ''))
    with pytest.raises(ValueError):
        transformed_source(original + '            d = pilot.decide(f)\n')


def test_dispatch_off_and_optin_calls_once_without_warmup_capture():
    class Pilot:
        def __init__(self): self.calls = 0
        def decide(self, frame):
            self.calls += 1
            return frame
    class Capture:
        def __init__(self): self.calls = 0
        def decide(self, pilot, frame):
            self.calls += 1
            return pilot.decide(frame)
    p, c = Pilot(), Capture()
    f = {'game_tick': 250}
    assert p.decide(f) is f  # warmup remains the canonical bare call
    assert c.calls == 0
    assert dispatch(None, p, f) is f and p.calls == 2
    assert dispatch(c, p, f) is f and p.calls == 3 and c.calls == 1
