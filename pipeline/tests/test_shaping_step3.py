"""Step-3 potentials (L74 reward/REWARD_ARCHITECTURE.md A2 solvency, A1 + A1b tower_score): pipeline/reward_shaping.py
rows + Phi, and their opt-in wiring in pipeline/rl_royale.py / e1_eval.py.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_shaping_step3.py

Pure python on synthetic raw() states and synthetic trajectories; no engine. Covers the section-9 unit checks (level
normalisation, foe king weight 0, solvency 0 with no push, a spell never in T_incoming), telescoping, the magnitude
bound over an exhaustive tower grid, adv_cfg / load_config / actor_cfg / collate / one_update wiring, and the e1_eval
record on the real SelfPlayMatch (test_league's fake env).
"""
from __future__ import annotations

import copy
import itertools
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import reward_shaping as RS                                 # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, _learner, _Tmp               # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

P = RS.STATE_PHI_DEFAULTS
# RoyaleSim catalogue rows (elixir, count, hitpoints, kind), level 11, as card_table builds them
CARDS = {0: (3.0, 1, 1766.0, "TROOP"), 7: (5.0, 1, 839.0, "TROOP"), 12: (3.0, 15, 81.0, "TROOP"),
         99: (4.0, 1, 1182.0, "BUILDING"), 111: (6.0, 0, 0.0, "SPELL"), 112: (3.0, 0, 0.0, "SPELL")}
KNIGHT, WITCH, SKARMY, TESLA, ROCKET, BARREL = 0, 7, 12, 99, 111, 112
KING, PRINCESS = 4824, 3052                      # level 11
KING15, PRINCESS15 = 6408, 4424                  # level 15 (live)


def ent(side, card, x, y, hp=None, max_hp=None, kind=None, eid=None):
    """A raw() body; kind as raw() gives it (EntityKind TROOP 0 / BUILDING 1, 12 = deploying)."""
    mx = CARDS[card][2] if max_hp is None else max_hp
    kind = int(CARDS[card][3] == "BUILDING") if kind is None else kind
    return {"side": side, "card_id": card, "x": x, "y": y, "hp": mx if hp is None else hp, "max_hp": mx, "kind": kind,
            "entity_id": eid if eid is not None else hash((side, card, x, y)) % 10 ** 6, "name": str(card)}


def sstate(ents=(), e0=5.0, e1=5.0, effects=(), tick=1000):
    return {"tick": tick, "players": [{"side": 0, "elixir_exact": e0}, {"side": 1, "elixir_exact": e1}],
            "entities": list(ents), "effects": list(effects), "episode": {"crown_towers": []}}


def mirror(st):
    """The same board seen from the other seat: sides swapped, coordinates rotated (own frame of side s = side 1-s)."""
    out = copy.deepcopy(st)
    for e in out["entities"]:
        e["side"], e["x"], e["y"] = 1 - e["side"], 18000 - e["x"], 32000 - e["y"]
    for p in out["players"]:
        p["side"] = 1 - p["side"]
    for t in out["episode"]["crown_towers"]:
        t["side"] = 1 - t["side"]
    return out


def tstate(own=(1, 1, 1), foe=(1, 1, 1), tick=0, level=11, crowns=None):
    """Towers as hp FRACTIONS (king, princess, princess) for side 0 (own) and side 1 (foe) at a tower level."""
    k, p = (KING, PRINCESS) if level == 11 else (KING15, PRINCESS15)
    tw = [{"side": s, "type": typ, "x": float(i), "y": 0.0, "hp": round(f * mx), "max_hp": mx,
           "destroyed": round(f * mx) <= 0}
          for s, fr in ((0, own), (1, foe)) for i, (typ, mx, f) in enumerate(zip(("king", "princess", "princess"),
                                                                                    (k, p, p), fr))]
    st = {"tick": tick, "players": [], "entities": [], "effects": [], "episode": {"crown_towers": tw}}
    if crowns is not None:
        st["crowns"] = list(crowns)
    return st


def ts_phi(st, side=0, p=P):
    return float(RS.phi_tower_score(RS.tower_score_record(st, side), p)[0])


# ------------------------------------------------------------------------------------------------------
class TestSolvency(unittest.TestCase):
    def rec(self, *states, side=0, cards=CARDS):
        prev = {}
        return [RS.solvency_record(s, side, cards, prev) for s in states][-1]

    def phi(self, row, **kw):
        return float(RS.phi_solvency(row, {**P, **kw})[0])

    def test_zero_when_no_push(self):
        """Enemy troops on their half not walking toward me (first sighting, standing still or walking away), enemy
        buildings anywhere, own units: Phi = 0 at ANY own elixir -- no hoarding incentive in quiet play."""
        quiet = [ent(1, KNIGHT, 3000, 25000, eid=1), ent(1, TESLA, 9000, 22000, eid=2), ent(0, KNIGHT, 3000, 9000, eid=3)]
        for e0 in (0.0, 3.0, 10.0):
            row = self.rec(sstate(quiet, e0=e0))
            self.assertEqual(row[:2], [0.0, 0.0])
            self.assertEqual(self.phi(row), 0.0)
        away = [ent(1, KNIGHT, 3000, 25000 + 500, eid=1)]           # second sighting further back
        row = self.rec(sstate([ent(1, KNIGHT, 3000, 25000, eid=1)]), sstate(away, e0=0.0))
        self.assertEqual(self.phi(row), 0.0)
        building_on_my_half = [ent(1, TESLA, 3000, 12000, eid=5)]  # never a "push"
        self.assertEqual(self.rec(sstate(building_on_my_half, e0=0.0))[:2], [0.0, 0.0])

    def test_spell_never_counted(self):
        """Spell effects and the bodies a SPELL card makes (Goblin Barrel goblins) never enter T_incoming, at any
        kind or position; the same board with a real troop instead does."""
        spells = [ent(1, BARREL, 3000, 4000, hp=200, max_hp=200, kind=0, eid=7),
                  ent(1, ROCKET, 3000, 5000, hp=1, max_hp=1, kind=12, eid=8)]
        eff = [{"side": 1, "x": 3000, "y": 4000, "name": "Rocket"}, {"side": 1, "x": 3000, "y": 6000, "name": "Log"}]
        row = self.rec(sstate(spells, e0=0.0, effects=eff), sstate(spells, e0=0.0, effects=eff))
        self.assertEqual(row[:2], [0.0, 0.0])
        self.assertEqual(self.phi(row), 0.0)
        self.assertIsNone(RS.body_value(spells[0], CARDS))
        row = self.rec(sstate([ent(1, KNIGHT, 3000, 4000, eid=9)], e0=0.0))
        self.assertAlmostEqual(row[0], 3.0)

    def test_commit_definition(self):
        """On my half -> counted at once; on their half -> counted once it walked toward me > MOVE_EPS."""
        a, b = sstate([ent(1, KNIGHT, 3000, 20000, eid=1)]), sstate([ent(1, KNIGHT, 3000, 19000, eid=1)])
        self.assertEqual(self.rec(a)[0], 0.0)                         # first sighting on their half
        self.assertAlmostEqual(self.rec(a, b)[0], 3.0)                 # walked 1 tile toward me
        self.assertEqual(self.rec(a, a)[0], 0.0)                       # standing (deploying / fighting)
        tiny = sstate([ent(1, KNIGHT, 3000, 20000 - RS.MOVE_EPS, eid=1)])
        self.assertEqual(self.rec(a, tiny)[0], 0.0)
        self.assertAlmostEqual(self.rec(sstate([ent(1, KNIGHT, 3000, 15000, eid=1)]))[0], 3.0)   # my half
        dep = sstate([ent(1, KNIGHT, 3000, 15000, kind=12, eid=1), ent(1, TESLA, 3000, 15000, kind=12, eid=2)])
        self.assertAlmostEqual(self.rec(dep)[0], 3.0)                  # deploying troop yes, deploying building no

    def test_formula_lanes_and_cap(self):
        knight_left = ent(1, KNIGHT, 3000, 12000, eid=1)
        st = sstate([knight_left], e0=1.0)
        row = self.rec(st)
        self.assertEqual(row, [3.0, 0.0, 0.0, 0.0, 1.0])
        self.assertAlmostEqual(self.phi(row), -P["shaping_solv_w"] * 2.0)
        # an own Knight in the OTHER lane does not defend; one in the push's lane or a centre Tesla does
        other = self.rec(sstate([knight_left, ent(0, KNIGHT, 15000, 8000, eid=2)], e0=1.0))
        self.assertAlmostEqual(self.phi(other), self.phi(row))
        same = self.rec(sstate([knight_left, ent(0, KNIGHT, 3000, 8000, eid=2)], e0=1.0))
        self.assertEqual(self.phi(same), 0.0)
        centre = self.rec(sstate([knight_left, ent(0, TESLA, 9000 + RS.CENTRE_BAND, 8000, eid=3)], e0=0.0))
        self.assertEqual((centre[2], centre[3]), (4.0, 4.0))
        self.assertEqual(self.phi(centre), 0.0)
        own_on_their_half = self.rec(sstate([knight_left, ent(0, KNIGHT, 3000, 20000, eid=2)], e0=1.0))
        self.assertEqual(own_on_their_half[2], 0.0)
        big = self.rec(sstate([ent(1, KNIGHT, 3000 + i, 12000, eid=10 + i) for i in range(9)], e0=0.0))
        self.assertAlmostEqual(big[0], 27.0)
        self.assertAlmostEqual(self.phi(big), -P["shaping_solv_w"] * P["shaping_solv_cap"])
        self.assertAlmostEqual(self.phi(row, shaping_solv_k=0.5), -P["shaping_solv_w"] * 0.5)

    def test_body_values(self):
        """hp-scaled; a spawned body is worth its share of the spawner's deployed hp; a swarm unit 1/count."""
        self.assertAlmostEqual(RS.body_value(ent(1, KNIGHT, 0, 0, hp=883), CARDS), 1.5)
        self.assertAlmostEqual(RS.body_value(ent(1, WITCH, 0, 0, hp=81, max_hp=81), CARDS), 5 * 81 / 839)
        self.assertAlmostEqual(RS.body_value(ent(1, SKARMY, 0, 0), CARDS), 0.2)
        self.assertIsNone(RS.body_value(ent(1, KNIGHT, 0, 0) | {"card_id": 55555}, CARDS))
        cat = RS.card_table([SimpleNamespace(card_id=0, elixir=3, count=1, hitpoints=1766, card_kind="TROOP")])
        self.assertEqual(cat, {0: (3.0, 1, 1766.0, "TROOP")})

    def test_level_normalisation(self):
        """The same fractional board at level 15 (every hp x 1.45, catalogue too) gives the same row."""
        def board(scale):
            cards = {k: (v[0], v[1], v[2] * scale, v[3]) for k, v in CARDS.items()}
            es = [ent(1, KNIGHT, 3000, 12000, hp=900 * scale, max_hp=1766 * scale, eid=1),
                  ent(1, WITCH, 14000, 14000, hp=60 * scale, max_hp=81 * scale, eid=2),
                  ent(0, TESLA, 4000, 7000, hp=600 * scale, max_hp=1182 * scale, eid=3)]
            return self.rec(sstate(es, e0=2.0), cards=cards)
        np.testing.assert_allclose(board(1.0), board(1.45), rtol=1e-12)

    def test_side_symmetry(self):
        a = sstate([ent(1, KNIGHT, 3000, 20000, eid=1), ent(0, TESLA, 9000, 7000, eid=2)], e0=2.0, e1=7.0)
        b = sstate([ent(1, KNIGHT, 3000, 18000, eid=1), ent(0, TESLA, 9000, 7000, eid=2)], e0=2.0, e1=7.0)
        self.assertEqual(self.rec(a, b, side=0), self.rec(mirror(a), mirror(b), side=1))


# ------------------------------------------------------------------------------------------------------
class TestTowerScore(unittest.TestCase):
    def test_start_is_zero(self):
        for tick in (0, 2400, 4000, 6000, 7000):
            self.assertAlmostEqual(ts_phi(tstate(tick=tick)), 0.0, places=12)

    def test_foe_king_weight_zero(self):
        """Foe king hp never moves Phi -- any crown state, any time, also through the tiebreak term."""
        for own, foe_pr, tick in itertools.product(((1, 1, 1), (1, .3, 0), (.6, 0, .2)), ((1, 1), (.4, 0), (0, 0), (.2, .7)),
                                                   (0, 3000, 6000)):
            vals = {round(ts_phi(tstate(own, (kf, *foe_pr), tick)), 12) for kf in (1.0, 0.7, 0.3, 0.05)}
            self.assertEqual(len(vals), 1, (own, foe_pr, tick, vals))

    def test_level_normalisation(self):
        cases =[((1, .5, .2), (.8, 1, 1), 0), ((.9, 0, .4), (1, .3, 0), 5000), ((.3, 0, 0), (.5, 0, .1), 6100)]
        for own, foe, tick in cases:
            r11 = RS.tower_score_record(tstate(own, foe, tick, 11), 0)
            r15 = RS.tower_score_record(tstate(own, foe, tick, 15), 0)
            np.testing.assert_allclose(r11, r15, atol=2e-3)            # hp rounding only
            self.assertAlmostEqual(ts_phi(tstate(own, foe, tick, 11)), ts_phi(tstate(own, foe, tick, 15)), places=2)

    def test_concave_and_crown_weights(self):
        """h concave: the last half of an own princess costs more than the first; ahead 1-0 own towers weigh more and
        the remaining foe princess less; at 1-1 the remaining foe princess carries the whole foe weight."""
        full, half, dead = ts_phi(tstate((1, 1, 1))), ts_phi(tstate((1, .5, 1))), ts_phi(tstate((1, .01, 1)))
        self.assertLess(full - half, half - dead)
        h = (lambda f: 1 - (1 - f) ** P["shaping_ts_h_power"])
        w_own, w_foe = P["shaping_ts_w_own"], P["shaping_ts_w_foe"]
        ahead = tstate((1, 1, .5), (1, 0, .6))                           # 1-0
        self.assertAlmostEqual(ts_phi(ahead), w_own[2] * (2 + h(.5)) / 3 - w_foe[2] * .6, places=3)
        oneone = tstate((1, 0, .5), (1, 0, .6))                          # 1-1, before 2x (no tiebreak term)
        self.assertAlmostEqual(ts_phi(oneone), w_own[1] * (1 + h(.5)) / 3 - w_foe[1] * .6, places=3)
        behind = tstate((1, 0, 1), (1, .5, .5))                           # 0-1
        self.assertAlmostEqual(ts_phi(behind), w_own[0] * 2 / 3 - w_foe[0] * .5, places=3)

    def test_tiebreak_term(self):
        """Weakest standing tower margin (princess units, own king x KING_PER_PRINCESS), ramp 0 before 2x -> 1 at the
        end of overtime; concentrating damage on ONE foe princess raises Phi late, not in 1x."""
        spread, focus = (1, .6, .6), (1, .2, 1.0)                       # same foe total
        self.assertAlmostEqual(ts_phi(tstate(foe=spread, tick=2000)), ts_phi(tstate(foe=focus, tick=2000)), places=3)
        d_ot = ts_phi(tstate(foe=focus, tick=6000)) - ts_phi(tstate(foe=spread, tick=6000))
        self.assertAlmostEqual(d_ot, P["shaping_ts_w_tb"] * .4, places=3)
        mid = ts_phi(tstate(foe=focus, tick=4200)) - ts_phi(tstate(foe=spread, tick=4200))
        self.assertAlmostEqual(mid, d_ot / 2, places=3)
        row = RS.tower_score_record(tstate(own=(.5, 0, .9), foe=(.1, .8, 0)), 0)
        self.assertAlmostEqual(row[6], .5 * RS.KING_PER_PRINCESS, places=3)   # own king the weakest in absolute hp
        self.assertAlmostEqual(row[7], .8, places=3)                     # foe king (.1) never counted

    def test_side_symmetry(self):
        st = tstate((1, .3, 0), (.9, .7, .5), tick=4500)
        np.testing.assert_allclose(RS.tower_score_record(st, 0), RS.tower_score_record(mirror(st), 1))


# ------------------------------------------------------------------------------------------------------
class TestBoundAndTelescoping(unittest.TestCase):
    def test_bound_holds_and_is_within_budget(self):
        """Exhaustive tower grid (fractions, crowns, ticks): max |Phi| <= phi_bound <= 0.5 and close to it; solvency
        on random rows likewise."""
        self.assertLessEqual(RS.phi_bound("tower_score", P), 0.5)
        self.assertLessEqual(RS.phi_bound("solvency", P), 0.5)
        g = (0.0, 0.01, 0.3, 1.0)
        rows = np.array([[ok, o1, o2, fk, f1, f2, min([x for x in (o1, o2) if x > 0] + [ok * RS.KING_PER_PRINCESS]),
                          min([x for x in (f1, f2) if x > 0], default=0.0), 2 - (f1 > 0) - (f2 > 0),
                          2 - (o1 > 0) - (o2 > 0), t]
                         for ok, o1, o2, fk, f1, f2, t in itertools.product((0.01, .5, 1.0), g, g, (.01, 1.0), g, g,
                                                                           (0, 4000, 6000))])
        m = float(np.abs(RS.phi_tower_score(rows, P)).max())
        self.assertLessEqual(m, RS.phi_bound("tower_score", P) + 1e-12)
        self.assertGreater(m, 0.9 * RS.phi_bound("tower_score", P))
        rng = np.random.default_rng(0)
        srows = np.concatenate([rng.uniform(0, 30, (5000, 4)), rng.uniform(0, 10, (5000, 1))], axis=1)
        self.assertLessEqual(float(np.abs(RS.phi_solvency(srows, P)).max()), RS.phi_bound("solvency", P) + 1e-12)

    def test_telescoping(self):
        """Through rl_royale.shaping_rewards: sum F = -Phi(s0) at gamma 1, and the per-row-gamma discounted sum too."""
        rng = np.random.default_rng(1)
        for mode, rows in (("solvency", np.concatenate([rng.uniform(0, 12, (60, 4)), rng.uniform(0, 10, (60, 1))], 1)),
                           ("tower_score", np.concatenate([rng.uniform(0, 1, (60, 8)), rng.integers(0, 2, (60, 2)),
                                                           np.sort(rng.integers(0, 7000, (60, 1)), 0)], 1))):
            phi0 = RS.state_phi(mode, rows[:1], P)[0]
            sh = RL.shaping_rewards(rows, {"mode": mode, "gamma": 1.0, "params": P})
            self.assertAlmostEqual(float(sh["F"].sum()), -phi0, places=12)
            np.testing.assert_array_equal(sh["phi"], RS.state_phi(mode, rows, P))
            gam = rng.uniform(0.9, 1.0, len(rows))
            sh = RL.shaping_rewards(rows, {"mode": mode, "gamma": gam, "params": P})
            disc = np.concatenate([[1.0], np.cumprod(gam[:-1])])
            self.assertAlmostEqual(float((disc * sh["F"]).sum()), -phi0, places=12)


# ------------------------------------------------------------------------------------------------------
class TestWiring(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def _with_rows(self, mode, seed=0):
        rng = np.random.default_rng(seed)
        out = copy.deepcopy(self.results)
        for r in out:
            n = len(r["traj"]["played"])
            r["traj"]["phi_state"] = (np.concatenate([rng.uniform(0, 12, (n, 4)), rng.uniform(0, 10, (n, 1))], 1)
                                      if mode == "solvency" else
                                      np.concatenate([rng.uniform(0, 1, (n, 8)), rng.integers(0, 2, (n, 2)),
                                                      np.arange(n)[:, None] * 100.0], 1))
        return out

    def test_adv_cfg(self):
        base = {"advantage": "gae", "critic_warmup_updates": 1}
        for mode in RS.STATE_PHI_MODES:
            c = RL.adv_cfg({**base, "shaping": mode})
            self.assertEqual({k: c[k] for k in RL.STATE_PHI_KEYS}, P)
            for bad in ({"shaping": mode}, {**base, "shaping": mode, "critic_warmup_updates": 0},
                        {**base, "shaping": mode, "shaping_critic_scale": 1.3}):
                with self.assertRaises(SystemExit, msg=bad):
                    RL.adv_cfg(bad)
        self.assertNotIn("shaping_solv_w", RL.adv_cfg({**base, "shaping": "tower_crown"}))
        for k, v in (("shaping_solv_w", -0.1), ("shaping_solv_cap", 0), ("shaping_ts_h_power", 0.5),
                     ("shaping_ts_w_own", [0.1, 0.2]), ("shaping_ts_w_foe", [0.1, -0.2, 0.3]), ("shaping_ts_w_tb", "x")):
            with self.assertRaises(SystemExit, msg=k) as cm:
                RL.adv_cfg({**base, "shaping": "tower_score", k: v})
            self.assertIn(k, str(cm.exception))
        with self.assertRaises(SystemExit) as cm:                         # w x cap = 0.6 -> scale 1.5 < 1.6
            RL.adv_cfg({**base, "shaping": "solvency", "shaping_solv_w": 0.06})
        self.assertIn("phi_bound", str(cm.exception))
        RL.adv_cfg({**base, "shaping": "solvency", "shaping_solv_w": 0.06, "shaping_critic_scale": 1.6})

    def test_config_and_actor(self):
        """The yaml carries none of the new keys (historical config hash); overrides are accepted; the rollout actor
        records the mode's row, the screen actor none."""
        path = REPO / "pipeline" / "rl_royale.yaml"
        cfg = RL.load_config(path, [], False)
        self.assertFalse(set(RL.STATE_PHI_KEYS) & set(cfg))
        on = RL.load_config(path, ["advantage=gae", "shaping=solvency", "shaping_solv_w=0.03"], False)
        self.assertEqual(on["shaping_solv_w"], 0.03)
        self.assertNotEqual(RL.config_sha(on), RL.config_sha(cfg))
        base = {**cfg, "grid": "lattice"}
        self.assertNotIn("record_phi", RL.actor_cfg(base, "rollout", 0, "cpu"))
        for mode in RS.STATE_PHI_MODES:
            self.assertEqual(RL.actor_cfg({**base, "shaping": mode}, "rollout", 0, "cpu")["record_phi"], mode)
            self.assertNotIn("record_phi", RL.actor_cfg({**base, "shaping": mode}, "screen", 0, "cpu"))

    def test_collate(self):
        for mode in RS.STATE_PHI_MODES:
            res = self._with_rows(mode)
            shp = {"mode": mode, "gamma": 0.9, "params": P}
            B, st = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping=shp)
            Bd, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae")
            self.assertEqual(sorted(B), sorted(list(Bd) + ["phi"]))
            for k in Bd:
                self.assertEqual(B[k].tobytes(), Bd[k].tobytes(), k)      # r_step stays the unshaped reward
            for j, r in enumerate(res):
                t = r["traj"]
                want = RS.state_phi(mode, t["phi_state"][t["gate_sampled"] | t["played"]], P)
                np.testing.assert_array_equal(B["phi"][B["match"] == j], want)
            self.assertEqual(st["shaping"]["mode"], mode)
            self.assertLessEqual(st["shaping"]["max_abs_phi"], RS.phi_bound(mode, P))

    def test_one_update(self):
        for mode in RS.STATE_PHI_MODES:
            L = _learner(RL, self.model, self._with_rows(mode, 2), self.tmp / mode, advantage="gae",
                         critic_warmup_updates=1, shaping=mode)
            for u in range(2):
                rec, _, crash = L.one_update(u)
                self.assertFalse(crash)
                self.assertEqual(rec["gae"]["shaping"], mode)
                self.assertEqual(rec["shaping"]["mode"], mode)
                self.assertEqual(rec["shaping"]["rows"], rec["rows"])
            self.assertTrue(any(f"| {mode} |F|" in m for m in L.log.lines))


# ------------------------------------------------------------------------------------------------------
class TestRecording(unittest.TestCase):
    """e1_eval's real SelfPlayMatch on test_league's fake env (+ a catalogue, troop kinds, a fast Hog): one row per
    recorded decision from the LEARNER's side, = the mode's state_record."""

    def _run(self, side, mode):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL

        class Env(TL._SPEnv):
            core = SimpleNamespace(cards=lambda: [
                SimpleNamespace(card_id=26000000, elixir=3, count=1, hitpoints=1400, card_kind="TROOP"),
                SimpleNamespace(card_id=26000021, elixir=4, count=1, hitpoints=1697, card_kind="TROOP")])

            def raw(self):
                st = super().raw()
                for e in st["entities"]:
                    e["kind"] = 0
                st["entities"][1]["y"] = 20000 - 50 * (self.tick - 90)     # the Hog walks 0.5 tile / decision
                return st

        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", side), 0, {"rollout_index": 0, "update": 0})]
        res, envs = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))},
                            TL._cfg(record_phi=mode), make_env=Env, n=1)
        return res[0]["traj"]["phi_state"]

    def test_rows(self):
        ts = self._run(0, "tower_score")
        self.assertEqual(ts.shape[1], 11)
        self.assertTrue((np.diff(ts[:, 10]) > 0).all())                  # the decision tick
        s0, s1 = self._run(0, "solvency"), self._run(1, "solvency")
        self.assertEqual(s0.shape[1], 5)
        hog = 4.0 * 1200 / 1697
        self.assertEqual(s0[0, 1], 0.0)                                   # first sighting on their half
        np.testing.assert_allclose(s0[1:, 1], hog)                         # then walking toward side 0 (right lane)
        self.assertTrue((s1[:, :2] == 0).all())                            # side 1: the fake Knight crawls < MOVE_EPS
        self.assertAlmostEqual(s1[0, 2], hog)                              # ... and its own Hog defends (own frame left)


if __name__ == "__main__":
    unittest.main()
