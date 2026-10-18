"""Offline tests for pipeline/spell_value.py (L74 combo reward) and its rl_royale wiring.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_spell_value -v

No engine: the tracker runs on hand-built states shaped like royalegym's BattleState (tick, spells, entities, game_over),
the reward on hand-built events; the collate test uses test_rl_royale's synthetic trajectories (the real sampler)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import spell_value as SV                           # noqa: E402

P = {k: float(v) for k, v in SV.DEFAULTS.items()}
ROCKET, TORNADO = 111, 120
T = SV.TILE


def sub(bx, by):
    """Board tiles in side 0's frame -> engine subtiles (to_board's inverse)."""
    return bx * T, (32.0 - by) * T


def ev(kill=0.0, dmg=0.0, princess=False, king=False, cost=6, tornado=None, tick=200, seen=110, aim=(9.0, 10.0)):
    return {"tick": tick, "seen": seen, "aim": aim, "cost": cost, "kill": kill, "dmg": dmg, "bodies": [],
            "princess": princess, "king": king, "tower_dmg": 0, "tornado": tornado}


class TestEventReward(unittest.TestCase):
    def test_miss_costs_the_rocket(self):
        self.assertAlmostEqual(SV.event_reward(ev(), P)[2], -0.12)              # 6 elixir for nothing

    def test_net_of_cost_and_damage_share(self):
        v, g, r = SV.event_reward(ev(kill=9.0, dmg=1.0), P)                     # Wizard + Musketeer killed, Knight 1/3
        self.assertAlmostEqual(v, 9.5)
        self.assertAlmostEqual(g, 9.5)
        self.assertAlmostEqual(r, 0.02 * (9.5 - 6.0))

    def test_princess_with_a_clump_bonus_and_no_cost(self):
        v, g, r = SV.event_reward(ev(kill=9.0, dmg=1.0, princess=True), P)
        self.assertAlmostEqual(g, 9.5 * 1.5)
        self.assertAlmostEqual(r, 0.02 * 14.25)

    def test_princess_alone_is_neutral_and_below_min_no_bonus(self):
        self.assertEqual(SV.event_reward(ev(princess=True), P)[2], 0.0)           # a tower Rocket: the win reward's job
        v, g, r = SV.event_reward(ev(kill=1.0, princess=True), P)              # one Knight-ish body < tower_min
        self.assertAlmostEqual(g, 1.0)
        self.assertAlmostEqual(r, 0.02)

    def test_king_hit_is_not_exempt(self):
        self.assertAlmostEqual(SV.event_reward(ev(king=True), P)[2], -0.12)

    def test_event_cap(self):
        self.assertAlmostEqual(SV.event_reward(ev(kill=40.0, princess=True), P)[2], P["spell_value_event_cap"])
        self.assertAlmostEqual(SV.event_reward(ev(cost=100), P)[2], -P["spell_value_event_cap"])


class TestRowRewards(unittest.TestCase):
    PLAYS = [{"tick": 60, "land_tick": 86, "card": "tornado", "accepted": True},
             {"tick": 70, "land_tick": 96, "card": "rocket", "accepted": False},      # refused: never credited
             {"tick": 74, "land_tick": 100, "card": "rocket", "accepted": True},
             {"tick": 84, "land_tick": 110, "card": "knight", "accepted": True}]
    TICKS = [40, 50, 60, 70, 74, 84]

    def test_rocket_row_gets_it(self):
        out = SV.row_rewards([ev(kill=9.0, dmg=1.0, seen=101)], self.PLAYS, self.TICKS, P)
        want = np.zeros(6)
        want[4] = 0.02 * 3.5
        np.testing.assert_allclose(out["r"], want)
        self.assertEqual(out["events"][0]["row"], 4)

    def test_combo_split_by_cost_with_the_tornado_row(self):
        e = ev(kill=9.0, dmg=1.0, princess=True, seen=101, tornado={"seen": 95, "aim": (9.0, 11.0), "cost": 3})
        out = SV.row_rewards([e], self.PLAYS, self.TICKS, P)
        self.assertAlmostEqual(out["r"][4], 0.285 * 2 / 3)
        self.assertAlmostEqual(out["r"][2], 0.285 / 3)
        self.assertAlmostEqual(out["r"].sum(), 0.285)
        self.assertEqual((out["events"][0]["row"], out["events"][0]["tornado_row"]), (4, 2))

    def test_combo_miss_charges_both_rows(self):
        e = ev(seen=101, tornado={"seen": 95, "aim": (9.0, 11.0), "cost": 3})
        out = SV.row_rewards([e], self.PLAYS, self.TICKS, P)
        self.assertAlmostEqual(out["r"][4], -0.08)
        self.assertAlmostEqual(out["r"][2], -0.04)

    def test_match_cap_running_sum(self):
        evs = [ev(kill=40.0, princess=True, tick=t, seen=101) for t in (200, 300, 400)]
        out = SV.row_rewards(evs, self.PLAYS, self.TICKS, P)
        self.assertEqual([e["reward"] for e in out["events"]], [0.3, 0.2, 0.0])
        self.assertAlmostEqual(out["r"].sum(), 0.5)

    def test_unmapped_event_lands_nowhere(self):
        out = SV.row_rewards([ev(kill=9.0, seen=500)], self.PLAYS, self.TICKS, P)   # no Rocket landed near 500
        self.assertEqual(out["r"].sum(), 0.0)
        self.assertIsNone(out["events"][0]["row"])

    def test_no_events(self):
        self.assertEqual(SV.row_rewards(None, self.PLAYS, self.TICKS, P)["r"].tolist(), [0.0] * 6)


def ent(uid, team, card, bx, by, hp, mx, kind=0, radius=0.5, unit=-1):
    x, y = sub(bx, by)
    return NS(uid=uid, team=team, kind=kind, card_id=card, x=x, y=y, hp=hp, max_hp=mx, radius=radius * T, unit_type=unit)


def state(t, spells=(), ents=(), over=False):
    return NS(tick=t, spells=list(spells), entities=list(ents), game_over=over)


class TestTracker(unittest.TestCase):
    def setUp(self):
        cards = [NS(card_id=ROCKET, elixir=6), NS(card_id=TORNADO, elixir=3), NS(card_id=1, elixir=5),
                 NS(card_id=2, elixir=4), NS(card_id=3, elixir=3), NS(card_id=4, elixir=5)]
        names = {ROCKET: "Rocket", TORNADO: "Tornado", 1: "Wizard", 2: "Musketeer", 3: "Knight", 4: "Giant"}
        env = NS(ids={v: k for k, v in names.items()}, names=names,
                 core=NS(cards=lambda: cards, unit_types=lambda: ["Wizard", "Musketeer", "Knight", "Giant"]))
        self.trk = SV.SpellTracker(env, 0)
        ax, ay = sub(9.0, 10.0)
        self.rocket = NS(team=0, card_id=ROCKET, x=0, y=0, aim_x=ax, aim_y=ay)
        tx, ty = sub(9.0, 11.0)
        self.tornado = NS(team=0, card_id=TORNADO, x=tx, y=ty, aim_x=tx, aim_y=ty)

    def board(self, hp):
        """Enemy bodies around the aim (9, 10): Wizard on it, Musketeer 1.5 tiles off, Knight 1 tile off, Giant 5 tiles off
        (outside), the enemy princess 2.5 tiles off (radius 1.5 -> touched), my own Knight on the aim (never counted)."""
        return [ent(1, 1, 1, 9.0, 10.0, hp[0], 700, unit=0), ent(2, 1, 2, 10.5, 10.0, hp[1], 600, unit=1),
                ent(3, 1, 3, 9.0, 9.0, hp[2], 1500, unit=2), ent(4, 1, 4, 14.0, 10.0, hp[3], 4000, unit=3),
                ent(5, 1, -1, 9.0, 7.5, hp[4], 3000, kind=SV.PRINCESS_TOWER, radius=1.5),
                ent(6, 0, 3, 9.0, 10.0, 1500, 1500, unit=2)]

    def test_kinds_match_the_engine_contract(self):
        try:
            from royalegym.protocol import EntityKind
        except ImportError:
            self.skipTest("royalegym not installed (icebow venv)")
        self.assertEqual((SV.KING_TOWER, SV.PRINCESS_TOWER), (int(EntityKind.KING_TOWER), int(EntityKind.PRINCESS_TOWER)))

    def test_impact_combo_with_princess(self):
        trk, full = self.trk, [700, 600, 1500, 4000, 3000]
        trk.observe(state(95, [self.tornado], self.board(full)))
        self.assertFalse(trk.busy(95))
        trk.played(0, ROCKET, 100)
        self.assertTrue(trk.busy(100))                                         # armed: single steps from now on
        for t in range(101, 110):
            trk.observe(state(t, [self.rocket] + ([self.tornado] if t < 116 else []), self.board(full)))
        self.assertEqual(trk.flying, {(self.rocket.aim_x, self.rocket.aim_y): 101})
        trk.observe(state(110, [self.tornado], self.board(full)))              # gone: the impact, hp not applied yet
        self.assertEqual((len(trk.events), len(trk.pending)), (0, 1))
        self.assertTrue(trk.busy(110))
        after = [b for b in self.board([0, 0, 1000, 3000, 2600]) if b.uid not in (1, 2)]   # Wizard + Musketeer dead
        trk.observe(state(111, [], after))
        self.assertFalse(trk.busy(111))
        (e,) = trk.events
        self.assertEqual((e["tick"], e["seen"], e["aim"]), (110, 101, (9.0, 10.0)))
        self.assertAlmostEqual(e["kill"], 9.0)                                 # Wizard 5 + Musketeer 4
        self.assertAlmostEqual(e["dmg"], 1.0)                                  # Knight 3 x 500 / 1500; the Giant is outside
        self.assertTrue(e["princess"])
        self.assertFalse(e["king"])
        self.assertEqual(e["tower_dmg"], 400)
        self.assertEqual(e["tornado"], {"seen": 95, "aim": (9.0, 11.0), "cost": 3})
        self.assertEqual([b[0] for b in e["bodies"]], ["Wizard", "Musketeer", "Knight"])

    def test_game_over_resolves_on_the_final_state(self):
        trk, full = self.trk, [700, 600, 1500, 4000, 3000]
        trk.played(0, ROCKET, 100)
        trk.observe(state(101, [self.rocket], self.board(full)))
        trk.observe(state(102, [], [b for b in self.board([0, 600, 1500, 4000, 3000]) if b.uid != 1], over=True))
        (e,) = trk.events
        self.assertAlmostEqual(e["kill"], 5.0)
        self.assertIsNone(e["tornado"])
        self.assertFalse(e["princess"])

    def test_opponent_rocket_and_unarmed_expiry(self):
        trk = self.trk
        trk.played(1, ROCKET, 100)                                            # the other side's Rocket: not mine
        self.assertFalse(trk.busy(100))
        trk.played(0, ROCKET, 100)
        self.assertFalse(trk.busy(100 + SV.ARM_TICKS + 1))                    # never seen: single stepping ends
        enemy = NS(team=1, card_id=ROCKET, x=0, y=0, aim_x=1, aim_y=1)
        trk.observe(state(200, [enemy], []))
        self.assertEqual(trk.flying, {})


class TestBodyValue(unittest.TestCase):
    def test_units_and_fallbacks(self):
        self.assertAlmostEqual(SV.body_value("Skeleton", "Witch"), 1 / 3)     # a child = the Skeletons card's share
        self.assertEqual(SV.body_value("Wizard", "Wizard"), 5.0)
        self.assertEqual(SV.body_value("Musketeer_EV1", "Musketeer"), 4.0)    # evo form = the base unit
        self.assertEqual(SV.body_value("", "Knight"), 3.0)                    # no unit name: the card's body
        self.assertEqual(SV.body_value("", "Rocket"), 0.0)                    # a spell is worth nothing
        self.assertEqual(SV.body_value("", ""), 0.0)


class TestSummary(unittest.TestCase):
    def test_counts(self):
        evs = [ev(), ev(kill=9.0, princess=True, aim=(9.0, 25.0), tornado={"seen": 1, "aim": (9, 25), "cost": 3}),
               {**ev(kill=1.2), "bodies": [["Skeleton", 0.333, 1.0, True]] * 4}]
        s = SV.match_summary(evs)
        self.assertEqual((s["rockets"], s["combos"], s["misses"], s["swarm"], s["princess"]), (3, 1, 2, 1, 1))
        self.assertEqual((s["my_half"], s["near_my_king"], s["combo_my_half"]), (1, 1, 1))
        self.assertAlmostEqual(s["value"], 10.2)


class TestTrainerWiring(unittest.TestCase):
    BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.5}

    def test_spell_cfg(self):
        from pipeline import rl_royale as RL
        self.assertIsNone(RL.spell_cfg(self.BASE))
        self.assertIsNone(RL.spell_cfg({**self.BASE, "spell_value_reward": False}))
        with self.assertRaises(SystemExit):
            RL.spell_cfg({**self.BASE, "spell_value_w": 0.03})                # a key without the switch
        self.assertEqual(RL.spell_cfg({**self.BASE, "spell_value_reward": True}), P)
        self.assertEqual(RL.spell_cfg({**self.BASE, "spell_value_reward": True, "spell_value_w": 0})["spell_value_w"], 0.0)
        for bad in ({"advantage": "match_loo"}, {"league": False}, {"spell_value_w": -1}, {"spell_value_match_cap": 0},
                    {"spell_value_reward": "yes"}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.spell_cfg({**self.BASE, "spell_value_reward": True, **bad})

    def test_adv_cfg_critic_scale_and_warmup(self):
        from pipeline import rl_royale as RL
        on = {**self.BASE, "spell_value_reward": True}
        RL.adv_cfg(on)                                                        # 1 + 0.5 = 1.5: passes
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**on, "shaping_critic_scale": 1.4})
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**on, "critic_warmup_updates": 0})
        with self.assertRaises(SystemExit):                                   # with tower_score shaping: 1 + bound + cap
            RL.adv_cfg({**on, "shaping": "tower_score", "shaping_critic_scale": 1.5})

    def test_config_sha_off_is_historical_and_on_is_one_hash(self):
        from pipeline import rl_royale as RL
        base = {**self.BASE, "seed": 1}
        h = RL.config_sha(base)
        self.assertEqual(RL.config_sha({**base, "spell_value_reward": None}), h)
        self.assertEqual(RL.config_sha({**base, "spell_value_reward": False}), h)
        on = RL.config_sha({**base, "spell_value_reward": True})
        self.assertNotEqual(on, h)
        self.assertEqual(RL.config_sha({**base, "spell_value_reward": True, "spell_value_w": 0.02}), on)
        self.assertNotEqual(RL.config_sha({**base, "spell_value_reward": True, "spell_value_w": 0}), on)

    def test_actor_cfg_only_with_the_key(self):
        from pipeline import rl_royale as RL
        base = {"tau": 0.27, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12, "obs": "live", "grid": "lattice",
                "decide_every": 10, "T": 0.5}
        off = RL.actor_cfg(base, "rollout", 0, "cpu")
        self.assertNotIn("spell_track", off)
        self.assertNotIn("record_tick", off)
        on = RL.actor_cfg({**base, "spell_value": True}, "rollout", 0, "cpu")
        self.assertTrue(on["spell_track"] and on["record_tick"])
        self.assertNotIn("spell_track", RL.actor_cfg({**base, "spell_value": True}, "screen", 0, "cpu"))
        self.assertEqual({k: v for k, v in on.items() if k not in ("spell_track", "record_tick", "noise")},
                         {k: v for k, v in off.items() if k != "noise"})

    def test_collate_adds_the_reward_on_the_rocket_rows_only(self):
        from pipeline import rl_royale as RL
        from pipeline.tests.test_rl_royale import _results, _tiny_model
        res = _results(_tiny_model(0), [(0, 0, 12, "win"), (0, 1, 10, "loss")], seed=3, all_allowed=True)
        for r in res:
            n = len(r["traj"]["played"])
            r["traj"]["tick"] = np.arange(n, dtype=np.int64) * 10 + 100
            j = int(np.flatnonzero(r["traj"]["played"])[0])                   # its first played row decided the Rocket
            r["plays"] = [{"tick": int(r["traj"]["tick"][j]), "land_tick": int(r["traj"]["tick"][j]) + 26,
                           "card": "rocket", "accepted": True}]
            r["spell"] = [ev(kill=9.0, seen=int(r["traj"]["tick"][j]) + 27)]
            r["rocket_row"] = j
        B0, st0 = RL.collate(res, advantage="gae")
        B1, st1 = RL.collate(res, advantage="gae", spell=P)
        self.assertNotIn("phi", B0)
        np.testing.assert_array_equal(B1["phi"], np.zeros(len(B1["r_step"])))
        d = B1["r_step"] - B0["r_step"]
        self.assertAlmostEqual(float(d.sum()), 2 * 0.02 * (9.0 - 6.0))
        self.assertEqual(int(np.count_nonzero(d)), 2)
        self.assertEqual(st1["spell"]["rows_rewarded"], 2)
        self.assertEqual((st1["spell"]["rows_lost"], st1["spell"]["unmapped_rockets"]), (0, 0))
        self.assertEqual(st1["spell"]["rockets_per_match"], 1.0)
        self.assertEqual({k: v for k, v in st1.items() if k != "spell"}, st0)
        for k in B0:
            if k != "r_step":
                np.testing.assert_array_equal(B0[k], B1[k], err_msg=k)


if __name__ == "__main__":
    unittest.main()
