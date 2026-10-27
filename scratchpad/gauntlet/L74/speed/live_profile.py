"""SPEED.md (a): where the live decision time goes. Recorded live logs (merged reader, with frames) replayed through the
REAL pipeline.live_gen_v2.GenPilot set up as live_play.load_pilot does from the log's own start event (decision
options, afford_ticks, identity_ext, cues, tau, extrapolate, own_effects, hero_ability_spec, 4 torch threads), on
``--device``. Every frame is observed (live: observe per frame, not in decide_ms); every ``--every``-th frame after
tick 150 is decided, timed in parts:
    row      GenPilot.row (public observation, extrapolation, board, tokens, cues, ident features)
    forward  every GenModel.forward call inside decide (trunk + heads; the cell call is a SECOND full forward)
    rest     decide minus both = decode rules (decision_options, lethal, rocket value, guards, audit)
(cuda: synchronized inside the forward wrapper so its time is the device time.) Also: a forward-only microbenchmark at
batch 1 of the same model for the scaling estimate, and widths/depths 5 / 10 / 15 M (random weights, same shapes).

    python live_profile.py --ckpt CLXIII.pt --device cuda --out out.json LOG.jsonl [LOG ...]
No ADB / MuMu / reader: nothing here touches the live path; it is safe on a pod (not on the live laptop while live runs).
"""
import argparse
import copy
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / "scratchpad/gauntlet/L74/cues/live")]


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def summ(xs):
    return {"n": len(xs), "mean": round(statistics.fmean(xs), 2) if xs else None, "p50": pct(xs, .5),
            "p90": pct(xs, .9), "p99": pct(xs, .99)}


def make_pilot(ckpt, start, device):
    import torch
    from pipeline import live_gen_v2
    from pipeline.decision_options import options_from_config
    torch.set_num_threads(4)                                    # live_play.load_pilot
    p = live_gen_v2.GenPilot(str(ckpt), device=device, gate_tau=start["tau"], use_counter=start.get("opp_counter", True),
                             extrapolate_ticks=start["extrapolate"],
                             decision_options=options_from_config(start["decision_options"]),
                             decision_seed=start.get("decision_seed", 0), public_audit=start.get("public_audit", False),
                             **({"own_effects": True} if start.get("own_effects") else {}),
                             **({"hero_ability_spec": start["hero_ability_spec"]}
                                if start.get("hero_ability_spec", "off") != "off" else {}))
    p.legal_guard = bool(start.get("legal_guard", True))
    if start.get("identity_ext"):
        p.identity_ext = True
    if start.get("afford_ticks") is not None:
        p.afford_ticks = int(start["afford_ticks"])
    if getattr(p.model, "cue_in", None) is not None:
        from pipeline.live_unit_state import LiveCues
        p.cues = LiveCues()
    return p


def logged_ms(path):
    out = []
    for line in open(path, encoding="utf-8"):
        if '"event": "decision"' in line[:40]:
            out.append(json.loads(line)["decide_ms"])
    return out


def forward_bench(model, b, device, reps=200):
    import torch
    with torch.no_grad():
        for _ in range(10):
            model(b)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(reps):
            out = model(b)
            float(out["gate"][0])                               # the decide's own sync point
        return (time.perf_counter() - t) / reps * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--max-decisions", type=int, default=400)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default=None, help="cProfile the decides -> this .pstats")
    a = ap.parse_args()
    import torch
    from logframes import full_frames
    start = json.loads(open(a.logs[0], encoding="utf-8").readline())
    pilot = make_pilot(a.ckpt, start, a.device)
    T = {"row": [], "forward": [], "decide": [], "n_forward": []}
    cur = {"row": 0.0, "forward": 0.0, "nf": 0}
    row0, fwd0 = pilot.row, pilot.model.forward
    sync = (lambda: torch.cuda.synchronize()) if a.device.startswith("cuda") else (lambda: None)

    def row(frame):
        t = time.perf_counter()
        r = row0(frame)
        cur["row"] += time.perf_counter() - t
        return r

    def fwd(*x, **k):
        sync()
        t = time.perf_counter()
        r = fwd0(*x, **k)
        sync()
        cur["forward"] += time.perf_counter() - t
        cur["nf"] += 1
        return r
    pilot.row, pilot.model.forward = row, fwd
    prof = None
    if a.profile:
        import cProfile
        prof = cProfile.Profile()
    n = 0
    for log in a.logs:
        pilot.reset_match()
        for i, f in enumerate(full_frames(log)):
            pilot.observe(copy.deepcopy(f))
            if f["game_tick"] < 150 or i % a.every:
                continue
            g = copy.deepcopy(f)
            cur.update(row=0.0, forward=0.0, nf=0)
            if prof:
                prof.enable()
            t = time.perf_counter()
            pilot.decide(g)
            dt = time.perf_counter() - t
            if prof:
                prof.disable()
            T["decide"].append(dt * 1000)
            T["row"].append(cur["row"] * 1000)
            T["forward"].append(cur["forward"] * 1000)
            T["n_forward"].append(cur["nf"])
            n += 1
            if n >= a.max_decisions:
                break
        if n >= a.max_decisions:
            break
    pilot.row, pilot.model.forward = row0, fwd0
    b, _ = pilot.row(g)                                         # a real batch-1 row for the forward microbenchmark
    torch.save({k: v.cpu() for k, v in b.items()}, Path(a.out).with_suffix(".batch.pt"))   # -> model_scale.py
    rest = [d - r - f for d, r, f in zip(T["decide"], T["row"], T["forward"])]
    res = {"device": a.device, "torch_threads": torch.get_num_threads(), "ckpt": str(a.ckpt),
           "n_params": sum(p.numel() for p in pilot.model.parameters()),
           "replayed": {k: summ(v) for k, v in T.items() if k != "n_forward"} | {"rest": summ(rest)},
           "forwards_per_decision": summ(T["n_forward"]),
           "logged_decide_ms_same_logs": summ([float(x) for lg in a.logs for x in logged_ms(lg)]),
           "forward_only_ms_b1": round(forward_bench(pilot.model, b, a.device), 2)}
    if prof:
        prof.dump_stats(a.profile)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
