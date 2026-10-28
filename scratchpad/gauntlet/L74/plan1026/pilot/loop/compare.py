"""LOOP-INT correctness: one dumped actor message (fastloop FASTLOOP_DUMP=1 -> <rl run>/fast_msg_uNNNN.pkl) played by BOTH
paths in one process on the same device: (1) production = rl_royale.actor_main (its 'selfplay' branch:
e1_eval.run_selfplay_batch over RoyaleSelfPlayEnv + CrforgeCore), (2) the fast loop's Producer (CfTrain + the same
per-side code). Per match: outcome, end tick, the learner's traj row count; per row and key: byte-identical or the max
|diff| (log-probs); the first diverging row of each match with the gate / card / cell draws around it.

usage (pod, run.sh's env): python compare.py MSG.pkl OUT.json [--device cuda] [--in-flight 1] [--matches 1] [--max-jobs N]
"""
from __future__ import annotations

import argparse
import json
import pickle
import queue
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5]), str(HERE)]

LP = ("lp_gate", "lp_card", "lp_cell", "p_gate")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--in-flight", type=int, default=1, help="production matches in flight (1 = batch-1 forwards)")
    ap.add_argument("--matches", type=int, default=1, help="fast loop matches in flight")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--max-jobs", type=int, default=0)
    a = ap.parse_args()
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    if a.max_jobs:
        jobs = jobs[:a.max_jobs]
    base = {**base, "actor_device": a.device, "in_flight": a.in_flight}
    from producer import Producer
    P = Producer(base, a.matches, a.threads, a.device, Path(__import__("os").environ["CRFORGE_FACADE_BUILD"]))
    from pipeline import e1_eval as E
    import hashlib
    trace, orig = {"cur": None}, E.SelfPlaySide._record

    def record(self, p, d):                              # every side's decisions, both paths (same production _record)
        t = orig(self, p, d)
        g = self._gen_row or {}
        h = {k: hashlib.sha1(np.ascontiguousarray(g[k]).tobytes()).hexdigest()[:8] for k in sorted(g)}
        trace[trace["cur"]].setdefault(f"{self.tag}#{self.k}", []).append(
            dict(tick=int(t), play=bool(d["play"]), slot=int(d["slot"]), cell=int(d["cell"]), p=float(p),
                 why=d.get("why"), lp=[float(d.get(k, 0.0)) for k in ("lp_gate", "lp_card", "lp_cell")], h=h,
                 opp_past=np.asarray(g.get("opp_past")).tolist(), opp_cycle=np.asarray(g.get("opp_cycle")).tolist()))
        return t
    E.SelfPlaySide._record = record
    trace["cur"], trace["fast"], trace["prod"] = "fast", {}, {}
    fast, skipped, st = P.run(update, sd, jobs)
    trace["cur"] = "prod"
    from pipeline import rl_royale as R
    iq, oq = queue.Queue(), queue.Queue()
    oq.cancel_join_thread = lambda: None             # actor_sender expects an mp.Queue
    iq.put(("selfplay", update, sd, jobs))
    iq.put(None)
    R.actor_main(0, 0, iq, oq, base)
    prod = None
    while not oq.empty():
        m = oq.get()
        if m[0] == "error":
            raise RuntimeError(m[3])
        if m[0] == "done":
            prod = sorted(m[3], key=R.row_key)
    assert prod is not None and len(prod) == len(fast), (None if prod is None else len(prod), len(fast))
    rep, keys_bad, lp_max = [], {}, {k: 0.0 for k in LP}
    for p, f in zip(prod, fast):
        assert R.row_key(p) == R.row_key(f)
        tp, tf = p["traj"], f["traj"]
        n = min(len(tp["played"]), len(tf["played"]))
        first = None
        for r in range(n):
            bad = [k for k in tp if k not in LP and k in tf and np.asarray(tp[k][r]).tobytes() != np.asarray(tf[k][r]).tobytes()]
            if bad:
                first = {"row": r, "keys": bad, "tick": int(tp["tick"][r]) if "tick" in tp else None,
                         **{f"{k}_prod": float(tp[k][r]) for k in LP}, **{f"{k}_fast": float(tf[k][r]) for k in LP},
                         "prod": {k: np.asarray(tp[k][r]).tolist() for k in ("played", "slot", "cell", "allowed")},
                         "fast": {k: np.asarray(tf[k][r]).tolist() for k in ("played", "slot", "cell", "allowed")}}
                for k in bad:
                    keys_bad[k] = keys_bad.get(k, 0) + 1
                break
            for k in LP:
                lp_max[k] = max(lp_max[k], abs(float(tp[k][r]) - float(tf[k][r])))
        rep.append({"key": list(map(str, R.row_key(p))), "outcome": [p["outcome"], f["outcome"]],
                    "end_tick": [p["end_tick"], f["end_tick"]], "rows": [len(tp["played"]), len(tf["played"])],
                    "plays": [p["plays_attempted"], f["plays_attempted"]], "accepted": [p["plays_accepted"], f["plays_accepted"]],
                    "opp_plays": [p["opp_side"]["plays_attempted"], f["opp_side"]["plays_attempted"]],
                    "identical": first is None and len(tp["played"]) == len(tf["played"]), "first_divergence": first})
    sides = []                                           # the first diverging decision of every side (learner + opp)
    for tag in sorted(set(trace["prod"]) | set(trace["fast"])):
        P_, F_ = trace["prod"].get(tag, []), trace["fast"].get(tag, [])
        j = next((i for i, (x, y) in enumerate(zip(P_, F_)) if
                  (x["tick"], x["play"], x["slot"], x["cell"], x["h"]) != (y["tick"], y["play"], y["slot"], y["cell"], y["h"])),
                 None)
        if j is None and len(P_) == len(F_):
            sides.append({"tag": tag, "decisions": len(P_), "identical": True})
            continue
        j = min(len(P_), len(F_)) if j is None else j
        x, y = (P_[j] if j < len(P_) else None), (F_[j] if j < len(F_) else None)
        if x and y:
            x = dict(x, h_diff=[k for k in x["h"] if x["h"][k] != y["h"].get(k)])
        sides.append({"tag": tag, "decisions": [len(P_), len(F_)], "identical": False, "at": j, "prod": x, "fast": y,
                      "prev_prod": P_[j - 1] if j else None})
    out_sides = sorted(sides, key=lambda s: (s["identical"], (s.get("prod") or {}).get("tick", 1e9)))
    out = {"sides": out_sides, "msg": a.msg, "device": a.device, "in_flight": a.in_flight, "fast_matches": a.matches, "matches": len(rep),
           "identical_matches": sum(r["identical"] for r in rep), "first_div_keys": keys_bad,
           "lp_maxdiff_before_divergence": lp_max, "fast_stats": st, "matches_detail": rep}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("matches", "identical_matches", "first_div_keys", "lp_maxdiff_before_divergence")}))


if __name__ == "__main__":
    main()
