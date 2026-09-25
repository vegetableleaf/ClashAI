"""rl_royale's held-out RoyaleSim screen for ANY checkpoint (S1 or generalist), plus paired scoring of two runs.

Play (Royale venv -- royalegym is not in the icebow venv):
    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py \
        --ckpt icebow/data/pipeline/gen_v1_s0/gen_s0.pt --out scratchpad/gauntlet/L68/generalist/screen_gen/gen_v1_s0.jsonl
Pair (B scored against A exactly as the RL screen scores a candidate against its init):
    ... run_screen.py --pair A.jsonl B.jsonl

What is reproduced from pipeline/rl_royale.py (Learner.screen + actor_main, kind="screen"):
  * entries: pool v1 held-out split (frozen-split sha checked), every entry RoyaleSim can load (UnsupportedDeck
    skipped, as Learner._entries filters them) -- screen_entries must be 0 in rl_royale.yaml (= all, 58);
  * seeds k = screen_seeds (0, 1, 2); obs seed = e1_eval.obs_seed(tag, k) (no per-job override, as the screen);
  * decide: policy "live" (greedy, NOT sampled), tau / afford_mask / stall_elixir / stall_seconds / obs / decide_every
    / T from rl_royale.yaml, Noise() all on, grid = the checkpoint's own;
  * e1_eval.run_batch with ``--batch`` matches in flight (the actors use in_flight 16).
Difference: ``entry_index`` in a line is the index in the whole held-out split, not in the loadable list (not scored).
Scoring: rl_royale.screen_score (screen_record per (tag, k), entry-clustered delta + bootstrap CI from rl_gate's
DRAWS / GATE_SEED via e1_score.cluster_bootstrap) -- reused, not reimplemented.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CONFIG = REPO / "pipeline" / "rl_royale.yaml"


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def pair(a_path: Path, b_path: Path) -> dict:
    from pipeline.rl_royale import screen_record, screen_score
    A, B = read_jsonl(a_path), read_jsonl(b_path)
    init = {f"{r['tag']}:{int(r['k'])}": screen_record(r) for r in A}
    sa, sb = screen_score(A, None), screen_score(B, init)
    for s in (sa, sb):
        s.pop("per_key")
    return {"A": str(a_path), "B": str(b_path), "A_screen": sa, "B_vs_A": sb}


def play(a) -> int:
    import torch
    from pipeline import e1_eval as E
    from pipeline.e1_pool import load_pool_v1, select_split, sha256_file
    from pipeline.e1_view import Noise
    from pipeline.obs_contract import load_deck
    from pipeline.rl_royale import load_config
    from pipeline.royale_env import RoyalePoolEnv, UnsupportedDeck

    out = Path(a.out)
    done = {(r["tag"], int(r["k"])) for r in read_jsonl(out)} if out.exists() else set()
    if done and not a.resume:
        raise SystemExit(f"REFUSING: {out} exists and is not empty (use --resume)")
    rc = load_config(CONFIG, [], smoke=False)
    if int(rc["screen_entries"]) != 0:
        raise SystemExit("rl_royale.yaml screen_entries != 0: this runner reproduces only the all-entries screen")
    torch.set_num_threads(max(1, int(a.threads)))
    pool = REPO / rc["pool"]
    frozen = json.loads(pool.with_name(pool.stem + "_split.json").read_text(encoding="utf-8"))
    if sha256_file(pool) != frozen["pool_sha256"]:
        raise SystemExit("REFUSING: pool sha256 != frozen split's")
    heldout = select_split(load_pool_v1(pool), "heldout")
    jobs = [(i, e, int(k)) for i, e in enumerate(heldout) for k in rc["screen_seeds"] if (e["tag"], int(k)) not in done]
    model, minfo = E.load_policy(Path(a.ckpt), a.device)
    cfg = {"policy": "live", "tau": float(rc["tau"]), "afford_mask": bool(rc["afford_mask"]),
           "stall_elixir": rc["stall_elixir"], "stall_seconds": float(rc["stall_seconds"]), "obs": rc["obs"],
           "noise": Noise(), "p_random": 0.0, "random_hand_only": False, "grid": minfo["grid"], "device": a.device,
           "decide_every": int(rc["decide_every"]), "slot": 0, "port": 0, "T": float(rc["T"]), "record": False}
    meta = {"ckpt": str(a.ckpt), "ckpt_sha256": sha256_file(Path(a.ckpt)), "model": minfo,
            "cfg": {k: v for k, v in cfg.items() if k != "noise"}, "screen_seeds": rc["screen_seeds"],
            "jobs": len(jobs), "resumed_done": len(done), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".run.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    skipped: list[dict] = []
    n = 0
    t0 = time.perf_counter()

    def emit(line):
        nonlocal n
        n += 1
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
        print(f"[screen] {n} {line['tag']} k={line['k']} {line['outcome']} {line['crowns_for']}-{line['crowns_against']}"
              f" {line['seconds']}s plays {line['plays_accepted']}/{line['plays_attempted']} wall {line['wall_s']}s",
              flush=True)

    def feed():                                  # --max-matches counts STARTED matches (unloadable entries don't count)
        fed = 0
        for j in jobs:
            if a.max_matches and fed - len(skipped) >= a.max_matches:
                return
            fed += 1
            yield j

    E.run_batch(lambda: RoyalePoolEnv(decision_ticks=int(rc["decide_every"])), model, load_deck("icebow"), feed(), cfg,
                max(1, min(int(a.batch), len(jobs))), on_result=emit, skip=(UnsupportedDeck,),
                on_skip=lambda e, exc: skipped.append({"tag": e["tag"], "why": str(exc)}))
    out.with_suffix(".skipped.json").write_text(json.dumps(skipped, indent=1), encoding="utf-8")
    print(json.dumps({"DONE": {"matches": n, "skipped_jobs": len(skipped),
                               "skipped_entries": len({s["tag"] for s in skipped}),
                               "wall_s": round(time.perf_counter() - t0, 1)}}), flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--ckpt", type=Path)
    ap.add_argument("--out", type=Path, help="JSONL, one e1_eval Match.result() line per (tag, k)")
    ap.add_argument("--pair", nargs=2, type=Path, metavar=("A", "B"), help="score B vs A (A = the reference)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16, help="matches in flight sharing one forward (actors: in_flight 16)")
    ap.add_argument("--max-matches", type=int, default=0, help="smoke: stop after N matches")
    ap.add_argument("--resume", action="store_true", help="append to --out, skipping (tag, k) already in it")
    a = ap.parse_args(argv)
    if a.pair:
        print(json.dumps(pair(*a.pair), indent=1))
        return 0
    if not (a.ckpt and a.out):
        ap.error("--ckpt and --out are required unless --pair")
    return play(a)


if __name__ == "__main__":
    raise SystemExit(main())
