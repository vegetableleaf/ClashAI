"""TARGET-OBS (pipeline/target_obs.py; model_gen tgt_in / tgt_out / tgt_back; rl_royale ``target_obs``;
scratchpad/gauntlet/L74/plan1026/target_obs/TARGET_OBS.md).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_target_obs.py

Covers: target_rows layout on a hand board (both sides, mirrored side 1, towers, incoming counts, degraded frame);
the token match = live_unit_state.align's assignment on random boards; config hash absent / off = the pre-change
rl_royale's; CLXIII NOLEAK + zero target layers = CLXIII bit-identical on real recorded live decisions (random target
rows, and the real live target rows), the layers wired in once non-zero, no bias, state-dict round trip; the live
target rows of real frames point only at enemy tokens.
"""
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

from pipeline import target_obs as TO                                    # noqa: E402

PRE = "de0f05e"                       # the last commit before TARGET-OBS code: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
N_DEC = 60                            # recorded live decisions used by the model tests


def _tok(rows):
    """rows = [(mine, x, y)] in the side's board frame -> tok [U, 16], mask [U] (unit tokens, not spells)."""
    tok = np.zeros((8, 16), np.float32)
    mask = np.zeros(8, bool)
    for i, (mine, x, y) in enumerate(rows):
        tok[i, 1 if mine else 2] = 1.0
        tok[i, 4], tok[i, 5] = x, y
        mask[i] = True
    return tok, mask


def _u(uid, team, x, y, target=None, frac=None, kind="troop"):
    return dict(uid=uid, team=team, x=x, y=y, kind=kind, attack=dict(target=target, frac=frac))


class TestRows(unittest.TestCase):
    def test_layout(self):
        # side 0: my Knight (uid 1) at (9, 10) fights an enemy Hog (uid 2) at (9, 12); the Hog targets my princess
        # tower (uid 10); the enemy tower (uid 11) shoots my Knight; uid 3 = an enemy far away with no token.
        units = [_u(10, 0, 3.5, 6.5, target=2, kind="princess_tower"), _u(11, 1, 3.5, 25.5, target=1, kind="princess_tower"),
                 _u(1, 0, 9.0, 10.0, target=2, frac=0.5), _u(2, 1, 9.0, 12.0, target=10, frac=0.25),
                 _u(3, 1, 1.0, 30.0)]
        tok, mask = _tok([(True, 9 / 18, 1 - 10 / 32), (False, 9 / 18, 1 - 12 / 32)])
        rows, idx = TO.target_rows(units, tok, mask, 0)
        self.assertEqual(rows.shape, (8, TO.TGT_N))
        np.testing.assert_allclose(rows[0], [1, 1, 0, 0.5, 0, -2 / 32, 0, 1], atol=1e-6)
        np.testing.assert_allclose(rows[1], [1, 0, 1, 0.25, (3.5 - 9) / 18, 5.5 / 32, 0.25, 1], atol=1e-6)
        self.assertEqual(idx.tolist(), [1, -1, -1, -1, -1, -1, -1, -1])
        self.assertFalse(rows[2:].any())
        # side 1 sees the same board mirrored: its tokens at mirrored points, its own unit = the Hog
        tok1, mask1 = _tok([(False, 1 - 9 / 18, 10 / 32), (True, 1 - 9 / 18, 12 / 32)])
        r1, i1 = TO.target_rows(units, tok1, mask1, 1)
        np.testing.assert_allclose(r1[0], [1, 1, 0, 0.5, 0, 2 / 32, 0, 1], atol=1e-6)
        np.testing.assert_allclose(r1[1], [1, 0, 1, 0.25, (9 - 3.5) / 18, -5.5 / 32, 0.25, 1], atol=1e-6)
        self.assertEqual(i1[:2].tolist(), [1, -1])
        # live schema (generation + tower flag) gives the same rows
        live = [dict(generation=u["uid"], team=u["team"], x=u["x"], y=u["y"], tower=u["kind"] != "troop",
                     attack=u["attack"]) for u in units]
        r2, i2 = TO.target_rows(live, tok, mask, 0)
        self.assertTrue(np.array_equal(r2, rows) and np.array_equal(i2, idx))

    def test_degraded_and_empty(self):
        tok, mask = _tok([(True, 0.5, 0.5)])
        for us in (None, []):
            r, i = TO.target_rows(us, tok, mask, 0)
            self.assertFalse(r.any())
            self.assertTrue((i == -1).all())

    def test_match_equals_align(self):
        from pipeline.e1_eval import CUE_MATCH_TILES
        from pipeline.live_unit_state import align
        self.assertEqual(TO.MATCH_TILES, CUE_MATCH_TILES)
        rng = np.random.default_rng(0)
        for trial in range(200):
            side = int(rng.integers(2))
            n_t, n_b = int(rng.integers(0, 8)), int(rng.integers(0, 8))
            tok, mask = _tok([(bool(rng.integers(2)), rng.random(), rng.random()) for _ in range(n_t)])
            bodies = [dict(team=int(rng.integers(2)), x=float(rng.random() * 18), y=float(rng.random() * 32)) for _ in range(n_b)]
            got = TO.token_match(tok, mask, side, bodies)
            ref = align(tok, mask, side, [(b["team"], b["x"], b["y"], [1.0] + [float(j == k) for k in range(21)])
                                          for j, b in enumerate(bodies)])
            want = {int(np.argmax(ref[t, 1:])): t for t in range(len(tok)) if ref[t, 0] > 0}
            self.assertEqual(got, want, trial)


class TestConfig(unittest.TestCase):
    def test_hash_absent_is_pre(self):
        from pipeline import rl_royale as RL
        cfg = RL.load_config(YAML, [], False)
        self.assertNotIn("target_obs", cfg)
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
        if src.returncode:
            raise unittest.SkipTest(src.stderr)
        P = types.ModuleType("rl_royale_pre_tgt")
        P.__file__, P.__package__ = str(REPO / "pipeline/rl_royale.py"), "pipeline"
        sys.modules[P.__name__] = P
        exec(compile(src.stdout, P.__name__, "exec"), P.__dict__)
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))
        for off in (None, False):
            self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, target_obs=off)))
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, target_obs=True)))
        self.assertIs(RL.load_config(YAML, ["target_obs=on"], False)["target_obs"], True)
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, ["target_obs=maybe"], False)


def _live_batches():
    """N_DEC recorded CLXIII live decisions (test_decide_identity's first log) through the live path: each decision's
    model batch b + the live target rows of its decision frame (target_obs.live_target_rows on the same frame / prev /
    tok / mask / side the cue rows use)."""
    from pipeline.tests import test_decide_identity as D
    if not D.CKPT.exists() or not (D.LIVE_DIR / D.LOGS[0]).exists():
        raise unittest.SkipTest("CLXIII or the recorded live logs are not on this machine")
    start, ev = D.read_log(D.LIVE_DIR / D.LOGS[0])
    pilot = D.live_pilot(start)
    if getattr(pilot, "cues", None) is None:
        raise unittest.SkipTest("the recorded start has no cue source")
    got, stash = [], {}
    rows_fn = pilot.cues.rows

    def rows(frame, prev, tok, mask, side):
        stash["tgt"] = TO.live_target_rows(pilot.cues, frame, prev, tok, mask, side)
        stash["tok"] = tok
        return rows_fn(frame, prev, tok, mask, side)
    pilot.cues.rows = rows
    fwd = pilot._policy_forward

    def wrapped(b):
        got.append(({k: v.clone() for k, v in b.items()}, stash["tgt"], stash["tok"]))
        return fwd(b)
    pilot._policy_forward = wrapped
    pilot.reset_match()
    f = None
    for e in ev:
        if len(got) >= N_DEC:
            break
        if e[0] == "frame":
            f = e[1]
            pilot.observe(f)
        elif e[0] == "decision" and f is not None and f["game_tick"] == e[1]:
            pilot.decide(f)
        elif e[0] == "confirmed" and None not in e[2:]:
            pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
        elif e[0] == "ability":
            pilot.record_ability(e[1], e[2])
    return pilot.model, got


def _heads(m, b):
    with torch.no_grad():
        enc = m.encode_gen(b)
        out = m.heads_gen(enc, b)
        out["g"] = enc["g"]
        out["cell"] = m.cell_logits_gen(enc, b["hand_card"][:, 0], b["hand_form"][:, 0])
    return {k: v for k, v in out.items() if torch.is_tensor(v)}


def _heads_grad(m, b):
    enc = m.encode_gen(b)
    return m.heads_gen(enc, b)


class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.dec = _live_batches()
        cls.model.eval()

    def _same(self, a, b):
        self.assertEqual(a.keys(), b.keys())
        for k in a:
            self.assertTrue(torch.equal(a[k], b[k]), k)

    def test_zero_layers_identical_to_clxiii(self):
        m = copy.deepcopy(self.model)
        m.add_target_in()
        g = torch.Generator().manual_seed(1)
        n_real = 0
        for b, (rows, idx), _ in self.dec:
            ref = _heads(self.model, b)
            U = b["tok"].shape[1]
            rnd = {"tgt": torch.randn(1, U, TO.TGT_N, generator=g),
                   "tgt_idx": torch.randint(-1, U, (1, U), generator=g)}
            real = {"tgt": torch.from_numpy(rows)[None], "tgt_idx": torch.from_numpy(idx)[None]}
            n_real += int((idx >= 0).sum())
            self._same(_heads(m, {**b, **rnd}), ref)
            self._same(_heads(m, {**b, **real}), ref)
            self._same(_heads(m, b), ref)                                  # no target keys: layers skipped
        self.assertGreater(n_real, 0)                                      # the real rows do carry target edges
        with torch.no_grad():
            for lin in (m.tgt_in, m.tgt_out, m.tgt_back):
                lin.weight.normal_(0, 0.05, generator=g)
        b, (rows, idx), _ = next(d for d in self.dec if (d[1][1] >= 0).any())
        real = {"tgt": torch.from_numpy(rows)[None], "tgt_idx": torch.from_numpy(idx)[None]}
        self.assertFalse(torch.equal(_heads(m, {**b, **real})["g"], _heads(self.model, b)["g"]))   # wired in
        U = b["tok"].shape[1]
        none = {"tgt": torch.zeros(1, U, TO.TGT_N), "tgt_idx": torch.full((1, U), -1)}
        self._same(_heads(m, {**b, **none}), _heads(self.model, b))       # no targets: no bias, nothing added
        # round trip: a target checkpoint builds the layers; a pre-target one into a model with them zero-fills
        fresh = copy.deepcopy(self.model)
        fresh.load_state_dict(m.state_dict())
        self.assertTrue(torch.equal(fresh.tgt_out.weight, m.tgt_out.weight))
        m.load_state_dict(self.model.state_dict())
        self.assertFalse(m.tgt_in.weight.any() or m.tgt_out.weight.any() or m.tgt_back.weight.any())
        self.assertNotIn("tgt_in.weight", self.model.state_dict())

    def test_zero_layers_get_gradients(self):
        """At zero init every target layer still gets a non-zero gradient from real target rows (it can train)."""
        m = copy.deepcopy(self.model).train()
        m.add_target_in()
        b, (rows, idx), _ = next(d for d in self.dec if (d[1][1] >= 0).any())
        out = _heads_grad(m, {**b, "tgt": torch.from_numpy(rows)[None], "tgt_idx": torch.from_numpy(idx)[None]})
        (out["gate"].sum() + out["value"].sum() + out["card"].logsumexp(-1).sum()).backward()
        for lin in (m.tgt_in, m.tgt_out, m.tgt_back):
            self.assertGreater(float(lin.weight.grad.abs().sum()), 0.0)

    def test_live_rows_point_at_enemy_tokens(self):
        edges = bad = known = 0
        for b, (rows, idx), tok in self.dec:
            known += int((rows[:, 0] > 0).sum())
            for t in np.flatnonzero(idx >= 0):
                edges += 1
                bad += int((tok[t, 1] > 0) == (tok[idx[t], 1] > 0))            # a target on the attacker's own side
        self.assertGreater(known, 0)
        self.assertGreater(edges, 0)
        self.assertEqual(bad, 0)


class TestLiveWiring(unittest.TestCase):
    """LIVE-TGT 10-31: live_play.load_pilot + GenPilot.row with a target-layer checkpoint (temp copies of CLXIII + zero /
    planted target layers) on N_DEC recorded live decisions: the TARGET-VAL acquired rule is picked for it (CLXIII keeps
    the S6 rule), zero layers decide exactly as CLXIII, planted layers move g exactly on the rows with known tokens."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pipeline.tests import test_decide_identity as D
        if not D.CKPT.exists() or not (D.LIVE_DIR / D.LOGS[0]).exists():
            raise unittest.SkipTest("CLXIII or the recorded live logs are not on this machine")
        cls.D, cls.tmp = D, tempfile.TemporaryDirectory()
        st = torch.load(D.CKPT, map_location="cpu", weights_only=False)
        d, g = int(st["args"]["d"]), torch.Generator().manual_seed(1)
        cls.ck = {}
        for tag, mk in (("zero", torch.zeros), ("planted", lambda *s: torch.randn(*s, generator=g) * 0.05)):
            sd = {**st["model"], "tgt_in.weight": mk(d, TO.TGT_N), "tgt_out.weight": mk(d, d), "tgt_back.weight": mk(d, d)}
            cls.ck[tag] = Path(cls.tmp.name) / f"{tag}.pt"
            torch.save({**st, "model": sd}, cls.ck[tag])
        cls.ck["clxiii"] = D.CKPT
        cls.start, cls.ev = D.read_log(D.LIVE_DIR / D.LOGS[0])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _pilot(self, tag, cue_inputs=True):
        D = self.D
        D_CKPT = D.CKPT
        D.CKPT = self.ck[tag]                                  # test_decide_identity.live_pilot reads the module global
        try:
            start = self.start if cue_inputs else {**self.start, "cue_inputs": None}
            return D.live_pilot(start)
        finally:
            D.CKPT = D_CKPT

    def _run(self, pilot):
        """-> [(decision without its 'tgt' log, the trunk g, b keys, tgt log)] for the first N_DEC decisions."""
        got, cur = [], {}
        fwd = pilot._policy_forward

        def wrapped(b):
            out, cell = fwd(b)
            cur.update(g=out["g"].clone(), keys=set(b))
            return out, cell
        pilot._policy_forward = wrapped
        pilot.reset_match()
        f = None
        for e in self.ev:
            if len(got) >= N_DEC:
                break
            if e[0] == "frame":
                f = e[1]
                pilot.observe(f)
            elif e[0] == "decision" and f is not None and f["game_tick"] == e[1]:
                d = self.D.canon(pilot.decide(f))
                got.append((dict(d, tgt=None), cur["g"], cur["keys"], d.get("tgt")))
            elif e[0] == "confirmed" and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == "ability":
                pilot.record_ability(e[1], e[2])
        return got

    def test_load_pilot_rule_and_log(self):
        import live_play as lp                                 # on sys.path after live_pilot
        ref, tgt = self._pilot("clxiii"), self._pilot("zero")
        self.assertEqual((ref.cues.acq_rule, tgt.cues.acq_rule), ("live", "engine"))
        self.assertNotIn("targets", lp.cue_log(ref))
        self.assertEqual({k: lp.cue_log(tgt)[k] for k in ("targets", "acq_rule")}, dict(targets=True, acq_rule="engine"))
        with self.assertRaises(SystemExit):                    # a target-layer model never plays target-blind
            self._pilot("zero", cue_inputs=False)

    def test_zero_layers_decide_as_clxiii_and_planted_reach_the_model(self):
        ref = self._run(self._pilot("clxiii"))
        runs = {}
        for tag in ("zero", "planted"):
            p = self._pilot(tag)
            p.cues.acq_rule = "live"                           # isolate the wiring from the reader rule (same cues)
            runs[tag] = self._run(p)
        self.assertEqual(len(ref), N_DEC)
        self.assertTrue(all("tgt" not in k and t is None for _, _, k, t in ref))
        for (dr, gr, _, _), (dz, gz, kz, tz) in zip(ref, runs["zero"]):
            self.assertEqual(dr, dz)                           # decision dicts (taps, xy, why, cue log) identical
            self.assertTrue(torch.equal(gr, gz) and {"tgt", "tgt_idx"} <= kz and tz["acq_rule"] == "live")
        moved = [not torch.equal(gr, gp) for (_, gr, _, _), (_, gp, _, _) in zip(ref, runs["planted"])]
        known = [tp["known"] > 0 for _, _, _, tp in runs["planted"]]
        self.assertEqual(moved, known)                         # rows reach the model: g moves iff a token has a row
        self.assertGreater(sum(known), 0)
        self.assertGreater(sum(tp["edges"] for _, _, _, tp in runs["planted"]), 0)


if __name__ == "__main__":
    unittest.main()
