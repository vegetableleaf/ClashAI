"""L74 W6 crown reward terms (pipeline/reward_terms.py + rl_royale ``lead_protect`` / ``princess_redirect`` /
``tornado_king_penalty``, e1_eval ``crown_track``, search_s0 ``--crown-log``).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_reward_terms_1020.py

Covers: absent / null / false = the pre-change trainer (config hash of rl_royale.yaml AND of the L16 recipe, adv_cfg,
actor_cfg, collate, whole gae updates and checkpoint keys -- compared with PRE, the last commit before the change); the
hash differs per key / mode / weight when on; validation; the tracker on hand-built engine states (princess HP lost while
both stand + the freeze at the first fall, falls with the crowns before, Tornado pull toward our king from the PRE-cast
board, gating on a fallen princess, Rocket tower aims); each term's sign on constructed records; the collate wiring; the
real SelfPlayMatch on test_league's fake env (crown record present, every traj array byte-identical with the tracker off);
one gae update end to end per key."""
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
from pipeline.tests.test_rl_gae import SPEC, _learner, _strip, _Tmp       # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "db84ac9"             # the last commit that touched pipeline/rl_royale.py before W6: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
L16 = REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml"
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0)
ON = {"lead_protect": True, "princess_redirect": "penalty", "tornado_king_penalty": True}
TILE, TORNADO, ROCKET = RT.TILE, 120, 111
W = {k: float(v) for k, v in RT.DEFAULTS.items()}


def _pre_module():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_w6")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_w6", "exec"), mod.__dict__)
    return mod


# ---- hand-built engine states (royalegym BattleState's shape), side 0, board tiles in side 0's frame ----------------
def sub(bx, by):
    return bx * TILE, (32.0 - by) * TILE


def ent(uid, team, bx, by, hp=1000, mx=1000, kind=0, radius=0.5):
    x, y = sub(bx, by)
    return NS(uid=uid, team=team, kind=kind, x=x, y=y, hp=hp, max_hp=mx, radius=radius * TILE)


def towers(own=(1.0, 1.0), foe=(1.0, 1.0), king=1.0):
    """Crown towers as hp fractions (0 = destroyed: dropped from the list, as RoyaleSim may do)."""
    out = [ent(1, 0, 9.0, 29.5, king * 4824, 4824, RT.KING_TOWER, 2.0), ent(4, 1, 9.0, 2.5, 4824, 4824, RT.KING_TOWER, 2.0)]
    for uid, team, (bx, by), f in ((2, 0, (3.5, 25.5), own[0]), (3, 0, (14.5, 25.5), own[1]),
                                   (5, 1, (3.5, 6.5), foe[0]), (6, 1, (14.5, 6.5), foe[1])):
        if f > 0:
            out.append(ent(uid, team, bx, by, f * 3052, 3052, RT.PRINCESS_TOWER, 1.5))
    return out


def state(t, ents, crowns=(0, 0), spells=()):
    return NS(tick=t, entities=list(ents), spells=list(spells), players=[NS(crowns=crowns[0]), NS(crowns=crowns[1])])


def spell(card, bx, by):
    x, y = sub(bx, by)
    return NS(team=0, card_id=card, x=x, y=y, aim_x=x, aim_y=y)


def tracker():
    return RT.CrownTracker(NS(ids={"Tornado": TORNADO, "Rocket": ROCKET}), 0)


def lead_match():
    """0-0, our L princess to 0.8, our KING hit (never charged), we take their L (1-0), our L to 0.5, then it falls while we
    lead 1-0 (1-1: a give-back), then our R takes damage (after the first fall: not charged)."""
    trk = tracker()
    for t, ents, cr in ((100, towers(), (0, 0)), (110, towers(own=(0.8, 1)), (0, 0)),
                        (120, towers(own=(0.8, 1), king=0.9), (0, 0)),
                        (130, towers(own=(0.8, 1), foe=(0, 1), king=0.9), (1, 0)),
                        (140, towers(own=(0.5, 1), foe=(0, 1), king=0.9), (1, 0)),
                        (150, towers(own=(0, 1), foe=(0, 1), king=0.9), (1, 1)),
                        (160, towers(own=(0, 0.6), foe=(0, 1), king=0.9), (1, 1))):
        trk.observe(state(t, ents, cr))
    return trk.result()


START = (14.5, 22.0)


def tornado_match(down: bool, centre=(12.0, 25.0), end=(12.2, 25.0)):
    """A Hog at START on its way in; our Tornado appears at ``centre`` on the stop after it was cast (the Hog has already
    moved a third of the way: the PRE-cast board must be used), drags the Hog to ``end``; our R princess is down first
    when ``down``. A Knight far away (2, 10) never counts."""
    trk = tracker()
    own = (1.0, 0.0) if down else (1.0, 1.0)
    hog = lambda f: ent(50, 1, START[0] + f * (end[0] - START[0]), START[1] + f * (end[1] - START[1]), radius=0.6)  # noqa
    knight = ent(51, 1, 2.0, 10.0)
    cr = (0, int(down))
    trk.observe(state(100, towers(), (0, 0)))
    trk.observe(state(105, towers(own=own), cr))
    trk.observe(state(110, towers(own=own) + [hog(0), knight], cr))
    trk.observe(state(120, towers(own=own) + [hog(1 / 3), knight], cr, [spell(TORNADO, *centre)]))
    trk.observe(state(130, towers(own=own) + [hog(2 / 3), knight], cr, [spell(TORNADO, *centre)]))
    trk.observe(state(140, towers(own=own) + [hog(1), knight], cr))
    return trk.result()


def dist_king(bx, by):
    return float(np.hypot(bx - 9.0, by - 29.5))


# ------------------------------------------------------------------------------------------------------
class TestTracker(unittest.TestCase):
    def test_princess_hp_lost_while_both_stand_then_frozen(self):
        c = lead_match()
        self.assertEqual(c["lost"], [[110, 0.2], [140, 0.5], [150, 1.0]])   # king damage (120) and post-fall (160): none
        self.assertEqual(c["falls"], [{"tick": 130, "who": "foe", "before": [0, 0]},
                                      {"tick": 150, "who": "own", "before": [1, 0]}])
        self.assertEqual(c["end"], {"tick": 160, "king": 0.9, "princess": [0.0, 0.6], "foe_princess": [0.0, 1.0],
                                    "crowns": [1, 1]})
        s = RT.match_summary(c)
        self.assertEqual((s["led_10"], s["gave_back"], s["lost_princess"], s["took_princess"], s["king_end"]),
                         (True, True, True, True, 0.9))

    def test_first_stop_must_show_all_princesses(self):
        with self.assertRaises(ValueError):
            tracker().observe(state(100, towers(own=(1, 0))))

    def test_tornado_toward_king_from_the_pre_cast_board(self):
        c = tornado_match(down=True)
        (e,) = c["tornados"]
        self.assertEqual((e["seen"], e["end"], e["down"], e["n"]), (120, 130, 1, 1))   # the far Knight is not caught
        self.assertAlmostEqual(e["toward"], dist_king(*START) - dist_king(12.2, 25.0), places=3)   # from START, not 1/3
        self.assertGreater(e["toward"], 3.0)
        self.assertEqual(RT.match_summary(c)["tornado_to_king"], 1)

    def test_tornado_pulling_away_or_with_both_princesses(self):
        away = tornado_match(down=True, centre=(14.5, 19.0), end=(14.5, 19.0))["tornados"][0]
        self.assertLess(away["toward"], 0)
        both = tornado_match(down=False)
        self.assertEqual(both["tornados"][0]["down"], 0)
        self.assertEqual(RT.match_summary(both)["tornado_to_king"], 0)    # only after a princess fell
        self.assertGreater(both["tornados"][0]["toward"], 0)

    def test_open_tornado_closes_at_the_match_end(self):
        trk = tracker()
        trk.observe(state(100, towers(), (0, 0)))
        trk.observe(state(110, towers() + [ent(50, 1, 14.5, 22.0)], (0, 0), [spell(TORNADO, 11.0, 27.0)]))
        self.assertEqual(len(trk.result()["tornados"]), 1)
        self.assertEqual(len(trk.result()["tornados"]), 1)                # result() twice: no double close

    def test_rockets_tower_aim(self):
        trk = tracker()
        trk.observe(state(100, towers(), spells=[spell(ROCKET, 4.0, 7.0)]))
        trk.observe(state(105, towers(), spells=[spell(ROCKET, 4.0, 7.0)]))          # the same Rocket still flying
        trk.observe(state(200, towers(), spells=[spell(ROCKET, 9.0, 20.0)]))
        self.assertEqual([(r["seen"], r["tower"]) for r in trk.result()["rockets"]], [(100, True), (200, False)])

    def test_enemy_rocket_and_own_bodies_ignored(self):
        trk = tracker()
        theirs = NS(**{**vars(spell(ROCKET, 4.0, 7.0)), "team": 1})
        trk.observe(state(100, towers() + [ent(60, 0, 11.0, 27.0)], spells=[theirs]))
        trk.observe(state(110, towers() + [ent(60, 0, 11.0, 27.0)], spells=[spell(TORNADO, 11.0, 27.0)]))
        c = trk.result()
        self.assertEqual((c["rockets"], c["tornados"][0]["n"]), ([], 0))


class TestTerms(unittest.TestCase):
    TICKS = np.array([100, 115, 135, 145, 155])

    def test_lead_protect_sign_and_row(self):
        r = RT.row_terms(lead_match(), [], self.TICKS, {"lead_protect": True, "lead_protect_w": 0.2})
        np.testing.assert_allclose(r["r"], [0, 0, 0, -0.2, 0])          # the last kept row before the fall at 150
        self.assertAlmostEqual(r["lead"], -0.2)
        for before in ([0, 0], [1, 1], [2, 0], [0, 1]):                  # no 1-0 lead given back -> nothing
            c = {"falls": [{"tick": 150, "who": "own", "before": before}], "lost": [], "tornados": [], "rockets": []}
            self.assertFalse(RT.row_terms(c, [], self.TICKS, {"lead_protect": True, "lead_protect_w": 0.2})["r"].any())
        foe = {"falls": [{"tick": 150, "who": "foe", "before": [1, 0]}], "lost": [], "tornados": [], "rockets": []}
        self.assertFalse(RT.row_terms(foe, [], self.TICKS, {"lead_protect": True, "lead_protect_w": 0.2})["r"].any())

    def test_redirect_penalty(self):
        p = {"princess_redirect": "penalty", "princess_redirect_w": 0.2}
        r = RT.row_terms(lead_match(), [], self.TICKS, p)
        # L at the rows 0, .2, .2, .5, 1.0 and 1.0 at the end: the damage FOLLOWING each row
        np.testing.assert_allclose(r["r"], [-0.04, 0, -0.06, -0.1, 0])
        self.assertAlmostEqual(r["redirect"], -0.2 * 1.0)
        self.assertIsNone(r["phi"])
        self.assertTrue((r["r"] <= 0).all())
        king_only = {"lost": [], "falls": [], "tornados": [], "rockets": []}   # damage moved onto the king: free
        self.assertFalse(RT.row_terms(king_only, [], self.TICKS, p)["r"].any())

    def test_redirect_potential(self):
        p = {"princess_redirect": "potential", "princess_redirect_w": 0.2}
        r = RT.row_terms(lead_match(), [], self.TICKS, p)
        np.testing.assert_allclose(r["phi"], [0, -0.04, -0.04, -0.1, -0.2])
        self.assertFalse(r["r"].any())

    def test_tornado_penalty_gated_on_a_fallen_princess(self):
        plays = [{"tick": 85, "land_tick": 111, "card": "Tornado", "accepted": True}]
        ticks = np.array([85, 95, 125])
        p = {"tornado_king_penalty": True, "tornado_king_w": 0.01}
        c = tornado_match(down=True)
        r = RT.row_terms(c, plays, ticks, p)
        want = -min(RT.TORNADO_EVENT_CAP, 0.01 * c["tornados"][0]["toward"])
        np.testing.assert_allclose(r["r"], [want, 0, 0])                  # on the row that decided the Tornado
        self.assertLess(want, 0)
        self.assertFalse(RT.row_terms(tornado_match(down=False), plays, ticks, p)["r"].any())   # both princesses up
        away = tornado_match(down=True, centre=(14.5, 19.0), end=(14.5, 19.0))
        self.assertFalse(RT.row_terms(away, plays, ticks, p)["r"].any())  # pulled away from the king
        un = RT.row_terms(c, [], ticks, p)
        self.assertEqual((un["unmapped"], float(un["r"].sum())), (1, 0.0))

    def test_tornado_caps(self):
        evs = [{"seen": 100 + 50 * i, "down": 1, "toward": 40.0} for i in range(4)]
        plays = [{"tick": 90 + 50 * i, "land_tick": 99 + 50 * i, "card": "Tornado", "accepted": True} for i in range(4)]
        c = {"lost": [], "falls": [], "tornados": evs, "rockets": []}
        r = RT.row_terms(c, plays, np.array([90, 140, 190, 240]), {"tornado_king_penalty": True, "tornado_king_w": 0.01})
        np.testing.assert_allclose(r["r"], [-0.15, -0.15, 0, 0])          # event cap 0.15, match cap 0.3
        self.assertAlmostEqual(RT.bound({"tornado_king_penalty": True}), RT.TORNADO_MATCH_CAP)

    def test_off_terms_are_zero(self):
        r = RT.row_terms(lead_match(), [], self.TICKS, {})
        self.assertFalse(r["r"].any())
        self.assertEqual((r["lead"], r["redirect"], r["tornado"], r["phi"]), (0.0, 0.0, 0.0, None))


class TestConfig(unittest.TestCase):
    BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.5}

    def test_crown_cfg(self):
        self.assertIsNone(RL.crown_cfg(self.BASE))
        self.assertIsNone(RL.crown_cfg({**self.BASE, "lead_protect": False, "princess_redirect": None}))
        self.assertEqual(RL.crown_cfg({**self.BASE, "lead_protect": True}), {"lead_protect": True, "lead_protect_w": 0.2})
        self.assertEqual(RL.crown_cfg({**self.BASE, "princess_redirect": "potential", "princess_redirect_w": 0.1}),
                         {"princess_redirect": "potential", "princess_redirect_w": 0.1})
        for bad in ({"lead_protect_w": 0.3}, {"lead_protect": "yes"}, {"princess_redirect": True},
                    {"princess_redirect": "both"}, {"tornado_king_penalty": True, "tornado_king_w": -1},
                    {"lead_protect": True, "advantage": "match_loo"}, {"lead_protect": True, "league": False},
                    {"tornado_king_penalty": 1}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.crown_cfg({**self.BASE, **bad})

    def test_adv_cfg_critic_scale_and_warmup(self):
        for k, v in ON.items():
            RL.adv_cfg({**self.BASE, k: v})                                # 1 + 0.2 / 0.4 / 0.3 <= 1.5
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**self.BASE, "princess_redirect": "penalty", "shaping_critic_scale": 1.3})
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**self.BASE, "lead_protect": True, "critic_warmup_updates": 0})
        with self.assertRaises(SystemExit):                               # two terms together: 1 + 0.2 + 0.4 > 1.5
            RL.adv_cfg({**self.BASE, "lead_protect": True, "princess_redirect": "penalty"})
        self.assertEqual(RL.adv_cfg({**self.BASE, "lead_protect": True}), RL.adv_cfg(self.BASE))   # adv dict unchanged

    def test_hash_absent_is_historical_and_on_differs(self):
        P = _pre_module()
        for path in (YAML, L16):
            cfg = RL.load_config(path, [], False)
            h = RL.config_sha(cfg)
            self.assertEqual(h, P.config_sha(cfg), path.name)              # the historical hash
            for k, wk in RT.TERMS.items():
                for off in (None, False):
                    self.assertEqual(RL.config_sha({**cfg, k: off}), h, (path.name, k, off))
            seen = {h}
            for k, v in [("lead_protect", True), ("princess_redirect", "penalty"), ("princess_redirect", "potential"),
                         ("tornado_king_penalty", True)]:
                on = RL.config_sha({**cfg, k: v})
                self.assertNotIn(on, seen, (k, v))
                seen.add(on)
                wk = RT.TERMS[k]
                self.assertEqual(RL.config_sha({**cfg, k: v, wk: RT.DEFAULTS[wk]}), on)   # implicit = explicit default
                self.assertNotEqual(RL.config_sha({**cfg, k: v, wk: RT.DEFAULTS[wk] * 2}), on)

    def test_arm_yamls_are_the_recipe_plus_one_key(self):
        base = RL.load_config(L16, [], False)
        for name, (k, v) in (("lead", ("lead_protect", True)), ("redirect", ("princess_redirect", "penalty")),
                             ("tornado", ("tornado_king_penalty", True))):
            cfg = RL.load_config(L16.with_name(f"stepd_l16_{name}.yaml"), [], False)
            self.assertEqual(cfg, {**base, k: v}, name)
            self.assertEqual(cfg["seed"], 74)
            self.assertEqual(cfg["live_levels"], "all16")
            RL.adv_cfg(cfg)                                               # validates (critic scale 1.5, warm-up 5)
            ov = RL.load_config(L16, [f"{k}={'on' if v is True else v}"], False)
            self.assertEqual(RL.config_sha(ov), RL.config_sha(cfg))      # the smoke override = the arm

    def test_load_config_override_and_actor_cfg(self):
        P = _pre_module()
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        for kind in ("rollout", "screen"):
            self.assertEqual(RL.actor_cfg(base, kind, 0, "cpu").keys(), P.actor_cfg(base, kind, 0, "cpu").keys())
        off = RL.actor_cfg(base, "rollout", 0, "cpu")
        self.assertNotIn("crown_track", off)
        on = RL.actor_cfg({**base, "crown_track": True}, "rollout", 0, "cpu")
        self.assertTrue(on["crown_track"] and on["record_tick"])
        self.assertNotIn("crown_track", RL.actor_cfg({**base, "crown_track": True}, "screen", 0, "cpu"))
        self.assertEqual({k: v for k, v in on.items() if k not in ("crown_track", "record_tick", "noise")},
                         {k: v for k, v in off.items() if k != "noise"})
        cfg = RL.load_config(YAML, ["princess_redirect=potential", "princess_redirect_w=0.1"], False)
        self.assertEqual((cfg["princess_redirect"], cfg["princess_redirect_w"]), ("potential", 0.1))


def _with_crown(results):
    """Synthetic ticks, plays and crown records on test_rl_royale's trajectories: every match leads 1-0, then its L
    princess loses 0.5 and falls (a give-back); one Tornado (decided on the first played row) pulls 6 tiles toward our
    king after the fall."""
    out = copy.deepcopy(results)
    for r in out:
        n = len(r["traj"]["played"])
        tk = np.arange(n, dtype=np.int64) * 10 + 100
        r["traj"]["tick"] = tk
        j = int(np.flatnonzero(r["traj"]["played"])[-1])
        mid = int(tk[n // 2])
        r["plays"] = [{"tick": int(tk[j]), "land_tick": int(tk[j]) + 26, "card": "Tornado", "accepted": True}]
        r["crown"] = {"lost": [[mid - 15, 0.5], [mid + 5, 1.0]],
                      "falls": [{"tick": mid - 25, "who": "foe", "before": [0, 0]},
                                {"tick": mid + 5, "who": "own", "before": [1, 0]}],
                      "tornados": [{"seen": int(tk[j]) + 30, "end": int(tk[j]) + 50, "down": 1, "toward": 6.0, "n": 2}],
                      "rockets": [], "end": {"tick": int(tk[-1]), "king": 0.7, "princess": [0.0, 1.0],
                                             "foe_princess": [0.0, 1.0], "crowns": [1, 1]}}
    return out


class TestCollate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _with_crown(_results(_tiny_model(0), [(0, 0, 12, "win"), (0, 1, 10, "loss"), (1, 0, 9, "draw")], seed=3,
                                       all_allowed=True))

    def test_each_term_adds_only_its_reward(self):
        B0, st0 = RL.collate(copy.deepcopy(self.res), advantage="gae")
        self.assertNotIn("phi", B0)
        for k, v in ON.items():
            p = RL.crown_cfg({**TestConfig.BASE, k: v})
            B1, st1 = RL.collate(copy.deepcopy(self.res), advantage="gae", crown=p)
            d = B1["r_step"] - B0["r_step"]
            self.assertTrue((d <= 0).all() and d.sum() < 0, k)              # every term is a penalty
            np.testing.assert_array_equal(B1["phi"], np.zeros(len(d)))
            want = 0.0
            for r in self.res:                                             # restated from the kept rows' ticks
                tk = r["traj"]["tick"][r["traj"]["gate_sampled"] | r["traj"]["played"]]
                fall = r["crown"]["falls"][1]["tick"]
                want += {"lead_protect": -0.2 * bool((tk <= fall).any()),
                         "princess_redirect": -0.2 * (1.0 - float(RT.lost_at(r["crown"], tk[:1])[0])),
                         "tornado_king_penalty": -0.01 * 6.0}[k]
            self.assertLess(want, 0)
            self.assertAlmostEqual(float(d.sum()), want, places=9, msg=k)
            self.assertEqual({kk: vv for kk, vv in st1.items() if kk != "crown"}, st0)
            self.assertEqual(st1["crown"]["gave_back_per_match"], 1.0)
            for key in B0:
                if key != "r_step":
                    np.testing.assert_array_equal(B0[key], B1[key], err_msg=f"{k} {key}")

    def test_potential_goes_into_phi_not_rewards(self):
        B0, _ = RL.collate(copy.deepcopy(self.res), advantage="gae")
        p = RL.crown_cfg({**TestConfig.BASE, "princess_redirect": "potential"})
        B1, _ = RL.collate(copy.deepcopy(self.res), advantage="gae", crown=p)
        np.testing.assert_array_equal(B1["r_step"], B0["r_step"])
        self.assertTrue((B1["phi"] <= 0).all())
        self.assertAlmostEqual(float(B1["phi"].min()), -0.2)

    def test_missing_record_or_match_loo_refused(self):
        p = RL.crown_cfg({**TestConfig.BASE, "lead_protect": True})
        bare = copy.deepcopy(self.res)
        del bare[0]["crown"]
        with self.assertRaises(ValueError):
            RL.collate(bare, advantage="gae", crown=p)
        with self.assertRaises(ValueError):
            RL.collate(copy.deepcopy(self.res), advantage="match_loo", crown=p)


class TestAbsentIsPre(_Tmp):
    """Every key absent / null / false: collate, whole gae updates (records, weights, beta, rng) and the checkpoint's rl keys
    are those of PRE; crown records in the results are ignored without a key."""

    @classmethod
    def setUpClass(cls):
        cls.P = _pre_module()
        cls.model = _tiny_model(6)
        cls.results = _with_crown(_monitor_fields(_results(cls.model, SPEC, seed=13)))

    def test_collate_identical(self):
        for adv in ("match_loo", "gae"):
            Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
            self.assertEqual(sn, sp)

    def test_adv_cfg_identical(self):
        for cfg in ({}, dict(GAE), RL.load_config(L16, [], False)):
            self.assertEqual(RL.adv_cfg(cfg), self.P.adv_cfg(cfg))

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        runs = {}
        nulls = {k: None for k in RT.TERMS}
        falses = {"lead_protect": False, "princess_redirect": False, "tornado_king_penalty": False}
        for name, mod, extra in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, nulls), ("false", RL, falses)):
            L = _learner(mod, self.model, self.results, self.tmp / name, **GAE, **extra)
            recs = [_strip(L.one_update(u)[0]) for u in range(2)]
            ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
            runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                          L.rng.bit_generator.state, sorted(ck["rl"]), ck["rl"]["config_sha256"])
        recs_p, beta_p, sd_p, rng_p, keys_p, sha_p = runs["pre"]
        for name in ("absent", "null", "false"):
            recs, beta, sd, rng, keys, sha = runs[name]
            self.assertEqual(recs, recs_p, name)
            self.assertEqual((beta, rng, keys, sha), (beta_p, rng_p, keys_p, sha_p), name)
            for k in sd_p:
                self.assertTrue(torch.equal(sd[k], sd_p[k]), (name, k))
        self.assertFalse(any('"crown"' in r for r in runs["absent"][0]))


class TestOneUpdateOn(_Tmp):
    """Each key on: a whole gae update runs, logs the crown monitors and changes the config hash."""

    def test_each_key(self):
        model = _tiny_model(6)
        res = _with_crown(_monitor_fields(_results(model, SPEC, seed=13)))
        shas = set()
        for k, v in list(ON.items()) + [("princess_redirect", "potential")]:
            L = _learner(RL, model, res, self.tmp / f"{k}_{v}", **GAE, league=True, **{k: v})
            rec = L.one_update(0)[0]
            rec = L.one_update(1)[0]                                       # past the critic warm-up: a policy step
            self.assertIn("crown", rec, k)
            self.assertEqual(rec["crown"]["matches"], len(SPEC))
            ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
            shas.add(ck["rl"]["config_sha256"])
        self.assertEqual(len(shas), 4)


class TestSelfPlayWiring(unittest.TestCase):
    """e1_eval's real SelfPlayMatch on test_league's fake env with a fake engine core: the crown record appears only with
    crown_track, and every recorded traj array is byte-identical either way (the tracker never changes play)."""

    def _run(self, **cfg):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL

        class Env(TL._SPEnv):
            ids = {"Tornado": TORNADO, "Rocket": ROCKET}

            def reset(self, *a, **k):
                st = super().reset(*a, **k)
                self.core = NS(state=lambda: state(self.tick, towers(own=(1.0, 0.7) if self.tick >= 120 else (1, 1))))
                return st

        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", 0), 0, {"rollout_index": 0, "update": 0})]
        res, _ = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))},
                         TL._cfg(record_tick=True, **cfg), make_env=Env, n=1)
        return res[0]

    def test_crown_record_and_identical_play(self):
        on, off = self._run(crown_track=True), self._run()
        self.assertNotIn("crown", off)
        self.assertEqual(on["crown"]["lost"][0][1], 0.3)
        self.assertEqual(on["crown"]["end"]["princess"], [1.0, 0.7])
        self.assertEqual(sorted(on["traj"]), sorted(off["traj"]))
        for k in off["traj"]:
            self.assertEqual(off["traj"][k].tobytes(), on["traj"][k].tobytes(), k)
        self.assertEqual(on["plays"], off["plays"])
        self.assertEqual(RT.crown_log(on)["summary"]["lost_princess"], False)
        self.assertIsNone(RT.crown_log(off))


if __name__ == "__main__":
    unittest.main()
