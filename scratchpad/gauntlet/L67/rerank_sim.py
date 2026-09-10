"""L67n: does the VALUE RERANKER play better than the student it reranks? The sim A/B that decides it.

Offline regret says the head carries some of the search's evaluation; this asks the only question that matters:
does choosing by the head -- no rollouts -- win games? Same instrument as every other L67 arm: the sim's own
play_match, degraded view (what the live student sees), identical seeds, so results pair per seed against the
unsearched student (student_sim_deg.json / arm2_baseline.json) and against the rollout search itself
(arm_search.json / arm2_search.json).

Decision rule at every step: build the student's own shortlist (top-K affordable cards x top-C cells, the same
candidates the corpus scored), predict each candidate's advantage over WAIT with the head, play the best one if its
predicted advantage exceeds --margin, otherwise WAIT. The student's gate is NOT consulted -- the head decides
play-vs-wait, which is exactly what the search did when it generated the targets.

usage: python scratchpad/gauntlet/L67/rerank_sim.py --ckpt <v6lat_s0.pt> --head <rerank_head.pt> --matches 12 \
           --seed0 900000 --out <json>
"""
from __future__ import annotations

import argparse
import json
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


class RerankActor(StudentSearcher):
    """StudentSearcher's shortlist, scored by the learned head instead of by rollouts."""

    def __init__(self, env, model, deck, *, head, margin, **kw):
        super().__init__(env, model, deck, **kw)
        self.head = head
        self.margin = float(margin)
        self.pred_adv = []
        self.head_played = 0
        self.head_waited = 0

    def act(self, i):
        p_play, cands, _order = self._shortlist()
        self.stats["decisions"] += 1
        self.p_hist.append(p_play)
        if not cands:
            self.stats["unaffordable"] += 1
            return (0, 0, 0), None
        self.searched += 1
        env = self.env
        bs = from_sim(env, self.deck, degrade_to_live=self.degrade)
        tok, mask, sc = self._to_tokens(bs)
        with torch.no_grad():
            enc = self.model.encode(torch.from_numpy(np.asarray(tok)[None]),
                                    torch.from_numpy(np.asarray(mask)[None]),
                                    torch.from_numpy(np.asarray(sc)[None]),
                                    torch.from_numpy(self._past_array(float(env.eng.t))[None]))
            g = enc["g"]                                                      # [1, d]
            cells = torch.tensor([int(c[5]) for c in cands])
            slots = torch.tensor([int(c[2]) for c in cands])
            cp = enc["p"][0, self.model.cell_patch[cells]]                    # [n, d]
            pred = self.head(g.expand(len(cands), -1), cp, slots, cells).numpy()
        k = int(np.argmax(pred))
        self.pred_adv.append(float(pred[k]))
        if float(pred[k]) <= self.margin:
            self.head_waited += 1
            self.chose_wait += 1
            self.stats["wait"] += 1
            return (0, 0, 0), None
        c = cands[k]
        self.head_played += 1
        self._past.append((c[2], c[3], c[4], float(env.eng.t)))
        self.stats["plays"] += 1
        return (1, int(c[0]), int(c[1])), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=12)
    ap.add_argument("--seed0", type=int, default=900000)
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--cells", type=int, default=3)
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
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()
    head, hst = load_head(a.head)
    if Path(str(hst.get("encoder_ckpt", ""))).name != a.ckpt.name:
        raise SystemExit(f"head was trained on {hst.get('encoder_ckpt')}, not {a.ckpt}: the encoder must match")
    deck = load_deck("icebow")

    actor = RerankActor(env, model, deck, head=head, margin=a.margin, horizon=12.0, interval=1, topk=a.topk,
                        cells=a.cells, crown_w=1.0, scorer_cls=Scorer, gate_tau=0.27, degrade=True, grid=grid,
                        torch=torch, cell_xy=cell_xy, hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens)
    recs = []
    t0 = time.perf_counter()
    for m in range(a.matches):
        actor.reset()
        r = play_match(env, actor, a.seed0 + m)
        recs.append(r)
        print("m%03d seed %d outcome %7s tower_delta %+0.3f plays %3d head_played %d head_waited %d"
              % (m, a.seed0 + m, r["outcome"], r["tower_delta"], r["plays"], actor.head_played, actor.head_waited),
              flush=True)
    td = np.array([r["tower_delta"] for r in recs])
    summary = {"ckpt": str(a.ckpt), "head": str(a.head), "margin": a.margin, "matches": len(recs),
               "win_pct": round(100.0 * float(np.mean([r["outcome"] == "win" for r in recs])), 1),
               "tower_delta_mean": round(float(td.mean()), 4),
               "tower_delta_sem": round(float(td.std(ddof=1) / max(1.0, np.sqrt(len(td)))), 4),
               "plays_per_match": round(float(np.mean([r["plays"] for r in recs])), 1),
               "head_played": actor.head_played, "head_waited": actor.head_waited,
               "pred_adv_median": round(float(np.median(actor.pred_adv)), 4) if actor.pred_adv else None,
               "wall_s": round(time.perf_counter() - t0, 1)}
    print(json.dumps(summary, indent=1), flush=True)
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "matches": recs}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
