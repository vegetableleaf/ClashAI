"""L67h: the S1 student ACTING inside the RL sim -- the baseline a search has to beat.

Chain of reasoning this sits in:
  * imitation is nearly exhausted (the pro-vs-pro ceiling is 27.5% exact cell and the student is at 21.0),
  * but the pro's own tile is in the student's top-3 44.2% of the time, so a RERANKER has room,
  * and the rollout search that licenses distillation (+19.9 sigma) was measured on the OLD CNN policy --
    which is NOT evidence about this model. Before building a search around the student, the student has to
    play in the sim at all, and its unsearched baseline has to be measured on the same instrument.

This file is the actor + that baseline. It reuses the sim's own play_match loop so the numbers land on the
same instrument the search arms use (tower_delta, crowns, plays), and it can run under either view:
  --degrade   the student sees what the LIVE path gives it (no unit HP, no exact elixir, no opponent elixir)
  (default)   the student sees the sim's ground truth -- the PRIVILEGED view the distillation spec warns about

usage: python scratchpad/gauntlet/L67/student_sim.py --ckpt <pt> --matches 24 [--degrade] [--tau 0.27]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sim_contract import assert_frame, from_sim                          # noqa: E402

PAST_K = 3


class StudentActor:
    """act(i) -> ((play, sim_card_id, sim_cell), meta), the interface rollout_search.play_match expects."""

    def __init__(self, env, model, deck, *, gate_tau, degrade, grid, torch, cell_xy,
                 hand_mask_from_sc, to_tokens, stall_elixir=None, stall_seconds=12.0):
        self.env, self.model, self.deck = env, model, deck
        self.gate_tau, self.degrade, self.grid = float(gate_tau), bool(degrade), str(grid)
        self._torch, self._cell_xy = torch, cell_xy
        self._hand_mask, self._to_tokens = hand_mask_from_sc, to_tokens
        self._past = []
        self.p_hist = []
        # ANTI-STALL: when elixir is at cap and nothing has been played for a while, take the top affordable
        # candidate regardless of the gate. Overflowing at 10 elixir is strictly wasted resource, and pros
        # play 23-36% of the time in exactly the states the live bot sits frozen in (L67i gate_by_state).
        # None disables it; this is the arm under test.
        self.stall_elixir = stall_elixir
        self.stall_seconds = float(stall_seconds)
        self._last_play_t = None
        self.stats = {"decisions": 0, "plays": 0, "wait": 0, "unaffordable": 0, "stall_fired": 0}

    def reset(self):
        self._past = []
        self._last_play_t = None

    def _past_array(self, now):
        p = np.full((PAST_K, 4), -1.0, dtype=np.float32)
        for k, (slot, x, y, t0) in enumerate(self._past[::-1][:PAST_K]):
            p[k] = (float(slot), float(x), float(y), float(now - t0))
        return p

    def act(self, i):
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
            self.p_hist.append(p_play)
            self.stats["decisions"] += 1
            # deck slot -> the sim card id actually in hand AND affordable
            elix = float(env.eng.elixir[0])
            slot_to_sim = {}
            for cid in env._hand_ids():
                base = str(list(env.deck_keys)[int(cid)])
                s = self.deck.slot_of(base)
                if s < 0:
                    continue
                if float(env.specs[int(cid)].elixir) <= elix + 1e-6:
                    slot_to_sim[s] = int(cid)
            if not slot_to_sim:
                self.stats["unaffordable"] += 1
                return (0, 0, 0), None
            stalled = False
            if self.stall_elixir is not None:
                idle = float(env.eng.t) - (self._last_play_t if self._last_play_t is not None else 0.0)
                stalled = (elix >= float(self.stall_elixir)) and (idle >= self.stall_seconds)
            if p_play <= self.gate_tau and not stalled:
                self.stats["wait"] += 1
                return (0, 0, 0), None
            if p_play <= self.gate_tau:
                self.stats["stall_fired"] += 1
            logits = out["card"][0].clone()
            ok = torch.zeros_like(logits, dtype=torch.bool)
            for s in slot_to_sim:
                ok[s] = True
            slot = int(logits.masked_fill(~ok, float("-inf")).argmax().item())
            cell = int(self.model.cell_logits(enc, torch.tensor([slot]))[0].argmax().item())
        bx, by = self._cell_xy(cell, self.grid)
        sim_cell = int(env.actions.cell_at(float(bx), float(by)))   # the sim warp is the identity (env.py:54-70)
        self._past.append((slot, float(bx), float(by), float(env.eng.t)))
        self._last_play_t = float(env.eng.t)
        self.stats["plays"] += 1
        return (1, int(slot_to_sim[slot]), sim_cell), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=24)
    ap.add_argument("--seed0", type=int, default=900000)
    ap.add_argument("--tau", type=float, default=0.27)
    ap.add_argument("--degrade", action="store_true")
    ap.add_argument("--deck", default="icebow")
    ap.add_argument("--stall-elixir", type=float, default=None,
                    help="anti-stall: elixir at or above this, with no play for --stall-seconds, forces the "
                         "top affordable candidate regardless of the gate")
    ap.add_argument("--stall-seconds", type=float, default=12.0)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import torch
    from clashrl.config import Config
    from clashrl.sim.env import SimMatchEnv
    from clashrl.sim.rollout_search import play_match
    from pipeline.model_v3 import S1Model, cell_xy, hand_mask_from_sc
    from pipeline.obs_contract import load_deck, to_tokens

    torch.set_num_threads(1)
    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None                    # LADDER pool, the trainer's own eval default
    env.reset()
    assert_frame(env)

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()
    deck = load_deck(a.deck)

    actor = StudentActor(env, model, deck, gate_tau=a.tau, degrade=a.degrade, grid=grid, torch=torch,
                         cell_xy=cell_xy, hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens,
                         stall_elixir=a.stall_elixir, stall_seconds=a.stall_seconds)
    recs = []
    t0 = time.perf_counter()
    for m in range(a.matches):
        actor.reset()
        r = play_match(env, actor, a.seed0 + m)
        recs.append(r)
        print("m%03d seed %d outcome %7s tower_delta %+0.3f plays %3d t_end %.0fs"
              % (m, a.seed0 + m, r["outcome"], r["tower_delta"], r["plays"], r["t_end"]), flush=True)
    td = np.array([r["tower_delta"] for r in recs])
    wins = float(np.mean([r["outcome"] == "win" for r in recs]))
    ph = np.array(actor.p_hist)
    summary = {"ckpt": str(a.ckpt), "matches": len(recs), "degrade": bool(a.degrade), "tau": a.tau,
               "win_pct": round(100.0 * wins, 1),
               "tower_delta_mean": round(float(td.mean()), 4),
               "tower_delta_sem": round(float(td.std(ddof=1) / max(1.0, np.sqrt(len(td)))), 4),
               "plays_per_match": round(float(np.mean([r["plays"] for r in recs])), 1),
               "decisions": actor.stats["decisions"], "wait": actor.stats["wait"],
               "no_affordable": actor.stats["unaffordable"],
               "gate_p_mean": round(float(ph.mean()), 4),
               "gate_frac_over_tau": round(float((ph > a.tau).mean()), 4),
               "stall_elixir": a.stall_elixir, "stall_seconds": a.stall_seconds,
               "stall_fired": actor.stats.get("stall_fired", 0),
               "wall_s": round(time.perf_counter() - t0, 1)}
    print(json.dumps(summary, indent=1), flush=True)
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "matches": recs}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
