"""LOOP-INT correctness: one dumped actor message (fastloop FASTLOOP_DUMP=1 -> <rl run>/fast_msg_uNNNN.pkl) played by BOTH
paths in one process on the same device: (1) production = rl_royale.actor_main (its 'selfplay' branch:
e1_eval.run_selfplay_batch over RoyaleSelfPlayEnv + CrforgeCore), (2) the fast loop's Producer (CfTrain + the same
per-side code). Per match: outcome, end tick, the learner's traj row count; per row and key: byte-identical or the max
|diff| (log-probs); the first diverging row of each match with the gate / card / cell draws around it.

usage (pod, run.sh's env): python compare.py MSG.pkl OUT.json [--device cuda] [--in-flight 1] [--matches 1] [--max-jobs N]
       [--server eager|graphs]   (the fast loop's forwards on a LOOP-SRV serve.py on --device; then every learner row's
       v_old is checked against production's critic on the same rows / device, and wver == the update)
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

LP = ("lp_gate", "lp_card", "lp_cell", "p_gate", "ab_lp", "lp_th")   # float noise of the forward: max |diff| reported (lp_th: OPP-LEARN-D)
AB_RESULT = ("ability_presses", "ability_deployments", "ability_fallback_generic", "ability_head")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--in-flight", type=int, default=1, help="production matches in flight (1 = batch-1 forwards)")
    ap.add_argument("--matches", type=int, default=1, help="fast loop matches in flight")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--max-jobs", type=int, default=0)
    ap.add_argument("--server", default=None, help="eager | graphs: fast-loop forwards on serve.py (LOOP-SRV)")
    ap.add_argument("--init", default="icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt",
                    help="server mode: the learner architecture checkpoint (the run's init; fastloop passes cfg init)")
    a = ap.parse_args()
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    if a.max_jobs:
        jobs = jobs[:a.max_jobs]
    base = {**base, "actor_device": a.device, "in_flight": a.in_flight}
    from producer import Producer
    servers, srv = [], None
    if a.server:
        from bench import start_servers
        import io
        import torch
        mf = torch.load(io.BytesIO(sd), map_location="cpu").get("mem.full")   # MEM-FULL: the message's learner layout
        mf = ",".join(str(int(x)) for x in mf) if mf is not None else ""
        servers = start_servers({**base, "init_path": a.init, "mem_full": mf}, update, sd, jobs, [a.device], a.server,
                                max(a.matches, 64), "/dev/shm/loopcmp")
        srv = "/dev/shm/loopcmp/srv0.sock"
    P = Producer(base, a.matches, a.threads, "cpu" if srv else a.device,
                 Path(__import__("os").environ["CRFORGE_FACADE_BUILD"]), server=srv)
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
    for s_ in servers:
        s_.kill()
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
        lpk = [k for k in LP if k in tp and k in tf]          # OPP-LEARN-C: a timing learner has no ab_lp
        first = None
        for r in range(n):
            bad = [k for k in tp if k not in LP and k in tf and np.asarray(tp[k][r]).tobytes() != np.asarray(tf[k][r]).tobytes()]
            if bad:
                first = {"row": r, "keys": bad, "tick": int(tp["tick"][r]) if "tick" in tp else None,
                         **{f"{k}_prod": float(tp[k][r]) for k in lpk}, **{f"{k}_fast": float(tf[k][r]) for k in lpk},
                         "prod": {k: np.asarray(tp[k][r]).tolist() for k in ("played", "slot", "cell", "allowed")},
                         "fast": {k: np.asarray(tf[k][r]).tolist() for k in ("played", "slot", "cell", "allowed")}}
                for k in bad:
                    keys_bad[k] = keys_bad.get(k, 0) + 1
                break
            for k in lpk:
                lp_max[k] = max(lp_max[k], abs(float(tp[k][r]) - float(tf[k][r])))
        rep.append({"key": list(map(str, R.row_key(p))), "outcome": [p["outcome"], f["outcome"]],
                    "end_tick": [p["end_tick"], f["end_tick"]], "rows": [len(tp["played"]), len(tf["played"])],
                    "plays": [p["plays_attempted"], f["plays_attempted"]], "accepted": [p["plays_accepted"], f["plays_accepted"]],
                    "opp_plays": [p["opp_side"]["plays_attempted"], f["opp_side"]["plays_attempted"]],
                    "ability": {k: [p.get(k), f.get(k)] for k in AB_RESULT if p.get(k) is not None or f.get(k) is not None},
                    "ability_equal": all(norm(p.get(k)) == norm(f.get(k)) for k in AB_RESULT),
                    "identical": first is None and len(tp["played"]) == len(tf["played"]), "first_divergence": first})
    vchk = vold_check(base, sd, fast, update, a.device, P.model.gid) if a.server else None
    from producer import mem_opts
    mchk = mem_check(prod, fast, P.model.gid, mem_opts(P.model)[0])   # MEM-FULL: the learner's e_max
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
    ab = abil_summary(prod, fast) if any("ability_presses" in r for r in prod) else None
    out = {"ability": ab, "heroiw_press": __import__("os").environ.get("ROYALE_HEROIW_PRESS"), "sides": out_sides, "msg": a.msg, "device": a.device, "in_flight": a.in_flight, "fast_matches": a.matches, "matches": len(rep),
           "identical_matches": sum(r["identical"] for r in rep), "first_div_keys": keys_bad,
           "lp_maxdiff_before_divergence": lp_max, "server": a.server, "v_old": vchk, "memory": mchk, "fast_stats": st, "matches_detail": rep}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("matches", "identical_matches", "first_div_keys", "lp_maxdiff_before_divergence",
                                          "v_old", "memory", "ability")}))


def norm(x):
    """A result field with int / str side keys (json round trips) -> comparable."""
    return json.loads(json.dumps(x, sort_keys=True, default=str)) if x is not None else None


def abil_summary(prod, fast):
    """Hero abilities: matches whose ability result fields are equal, and per path the learner's press decisions
    (ab_sampled / ab_press), labels (ab_cand) and engine-accepted presses of both sides."""
    out = {"matches_equal": 0, "matches": len(prod)}
    for name, rs in (("prod", prod), ("fast", fast)):
        t = [r["traj"] for r in rs]
        out[name] = {"ab_sampled": int(sum(int(np.sum(x.get("ab_sampled", 0))) for x in t)),
                     "ab_press": int(sum(int(np.sum(x.get("ab_press", 0))) for x in t)),
                     "ab_cand": int(sum(int(np.sum(x.get("ab_cand", 0))) for x in t)),
                     "presses_side": [int(sum(sum((r.get("ability_presses") or {}).get(k, {}).values()) for r in rs
                                              for k in (s, str(s)))) for s in (0, 1)]}
    out["matches_equal"] = sum(all(norm(p.get(k)) == norm(f.get(k)) for k in AB_RESULT) for p, f in zip(prod, fast))
    return out


def mem_check(prod, fast, gid, e_max=128):
    """Memory models: each match's learner event table (result["memory"], rl_royale's mem_tab_*) byte-identical, and every
    learner row's rollout MEM_KEYS (fast traj mem_h, FASTLOOP_MEMHASH=1) == the learner's rebuild from PRODUCTION's table
    (match_memory.rows_features on mem_t / deck_card, as e1_eval.gen_batch; LOOP-MEM measured rebuild == rollout)."""
    import hashlib
    from pipeline import match_memory as MM
    if not any("memory" in p for p in prod):
        return None
    out = {"tables": 0, "tables_equal": 0, "table_diff_keys": {}, "rows": 0, "rows_equal": 0, "no_hash": 0,
           "first_row_diff": None}
    for p, f in zip(prod, fast):
        if "memory" not in p:
            continue
        out["tables"] += 1
        bad = [k for k in MM.TABLE_KEYS if k not in f.get("memory", {}) or np.asarray(p["memory"][k]).dtype !=
               np.asarray(f["memory"][k]).dtype or np.asarray(p["memory"][k]).tobytes() != np.asarray(f["memory"][k]).tobytes()]
        out["tables_equal"] += int(not bad)
        for k in bad:
            out["table_diff_keys"][k] = out["table_diff_keys"].get(k, 0) + 1
        if bad and len(out.setdefault("table_diffs", [])) < 6:   # the first differing event of each bad table
            P_, F_ = p["memory"], f.get("memory", {})
            n_ = min(len(P_["tick"]), len(F_.get("tick", [])))
            d = {"key": str(p.get("tag")), "events": [len(P_["tick"]), len(F_.get("tick", []))], "keys": bad}
            for i in range(n_):
                dk = [k for k in bad if np.asarray(P_[k][i]).tobytes() != np.asarray(F_[k][i]).tobytes()]
                if dk:
                    cols = (np.flatnonzero(np.asarray(P_["vals"][i]) != np.asarray(F_["vals"][i])).tolist()
                            if "vals" in dk else [])
                    d.update(at=i, diff_keys=dk, tick=int(P_["tick"][i]), card=int(P_["card"][i]),
                             vals_cols=[(MM.FIELDS[c] if c < len(MM.FIELDS) else c, float(P_["vals"][i][c]),
                                         float(F_["vals"][i][c])) for c in cols][:12],
                             vpe=[float(P_["vpe"][i]), float(F_["vpe"][i])],
                             is_ability=float(P_["vals"][i][MM.FIELDS.index("is_ability")]))
                    break
            out["table_diffs"].append(d)
        t = f["traj"]
        if "mem_h" not in t:
            out["no_hash"] += 1
            continue
        n = len(t["mem_t"])
        rf = MM.rows_features(MM.pack([p["memory"]]), np.zeros(n, np.int64), np.asarray(t["mem_t"], np.int64),
                              np.asarray(t["deck_card"], np.int64), np.arange(n), "v2", gid, e_max=e_max)
        for i in range(n):
            h = hashlib.sha1(b"".join(np.ascontiguousarray(rf[k][i]).tobytes() for k in MM.MEM_KEYS)).hexdigest()
            out["rows"] += 1
            out["rows_equal"] += int(h == t["mem_h"][i])
            if h != t["mem_h"][i] and out["first_row_diff"] is None:
                out["first_row_diff"] = {"key": str(p.get("tag")), "row": i, "mem_t": int(t["mem_t"][i])}
    return out


def vold_check(base, sd, fast, update, device, gid=None, bs=512):
    """Server mode: v_old of every learner row vs rl_royale.value_scalar of the PRODUCTION model's critic (value_head on
    encode_gen's g, the server's own definition) on the same rows, same device, TF32 off; wver must equal the update."""
    import torch
    from pipeline import e1_eval as E
    from pipeline import rl_royale as R
    from pipeline.model_gen import GenModel
    g = base["gen"]
    net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]), n_cards=len(g["card_vocab"]),
                   feature_version=int(g.get("feature_version", 1))).to(device).eval()
    msd, _ = R.split_actor_sd(sd, device)
    R.pop_prefix(msd, R.ABILITY_SD)
    net.load_state_dict(msd)
    keys = E.gen_row_keys(net)
    dmax, n, bad_ver, missing = 0.0, 0, 0, 0
    for r in fast:
        t = r["traj"]
        if "v_old" not in t:
            missing += 1
            continue
        bad_ver += int((np.asarray(t["wver"]) != int(update)).sum())
        mrows = {}
        if "memory" in r:                                 # MEM_KEYS as the learner rebuilds them (e1_eval.gen_batch)
            from pipeline import match_memory as MM
            n_ = len(t["mem_t"])
            mrows = MM.rows_features(MM.pack([r["memory"]]), np.zeros(n_, np.int64), np.asarray(t["mem_t"], np.int64),
                                     np.asarray(t["deck_card"], np.int64), np.arange(n_), "v2", gid,
                                     e_max=MM.opts(net.mem)["e_max"])   # MEM-FULL
        for i in range(0, len(t["played"]), bs):
            with torch.no_grad():
                b = {k: torch.from_numpy(np.ascontiguousarray((mrows if k in mrows else t)[k][i:i + bs])).to(device)
                     for k in keys}
                v = R.value_scalar(net.value_head(net.encode_gen(b)["g"])).cpu().numpy()
            dmax = max(dmax, float(np.abs(v - np.asarray(t["v_old"][i:i + bs])).max()))
            n += len(v)
    return {"rows": n, "matches_without_v_old": missing, "wver_mismatch_rows": bad_ver, "v_old_maxdiff": dmax}


if __name__ == "__main__":
    main()
