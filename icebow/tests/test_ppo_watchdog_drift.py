"""The watchdog's relative-decline detector.

Written because the ABSOLUTE bands could not have caught the failure this project actually has:
the shipped never-play floor is 0.05 and the live 8k checkpoint sits at 0.171 while failing every
ACT drill, so the watchdog would have run all night in silence. These tests pin the behaviour the
drift check exists for, INCLUDING the negative control -- a detector that never stays quiet is
just as useless as one that never fires.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "ppo_watchdog", Path(__file__).resolve().parents[1] / "tools" / "ppo_watchdog.py")
_wd = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_wd)
    _OK = True
except Exception:                                        # torch/env missing -> skip, do not fail
    _OK = False


@unittest.skipUnless(_OK, "ppo_watchdog could not be imported in this environment")
class TestDrift(unittest.TestCase):

    def test_fires_on_a_gradual_decline(self):
        """The 40k-run shape: climb, then decay slowly. An absolute floor never trips on this."""
        d = _wd._Drift()
        for v in (0.30, 0.42, 0.50, 0.48):               # peak establishes at 0.50
            self.assertIsNone(d.check("GATE", v, 5000))
        self.assertIsNone(d.check("GATE", 0.34, 5000))   # -32%, still inside the 40% band
        msg = d.check("GATE", 0.28, 5000)                # -44%
        self.assertIsNotNone(msg, "a 44% decline from peak must fire")
        self.assertIn("GATE DRIFT", msg)
        self.assertIn("0.500", msg)

    def test_silent_on_noise_around_a_flat_level(self):
        """NEGATIVE CONTROL. Seed noise on this project is large -- per-seed winrates inside ONE
        arm ran [0, 16, 0]. A detector that fires on that would restart a healthy run."""
        d = _wd._Drift()
        for v in (0.20, 0.17, 0.22, 0.16, 0.21, 0.18, 0.19, 0.16, 0.20):
            self.assertIsNone(d.check("GATE", v, 5000),
                              "+-15%% noise around a flat level must NOT fire")

    def test_silent_before_min_matches(self):
        """Early training legitimately swings; the gate starts near 0.5 and moves fast."""
        d = _wd._Drift()
        self.assertIsNone(d.check("GATE", 0.90, 10))
        self.assertIsNone(d.check("GATE", 0.05, 10))

    def test_silent_when_the_peak_is_meaningless(self):
        """A run that never played at all has no peak worth declining from."""
        d = _wd._Drift()
        d.check("GATE", 0.02, 5000)
        self.assertIsNone(d.check("GATE", 0.001, 5000))

    def test_recovery_rearms(self):
        d = _wd._Drift()
        d.check("GATE", 0.50, 5000)
        self.assertIsNotNone(d.check("GATE", 0.20, 5000))
        self.assertIsNone(d.check("GATE", 0.45, 5000))   # recovered -> quiet again
        self.assertIsNotNone(d.check("GATE", 0.20, 5000))

    def test_alert_key_is_stable_for_the_dedup_machinery(self):
        """The loop dedupes on v.split('(')[0].split('--')[0].strip(). A message whose key is not
        stable would re-post every cycle -- the exact noise the watchdog exists to avoid."""
        d = _wd._Drift()
        d.check("GATE", 0.50, 5000)
        msg = d.check("GATE", 0.20, 5000)
        key = msg.split("(")[0].split("--")[0].strip()
        self.assertEqual(key, "GATE DRIFT")


if __name__ == "__main__":
    unittest.main()
