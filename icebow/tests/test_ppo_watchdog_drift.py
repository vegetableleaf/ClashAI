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
        # BASELINE IS A ROLLING MEDIAN, not the running max -- so it needs history first, and a
        # single high excursion no longer sets the bar for everything after it.
        d = _wd._Drift()
        for v in (0.48, 0.50, 0.49, 0.51, 0.50, 0.49):   # median settles near 0.50
            self.assertIsNone(d.check("GATE", v, 5000))
        self.assertIsNone(d.check("GATE", 0.34, 5000))   # -32%, inside the 40% band
        msg = d.check("GATE", 0.25, 5000)                # -50%
        self.assertIsNotNone(msg, "a 50% decline from the rolling median must fire")
        self.assertIn("GATE DRIFT", msg)

    def test_silent_on_noise_around_a_flat_level(self):
        """NEGATIVE CONTROL. Seed noise on this project is large -- per-seed winrates inside ONE
        arm ran [0, 16, 0]. A detector that fires on that would restart a healthy run."""
        d = _wd._Drift()
        for v in (0.20, 0.17, 0.22, 0.16, 0.21, 0.18, 0.19, 0.16, 0.20):
            self.assertIsNone(d.check("GATE", v, 5000),
                              "+-15%% noise around a flat level must NOT fire")

    def test_it_does_NOT_fire_on_the_oscillation_that_actually_happens(self):
        """THE REGRESSION. The first version compared against a RUNNING MAX, which ratchets: every
        high excursion raises the bar so the next normal low reads as a big decline.

        These are the REAL P(play) readings from the live-search PPO run. The metric oscillated
        0.093-0.359 and kept returning to its highs -- it was not decaying -- and the max-based
        rule fired three separate alerts on it. A rolling median must stay silent.
        """
        real = [0.093, 0.194, 0.356, 0.186, 0.188, 0.168, 0.346, 0.169, 0.176, 0.344, 0.359, 0.345]
        d = _wd._Drift()
        fired = [m for v in real if (m := d.check("GATE", v, 5000))]
        self.assertEqual(fired, [], f"fired on healthy oscillation: {fired}")

    def test_it_still_fires_on_a_real_sustained_decay(self):
        """...and must not have been made blind by the fix. A genuine one-way slide still trips."""
        d = _wd._Drift()
        for v in (0.35, 0.34, 0.36, 0.35, 0.33, 0.34):        # establish a stable median
            self.assertIsNone(d.check("GATE", v, 5000))
        out = [d.check("GATE", v, 5000) for v in (0.24, 0.19, 0.15, 0.12)]
        self.assertTrue(any(out), "a sustained decay to a third of baseline never fired")

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
        for v in (0.50, 0.49, 0.51, 0.50, 0.49, 0.50):
            d.check("GATE", v, 5000)
        self.assertIsNotNone(d.check("GATE", 0.20, 5000))
        self.assertIsNone(d.check("GATE", 0.48, 5000))   # recovered -> quiet again
        self.assertIsNotNone(d.check("GATE", 0.20, 5000))

    def test_alert_key_is_stable_for_the_dedup_machinery(self):
        """The loop dedupes on v.split('(')[0].split('--')[0].strip(). A message whose key is not
        stable would re-post every cycle -- the exact noise the watchdog exists to avoid."""
        d = _wd._Drift()
        for v in (0.50, 0.49, 0.51, 0.50, 0.49, 0.50):
            d.check("GATE", v, 5000)
        msg = d.check("GATE", 0.20, 5000)
        self.assertIsNotNone(msg)
        key = msg.split("(")[0].split("--")[0].strip()
        self.assertEqual(key, "GATE DRIFT")


if __name__ == "__main__":
    unittest.main()
