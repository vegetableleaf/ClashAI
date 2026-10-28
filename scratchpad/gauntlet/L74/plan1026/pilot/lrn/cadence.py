"""LOOP-LRN learner cadence in the FINAL pilot config (pilot.yaml as is: stored_values + lazy_refine + ent_pair_every +
kl_stop_prev 0.02), one policy update (u 5) from a fresh B0 learner per size, on the 4090: matches per update 512 (id1),
1,024 (id1 + id0) and 2,048 (the 1,024 twice: timing only, the duplicate rows make it no identity test). Prints the update
seconds, steps, rows and matches/h = m / update seconds (the learner alone; producers run in parallel in the loop).

    source env.sh; cd $CB; RL_PROFILE=1 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/cadence.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep \
        --keep2 /workspace/lrn/id0_freshhead/keep --out /workspace/lrn/cadence [--sizes 512,1024,2048]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402
from stored_gate import R, LR, torch  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--keep2", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, default=None, help="the T_gate the kept records were SAMPLED at (id1 / id0: "
                    "0.3; tgate_probe.py) -- a learner at another T_gate is off-policy on the gate")
    ap.add_argument("--sizes", default="512,1024,2048")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cfg = R.load_config(SG.REPO / a.config, [], smoke=False)
    if a.T_gate is not None:
        cfg["T_gate"] = a.T_gate
    r1 = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    r2 = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep2.glob("*.rec"))]
    sets = {512: r1, 1024: r1 + r2, 2048: r1 + r2 + r1 + r2}
    out = {"config": {k: cfg.get(k) for k in ("T_gate", "stored_values", "lazy_refine", "ent_pair_every", "kl_stop_prev",
                                              "minibatch", "ppo_epochs")}}
    for m in (int(x) for x in a.sizes.split(",")):
        L = SG.learner(cfg, f"cad{m}")
        t = time.perf_counter()
        res = SG.with_v(L, cfg, sets[m])
        prep = time.perf_counter() - t
        rec = SG.run_update(L, 5, res, {})
        if rec["first_minibatch"]["ratio_maxdev"] >= R.ASSERT_RATIO:              # B0 on B0's records
            raise SystemExit(f"OFF-POLICY records: first ratio_maxdev {rec['first_minibatch']} -- T_gate?")
        out[m] = {"matches": len(res), "rows": rec["rows"], "steps": rec.get("steps"), "kl_stop": rec.get("kl_stop"),
                  "wall_update_s": rec["wall_update_s"], "matches_per_h": 3600 * len(res) / rec["wall_update_s"],
                  "v_old_prep_s (gate only)": prep, "ent_pair_rows": rec.get("ent_pair_rows"),
                  "gpu_peak_mb": rec.get("learner_gpu_peak_mb")}
        print("cadence", m, json.dumps(out[m], default=str), flush=True)
        del L, res
        torch.cuda.empty_cache()
    (a.out / f"cadence_{SG.TAG}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
