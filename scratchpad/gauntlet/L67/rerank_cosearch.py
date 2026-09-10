"""L67n: BUG or SHIFT? Score the reranker head on the SEARCH's own states, inside the search's own matches.

Observed: offline, the head's best candidate beats WAIT on ~18% of held-out decisions at margin 0 (search plays
~20%). In closed loop -- the reranker choosing its own moves -- it plays on 1.5% (18 of 1,184 decisions over 4
matches, all lost, mean tower -2.61). Two very different explanations produce that gap:

  COVARIATE SHIFT -- the corpus states come from matches the SEARCH was steering; once the reranker hesitates,
                     the board empties into states the corpus rarely contains, where it predicts "wait" again.
                     Fix: label the learner's own states (DAgger).
  FEATURE BUG     -- the online path (sim state -> contract -> encoder -> head) does not reproduce the offline
                     inputs, so predictions are wrong everywhere online. Fix: find the mismatch; DAgger would
                     only hide it.

This separates them. The search plays exactly as when it generated the corpus (its moves decide the match), and
at every searched decision the head also scores the same shortlist through the ONLINE path. If the head's
would-play rate on these search-visited states is ~18%, the online path is consistent and the closed-loop
collapse is shift. If it is ~1.5% here too, it is a bug.

Also records, per decision, the head's predicted advantage beside the rollout's true advantage, so their online
correlation can be compared with the offline one (0.66 on the clean report fold).

usage: python scratchpad/gauntlet/L67/rerank_cosearch.py --ckpt <v6lat_s0.pt> --head <head.pt> --matches 2
"""
from __future__ import annotations

import argparse
import json
import sys
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


class CoScoringSearcher(StudentSearcher):
    """Plays exactly like the search; additionally scores each searched shortlist with the head (online path)."""

    def __init__(self, env, model, deck, *, head, **kw):
        super().__init__(env, model, deck, **kw)
        self.head = head
        self.rows = []           # (head_max_pred, true_best_adv, list of (pred, true_adv))

    def act(self, i):
        p_play, cands, _order = self._shortlist()
        if not cands:
            return super().act(i)
        env = self.env
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
        wait_s = self._rollout((0, 0, 0))
        true_adv = np.array([self._rollout((1, c[0], c[1])) - wait_s for c in cands], dtype=np.float32)
        self.rows.append((float(pred.max()), float(true_adv.max()), list(zip(pred.tolist(), true_adv.tolist()))))
        # now play exactly as the search does (its own rollouts decide), so the states stay search-visited
        return super().act(i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=2)
    ap.add_argument("--seed0", type=int, default=950000)
    ap.add_argument("--margin", type=float, default=0.0)
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
    actor = CoScoringSearcher(env, model, deck, head=head, horizon=12.0, interval=1, topk=4, cells=3, crown_w=1.0,
                              scorer_cls=Scorer, mode="search", gate_tau=0.27, degrade=True,
                              grid=str(args.get("grid", "floor")), torch=torch, cell_xy=cell_xy,
                              hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens)
    for m in range(a.matches):
        actor.reset()
        r = play_match(env, actor, a.seed0 + m)
        print("m%03d outcome %s tower_delta %+.3f plays %d decisions-scored %d"
              % (m, r["outcome"], r["tower_delta"], r["plays"], len(actor.rows)), flush=True)

    mx = np.array([r[0] for r in actor.rows]); tb = np.array([r[1] for r in actor.rows])
    pairs = np.array([p for r in actor.rows for p in r[2]])
    out = {"decisions_scored": int(len(mx)),
           "head_would_play_rate_on_search_states": round(float((mx > a.margin).mean()), 4),
           "search_play_rate_on_these_states": round(float((tb > 0).mean()), 4),
           "head_max_pred_median": round(float(np.median(mx)), 4),
           "online_corr_pred_vs_true_adv": round(float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1]), 4),
           "verdict_hint": "SHIFT if would-play rate is near the search's (~0.2); BUG if it is near 0.015",
           "margin": a.margin}
    print(json.dumps(out, indent=1), flush=True)
    if a.out:
        a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
