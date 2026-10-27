"""S1 speed harness (plan1026 Pillar 4b): ONE training actor's update-0 self-play job list, built by the real trainer
(rl_royale.Learner + actor_base + sample_matchups, exactly Learner.rollout's league branch) and played by the real
actor (rl_royale.actor_main, in-process: plain queues, no ActorPool). ``e1_eval.run_selfplay_batch`` is wrapped so the
call actor_main makes is CAPTURED (make_env, learner policy, opponents, jobs, cfg, n) and then played by

    --mode ref      the original run_selfplay_batch (the reference rollout decide: sample_decide_batch / styled)
    --mode batched  pipeline.batched_rollout.run (W worker processes + one forward per policy per round)

Writes <out>/results.jsonl (one learner record per match, rows stripped to their decision fields) and <out>/meta.json
(wall, matches, matches/h). ``--profile`` wraps the call in cProfile (ref mode) -> <out>/prof.pstats + timing table.

    ROYALE_RUNTIME=fin15-linux PYTHONPATH=/workspace/cb /workspace/venvf15/bin/python -I \
        scratchpad/gauntlet/L74/speed/harness.py --cfg scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml \
        --E 8 --G 4 --mode ref --out /workspace/speed/ref_e8
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))


class Q(queue.Queue):
    def cancel_join_thread(self):                       # rl_royale.actor_sender calls it on an mp queue
        pass


def build(cfg_path: str, E_: int, G: int, overrides: list[str], run_dir: Path, update: int = 0):
    import numpy as np
    from pipeline import rl_royale as R
    cfg = R.load_config(REPO / cfg_path, overrides, smoke=False)
    cfg["E"], cfg["G"] = E_, G
    run_dir.mkdir(parents=True, exist_ok=True)
    ck = run_dir / "ck"
    ck.mkdir(exist_ok=True)
    L = R.Learner(cfg, "speed", run_dir, ck, R.Log(run_dir), resume=False)
    base = L.actor_base()
    specs = R.sample_matchups(L.rng, E_, update, L.league["snapshots"], cfg, L.census, L.census_p,
                              **({"league_state": L.league} if cfg.get("league_pfsp") == "hard" else {}),
                              exploiters=getattr(L, "exploiters", None))
    jobs = [(i, sp, g) for i, sp in enumerate(specs) for g in range(G)]
    _ = np
    return L, base, jobs


def strip(line: dict) -> dict:
    """A learner record reduced to what the identity check compares: per decision the action + log-probs."""
    import hashlib
    import numpy as np
    act = ("played", "slot", "cell", "gate_sampled", "stalled", "ab_press", "ab_sampled")
    lp = ("lp_gate", "lp_card", "lp_cell", "p_gate", "ab_lp")
    tj = line.get("traj") or {}
    h_all, h_act, h_obs = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    for k in sorted(tj):
        b = np.ascontiguousarray(tj[k]).tobytes()
        h_all.update(k.encode() + b)
        if k in act:
            h_act.update(k.encode() + b)
        if k not in act and k not in lp and k not in ("ab_q",):
            h_obs.update(k.encode() + b)
    out = {k: line.get(k) for k in ("tag", "k", "entry_index", "side", "outcome", "crowns", "end_tick", "rollout_index")}
    out["n_rows"] = int(len(tj.get("slot", ())))
    out["sha_all"], out["sha_act"], out["sha_obs"] = (h.hexdigest()[:16] for h in (h_all, h_act, h_obs))
    out["act"] = {k: np.asarray(tj[k]).tolist() for k in act if k in tj}
    out["lp"] = {k: np.asarray(tj[k], np.float64).tolist() for k in lp if k in tj}
    out["opp_side"] = line.get("opp_side")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--E", type=int, default=8)
    ap.add_argument("--G", type=int, default=4)
    ap.add_argument("--mode", choices=("ref", "batched"), default="ref")
    ap.add_argument("--out", required=True)
    ap.add_argument("--in-flight", type=int, default=8, help="ref: run_selfplay_batch n (the actor's in_flight)")
    ap.add_argument("--workers", type=int, default=4, help="batched: worker processes")
    ap.add_argument("--device", default="cuda", help="batched: the forward's device")
    ap.add_argument("--cohorts", type=int, default=2, help="batched: worker cohorts served in turn")
    ap.add_argument("--amp", default=None, choices=(None, "bf16"), help="batched: server autocast (not identical)")
    ap.add_argument("--actor-device", default=None, help="override actor_device (ref forward device)")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--timing", action="store_true", help="ref: per-phase wall clock of run_selfplay_batch")
    ap.add_argument("--set", action="append", default=[], help="config override key=value")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    L, base, jobs = build(a.cfg, a.E, a.G, a.set, out / "run")
    base["in_flight"] = a.in_flight
    if a.actor_device:
        base["actor_device"] = a.actor_device
    t_build = time.perf_counter() - t0
    from pipeline import e1_eval as E
    from pipeline import rl_royale as R
    orig = E.run_selfplay_batch
    wall = {}

    def capture(make_env, learner, opponents, jobs_it, cfg, n, on_result, on_skip=None, skip=()):
        t = time.perf_counter()
        if a.mode == "ref":
            if a.timing:
                import timing
                timing.install(E)
            if a.profile:
                import cProfile
                pr = cProfile.Profile()
                pr.enable()
                orig(make_env, learner, opponents, jobs_it, cfg, n, on_result, on_skip, skip)
                pr.disable()
                pr.dump_stats(str(out / "prof.pstats"))
            else:
                orig(make_env, learner, opponents, jobs_it, cfg, n, on_result, on_skip, skip)
            if a.timing:
                import timing
                (out / "timing.json").write_text(json.dumps(timing.report(), indent=1))
        else:
            from pipeline import batched_rollout as BR
            st = BR.run(make_env, learner, opponents, jobs_it, cfg, on_result, on_skip=on_skip, skip=skip,
                        workers=a.workers, device=a.device, cohorts=a.cohorts, amp=a.amp)
            (out / "batched_stats.json").write_text(json.dumps(st, indent=1))
        wall["rollout_s"] = time.perf_counter() - t

    E.run_selfplay_batch = capture
    in_q, out_q = Q(), Q()
    in_q.put(("selfplay", 0, L._actor_bytes(), jobs))
    in_q.put(None)
    R.actor_main(0, 0, in_q, out_q, base)
    msgs = []
    while not out_q.empty():
        msgs.append(out_q.get())
    done = [m for m in msgs if m[0] == "done"]
    if not done:
        print("\n".join(str(m)[:4000] for m in msgs if m[0] == "error"))
        return 1
    results = sorted(done[0][3], key=R.row_key)
    with open(out / "results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(strip(r)) + "\n")
    meta = {"mode": a.mode, "E": a.E, "G": a.G, "matches": len(results), "skipped": len(done[0][4]),
            "build_s": round(t_build, 1), "rollout_s": round(wall["rollout_s"], 2),
            "matches_per_h": round(len(results) / wall["rollout_s"] * 3600, 1),
            "decisions": sum(len((r.get("traj") or {}).get("slot", ())) for r in results),
            "in_flight": a.in_flight, "workers": a.workers, "cohorts": a.cohorts, "amp": a.amp, "device": a.device, "actor_device": base["actor_device"]}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
