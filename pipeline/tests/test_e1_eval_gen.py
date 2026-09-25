"""Offline tests for e1_eval's generalist path (``GenPolicy``, ``load_policy``, ``Match.gen_row``, ``run_batch``).

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_eval_gen.py

No engine, no GPU, no royalegym: a fake env serves the obs-contract fixture board (``test_obs_contract.raw_obs``) with
the fixture engine deck; tiny random GenModel / S1Model stand in for checkpoints.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import obs_contract as oc                                   # noqa: E402
from pipeline import vocab                                                # noqa: E402
from pipeline import engine_play as ep                                    # noqa: E402
from pipeline.model_gen import GenModel                                   # noqa: E402
from pipeline.dataset import PAST_K, _past                                # noqa: E402
from pipeline.dataset_gen import card_form, card_key                      # noqa: E402
from pipeline.e1_view import Noise                                        # noqa: E402
from pipeline.tests.test_obs_contract import ENGINE_DECK, raw_obs         # noqa: E402

# name, form, cost of the fixture's engine deck (ENGINE_DECK order)
FINAL = [("Tesla", "evolution", 4), ("Knight", "evolution", 3), ("Xbow", "base", 6), ("IceWizard", "base", 3),
         ("Skeletons", "base", 1), ("Log", "base", 2), ("Rocket", "base", 6), ("Tornado", "base", 3)]
# a vocab where the fixture cards are NOT in engine order and other cards sit between them
VOCAB = ["<pad>"] + sorted({card_key(n) for n in ENGINE_DECK} | {"golem", "hog-rider", "zap", "musketeer"})


def _tiny_gen(seed=0):
    import torch
    from pipeline.model_gen import GenModel
    torch.manual_seed(seed)
    return GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(VOCAB)).eval()


class _Eng:
    def __init__(self, state):
        self.state, self.calls, self.last_episode = state, [], {"winner": 0, "crowns": [1, 0]}

    def act(self, side, deck_index, x, y):
        self.calls.append((side, deck_index, x, y))
        return {"accepted": True, "result_code": 0}

    def observe(self):
        return self.state


class _FakeEnv:
    """What Match needs of RoyalePoolEnv; one decision per match (tail_cap = first tick + decide_every)."""

    def __init__(self, costs=None):
        self.side, self.opp, self._mirror = 0, 1, False
        costs = costs or {}
        self.final_decks = {0: [{"name": n, "form": f, "cost": costs.get(n, c)} for n, f, c in FINAL]}
        self.terminated, self.episode = False, None
        self.ghost_ok = self.ghost_rejected = 0
        self.ghost_cards_delivered, self.ghost_reject_reasons = {}, {}

    def reset(self, entry):
        st = raw_obs(0)
        self.tick, self.tail_cap = int(st["tick"]), int(st["tick"]) + 10
        self.eng = _Eng(st)
        return st

    def _advance_to(self, t):
        self.tick = int(t)
        self.eng.state = dict(self.eng.state, tick=self.tick)

    def ghost_undelivered(self):
        return 0

    def _tower_hp(self, state):
        return None

    def _crowns(self, hp):
        return (0, 0)


def _cfg(tau=0.0, grid="lattice"):
    return {"policy": "live", "tau": tau, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0,
            "obs": "clean", "noise": Noise(), "p_random": 0.0, "random_hand_only": False, "grid": grid,
            "device": "cpu", "decide_every": 10, "slot": 0, "port": 0, "T": 0.5, "entry_index": 0}


class TestGenRow(unittest.TestCase):
    """(a) identity arrays + zeroed sc == dataset_gen's construction, built independently from the ENGINE deck."""

    def test_row_matches_dataset_gen(self):
        deck = oc.load_deck("icebow")
        env = _FakeEnv()
        engine_deck, dios, _ = E._slot_maps(env, deck, {"tag": "t"})
        st = raw_obs(0)
        bs = oc.from_engine(ep.compact_raw(st), 0, deck,
                            engine_deck=engine_deck, unmapped=set())
        tok, mask, sc = oc.to_tokens(bs, E.MAX_U)
        tick = int(st["tick"])
        done = [(tick - 60, deck.slot_of("rocket"), 0.3, 0.2), (tick - 20, deck.slot_of("the_log"), 0.6, 0.4)]
        past = _past(done, tick)
        pol = E.GenPolicy(None, VOCAB)
        r = pol.row(tok, mask, sc, past, *pol.slot_ident(engine_deck, dios))

        gid = {k: i for i, k in enumerate(VOCAB)}
        me = st["players"][0]
        # hand / next: the engine deck NAME at each hand deck index -> dataset_gen.card_key / card_form
        exp_hand = [gid[card_key(ENGINE_DECK[d])] for d in me["hand_deck_indices"]]
        exp_hform = [card_form(ENGINE_DECK[d]) for d in me["hand_deck_indices"]]
        nd = me["next_deck_index"]
        np.testing.assert_array_equal(r["hand_card"], exp_hand)
        np.testing.assert_array_equal(r["hand_form"], exp_hform)
        self.assertEqual((int(r["next_card"]), int(r["next_form"])), (gid[card_key(ENGINE_DECK[nd])], card_form(ENGINE_DECK[nd])))
        self.assertEqual(exp_hform, [1, 1, 0, 0])                          # Tesla/Knight decked as evo
        # deck: canonical = sorted by card id, forms carried along
        pairs = sorted((gid[card_key(n)], card_form(n)) for n in ENGINE_DECK)
        np.testing.assert_array_equal(r["deck_card"], [c for c, _ in pairs])
        np.testing.assert_array_equal(r["deck_form"], [f for _, f in pairs])
        # past: dataset_gen's form table {base_key(engine_key(n)): card_form(n)} on the played slot's card
        form_of = {vocab.base_key(vocab.engine_key(n)): card_form(n) for n in ENGINE_DECK}
        exp_past = np.tile(np.array([0, 3, -1, -1, -1], np.float32), (PAST_K, 1))
        for i, (tk, sl, x, y) in enumerate(reversed(done)):
            key = vocab.base_key(deck.cards[sl])
            exp_past[i] = (gid[key.replace("_", "-")], form_of[key], x, y, (tick - tk) * 0.05)
        np.testing.assert_allclose(r["past"], exp_past, rtol=0, atol=1e-6)
        # sc: columns 7..51 zeroed, all others untouched
        self.assertTrue(sc[7:52].any())
        self.assertFalse(r["sc"][7:52].any())
        np.testing.assert_array_equal(r["sc"][:7], sc[:7])
        np.testing.assert_array_equal(r["sc"][52:], sc[52:])
        np.testing.assert_array_equal(r["tok"], tok)


class TestGenDecide(unittest.TestCase):
    """(b) the chosen hand position reaches env.eng.act as that card's engine deck index; (c) masking."""

    def _run(self, model, costs=None, batched=True):
        pol = E.GenPolicy(model, VOCAB)
        env = _FakeEnv(costs)
        out = []
        entry = {"tag": "t0"}
        if batched:
            E.run_batch(lambda: env, pol, oc.load_deck("icebow"), [(0, entry, 0)], _cfg(), 1, on_result=out.append)
        else:
            out.append(E.run_match(env, pol, oc.load_deck("icebow"), entry, 0, _cfg()))
        return out[0], env

    def _expected_deck_index(self, model, costs):
        """Independent: forward the row, argmax of the 4 hand-position logits over AFFORDABLE positions."""
        import torch
        pol = E.GenPolicy(model, VOCAB)
        deck = oc.load_deck("icebow")
        env = _FakeEnv(costs)
        m = E.Match(env, deck, {"tag": "t0"}, 0, _cfg())
        m.prepare()
        _, heads, _, _ = pol.forward_batch([m.gen_row(pol)])
        logits = heads["card_hand"][0].clone()
        me = raw_obs(0)["players"][0]
        el = int(me["elixir"])
        cost = {n: c for n, _, c in FINAL}
        cost.update(costs or {})
        ok = torch.tensor([cost[FINAL[d][0]] <= el for d in me["hand_deck_indices"]])
        pos = int(logits.masked_fill(~ok, float("-inf")).argmax())
        return me["hand_deck_indices"][pos]

    def test_hand_position_maps_to_engine_deck_index(self):
        for seed in range(4):
            model = _tiny_gen(seed)
            res, env = self._run(model)
            self.assertEqual(res["plays_attempted"], 1)
            d = env.eng.calls[0][1]
            self.assertEqual(d, self._expected_deck_index(model, None), seed)
            # the recorded card (icebow slot key) is the same card the engine was told to play
            self.assertEqual(vocab.base_key(res["plays"][0]["card"]), vocab.base_key(vocab.engine_key(ENGINE_DECK[d])))

    def test_forced_card_is_played_then_masked_when_unaffordable(self):
        import torch
        model = _tiny_gen(0)
        xb = VOCAB.index(card_key("Xbow"))
        with torch.no_grad():
            model.card_b.weight[xb] = 100.0                               # Xbow dominates the pointer
        xb_index = [n for n, _, _ in FINAL].index("Xbow")
        _, env = self._run(model)                                         # cost 6 <= floored elixir 6
        self.assertEqual(env.eng.calls[0][1], xb_index)
        res, env = self._run(model, costs={"Xbow": 9})                    # unaffordable -> never chosen
        self.assertEqual(res["plays_attempted"], 1)
        self.assertNotEqual(env.eng.calls[0][1], xb_index)
        self.assertEqual(env.eng.calls[0][1], self._expected_deck_index(model, {"Xbow": 9}))

    def test_batched_equals_sequential(self):
        model = _tiny_gen(2)
        a, ea = self._run(model, batched=True)
        b, eb = self._run(model, batched=False)
        self.assertEqual(ea.eng.calls, eb.eng.calls)
        self.assertEqual(a["plays"], b["plays"])

    def test_record_refused_for_gen(self):
        with self.assertRaises(ValueError):
            E.run_batch(lambda: _FakeEnv(), E.GenPolicy(_tiny_gen(), VOCAB), None, [], {**_cfg(), "record": True}, 1,
                        on_result=print)


class TestLoadPolicy(unittest.TestCase):
    """(d) a 'gen' checkpoint -> GenPolicy; an S1 checkpoint -> engine_play.load_model's S1Model, unchanged."""

    def test_detects_by_gen_key(self):
        import torch
        from pipeline.model_v3 import S1Model
        with tempfile.TemporaryDirectory() as td:
            s1p, gp = Path(td) / "s1.pt", Path(td) / "gen.pt"
            torch.manual_seed(0)
            s1 = S1Model(d=16, layers=1)
            torch.save({"args": {"d": 16, "layers": 1, "grid": "lattice"}, "model": s1.state_dict(), "epoch": 1}, s1p)
            g = _tiny_gen()
            g4 = GenModel(d=16, layers=1, d_c=8, n_cards=len(VOCAB))
            g4.load_state_dict(g.state_dict())
            torch.save({"gen": True, "args": {"d": 16, "layers": 1, "grid": "lattice"}, "d_c": 8, "card_vocab": VOCAB,
                        "model": g4.state_dict(), "epoch": 2}, gp)
            m1, i1 = E.load_policy(s1p, "cpu")
            m2, i2 = E.load_policy(gp, "cpu")
        self.assertIsInstance(m1, S1Model)
        self.assertNotIsInstance(m1, E.GenPolicy)
        self.assertNotIn("gen", i1)
        self.assertEqual(i1["grid"], "lattice")
        for k, v in s1.state_dict().items():
            self.assertTrue(torch.equal(m1.state_dict()[k], v), k)
        self.assertIsInstance(m2, E.GenPolicy)
        self.assertEqual((i2["gen"], i2["grid"]), (True, "lattice"))


if __name__ == "__main__":
    unittest.main()
