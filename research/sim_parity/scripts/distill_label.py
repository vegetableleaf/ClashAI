"""DISTILLATION CORPUS LABELLER -- teacher = flat rollout search over the frozen policy.

HANDOFF section 6-PRIORITY-B. This is a MEASUREMENT/BUILD tool, not shipped code: nothing in
`icebow/src` or `hogeq/src` imports it.

WHAT IT DOES. Plays matches with the shipped greedy policy, and at EVERY decision runs the
existing `scratchpad/rollout_search.py` search over the SAME frozen weights. The search's pick is
the teacher label; the policy's own greedy action is recorded alongside it as the FLOOR that any
student has to beat to be worth anything.

THE TEACHER IS NOT REIMPLEMENTED. `Searcher` is imported and subclassed, so the corpus is labelled
by the identical code that produced the 37.0% -> 85.7% measurement in
`research/sim_parity/ledger/rollout_search.md`. A second implementation would be a second thing to
keep in sync, and the ledger's numbers would stop applying to it.

THE SETTINGS ARE MEASURED, NOT CHOSEN (section 6-PRIORITY-B; do not re-litigate):
  H = 12 s   horizon. A measured optimum -- 16/20/30 are within 1 sigma, and rolling to the MATCH
             END is 5.14 sigma WORSE. The cap is the idle-rollout default, not search.
  N = 1      search EVERY decision. ⚠ THE ONE SETTING THAT MUST NOT MOVE. At N=5 the targets are
             contaminated by the unsearched policy decisions that follow them and the restraint
             signal comes out with the WRONG SIGN (search appears to play MORE; at N=1 it plays
             LESS). Distilling N=5 targets teaches the opposite lesson. Guarded below.
  K = 4      candidate cards. INERT (2/4/8 within 0.3 sigma); K=4 is already all-affordable.
  cells = 3  cells per candidate card. Kept because it is the ceiling arm's setting, but the CELL
             LABEL IS NOT A TARGET -- see below.

WHAT IS LABELLED, AND WHAT IS DELIBERATELY NOT. The corpus carries the teacher's GATE decision and
CARD choice. It also records the cell, but only as provenance: card+gate search alone is +22.0pp
and adding cell search adds +3.3pp, while placement is separately measured as worth ~nothing (the
perfect-aim arm is +0.07 sigma). A cell-distillation arm is not worth its own risk, so the student
trainer ignores that column.

THE RECORD IS THE STUDENT'S EXACT INPUT. `_forward` feeds the net exactly
(obs, hand_vec, next_vec, elixir_vec, threat_vec); all five are stored verbatim, so a student can be
fed the identical tensors with no reconstruction step that could drift.

⚠ REPRODUCIBILITY. `rollout_search.py` sets PYTHONHASHSEED with `os.environ.setdefault` AFTER
interpreter start, which is a NO-OP: two runs of the identical N=1 config gave 78.7% and 80.7%.
EXPORT IT IN THE ENVIRONMENT before running this. The check below refuses to start otherwise, and
the value that was actually in force is written into the metadata either way.

⚠ RUN IT WITH THE DECK'S OWN VENV: `icebow\\.venv\\Scripts\\python.exe`. Bare `python` is the ROOT
venv (torch 2.13.0+cpu, not the deck's 2.11.0+cu128) and is worth -6.0pp winrate / 2.62 sigma on
its own -- larger than most effects this project measures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(r"C:\Users\benpe\ClashBot")
SCRATCH = ROOT / "scratchpad"
sys.path.insert(0, str(SCRATCH))            # the teacher lives here; reuse it, never re-write it

import numpy as np                                                        # noqa: E402
import torch                                                              # noqa: E402

import rollout_search as RS                                               # noqa: E402
from clashrl.config import Config                                         # noqa: E402
from clashrl.sim.env import SimMatchEnv                                   # noqa: E402


def _sha(path: pathlib.Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(("git",) + args, cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:                                                     # noqa: BLE001
        return "<unavailable>"


class LabellingSearcher(RS.Searcher):
    """`Searcher` with one extra job: keep the student's exact input beside the teacher's answer.

    Overriding `act` rather than copying it means the teacher's decision procedure is literally the
    shipped one -- the rows below are a side effect of it, never a re-derivation.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rows: list[dict] = []
        self._match = -1
        self._collect = True

    def act(self, step_i: int):
        e = self.env
        # Snapshot the input BEFORE `act` -- the search forks the engine, and although the fork is
        # a deepcopy, taking the record first makes that independent of any future change to it.
        obs = np.asarray(e._last_obs, dtype=np.uint8).copy()
        hand = np.asarray(e.hand_vec, dtype=np.float32).copy()
        nxt = np.asarray(e.next_vec, dtype=np.float32).copy()
        elx = np.asarray(e.elixir_vec, dtype=np.float32).copy()
        thr = np.asarray(e.threat_vec, dtype=np.float32).copy()
        t_now = float(e.eng.t)
        pol_before = self.greedy_action()[0]

        pick, searched = super().act(step_i)

        if self._collect and searched:
            self.rows.append({
                "obs": obs, "hand": hand, "next": nxt, "elx": elx, "thr": thr,
                "match": self._match, "step": int(step_i), "t": t_now,
                "teach_gate": int(pick[0]), "teach_card": int(pick[1]) if pick[0] else -1,
                "teach_cell": int(pick[2]) if pick[0] else -1,
                "pol_gate": int(pol_before[0]),
                "pol_card": int(pol_before[1]) if pol_before[0] else -1,
                "pol_cell": int(pol_before[2]) if pol_before[0] else -1,
            })
        return pick, searched


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=12,
                    help="SMALL by default: the box is shared with training and labelling is "
                         "CPU-heavy. The full corpus is a separate, deliberate run.")
    ap.add_argument("--seed0", type=int, default=700000)
    ap.add_argument("--horizon", type=float, default=12.0)
    ap.add_argument("--interval", type=int, default=1, help="N. MUST be 1; see the module docstring")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--cells", type=int, default=3)
    ap.add_argument("--crown", type=float, default=1.0)
    ap.add_argument("--gate-tau", type=float, default=None)
    ap.add_argument("--ckpt", default=str(SCRATCH / "_rs_policy.pt"))
    ap.add_argument("--out", default=str(ROOT / "scratchpad" / "distill_corpus.npz"))
    ap.add_argument("--allow-interval", action="store_true",
                    help="override the N=1 guard. Only for a deliberate contamination experiment.")
    args = ap.parse_args()

    if args.interval != 1 and not args.allow_interval:
        raise SystemExit(
            "REFUSING: --interval must be 1. At N=5 the targets are contaminated by the unsearched\n"
            "policy decisions that follow them and the restraint signal INVERTS (search appears to\n"
            "play MORE; at N=1 it plays LESS). Distilling those targets teaches the opposite\n"
            "lesson. Pass --allow-interval only to reproduce that contamination on purpose.")

    hashseed = os.environ.get("PYTHONHASHSEED")
    if hashseed != "0":
        raise SystemExit(
            f"REFUSING: PYTHONHASHSEED={hashseed!r}, not '0'. rollout_search.py sets it with\n"
            "os.environ.setdefault AFTER interpreter start, which is a NO-OP -- two runs of the\n"
            "identical N=1 config gave 78.7% and 80.7%. Export it in the ENVIRONMENT first:\n"
            "  $env:PYTHONHASHSEED='0'   (PowerShell)  /  export PYTHONHASHSEED=0   (bash)")

    torch.set_num_threads(1)
    torch.manual_seed(0)
    np.random.seed(0)
    RS.random.seed(0)

    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None                 # LADDER pool -- the trainer's own eval setting
    device = torch.device("cpu")
    net = RS.load_net(args.ckpt, env, device)
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    if args.gate_tau is not None:
        gate_tau = float(args.gate_tau)

    s = LabellingSearcher(env, net, device, args.horizon, args.interval, args.topk,
                          args.crown, gate_tau, cells=args.cells)

    recs, wall0 = [], time.perf_counter()
    for m in range(args.matches):
        s._match = m
        recs.append(RS.play_match(env, s, args.seed0 + m))
        el = time.perf_counter() - wall0
        print(f"  [label] match {m+1}/{args.matches}  rows={len(s.rows)}  "
              f"{el/(m+1):.1f} s/match  {60.0*len(s.rows)/max(el,1e-9):.0f} rows/min", flush=True)

    rows = s.rows
    if not rows:
        raise SystemExit("no rows labelled")

    out = pathlib.Path(args.out)
    meta = {
        # EVERY ONE OF THESE HAS PRODUCED A WRONG CONCLUSION ON THIS PROJECT AT LEAST ONCE.
        "checkpoint": os.path.abspath(args.ckpt),
        "checkpoint_sha256_16": _sha(pathlib.Path(args.ckpt)),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "interpreter": sys.executable,
        "torch": torch.__version__,
        "pythonhashseed": hashseed,
        "seed0": args.seed0, "matches": args.matches,
        "seed_range": [args.seed0, args.seed0 + args.matches - 1],
        "horizon": args.horizon, "interval": args.interval, "topk": args.topk,
        "cells": args.cells, "crown_w": args.crown, "gate_tau": gate_tau,
        "obs_shape": list(env.obs_shape), "n_cards": int(env.n_cards),
        "n_cells": int(env.n_cells), "threat_dim": int(env.threat_dim),
        "card_bases": [env.specs[i].base for i in range(env.n_cards)],
        "card_elixir": [float(env.specs[i].elixir) for i in range(env.n_cards)],
        "rows": len(rows),
        "matches_won": sum(r["outcome"] == "win" for r in recs),
        "tower_delta_mean": float(np.mean([r["tower_delta"] for r in recs])),
        "wall_s": round(time.perf_counter() - wall0, 1),
        "note": "teacher = flat rollout search over the SAME frozen policy (rollout_search.py). "
                "The cell column is provenance only: the student trains the GATE and CARD heads.",
    }
    np.savez_compressed(
        out,
        obs=np.stack([r["obs"] for r in rows]),
        hand=np.stack([r["hand"] for r in rows]),
        nxt=np.stack([r["next"] for r in rows]),
        elx=np.stack([r["elx"] for r in rows]),
        thr=np.stack([r["thr"] for r in rows]),
        match=np.array([r["match"] for r in rows], np.int32),
        step=np.array([r["step"] for r in rows], np.int32),
        t=np.array([r["t"] for r in rows], np.float32),
        teach_gate=np.array([r["teach_gate"] for r in rows], np.int8),
        teach_card=np.array([r["teach_card"] for r in rows], np.int16),
        teach_cell=np.array([r["teach_cell"] for r in rows], np.int16),
        pol_gate=np.array([r["pol_gate"] for r in rows], np.int8),
        pol_card=np.array([r["pol_card"] for r in rows], np.int16),
        pol_cell=np.array([r["pol_cell"] for r in rows], np.int16),
        meta=np.array(json.dumps(meta)),
    )
    dis = float(np.mean([r["teach_gate"] != r["pol_gate"]
                         or (r["teach_gate"] and r["teach_card"] != r["pol_card"]) for r in rows]))
    print(json.dumps({**meta, "out": str(out), "mb": round(out.stat().st_size / 1e6, 1),
                      "teacher_vs_policy_disagree": round(dis, 4),
                      "teacher_play_rate": round(float(np.mean([r["teach_gate"] for r in rows])), 4),
                      "policy_play_rate": round(float(np.mean([r["pol_gate"] for r in rows])), 4)},
                     indent=1))


if __name__ == "__main__":
    main()
