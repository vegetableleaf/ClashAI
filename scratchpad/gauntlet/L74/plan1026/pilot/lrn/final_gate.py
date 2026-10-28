"""LOOP-LRN final learner gates (owner / lead 10-28), STORED mode on real crforge records: 3 consecutive updates (u 5, 6, 7)
on 3 disjoint ~341-match batches (stored_gate.py gate c's construction, v_old = the update-start model's V), each arm from
the same fresh B0 learner. Arms: (lazy_refine, ent_pair_every) = (False, 4), (True, 4), (True, 2), (True, 1).
  lazy  (False, 4) vs (True, 4): per update kl_gate / kl_card / kl_cell, clip_frac, entropy (3 heads), l_v, steps, stop
        minibatch, and the weights' max |diff| after each update -> the reversal criterion in LRN.md (R1).
  pair  k = 1 / 2 / 4 (lazy on): weights bit-identical across k (the paired forwards take no step, draw no RNG); per
        update and head the paired ratio r_k = ent_pair / ent_pair_init vs the all-minibatch r_1: |r_k / r_1 - 1| <= 1%
        on all 3 updates x 3 heads (else try 2, then 1).
Cost: P_k = the ppo_update seconds of arm k (same steps for every k) = P_0 + (n / k) t, so the paired forwards at k cost
(P_1 - P_k) / (k - 1) per update (k > 1), and at k = 1: 2 (P_1 - P_2).

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/final_gate.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep \
        --keep2 /workspace/lrn/id0_freshhead/keep --out /workspace/lrn/final
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402  (sets the deterministic / TF32-off flags, as rl_royale's learner_deterministic)
from stored_gate import R, LR, torch  # noqa: E402

ARMS = ((False, 4), (True, 4), (True, 2), (True, 1))
MON = ("kl_gate", "kl_card", "kl_cell", "clip_frac", "l_v", "steps", "stop_mb")
HEADS = ("gate", "card", "cell")


def mons(rec):
    out = {k: rec.get(k) for k in ("kl_gate", "kl_card", "kl_cell", "clip_frac", "steps")}
    out["l_v"] = (rec.get("gae") or {}).get("l_v")
    out["stop_mb"] = (rec.get("kl_stop") or {}).get("minibatch")
    out.update({f"ent_{h}": (rec.get("entropy") or {}).get(h) for h in HEADS})
    return out


def rel(a, b):
    if a is None or b is None:
        return None if a == b else float("inf")
    return abs(a - b) / max(abs(b), 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--keep2", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, default=None, help="the T_gate the kept records were SAMPLED at (id1 / id0: "
                    "0.3; tgate_probe.py) -- a learner at another T_gate is off-policy on the gate")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    base = R.load_config(SG.REPO / a.config, [], smoke=False)
    if a.T_gate is not None:
        base["T_gate"] = a.T_gate
    allr = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))] + \
        [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep2.glob("*.rec"))]
    batches = [allr[i::3] for i in range(3)]
    real_ppo, ppo_s = R.ppo_update, []

    def timed(*x, **k):
        t = time.perf_counter()
        out = real_ppo(*x, **k)
        ppo_s.append(time.perf_counter() - t)
        return out
    R.ppo_update = timed
    arms = {}
    try:
        for lazy, k in ARMS:
            name = f"lazy{int(lazy)}_k{k}"
            cfg = {**base, "stored_values": True, "ent_init_rows": None, "lazy_refine": lazy, "ent_pair_every": k}
            L = SG.learner(cfg, name)
            assert all(getattr(m, "lazy_refine", False) is lazy for m in (L.model, L.ref, L.ref_init))
            arm = arms[name] = {"updates": [], "w": []}
            for i, b in enumerate(batches):
                ppo_s.clear()
                rec = SG.run_update(L, 5 + i, SG.with_v(L, cfg, b), {})
                if i == 0 and rec["first_minibatch"]["ratio_maxdev"] >= R.ASSERT_RATIO:   # B0 on B0's records
                    raise SystemExit(f"OFF-POLICY records: first ratio_maxdev {rec['first_minibatch']} -- T_gate?")
                row = {"u": 5 + i, **mons(rec), "ppo_s": ppo_s[0], "wall_update_s": rec["wall_update_s"],
                       "ent_pair": rec.get("entropy_pair"), "ent_pair_init": rec.get("entropy_init"),
                       "ent_pair_rows": rec.get("ent_pair_rows")}
                arm["updates"].append(row)
                arm["w"].append({n: v.detach().cpu().double().clone() for n, v in L.model.state_dict().items()})
                print("arm", name, json.dumps(row, default=str), flush=True)
            del L
            torch.cuda.empty_cache()
    finally:
        R.ppo_update = real_ppo
    out = {"arms": {n: arm["updates"] for n, arm in arms.items()}}
    # lazy: (False, 4) vs (True, 4)
    e, z = arms["lazy0_k4"], arms["lazy1_k4"]
    lz = []
    for i in range(3):
        ue, uz = e["updates"][i], z["updates"][i]
        lz.append({"u": ue["u"], "max_abs_weight": max(float((e["w"][i][n] - z["w"][i][n]).abs().max()) for n in e["w"][i]),
                   "rel": {m: rel(uz[m], ue[m]) for m in ("kl_gate", "kl_card", "kl_cell", "clip_frac", "l_v",
                                                           "ent_gate", "ent_card", "ent_cell")},
                   "steps": [ue["steps"], uz["steps"]], "stop_mb": [ue["stop_mb"], uz["stop_mb"]],
                   "ppo_s": [ue["ppo_s"], uz["ppo_s"]], "wall_update_s": [ue["wall_update_s"], uz["wall_update_s"]]})
    worst = max(v for x in lz for v in x["rel"].values() if v is not None)
    dstop = max(abs((x["stop_mb"][0] or 0) - (x["stop_mb"][1] or 0)) for x in lz)
    out["lazy"] = {"per_update": lz, "worst_rel": worst, "max_stop_shift": dstop,
                   "R1_pass": worst <= 1e-2 and dstop <= 2}           # LRN.md R1 (pre-registered 10-28)
    print("GATE lazy", json.dumps({k: v for k, v in out["lazy"].items() if k != "per_update"}), flush=True)
    for x in lz:
        print("  lazy u", x["u"], json.dumps(x, default=str), flush=True)
    # pair: k = 1 / 2 / 4 with lazy on
    k1 = arms["lazy1_k1"]["updates"]
    pair = {}
    for k in (4, 2):
        uk = arms[f"lazy1_k{k}"]["updates"]
        same_w = all(all(torch.equal(arms[f"lazy1_k{k}"]["w"][i][n], arms["lazy1_k1"]["w"][i][n])
                         for n in arms["lazy1_k1"]["w"][i]) for i in range(3))
        dev = [{h: abs((uk[i]["ent_pair"][h] / uk[i]["ent_pair_init"][h]) /
                       (k1[i]["ent_pair"][h] / k1[i]["ent_pair_init"][h]) - 1) for h in HEADS} for i in range(3)]
        worst_k = max(v for d in dev for v in d.values())
        cost = [(k1[i]["ppo_s"] - uk[i]["ppo_s"]) / (k - 1) for i in range(3)]
        pair[k] = {"weights_identical_to_k1": same_w, "dev": dev, "worst_dev": worst_k, "pass_1pct": worst_k <= 0.01,
                   "cost_s_per_update": cost, "rows": [uk[i]["ent_pair_rows"] for i in range(3)],
                   "ratio": [{h: uk[i]["ent_pair"][h] / uk[i]["ent_pair_init"][h] for h in HEADS} for i in range(3)]}
        print("GATE pair k", k, json.dumps({x: y for x, y in pair[k].items() if x not in ("dev", "ratio")}), flush=True)
    pair[1] = {"ratio": [{h: k1[i]["ent_pair"][h] / k1[i]["ent_pair_init"][h] for h in HEADS} for i in range(3)],
               "rows": [k1[i]["ent_pair_rows"] for i in range(3)],
               "cost_s_per_update": [2 * (k1[i]["ppo_s"] - arms["lazy1_k2"]["updates"][i]["ppo_s"]) for i in range(3)]}
    out["pair"] = pair
    out["choice"] = next((k for k in (4, 2) if pair[k]["pass_1pct"] and pair[k]["weights_identical_to_k1"]), 1)
    print("GATE pair choice ent_pair_every", out["choice"], flush=True)
    (a.out / f"final_gate_{SG.TAG}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
