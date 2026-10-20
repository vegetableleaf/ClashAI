"""L74 W10 (10-20): the opt-in crown term ``rocket_tower`` (pipeline/reward_terms.py; rl_royale actor crown_track
"rocket_dmg"; e1_eval CrownTracker(rocket_dmg=...)). scratchpad/gauntlet/L74/rocket/ROCKET.md has the evidence.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rocket_tower_1020.py

Covers: absent = PRE (2a3da3b, the last commit before W10): config hash of rl_royale.yaml and the L16 recipe, crown_cfg None,
the tracker's result without rocket_dmg (and every non-Rocket field with it), every earlier term's row_terms / bound /
batch_stats / match_summary, actor_cfg, collate and the real SelfPlayMatch play; on: the tracker measures enemy PRINCESS HP
inside our Rocket's blast across its impact (lagged one stop; king and troop aims pay nothing; a felled tower counts its
remainder), the reward lands on the row that decided the Rocket, the match cap, unmapped hits, validation, bound, hash, the
arm yaml = the L16 recipe + one key, and one whole gae update."""
from __future__ import annotations

import copy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import reward_terms as RT                                   # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests import test_reward_terms_1020 as W6                   # noqa: E402
from pipeline.tests.test_reward_terms_1020 import (ROCKET, TORNADO, ent, lead_match, spell, state, tornado_match,  # noqa: E402
                                                   towers)
from pipeline.tests.test_rl_gae import SPEC, _learner, _Tmp               # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "2a3da3b"
YAML = REPO / "pipeline/rl_royale.yaml"
L16 = REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml"
ARM = REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_rocket_s74.yaml"
BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.5}
ON = {"rocket_tower": True, "rocket_tower_w": 0.5}
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0)


def _pre(path, name):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{path}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__ = str(REPO / path)
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def trk(mod=RT, **kw):
    return mod.CrownTracker(NS(ids={"Tornado": TORNADO, "Rocket": ROCKET}), 0, **kw)


def rocket_match(mod=RT, aim=(3.5, 6.5), after=0.89, end_early=False, **kw):
    """0-0. Our Rocket appears at ``aim`` on stop 110, flies through 120, is gone at 130 (the hp has not moved yet: the
    one-tick lag), their L princess reads ``after`` from 140 (and their king 0.9: never paid). A Tornado at 150 and a
    second, troop-aimed Rocket at 160-170 ride along. ``end_early``: the match ends on the gone stop."""
    t = trk(mod, **kw)
    seq = [(100, towers(), []), (110, towers(), [spell(ROCKET, *aim)]), (120, towers(), [spell(ROCKET, *aim)]),
           (130, towers(), [])]
    if not end_early:
        seq += [(140, towers(foe=(after, 1.0), king=1.0), []),
                (150, towers(foe=(after, 1.0), king=1.0) + [ent(50, 1, 12.0, 24.0)], [spell(TORNADO, 12.0, 25.0)]),
                (160, towers(foe=(after, 1.0), king=1.0), [spell(ROCKET, 9.0, 20.0)]),
                (170, towers(foe=(after, 1.0), king=1.0), [])]
    for tk, ents, sp in seq:
        if tk >= 140:                                     # their king at 0.9 too (towers() sets OUR king only)
            ents = [NS(**{**vars(e), "hp": 0.9 * e.max_hp}) if e.uid == 4 else e for e in ents]
        t.observe(state(tk, ents, (0, 0), sp))
    return t.result()


class TestAbsentIsPre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = _pre("pipeline/reward_terms.py", "reward_terms_pre_w10")

    def test_hash_and_crown_cfg(self):
        for path in (YAML, L16):
            cfg = RL.load_config(path, [], False)
            self.assertIsNone(RL.crown_cfg(cfg), path.name)
            h = RL.config_sha(cfg)
            saved = RL.RT
            try:
                RL.RT = self.P
                self.assertEqual(RL.config_sha(cfg), h, path.name)       # the pre-W10 module's hash
            finally:
                RL.RT = saved
            for off in (None, False):
                self.assertEqual(RL.config_sha({**cfg, "rocket_tower": off}), h)

    def test_tracker_default_is_pre(self):
        for kw in ({}, {"aim": (9.0, 2.5)}, {"end_early": True}):
            pre, now = rocket_match(self.P, **kw), rocket_match(RT, **kw)
            self.assertEqual(now, pre, kw)
            self.assertNotIn("rocket_hits", now)
            on = rocket_match(RT, rocket_dmg=True, **kw)                  # the measurement changes nothing else
            self.assertEqual({k: v for k, v in on.items() if k != "rocket_hits"}, pre, kw)
        self.assertEqual(lead_match(), lead_match())                      # W6 fixtures still build

    def test_earlier_terms_unchanged(self):
        plays = [{"tick": 85, "land_tick": 111, "card": "Tornado", "accepted": True}]
        ticks, T5 = np.array([85, 95, 125]), np.array([100, 115, 135, 145, 155])
        ps = [{}, {"lead_protect": True, "lead_protect_w": 0.2}, {"princess_redirect": "penalty", "princess_redirect_w": 0.2},
              {"princess_redirect": "potential", "princess_redirect_w": 0.2},
              {"tornado_king_penalty": True, "tornado_king_w": 0.01}]
        if "princess_take" in RT.TERMS and "princess_take" in self.P.TERMS:   # W7's term, when both modules carry it
            ps.append({"princess_take": True, "princess_take_w": 0.2})
        for p in ps:
            for c, tk, pl in ((lead_match(), T5, []), (tornado_match(down=True), ticks, plays)):
                a, b = RT.row_terms(c, pl, tk, p), self.P.row_terms(c, pl, tk, p)
                self.assertEqual(set(a), set(b), p)
                np.testing.assert_array_equal(a["r"], b["r"])
                self.assertEqual({k: v for k, v in a.items() if k not in ("r", "phi")},
                                 {k: v for k, v in b.items() if k not in ("r", "phi")})
                self.assertEqual(RT.bound(p), self.P.bound(p))
                self.assertEqual(RT.match_summary(c), self.P.match_summary(c))
                self.assertEqual(RT.batch_stats([RT.match_summary(c)], [a]), self.P.batch_stats([self.P.match_summary(c)], [b]))
                self.assertEqual(RT.crown_log({"crown": c}), self.P.crown_log({"crown": c}))

    def test_actor_cfg(self):
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_w10")
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        for b in (base, {**base, "crown_track": True}):
            for kind in ("rollout", "screen"):
                a, p = RL.actor_cfg(b, kind, 0, "cpu"), P.actor_cfg(b, kind, 0, "cpu")
                self.assertEqual({k: v for k, v in a.items() if k != "noise"}, {k: v for k, v in p.items() if k != "noise"})
        on = RL.actor_cfg({**base, "crown_track": "rocket_dmg"}, "rollout", 0, "cpu")
        self.assertEqual((on["crown_track"], on["record_tick"]), ("rocket_dmg", True))
        self.assertNotIn("crown_track", RL.actor_cfg({**base, "crown_track": "rocket_dmg"}, "screen", 0, "cpu"))


class TestTracker(unittest.TestCase):
    def test_princess_hit_lagged_one_stop(self):
        c = rocket_match(rocket_dmg=True)
        self.assertEqual(len(c["rockets"]), 2)
        (h, troops) = c["rocket_hits"]
        self.assertEqual((h["seen"], h["impact"]), (110, 130))
        self.assertAlmostEqual(h["dmg"], 0.11)                            # the drop seen on 140, not on the gone stop 130
        self.assertEqual((troops["seen"], troops["dmg"]), (160, 0.0))      # aimed at troops: no tower in the blast
        self.assertAlmostEqual(RT.match_summary(c)["rocket_princess_dmg"], 0.11)

    def test_king_never_counts(self):
        (h, _) = rocket_match(aim=(9.0, 2.5), rocket_dmg=True)["rocket_hits"]   # their king took 0.1, their L 0.11
        self.assertEqual(h["dmg"], 0.0)

    def test_felled_tower_counts_its_remainder(self):
        (h, _) = rocket_match(after=0.0, rocket_dmg=True)["rocket_hits"]       # 0 = dropped from the entity list
        self.assertAlmostEqual(h["dmg"], 1.0)
        t = trk(rocket_dmg=True)
        for tk, foe in ((100, (1.0, 1.0)), (110, (0.05, 1.0)), (120, (0.05, 1.0)), (130, (0.05, 1.0)), (140, (0.0, 1.0))):
            t.observe(state(tk, towers(foe=foe), (0, 0), [spell(ROCKET, 3.5, 6.5)] if tk in (110, 120) else []))
        self.assertAlmostEqual(t.result()["rocket_hits"][0]["dmg"], 0.05)

    def test_match_ends_before_the_next_stop(self):
        (h,) = rocket_match(end_early=True, rocket_dmg=True)["rocket_hits"]
        self.assertEqual((h["impact"], h["dmg"]), (130, 0.0))              # resolved on the last stop seen
        c = trk(rocket_dmg=True)
        c.observe(state(100, towers()))
        self.assertEqual(c.result()["rocket_hits"], [])
        self.assertEqual(c.result()["rocket_hits"], [])                   # result() twice: no double count


class TestTerm(unittest.TestCase):
    PLAYS = [{"tick": 85, "land_tick": 111, "card": "Rocket", "accepted": True},
             {"tick": 95, "land_tick": 121, "card": "Tornado", "accepted": True}]
    TICKS = np.array([85, 95, 125])

    @staticmethod
    def rec(*hits):
        return {"lost": [], "falls": [], "tornados": [], "rockets": [], "end": None,
                "rocket_hits": [{"seen": s, "impact": s + 20, "dmg": d} for s, d in hits]}

    def test_row_cap_unmapped(self):
        r = RT.row_terms(self.rec((115, 0.11)), self.PLAYS, self.TICKS, ON)
        np.testing.assert_allclose(r["r"], [0.055, 0.0, 0.0])            # the row that decided the Rocket
        self.assertAlmostEqual(r["rocket"], 0.055)
        self.assertEqual(r["rocket_unmapped"], 0)
        big = RT.row_terms(self.rec((115, 0.5), (116, 0.5)), self.PLAYS * 1, self.TICKS, ON)
        self.assertAlmostEqual(big["rocket"], RT.ROCKET_MATCH_CAP)        # 0.25 + min(0.25, 0.05)
        far = RT.row_terms(self.rec((400, 0.2)), self.PLAYS, self.TICKS, ON)   # no Rocket play lands within 40 ticks
        self.assertEqual((far["rocket_unmapped"], far["rocket"]), (1, 0.0))
        self.assertFalse(far["r"].any())
        zero = RT.row_terms(self.rec((115, 0.0)), self.PLAYS, self.TICKS, ON)
        self.assertEqual((zero["rocket"], zero["rocket_unmapped"]), (0.0, 0))
        off = RT.row_terms(self.rec((115, 0.11)), self.PLAYS, self.TICKS, {})
        self.assertNotIn("rocket", off)
        self.assertFalse(off["r"].any())

    def test_needs_the_measuring_tracker(self):
        rec = self.rec()
        del rec["rocket_hits"]
        with self.assertRaises(ValueError):
            RT.row_terms(rec, self.PLAYS, self.TICKS, ON)

    def test_batch_stats(self):
        c = self.rec((115, 0.11))
        on = RT.batch_stats([RT.match_summary(c)], [RT.row_terms(c, self.PLAYS, self.TICKS, ON)])
        self.assertAlmostEqual(on["rocket_reward_per_match"], 0.055)
        self.assertEqual(on["rocket_unmapped"], 0)
        self.assertAlmostEqual(on["rocket_princess_dmg_per_match"], 0.11)
        off = RT.batch_stats([RT.match_summary(c)], [RT.row_terms(c, self.PLAYS, self.TICKS, {})])
        self.assertNotIn("rocket_reward_per_match", off)

    def test_cfg_bound_hash(self):
        self.assertAlmostEqual(RT.bound(ON), 0.3)
        self.assertEqual(RL.crown_cfg({**BASE, "rocket_tower": True}), ON)
        RL.adv_cfg({**BASE, "rocket_tower": True})                        # 1 + 0.3 <= 1.5
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**BASE, "rocket_tower": True, "shaping_critic_scale": 1.25})
        for bad in ({"rocket_tower": "yes"}, {"rocket_tower_w": 0.3}, {"rocket_tower": True, "rocket_tower_w": -1}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.crown_cfg({**BASE, **bad})
        cfg = RL.load_config(L16, [], False)
        h, on = RL.config_sha(cfg), RL.config_sha({**cfg, "rocket_tower": True})
        self.assertNotEqual(on, h)
        self.assertEqual(RL.config_sha({**cfg, "rocket_tower": True, "rocket_tower_w": 0.5}), on)
        self.assertNotEqual(RL.config_sha({**cfg, "rocket_tower": True, "rocket_tower_w": 1.0}), on)

    def test_arm_yaml_is_the_recipe_plus_one_key(self):
        base, arm = RL.load_config(L16, [], False), RL.load_config(ARM, [], False)
        self.assertEqual(arm, {**base, "rocket_tower": True})
        RL.adv_cfg(arm)
        self.assertEqual(RL.config_sha(RL.load_config(L16, ["rocket_tower=on"], False)), RL.config_sha(arm))


def _with_rocket(results):
    """W6's synthetic crown records + one Rocket per match, decided on the first played row, that took 0.11 of a princess."""
    out = W6._with_crown(results)
    for r in out:
        tk = r["traj"]["tick"]
        j = int(np.flatnonzero(r["traj"]["played"])[0])
        r["plays"] = r["plays"] + [{"tick": int(tk[j]), "land_tick": int(tk[j]) + 26, "card": "Rocket", "accepted": True}]
        r["crown"]["rocket_hits"] = [{"seen": int(tk[j]) + 30, "impact": int(tk[j]) + 60, "dmg": 0.11}]
    return out


class TestCollate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _with_rocket(_results(_tiny_model(0), [(0, 0, 12, "win"), (0, 1, 10, "loss"), (1, 0, 9, "draw")], seed=3,
                                        all_allowed=True))

    def test_adds_only_its_reward_on_the_rocket_row(self):
        B0, st0 = RL.collate(copy.deepcopy(self.res), advantage="gae")
        B1, st1 = RL.collate(copy.deepcopy(self.res), advantage="gae", crown=RL.crown_cfg({**BASE, "rocket_tower": True}))
        d = B1["r_step"] - B0["r_step"]
        self.assertTrue((d >= 0).all())
        self.assertAlmostEqual(float(d.sum()), 0.055 * len(self.res), places=9)
        self.assertEqual(int(np.count_nonzero(d)), len(self.res))
        self.assertAlmostEqual(st1["crown"]["rocket_reward_per_match"], 0.055)
        for key in B0:
            if key != "r_step":
                np.testing.assert_array_equal(B0[key], B1[key], err_msg=key)


class TestAbsentCollateIsPre(unittest.TestCase):
    """rocket_tower absent / null / false: collate (every batch array byte-identical, the stats equal) and adv_cfg equal PRE's
    with rocket records present in the results (ignored without the key). A whole-update byte comparison is NOT used: on
    this laptop two runs of the SAME PRE module already differ in the 9th digit after 2 updates (measured 10-20; it is also
    why W6's test_updates_identical fails at PRE itself)."""

    def test_collate_and_adv_cfg_identical(self):
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_w10_col")
        res = _with_rocket(_monitor_fields(_results(_tiny_model(6), SPEC, seed=13)))
        for adv in ("match_loo", "gae"):
            Bp, sp = P.collate(copy.deepcopy(res), 2.0, advantage=adv)
            for crown in (None, RL.crown_cfg({**BASE, "rocket_tower": None}), RL.crown_cfg({**BASE, "rocket_tower": False})):
                Bn, sn = RL.collate(copy.deepcopy(res), 2.0, advantage=adv, crown=crown)
                self.assertEqual(sorted(Bn), sorted(Bp))
                for k in Bp:
                    self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
                self.assertEqual(sn, sp)
        for cfg in ({}, dict(GAE), RL.load_config(L16, [], False)):
            self.assertEqual(RL.adv_cfg(cfg), P.adv_cfg(cfg))


class TestOneUpdateOn(_Tmp):
    def test_update(self):
        model = _tiny_model(6)
        res = _with_rocket(_monitor_fields(_results(model, SPEC, seed=13)))
        L = _learner(RL, model, res, self.tmp / "rocket", **GAE, league=True, rocket_tower=True)
        L.one_update(0)
        rec = L.one_update(1)[0]                                          # past the critic warm-up: a policy step
        self.assertGreater(rec["crown"]["rocket_reward_per_match"], 0)
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        self.assertTrue(ck["rl"]["config_sha256"])


class TestSelfPlayWiring(W6.TestSelfPlayWiring):
    """e1_eval's real SelfPlayMatch: crown_track "rocket_dmg" = the measuring tracker (rocket_hits); True = the W6 record;
    the recorded play is byte-identical either way."""

    def test_crown_record_and_identical_play(self):
        on, w6 = self._run(crown_track="rocket_dmg"), self._run(crown_track=True)
        self.assertIn("rocket_hits", on["crown"])
        self.assertNotIn("rocket_hits", w6["crown"])
        self.assertEqual({k: v for k, v in on["crown"].items() if k != "rocket_hits"}, w6["crown"])
        for k in w6["traj"]:
            self.assertEqual(w6["traj"][k].tobytes(), on["traj"][k].tobytes(), k)
        self.assertEqual(on["plays"], w6["plays"])


if __name__ == "__main__":
    unittest.main()
