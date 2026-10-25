"""Plan A S1b: the match memory wired in (scratchpad/gauntlet/L74/memory/PLAN_A.md; pipeline/match_memory.py).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_s1b.py -q

Covers: the model flag (model_gen MemoryEncoder / add_memory / load_model memory="v1": a checkpoint without memory weights
-> a fresh zero-output encoder; weights in a state dict build it; the output layer is zero, the encoder is live once it is
not); the rl config key (absent = the PRE hash, v1 = another, a bad value / branch_gate refused); a whole recorded SIM
self-play match: without memory = the PRE code byte for byte (traj, result, collate), with a memory learner = per-match
event table + per-row mem_t, and the learner's recomputed log-probs (rl_royale.policy_terms -> e1_eval.gen_batch ->
match_memory.rows_features) equal the actor's (the memory reached both, identically); the live pilot's memory rows
(GenPilot.memory_rows on reader frames + record_play / record_ability) = the offline build of the same match; the pro
builder (dataset_gen.memory_replay) on a real replay."""
from __future__ import annotations

import copy
import subprocess
import sys
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import match_memory as MM                                  # noqa: E402
from pipeline import model_gen as MG                                     # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402

PRE = "7f4bc70"                       # the last commit before S1b: the absent-flag reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
CORPUS = REPO / "scratchpad/gauntlet/ext/corpus_gen_pilot/s0_public_v1"
try:
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
except ImportError:                   # no royalegym in this venv
    RoyaleSelfPlayEnv = None
ICEBOW = ["Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons"]
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]


def _pre(rel: str, name: str):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE}:{rel} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__ = str(REPO / rel)
    mod.__package__ = "pipeline"
    sys.modules[name] = mod
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def _vocab():
    from pipeline.dataset_gen import card_key
    return ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ})


def _tiny(memory: bool, seed=0, live=False, version="v1"):
    """A small fv5 GenModel (the public observation memory is built from); ``live`` = a NONZERO memory output layer."""
    torch.manual_seed(seed)
    net = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(_vocab()), feature_version=5).eval()
    if memory:
        net.add_memory(version=version)
        MG.attach_vocab(net, _vocab())                  # v2: the learner's gen_batch reads the counter priors by it
        if live:
            with torch.no_grad():
                net.mem.out.weight.normal_(0, 0.05)
    return net


# ------------------------------------------------------------------------------------------------------ model / config
class TestModelFlag(unittest.TestCase):
    def test_load_path_and_state_dict(self):
        base = _tiny(False)
        m = copy.deepcopy(base)
        m.add_memory()
        self.assertTrue(torch.equal(m.mem.out.weight, torch.zeros_like(m.mem.out.weight)))
        self.assertTrue(torch.equal(m.mem.out.bias, torch.zeros_like(m.mem.out.bias)))
        self.assertEqual(m.mem.out.out_features, m.global_in[0].in_features)
        m.load_state_dict(base.state_dict())                             # no mem.* keys: the fresh encoder is kept
        sd = {k: v.clone() for k, v in _tiny(True, live=True).state_dict().items()}
        plain = _tiny(False)
        plain.load_state_dict(sd)                                         # mem.* keys build the encoder (by content)
        self.assertIsNotNone(getattr(plain, "mem", None))
        self.assertTrue(torch.equal(plain.mem.out.weight, sd["mem.out.weight"]))
        with self.assertRaises(ValueError):
            MG.memory_flag("v3")                                         # v2 = S1c (test_memory_v2.py)
        self.assertEqual(MG.memory_flag(None), None)

    def test_checkpoint_round_trip(self):
        import tempfile
        net = _tiny(False)
        args = {"d": 16, "layers": 1, "feature_version": 5}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ck.pt"
            torch.save({"gen": True, "args": args, "d_c": 8, "card_vocab": _vocab(), "model": net.state_dict()}, p)
            self.assertIsNone(getattr(MG.load_model(p, torch.device("cpu"))[0], "mem", None))      # absent = none
            m = MG.load_model(p, torch.device("cpu"), memory="v1")[0]                            # fv5 + memory v1
            self.assertTrue(torch.equal(m.mem.out.weight, torch.zeros_like(m.mem.out.weight)))
            torch.save({"gen": True, "args": args, "d_c": 8, "card_vocab": _vocab(), "memory": "v1",
                        "model": _tiny(True, live=True).state_dict()}, p)
            m = MG.load_model(p, torch.device("cpu"))[0]                                         # weights build it
            self.assertGreater(float(m.mem.out.weight.abs().sum()), 0)
            with self.assertRaises(ValueError):
                MG.load_model(p, torch.device("cpu"), memory="v3")


class TestConfig(unittest.TestCase):
    def test_hash_absent_is_pre_and_key(self):
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_s1b")
        cfg = RL.load_config(YAML, [], False)
        self.assertEqual(RL.config_sha(cfg), P.config_sha(P.load_config(YAML, [], False)))
        self.assertEqual(RL.config_sha({**cfg, "memory": None}), RL.config_sha(cfg))     # null = absent
        on = RL.load_config(YAML, ["memory=v1"], False)
        self.assertEqual(on["memory"], "v1")
        self.assertNotEqual(RL.config_sha(on), RL.config_sha(cfg))
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, ["memory=v3"], False)
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, ["memory=v1", "branch_gate=true"], False)


# ------------------------------------------------------------------------------------------------------ SIM rollouts
def _spec(seed=3):
    return {"tag": f"mem:{seed}", "opp": {"id": "gen"}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
            "opp_deck": list(HOGEQ), "learner_side": seed % 2, "seed": seed}


def _record_cfg():
    return dict(S.live_cfg(S.TAU_PLAIN, "lattice"), policy="sample", record=True)


def _run(mod, learner, opp, seed=3, tail=900):
    got = []
    mod.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=tail), mod.GenPolicy(learner, _vocab()),
                           {"gen": (mod.GenPolicy(opp, _vocab()), S.live_cfg(S.TAU_OPP, "lattice"))},
                           [(0, _spec(seed), 0)], _record_cfg(), 1, on_result=got.append)
    got[0].pop("wall_s", None)
    return dict(got[0], entry_index=0)


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable")
class TestRollouts(unittest.TestCase):
    def test_absent_is_pre(self):
        """No memory model: a whole recorded self-play match and its collate = the PRE code's, byte for byte."""
        P = _pre("pipeline/e1_eval.py", "pipeline._e1_eval_pre_s1b")
        PR = _pre("pipeline/rl_royale.py", "rl_royale_pre_s1b2")
        new, old = _run(E, _tiny(False), _tiny(False, 1)), _run(P, _tiny(False), _tiny(False, 1))
        self.assertGreater(len(new["traj"]["tok"]), 10)
        self.assertNotIn("memory", new)
        self.assertNotIn("mem_t", new["traj"])
        self.assertEqual(sorted(new["traj"]), sorted(old["traj"]))
        for k in old["traj"]:
            self.assertEqual(new["traj"][k].tobytes(), old["traj"][k].tobytes(), k)
        self.assertEqual({k: v for k, v in new.items() if k != "traj"}, {k: v for k, v in old.items() if k != "traj"})
        Bn, _ = RL.collate([copy.deepcopy(new)], 2.0, advantage="gae")
        Bp, _ = PR.collate([copy.deepcopy(new)], 2.0, advantage="gae")
        self.assertEqual(sorted(Bn), sorted(Bp))
        for k in Bp:
            self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)

    def test_memory_rollout_collate_learner(self, version="v1"):
        """A memory learner (nonzero output layer, so memory moves its outputs): the result carries the match's event table
        and every row its mem_t; the learner's recomputed log-probs from the tables = the actor's (sampled with the
        rollout's own MatchMemory.features); an EMPTY memory gives other log-probs (the memory reached the learner)."""
        net = _tiny(True, live=True, version=version)
        res = _run(E, net, _tiny(False, 1), seed=4, tail=1500)
        tj = res["traj"]
        self.assertIn("memory", res)
        self.assertEqual(sorted(res["memory"]), sorted(MM.TABLE_KEYS))
        self.assertEqual(len(tj["mem_t"]), len(tj["tok"]))
        self.assertGreater(len(res["memory"]["tick"]), 10)               # plays of both sides + tower events
        self.assertTrue(np.all(np.diff(tj["mem_t"]) > 0))
        B, _ = RL.collate([copy.deepcopy(res)], 2.0, advantage="gae")
        self.assertTrue(all(k in B for k in ("mem_row_tab", "mem_row_t", "mem_tab_vals", "mem_tab_off")))
        Bt = RL.to_device(B, "cpu")
        self.assertIsInstance(Bt["mem_tab_vals"], np.ndarray)             # the tables stay CPU numpy
        idx = torch.arange(len(B["A"]))
        cfg = _record_cfg()
        with torch.no_grad():
            t = RL.policy_terms(net, Bt, idx, cfg["tau"], cfg["T"])
            diff = {k: float((t[k] - Bt[k][idx]).abs().max()) for k in ("lp_gate", "lp_card", "lp_cell")}
            self.assertLess(max(diff.values()), 1e-5, diff)
            empty = RL.policy_terms(net, {**Bt, "mem_row_tab": np.full(len(B["A"]), -1)}, idx, cfg["tau"], cfg["T"])
            self.assertGreater(float((empty["lp_gate"] - Bt["lp_gate"][idx]).abs().max()), 1e-4)
            g = RL.trunk_g(net, Bt, idx)                                  # the ability head's trunk path too
            self.assertEqual(tuple(g.shape), (len(idx), net.d))
        if version == "v2":                                               # S1c: the v2 rows (114-wide summary) reached it
            from pipeline.e1_eval import gen_batch
            self.assertEqual(tuple(gen_batch(net, Bt, idx)["mem_summary"].shape), (len(idx), MM.S_V2))

    def test_memory_v2_rollout_collate_learner(self):
        """The same for a memory v2 learner (S1c): actor MatchMemory.features(v2) = learner rows_features(v2) from the tables."""
        self.test_memory_rollout_collate_learner(version="v2")

    def test_search_s0_forward_feeds_memory(self):
        pol = E.GenPolicy(_tiny(True, live=True), _vocab())
        run = S.Runner(pol, {"gen": (E.GenPolicy(_tiny(False, 1), _vocab()), S.live_cfg(S.TAU_OPP, "lattice"))},
                       S.live_cfg(S.TAU_PLAIN, "lattice"), lambda: RoyaleSelfPlayEnv(tail_cap=7200), horizon_s=4.0)
        m = run.setup("gen", 3, HOGEQ)
        import random
        st = {k: 0 for k in ("eligible", "searched", "unsearched", "gate_skipped", "overrides", "chose_wait",
                             "plain_wait_overridden", "moved_cell", "n_cands")}
        st["search_s"], rng, seen = 0.0, random.Random(0), 0
        while seen < 5:                                                # play on (plain rule) through 5 learner decisions
            ds = m.due()
            self.assertTrue(ds, "match ended")
            if m.learner in ds:
                for s in ds:
                    s.prepare()
                S.forward(m.learner)
                self.assertTrue(all(k in m.learner._gen_row for k in MM.MEM_KEYS))
                seen += 1
            run.round(m, ds, "plain", st, rng)
        self.assertIsNotNone(m.learner.mem)
        self.assertEqual(len(m.learner.mem.t), 5)


# ------------------------------------------------------------------------------------------------------ live pilot
class TestLivePilot(unittest.TestCase):
    """GenPilot.memory_rows (the live path) on hand-made reader frames = the offline build of the same match."""

    def _frames(self):
        side = 1
        def ent(s, x, y, cid, hp, mx, kind, addr):
            return dict(side=s, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, address=addr, category=0)
        from pipeline.public_observation import _native_ids
        from pipeline import vocab
        knight = _native_ids()[(vocab.engine_key("Knight"), 0)]
        towers = [(0, 9000, 3000, 12), (0, 3500, 6500, 13), (0, 14500, 6500, 13),
                  (1, 9000, 29000, 12), (1, 3500, 25500, 13), (1, 14500, 25500, 13)]
        frames = []
        for t in range(150, 900, 10):
            ents = [ent(s, x, y, -1, 4858 if k == 13 else 7728, 4858 if k == 13 else 7728, k, f"T{i}")
                    for i, (s, x, y, k) in enumerate(towers)]
            if t >= 400:                                               # their princess (my-frame L) takes damage
                ents[1]["hp"] = 4858 - 8 * (t - 400)
            if 300 <= t < 600:                                         # an enemy Knight walks down my left lane
                ents.append(ent(0, 3500, 12000 + 10 * (t - 300), knight, 1500 - 3 * (t - 300), 1500, 14, "K1"))
            me = dict(side=side, hand_deck_indices=[0, 1, 2, 3], next_deck_index=4, elixir_raw=50000 + 10 * t,
                      deck_card_ids=[knight] * 8)
            frames.append(dict(game_tick=t, entities=ents, projectiles=[], effects=[],
                               players=[me, dict(side=1 - side, hand_deck_indices=[-1] * 4, next_deck_index=-1,
                                                 elixir_raw=0, deck_card_ids=[-1] * 8)]))
        return side, frames

    def test_memory_rows_equal_offline(self, version="v1"):
        from pipeline.live_gen import GenPilot
        side, frames = self._frames()
        pilot = GenPilot.__new__(GenPilot)                              # no checkpoint: the memory path only
        if version != "v1":                                            # only the encoder's version is read
            pilot.model = types.SimpleNamespace(mem=types.SimpleNamespace(version=version))
        pilot.feature_version, pilot.public, pilot.public_battle = 5, None, None
        pilot.frames, pilot.opp, pilot.own_fx, pilot.past = __import__("collections").deque(maxlen=30), None, None, []
        pilot.gid = {k: i for i, k in enumerate(_vocab())}
        deck = np.array(sorted(pilot.gid[k] for k in ("knight", "x-bow", "rocket", "tornado", "tesla", "the-log",
                                                     "ice-wizard", "skeletons")))
        got, want_s, want_p = {}, [], []
        for f in frames:
            pilot.observe(f)
            t = f["game_tick"]
            if t == 350:                                               # my confirmed Knight (model-frame xy) + a press
                pilot.record_play(pilot.gid["knight"], 1, (0.25, 0.55), t * 0.05)
            if t == 470:
                pilot.record_ability("IceWizard", 455)                 # confirmed at 470, stamped with its tap tick
            got[t] = pilot.memory_rows(f, side, deck)
            from pipeline.live_mem import to_observe
            from pipeline.public_observation import public_frame
            tw, al = MM.tower_reads_engine(to_observe(f, side, ["Knight"] * 8)["episode"]["crown_towers"], side)
            want_s.append(dict(tick=t, towers=tw, alive=al, elixir=f["players"][0]["elixir_raw"] / 1e4,
                               units=public_frame(f, source="reader")["entities"]))
        x, y = MM.engine_xy(0.25, 0.55, side)
        want_p = list(pilot.public.plays) + [dict(tick=350, side=side, card="knight", form=1, x=x, y=y),
                                             dict(tick=455, seen=470, side=side, card="IceWizard", ability=True)]
        ref = MM.build(side, want_s, want_p)
        self.assertTrue(pilot.public.plays, "the enemy Knight was detected")
        for t, f in got.items():
            r = ref.features(t, pilot.gid, deck, version)
            for k in MM.MEM_KEYS:
                self.assertTrue(np.array_equal(f[k], r[k]), (t, k))
            self.assertEqual(f["mem_summary"].shape, (MM.N_SUM[version],))
        ev = ref.events(10 ** 6)
        own = [e for e in ev if e.get("card") == "knight" and e["mine"]]
        self.assertEqual(own[0]["form"], 1)
        self.assertAlmostEqual(own[0]["xy"][0], 0.25)
        self.assertTrue(any(e["type"] == "tower_damage" for e in ev))
        self.assertEqual(pilot.mem.late, 1)                             # the press arrived after its tap tick

    def test_memory_rows_equal_offline_v2(self):
        """S1c: the live pilot's v2 rows (incremental, reader frames) = the offline v2 build of the same match."""
        self.test_memory_rows_equal_offline(version="v2")


# ------------------------------------------------------------------------------------------------------ pro builder
class TestProBuilder(unittest.TestCase):
    def test_memory_replay(self):
        files = sorted(CORPUS.glob("j*/replay_*.json"))[:1]
        if not files:
            raise unittest.SkipTest(f"{CORPUS} not on this machine")
        from pipeline.dataset_gen import memory_replay
        r = memory_replay(str(files[0]), _vocab() + ["x"])             # a vocab without most pro cards: ids 0 allowed
        self.assertNotIn("error", r, r.get("error"))
        self.assertEqual(sorted(r["tables"]), [0, 1])
        st = r["stats"]
        self.assertEqual((st["frames_no_towers"], st["frames_no_elixir"], st["own_plays_no_xy"]), (0, 0, 0))
        for s, tab in r["tables"].items():
            self.assertEqual(sorted(tab), sorted(MM.TABLE_KEYS))
            mine = tab["vals"][:, MM._COL["mine"]] == 1
            play = tab["vals"][:, MM._COL["is_play"]] == 1
            self.assertGreater(int((play & mine).sum()), 10)
            self.assertGreater(int((play & ~mine).sum()), 10)
            self.assertTrue(np.all(np.diff(tab["tick"]) >= 0))


if __name__ == "__main__":
    unittest.main()


class TestLiveRow(unittest.TestCase):
    """GenPilot.row with a memory model (a real reader frame, pipeline/tests/test_live_decision_options.icebow_frame): the
    memory rows reach the batch; a zero-output encoder leaves every output unchanged on that live row."""

    def test_row_feeds_memory(self):
        try:
            from pipeline.tests.test_live_decision_options import icebow_frame, pilot
        except Exception as exc:                                      # noqa: BLE001 -- its fixture file / deps
            raise unittest.SkipTest(f"live fixtures unavailable: {exc}")
        from pipeline import live_gen
        outs, decided = {}, {}
        for name, mem in (("base", False), ("mem", True), ("mem2", "v2")):
            p = pilot(None, cls=live_gen.GenPilot)
            torch.manual_seed(0)
            p.model = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=max(p.gid.values()) + 1, feature_version=5).eval()
            if mem:
                p.model.add_memory(version="v2" if mem == "v2" else "v1")
            p.feature_version, p.public, p.public_battle, p.use_counter = 5, None, None, True
            rows = []
            for t in (1000, 1010, 1020):
                f = icebow_frame(tick=t)
                p.observe(f)
                b, _ = p.row(f)
                rows.append(b)
            if mem:
                self.assertTrue(all(k in rows[-1] for k in MM.MEM_KEYS))
                self.assertEqual(tuple(rows[-1]["mem_ev"].shape), (1, MM.E_MAX, MM.F))
                self.assertEqual(tuple(rows[-1]["mem_answer"].shape), (1,))
                self.assertEqual(tuple(rows[-1]["mem_summary"].shape), (1, MM.S_V2 if mem == "v2" else MM.S))
                self.assertEqual(len(p.mem.t), 3)
            with torch.no_grad():
                outs[name] = [p.model(b) for b in rows]
                decided[name] = p.decide(icebow_frame(tick=1030))
        for other in ("mem", "mem2"):
            for a, b in zip(outs["base"], outs[other]):
                for k in ("gate", "card", "value"):
                    self.assertTrue(torch.equal(a[k], b[k]), (other, k))
        p_lock = decided["mem2"].pop("xb_lock_p")                     # S1c: logged for a v2 model only, nothing else moves
        self.assertTrue(0 < p_lock < 1)
        self.assertNotIn("xb_lock_p", decided["mem"])
        self.assertEqual({k: v for k, v in decided["mem2"].items() if k != "bs"},
                         {k: v for k, v in decided["base"].items() if k != "bs"})
