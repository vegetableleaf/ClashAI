"""L67n: DAgger for the value reranker -- label the states the HEAD itself visits.

Measured (HANDOFF 5cs.99 R): the head is consistent with its offline numbers on search-visited states (would-play
17.9% there) but plays 1.5% in its own games -- covariate shift. The search-driven corpus rarely contains the
emptied boards the head creates by hesitating, so it keeps predicting WAIT there. The standard fix is to put the
learner's own states into the training set, labelled by the expert.

Each decision here:
  * builds the student's shortlist (same candidates as the corpus) and snapshots the state,
  * rolls out WAIT and every candidate (the expert LABEL, identical to --dump-rerank),
  * then ACTS with a beta-mix: with probability --beta the search's argmax, otherwise the head's choice
    (best predicted advantage over --margin, else WAIT).
beta=1 reproduces the original corpus; beta=0 is pure on-policy. A mix keeps some games from sliding entirely into
the never-play regime, where every label would be the same lesson.

Output is the SAME format as student_search.py --dump-rerank, so rerank_train.py --shards takes it directly.

usage: python scratchpad/gauntlet/L67/rerank_dagger.py --ckpt <v6lat_s0.pt> --head <head.pt> --matches 40 \
           --seed0 960000 --beta 0.5 --dump <rr_dagger_0.npz>
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rerank_train import load_head                                       # noqa: E402
from sim_contract import from_sim                                        # noqa: E402
from student_search import StudentSearcher                               # noqa: E402


class DaggerActor(StudentSearcher):
    def __init__(self, env, model, deck, *, head, beta, margin, seed, **kw):
        super().__init__(env, model, deck, **kw)
        self.head, self.beta, self.margin = head, float(beta), float(margin)
        self._mix = random.Random(int(seed))
        self.n_expert = self.n_head = self.n_head_play = 0

    def act(self, i):
        p_play, cands, _order = self._shortlist()
        self.stats["decisions"] += 1
        if not cands:
            self.stats["unaffordable"] += 1
            return (0, 0, 0), None
        env = self.env
        snap = self._snapshot()
        wait_s = self._rollout((0, 0, 0))
        scores = [self._rollout((1, c[0], c[1])) for c in cands]
        self._rr.append({**snap, "wait_score": float(wait_s), "rep": int(self._match_id),
                         "cands": [(int(c[2]), int(c[5]), float(v)) for c, v in zip(cands, scores)]})
        if self._mix.random() < self.beta:                                   # expert acts
            self.n_expert += 1
            k = int(np.argmax(scores))
            if scores[k] <= wait_s:
                return (0, 0, 0), None
        else:                                                                # learner acts
            self.n_head += 1
            bs = from_sim(env, self.deck, degrade_to_live=self.degrade)
            tok, mask, sc = self._to_tokens(bs)
            with torch.no_grad():
                enc = self.model.encode(torch.from_numpy(np.asarray(tok)[None]),
                                        torch.from_numpy(np.asarray(mask)[None]),
                                        torch.from_numpy(np.asarray(sc)[None]),
                                        torch.from_numpy(self._past_array(float(env.eng.t))[None]))
                cells = torch.tensor([int(c[5]) for c in cands])
                slots = torch.tensor([int(c[2]) for c in cands])
                pred = self.head(enc["g"].expand(len(cands), -1), enc["p"][0, self.model.cell_patch[cells]],
                                 slots, cells).numpy()
            k = int(np.argmax(pred))
            if float(pred[k]) <= self.margin:
                return (0, 0, 0), None
            self.n_head_play += 1
        c = cands[k]
        self._past.append((c[2], c[3], c[4], float(env.eng.t)))
        self.stats["plays"] += 1
        return (1, int(c[0]), int(c[1])), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=40)
    ap.add_argument("--seed0", type=int, default=960000)
    ap.add_argument("--beta", type=float, default=0.5)
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--dump", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

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
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"]); model.eval()
    head, _ = load_head(a.head)
    deck = load_deck("icebow")
    actor = DaggerActor(env, model, deck, head=head, beta=a.beta, margin=a.margin, seed=a.seed0,
                        horizon=12.0, interval=1, topk=4, cells=3, crown_w=1.0, scorer_cls=Scorer, mode="search",
                        gate_tau=0.27, degrade=True, grid=str(args.get("grid", "floor")), torch=torch,
                        cell_xy=cell_xy, hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens)
    recs = []
    t0 = time.perf_counter()
    for m in range(a.matches):
        actor.reset()
        actor._match_id = m
        r = play_match(env, actor, a.seed0 + m)
        recs.append(r)
        print("m%03d outcome %7s tower_delta %+0.3f plays %3d | expert %d head %d head_plays %d | labelled %d"
              % (m, r["outcome"], r["tower_delta"], r["plays"], actor.n_expert, actor.n_head, actor.n_head_play,
                 len(actor._rr)), flush=True)
    n = actor.save_rerank(a.dump)
    summary = {"matches": len(recs), "beta": a.beta, "labelled_decisions": n,
               "candidates": sum(len(r["cands"]) for r in actor._rr),
               "expert_steps": actor.n_expert, "head_steps": actor.n_head, "head_plays": actor.n_head_play,
               "tower_delta_mean": round(float(np.mean([r["tower_delta"] for r in recs])), 4),
               "wall_s": round(time.perf_counter() - t0, 1)}
    print(json.dumps(summary), flush=True)
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "matches": recs}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
