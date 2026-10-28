"""ONE_FORWARD.md (a): where a HEAD live decide spends its time, per model, on one GPU.

Replays the recorded decisions of the identity test's live logs (pipeline/tests/test_decide_identity.py: read_log +
live_pilot, the REAL live_gen_v2.GenPilot set up from each log's start event) and times every ``pilot.decide(frame)``.
HEAD's decide runs ONE trunk pass per decision (GenPilot._policy_forward = encode_gen -> heads_gen, then
cell_logits_gen from that same encoding), so the stages are timed by wrapping, with a CUDA sync on each side:
  row     GenPilot.row (public observation -> model batch)           enc    model.encode_gen (trunk + refine features)
  heads   model.heads_gen                                            cell   model.cell_logits_gen (each call)
  rest    decide minus the four = decode rules, guards, host work
Two passes per log: "plain" (no wrappers: the honest total) and "staged" (wrappers: the breakdown; its total is a little
longer because of the syncs).

usage (pod, from the checkout that holds scratchpad/gauntlet/L68/live_reader and pipeline/tests, e.g. /workspace/cb):
  python live_profile_v2.py --ckpt CKPT --out OUT.json [--logs a.jsonl ...] [--max 300] [--device cuda]
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT)]


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def summ(xs):
    return {"n": len(xs), "mean": round(statistics.fmean(xs), 2) if xs else None, "p50": pct(xs, .5), "p90": pct(xs, .9),
            "p99": pct(xs, .99)}


def run(T, ckpt, device, logs, max_n, staged, iw_press=None):
    import torch
    sync = (lambda: torch.cuda.synchronize()) if device.startswith("cuda") else (lambda: None)
    tot, parts, ncell, nplay = [], {"row": [], "enc": [], "heads": [], "cell": []}, [], 0
    sigs = set()
    n = 0
    for name in logs:
        start, ev = T.read_log(T.LIVE_DIR / name)
        if iw_press:                        # a checkpoint without the learned ability head cannot take the logged "head"
            start["iw_press"] = iw_press
        pilot = T.live_pilot(start)
        m = pilot.model
        acc = dict(row=0.0, enc=0.0, heads=0.0, cell=0.0, ncell=0)
        if staged:
            def wrap(obj, attr, key, cnt=None):
                f = getattr(obj, attr)

                def g(*a, **k):
                    sync(); t = time.perf_counter()
                    r = f(*a, **k)
                    sync(); acc[key] += time.perf_counter() - t
                    if cnt:
                        acc[cnt] += 1
                    return r
                setattr(obj, attr, g)
            pf0 = pilot._policy_forward

            def pf(b, _pf0=pf0):                # batch shape signatures: a CUDA graph needs ONE per capture
                sigs.add(tuple(sorted((k, tuple(v.shape), str(v.dtype)) for k, v in b.items() if torch.is_tensor(v))))
                return _pf0(b)
            pilot._policy_forward = pf
            wrap(pilot, "row", "row")
            wrap(m, "encode_gen", "enc")
            wrap(m, "heads_gen", "heads")
            wrap(m, "cell_logits_gen", "cell", "ncell")
        pilot.reset_match()
        f = None
        for e in ev:
            if e[0] == "frame":
                f = e[1]
                pilot.observe(f)
            elif e[0] == "decision" and f is not None and f["game_tick"] == e[1]:
                for k in acc:
                    acc[k] = 0
                sync(); t = time.perf_counter()
                d = pilot.decide(f)
                sync(); dt = time.perf_counter() - t
                n += 1
                if n <= 5:                      # cold start (cuda context, first kernels): not recorded
                    continue
                tot.append(dt * 1e3)
                if staged:
                    for k in parts:
                        parts[k].append(acc[k] * 1e3)
                    ncell.append(acc["ncell"])
                nplay += bool(d.get("play"))
                if n >= max_n:
                    break
            elif e[0] == "confirmed" and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == "ability":
                pilot.record_ability(e[1], e[2])
        if n >= max_n:
            break
    out = {"decide": summ(tot), "plays": nplay}
    if staged:
        out.update({k: summ(v) for k, v in parts.items()})
        out["rest"] = summ([t - sum(parts[k][i] for k in parts) for i, t in enumerate(tot)])
        out["cell_calls_per_decision"] = summ([float(c) for c in ncell])
        out["n_batch_shape_signatures"] = len(sigs)
        out["batch_keys"] = sorted({s[0] for sg in sigs for s in sg})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--logs", nargs="*", default=None)
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--iw-press", default=None, help="override the logged iw_press (rule for a checkpoint without an ability head)")
    a = ap.parse_args()
    import torch
    import pipeline.tests.test_decide_identity as T
    from pipeline import live_unit_state as LU
    load0 = LU.load_table

    def load_file(path=LU.TABLE_PATH):          # the laptop's cue table FILE (live's), not this pod's royalesim copy
        sim = sys.modules.pop("royalesim", None)
        try:
            return load0(path)
        finally:
            if sim is not None:
                sys.modules["royalesim"] = sim
    LU.load_table = load_file
    T.CKPT = Path(a.ckpt)
    orig = T.SimpleNamespace

    def ns(**kw):
        if "device" in kw and "ckpt" in kw:
            kw["device"] = a.device
        return orig(**kw)
    T.SimpleNamespace = ns
    logs = a.logs or list(T.LOGS)
    res = {"ckpt": a.ckpt, "device": a.device, "gpu": torch.cuda.get_device_name(0) if a.device.startswith("cuda") else None,
           "logs": logs, "torch_threads": torch.get_num_threads()}
    for staged in (False, True):
        res["staged" if staged else "plain"] = run(T, a.ckpt, a.device, logs, a.max, staged, a.iw_press)
        print(json.dumps(res["staged" if staged else "plain"]), flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
