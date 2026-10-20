"""L74 W7 (10-20): rl_royale's opt-in ``league_opp_live`` (frozen icebow league opponents play their live decision stack).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_league_opp_live_1020.py

Covers: absent / null = the pre-change trainer (PRE = 0bcc4c5: config_sha of rl_royale.yaml, the L16 recipe and the W7 C1
arm; load_config); ``live_opp_cfg`` returns the opponent cfg object itself when off and for init / snapshot / s1 /
league_exploiters opponents; merges the stack for league_external ("exploiter") and frozen opponents; validation."""
from __future__ import annotations

import subprocess
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.decision_options import options_from_config                # noqa: E402

PRE = "0bcc4c5"
YAMLS = (REPO / "pipeline/rl_royale.yaml", REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml",
         REPO / "scratchpad/gauntlet/L74/opp_model/cfg/oppC1_icemix_s74.yaml")
LIVE = dict(xbow_class="class_sample", xbow_class_floor=.3, tau_phase=[.35, .45, .55], spell_aim="rocket_area",
            gate_decode="hazard_below_tau", gate_hazard_min_elixir=9, log_aim="log_barrel", lethal_rocket="ot_behind",
            xbow_dead_lane="block", gate_hazard_threatened=2, rocket_dead_target="block", tau_threatened=.2,
            lethal_log="on", tau=0.35, own_effects=True)


def _pre_module():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_w7")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_w7", "exec"), mod.__dict__)
    return mod


class TestLeagueOppLive(unittest.TestCase):
    def test_absent_is_historical(self):
        P = _pre_module()
        for path in YAMLS:
            cfg = RL.load_config(path, [], False)
            self.assertEqual(cfg, P.load_config(path, [], False), path.name)
            self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg), path.name)
            self.assertEqual(RL.config_sha({**cfg, "league_opp_live": None}), RL.config_sha(cfg))
            self.assertIsNone(RL.league_opp_live(cfg))
            self.assertNotEqual(RL.config_sha({**cfg, "league_opp_live": {"tau": 0.35}}), RL.config_sha(cfg))

    def test_merge_only_external_and_frozen(self):
        oc = {"policy": "live", "tau": 0.27, "decide_every": 10}
        base = {"league_opp_live": dict(LIVE)}
        for t in ("init", "snapshot", "s1", "exploiter_league"):
            self.assertIs(RL.live_opp_cfg(oc, {"type": t}, base), oc, t)
        for t in ("exploiter", "frozen"):
            got = RL.live_opp_cfg(oc, {"type": t}, base)
            self.assertEqual(got, {**oc, **LIVE}, t)
            self.assertEqual(got["tau"], 0.35)
            self.assertTrue(options_from_config(got).active)
        self.assertEqual(oc, {"policy": "live", "tau": 0.27, "decide_every": 10})          # the input is not mutated
        for off in ({}, {"league_opp_live": None}):
            self.assertIs(RL.live_opp_cfg(oc, {"type": "exploiter"}, off), oc)

    def test_actor_base_carries_it_only_when_on(self):
        """The actors see ``actor_base()`` only (10-20: the first W7 launch merged nothing because the key never got
        there). Off: the base is the pre-change one; on: it carries the dict."""
        from types import SimpleNamespace as NS
        P = _pre_module()
        cfg = RL.load_config(YAMLS[2], [], False)
        stub = lambda c: NS(cfg=c, init_meta={"args": {}}, grid="lattice", gen=None, runtime=None)   # noqa: E731
        off = RL.Learner.actor_base(stub(cfg))
        self.assertNotIn("league_opp_live", off)
        self.assertEqual(off, P.Learner.actor_base(stub(cfg)))
        on = RL.Learner.actor_base(stub({**cfg, "league_opp_live": dict(LIVE)}))
        self.assertEqual(on["league_opp_live"], LIVE)
        self.assertEqual({k: v for k, v in on.items() if k != "league_opp_live"}, off)
        oc = {"policy": "live", "tau": 0.27}
        self.assertEqual(RL.live_opp_cfg(oc, {"type": "exploiter"}, on)["tau_phase"], [.35, .45, .55])

    def test_validation(self):
        good = {"league": True, "extrapolate_ticks": 26, "league_opp_live": dict(LIVE)}
        self.assertEqual(RL.league_opp_live(good), LIVE)
        for bad in ({"league_opp_live": {}}, {"league_opp_live": {"nope": 1}}, {"league_opp_live": {"tau": 1.5}},
                    {"league_opp_live": {"own_effects": False}}, {"extrapolate_ticks": 0},
                    {"league": False}, {"league_opp_live": {"xbow_class": "bogus"}}, {"league_opp_live": [1]}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.league_opp_live({**good, **bad})


if __name__ == "__main__":
    unittest.main()
