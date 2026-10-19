"""L16 opt-in match levels, with real catalog clamping and legacy config compatibility."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import rl_royale as RL                                  # noqa: E402
from pipeline.decision_options import _catalog_cards                  # noqa: E402


class TestL16Levels(unittest.TestCase):
    def test_all16_table_draws_every_catalog_card_and_both_towers(self):
        table = RL.live_levels({"league": True, "live_levels": "all16"})
        self.assertEqual(table, {"own": {"cards": {}, "default": 16, "tower": 16},
                                 "opp_profiles": [[None, 16, [16]]]})
        names = sorted({c["name"] for c in _catalog_cards().values()})
        self.assertGreater(len(names), 100)
        # Both supported deck representations, including form suffixes.
        levels = RL.draw_live_levels(table, names, [{"name": n + "@Evo"} for n in names], "l16")
        self.assertEqual(levels, {"learner": {"cards": [16] * len(names), "tower": 16},
                                  "opp": {"cards": [16] * len(names), "tower": 16, "profile": 0}})
        # Exercise the real rarity limits, including values above and below the range.
        for name, lower in (("Knight", 1), ("Rocket", 3), ("Xbow", 6), ("IceWizard", 9), ("ArcherQueen", 11)):
            self.assertEqual(RL.card_level(name, 0), lower)
            self.assertEqual(RL.card_level(name, 99), 16)

    def test_validation_and_yaml_override(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cfg.yaml"
            path.write_text("league: true\n", encoding="utf-8")
            cfg = RL.load_config(path, ["live_levels=all16"], smoke=False)
        self.assertEqual(cfg["live_levels"], "all16")
        for value in ("all15", 1, "true"):
            with self.assertRaises(SystemExit):
                RL.live_levels({"league": True, "live_levels": value})
        with self.assertRaises(SystemExit):
            RL.live_levels({"live_levels": "all16"})

    def test_measured_true_and_no_argument_table_are_unchanged(self):
        table = {"own": {"cards": {"Knight": 15}, "default": 14, "tower": 15},
                 "opp_profiles": [["measured", 13, [12, 14]]]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "levels.json"
            path.write_text(json.dumps(table), encoding="utf-8")
            with patch.object(RL, "LIVE_LEVELS", path), patch.object(RL, "_LIVE_TABLE", {}):
                self.assertEqual(RL._live_level_table(), table)
                self.assertIs(RL._live_level_table(True), RL._live_level_table())
                self.assertIs(RL.live_levels({"league": True, "live_levels": True}), RL._live_level_table())
                RL._live_level_table("all16")
                self.assertEqual(RL._live_level_table(), table)

    def test_hash_keeps_all16_string_and_legacy_off_and_true_hashes(self):
        base = {"seed": 74, "league": True}
        sha = lambda cfg: hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
        self.assertEqual(RL.config_sha(base), sha(base))
        for value in (None, False):
            cfg = {**base, "live_levels": value}
            self.assertIsNone(RL.live_levels(cfg))
            self.assertEqual(RL.config_sha(cfg), sha(base))
        self.assertIsNone(RL.live_levels(base))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "levels.json"
            path.write_bytes(b'{"measured": "table bytes"}')
            with patch.object(RL, "LIVE_LEVELS", path):
                measured = RL.config_sha({**base, "live_levels": True})
                self.assertEqual(measured, sha({**base, "live_levels": hashlib.sha256(path.read_bytes()).hexdigest()}))
                path.unlink()  # all16 must not read or depend on the measured table.
                all16 = RL.config_sha({**base, "live_levels": "all16"})
                self.assertEqual(all16, sha({**base, "live_levels": "all16"}))
                self.assertNotEqual(all16, measured)
                self.assertIsNotNone(RL.live_levels({**base, "live_levels": "all16"}))

    def test_matchups_off_unchanged_and_all16_preserves_match_and_rng_draws(self):
        base = {"league": True, "league_icebow_share": 1.0, "league_mix": {"init": 1.0},
                "init": "init.pt", "league_specialist": "s1.pt"}

        def draw(cfg):
            rng = np.random.default_rng(74)
            rows = RL.sample_matchups(rng, 4, 7, [], cfg, [], np.array([]))
            return rows, rng.bit_generator.state

        absent, state = draw(base)
        self.assertTrue(all("levels" not in row for row in absent))
        for value in (None, False):
            self.assertEqual(draw({**base, "live_levels": value}), (absent, state))
        rows, all16_state = draw({**base, "live_levels": "all16"})
        self.assertEqual(all16_state, state)
        for row, original in zip(rows, absent):
            self.assertEqual(row.pop("levels"), {"learner": {"cards": [16] * 8, "tower": 16},
                                                  "opp": {"cards": [16] * 8, "tower": 16, "profile": 0}})
            self.assertEqual(row, original)


if __name__ == "__main__":
    unittest.main()
