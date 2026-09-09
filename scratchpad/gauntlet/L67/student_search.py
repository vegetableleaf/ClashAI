"""L67h: ROLLOUT SEARCH over the S1 STUDENT's own shortlist -- does evaluating outcomes beat its argmax?

This is the measurement that decides whether distillation is worth building, and it is deliberately NOT
inherited: the +19.9 sigma that licenses the distillation spec (HANDOFF 6-PRIORITY-B) was measured on the OLD
CNN policy, whose baseline was 37% win / tower -0.928. Search rescuing a weak policy says nothing about a
strong one, and this project has been burned by exactly that kind of transfer before.

What makes it worth asking of THIS model (measured, topk_headroom.json): the pro's own tile sits in the
student's top-3 44.2% of the time and top-5 55.5%, against a pro-vs-pro ceiling of 27.5% -- so the answer is
already inside the shortlist and the argmax is not picking it. A reranker has room. Whether a 12 s rollout can
FIND it is what this file measures.

Candidates at a searched decision: WAIT, plus the student's top-K affordable cards x top-C cells each (its own
card- and cell-head ranking, the same one the headroom was measured on). Each is rolled out by forking the
engine, applying it, then idling our side while the opponent plays on, and scored by the sim's own Scorer --
identical machinery to rollout_search.Searcher, so the arms land on one instrument.

  --interval 1   search EVERY decision (the spec's N=1; at N=5 the targets are contaminated by the unsearched
                 decisions that follow, and the restraint signal comes out with the WRONG SIGN)

usage: python scratchpad/gauntlet/L67/student_search.py --ckpt <pt> --matches 12 --horizon 12 --topk 4 --cells 3
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sim_contract import from_sim                                        # noqa: E402
from student_sim import StudentActor                                     # noqa: E402


class StudentSearcher(StudentActor):
    """StudentActor, but at every Nth decision the shortlist is rolled out and the best-scoring one played."""

    def __init__(self, env, model, deck, *, horizon, interval, topk, cells, crown_w, scorer_cls,
                 mode="search", rng_seed=0, **kw):
        super().__init__(env, model, deck, **kw)
        # CONTROLS the spec demands, because "search overrides WAIT" is most of its effect and that is also
        # what a miscalibrated gate would look like:
        #   force_play -- at a searched decision play the student's TOP candidate, no rollouts at all. If this
        #                 reproduces the gain, the finding is a GATE calibration result, not a search result.
        #   random     -- play a RANDOM candidate from the same shortlist. Separates "chooses well" from
        #                 "plays at all", and is the floor any real reranker must beat.
        self.mode = str(mode)
        import random as _r
        self._rng = _r.Random(int(rng_seed))
        self.horizon, self.interval = float(horizon), int(interval)
        self.topk, self.cells = int(topk), int(cells)
        self.scorer = scorer_cls(env, float(crown_w))
        self.sub_dt = float(getattr(env, "sub_dt", 0.1))
        self.subs = int(getattr(env, "subs", 1))
        self.rollout_steps = max(1, int(round(self.horizon / max(1e-6, self.sub_dt * self.subs))))
        self.searched = 0
        self.overrode = 0
        self.moved_cell = 0
        self.chose_wait = 0
        self.policy_wait_overridden = 0

    # -- candidate generation ------------------------------------------------------------------------
    def _shortlist(self):
        """-> (p_play, [(sim_card_id, sim_cell, slot, bx, by), ...]) from the student's OWN ranking."""
        torch = self._torch
        env = self.env
        bs = from_sim(env, self.deck, degrade_to_live=self.degrade)
        tok, mask, sc = self._to_tokens(bs)
        past = self._past_array(float(env.eng.t))
        tt = torch.from_numpy(np.asarray(tok)[None])
        mm = torch.from_numpy(np.asarray(mask)[None])
        ss = torch.from_numpy(np.asarray(sc)[None])
        pp = torch.from_numpy(past[None])
        with torch.no_grad():
            enc = self.model.encode(tt, mm, ss, pp)
            out = self.model.heads(enc, self._hand_mask(ss))
            p_play = float(torch.sigmoid(out["gate"][0]).item())
            elix = float(env.eng.elixir[0])
            slot_to_sim = {}
            for cid in env._hand_ids():
                base = str(list(env.deck_keys)[int(cid)])
                s = self.deck.slot_of(base)
                if s >= 0 and float(env.specs[int(cid)].elixir) <= elix + 1e-6:
                    slot_to_sim[s] = int(cid)
            if not slot_to_sim:
                return p_play, [], None
            logits = out["card"][0].clone()
            ok = torch.zeros_like(logits, dtype=torch.bool)
            for s in slot_to_sim:
                ok[s] = True
            order = torch.argsort(logits.masked_fill(~ok, float("-inf")), descending=True).tolist()
            cands = []
            for slot in order[:self.topk]:
                if slot not in slot_to_sim:
                    continue
                cl = self.model.cell_logits(enc, torch.tensor([int(slot)]))[0]
                for cell in torch.topk(cl, self.cells).indices.tolist():
                    bx, by = self._cell_xy(int(cell), self.grid)
                    sim_cell = int(env.actions.cell_at(float(bx), float(by)))
                    cands.append((int(slot_to_sim[slot]), sim_cell, int(slot), float(bx), float(by)))
        return p_play, cands, order

    # -- rollout -------------------------------------------------------------------------------------
    def _rollout(self, action):
        """Fork the (engine, opponent) PAIR -- they share one RNG object, and two deepcopies would split it
        into independent streams, which is the bug rollout_search.py documents at its own _rollout."""
        e = self.env
        eng, opp = copy.deepcopy((e.eng, e.opponent))
        s0 = self.scorer.snapshot(eng)
        spent = 0.0
        play, card_id, cell = action
        if play:
            spec = e.specs[card_id]
            cell = e.actions.deploy_clamp(card_id in e.anywhere_ids, cell)
            nx, ny = e.actions.cell_center(cell % e.gw, cell // e.gw)
            if eng.deploy(0, spec, nx, ny, delay_s=e.action_latency):
                spent = float(spec.elixir)
        for _ in range(self.rollout_steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(self.subs):
                eng.advance(e.sub_dt)
                if eng.done:
                    break
        return self.scorer.score(s0, eng, spent)

    # -- decision ------------------------------------------------------------------------------------
    def act(self, i):
        if self.interval <= 0 or (i % self.interval):
            return super().act(i)
        p_play, cands, _order = self._shortlist()
        self.stats["decisions"] += 1
        self.p_hist.append(p_play)
        if not cands:
            self.stats["unaffordable"] += 1
            return (0, 0, 0), None
        self.searched += 1
        if self.mode in ("force_play", "random"):
            pick = cands[0] if self.mode == "force_play" else self._rng.choice(cands)
            if not (p_play > self.gate_tau):
                self.policy_wait_overridden += 1
                self.overrode += 1
            self._past.append((pick[2], pick[3], pick[4], float(self.env.eng.t)))
            self.stats["plays"] += 1
            return (1, pick[0], pick[1]), None
        best, best_s = (0, 0, 0), self._rollout((0, 0, 0))          # WAIT is always a candidate
        wait_s = best_s
        for card_id, cell, slot, bx, by in cands:
            s = self._rollout((1, card_id, cell))
            if s > best_s:
                best, best_s = (1, card_id, cell), s
        # what the UNSEARCHED student would have done, for the disagreement counters
        pol_play = p_play > self.gate_tau
        pol = cands[0] if pol_play else None
        if best[0] == 0:
            self.chose_wait += 1
            self.stats["wait"] += 1
            if pol_play:
                self.overrode += 1
            return (0, 0, 0), None
        if not pol_play:
            self.policy_wait_overridden += 1
            self.overrode += 1
        elif pol is not None and best[1] != pol[0]:
            self.overrode += 1
        elif pol is not None and best[2] != pol[1]:
            self.moved_cell += 1
        for card_id, cell, slot, bx, by in cands:
            if card_id == best[1] and cell == best[2]:
                self._past.append((slot, bx, by, float(self.env.eng.t)))
                break
        self.stats["plays"] += 1
        return best, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=12)
    ap.add_argument("--seed0", type=int, default=900000)
    ap.add_argument("--tau", type=float, default=0.27)
    ap.add_argument("--horizon", type=float, default=12.0)
    ap.add_argument("--interval", type=int, default=1)
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--cells", type=int, default=3)
    ap.add_argument("--crown", type=float, default=1.0)
    ap.add_argument("--degrade", action="store_true")
    ap.add_argument("--mode", default="search", choices=("search", "force_play", "random"))
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import torch
    from clashrl.config import Config
    from clashrl.sim.env import SimMatchEnv
    from clashrl.sim.rollout_search import Scorer, play_match
    from pipeline.model_v3 import S1Model, cell_xy, hand_mask_from_sc
    from pipeline.obs_contract import load_deck, to_tokens

    torch.set_num_threads(1)
    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None
    env.reset()

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()
    deck = load_deck("icebow")

    searcher = StudentSearcher(env, model, deck, horizon=a.horizon, interval=a.interval, topk=a.topk,
                               cells=a.cells, crown_w=a.crown, scorer_cls=Scorer, mode=a.mode,
                               gate_tau=a.tau, degrade=a.degrade, grid=grid, torch=torch, cell_xy=cell_xy,
                               hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens)
    recs = []
    t0 = time.perf_counter()
    for m in range(a.matches):
        searcher.reset()
        r = play_match(env, searcher, a.seed0 + m)
        recs.append(r)
        print("m%03d outcome %7s tower_delta %+0.3f plays %3d searched %d overrode %d wait %d"
              % (m, r["outcome"], r["tower_delta"], r["plays"], searcher.searched, searcher.overrode,
                 searcher.chose_wait), flush=True)
    td = np.array([r["tower_delta"] for r in recs])
    summary = {"ckpt": str(a.ckpt), "matches": len(recs), "degrade": bool(a.degrade), "mode": a.mode,
               "horizon": a.horizon, "interval": a.interval, "topk": a.topk, "cells": a.cells,
               "win_pct": round(100.0 * float(np.mean([r["outcome"] == "win" for r in recs])), 1),
               "tower_delta_mean": round(float(td.mean()), 4),
               "tower_delta_sem": round(float(td.std(ddof=1) / max(1.0, np.sqrt(len(td)))), 4),
               "plays_per_match": round(float(np.mean([r["plays"] for r in recs])), 1),
               "searched": searcher.searched, "overrode": searcher.overrode,
               "moved_cell": searcher.moved_cell, "chose_wait": searcher.chose_wait,
               "policy_wait_overridden": searcher.policy_wait_overridden,
               "wall_s": round(time.perf_counter() - t0, 1)}
    print(json.dumps(summary, indent=1), flush=True)
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "matches": recs}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
