"""LOOP-LRN (i) gate: GenModel.lazy_refine (cell_refine / tower_refine cell features built only for the rows whose cell
logits are taken) vs the eager model, same update (u 5) on the same 512 records, recompute mode and stored mode.
Reports bit identity, or the max |diff| of advantages, returns, final weights, and the update seconds.

    source env.sh; cd $CB; RL_PROFILE=1 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/lazy_gate.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep --out DIR
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402  (sets the deterministic / TF32-off flags)
from stored_gate import R, LR, torch, np  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    base = R.load_config(SG.REPO / a.config, [], smoke=False)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    out = {}
    for mode, extra in (("recompute", {}), ("stored", {"stored_values": True, "ent_init_rows": 20000})):
        caps = {}
        for lazy in (False, True):
            cfg = {**base, **extra, "lazy_refine": lazy}       # the rl_royale key (set on model + refs at init)
            L = SG.learner(cfg, f"lz{mode}{int(lazy)}")
            assert all(getattr(m, "lazy_refine", False) is lazy for m in (L.model, L.ref, L.ref_init))
            rr = SG.with_v(L, cfg, res) if extra else res
            cap = {}
            SG.run_update(L, 5, rr, cap)
            cap["w"] = {k: v.detach().cpu().double() for k, v in L.model.state_dict().items()}
            caps[lazy] = cap
            print(mode, "lazy" if lazy else "eager", json.dumps(SG.summ(cap["rec"]), default=str), flush=True)
            del L
            torch.cuda.empty_cache()
        e, z = caps[False], caps[True]
        out[mode] = {"weights_identical": all(torch.equal(e["w"][k], z["w"][k]) for k in e["w"]),
                     "max_abs_weight": max(float((e["w"][k] - z["w"][k]).abs().max()) for k in e["w"]),
                     "max_abs_A": float(np.abs(e["A"] - z["A"]).max()), "max_abs_ret": float(np.abs(e["ret"] - z["ret"]).max()),
                     "eager": SG.summ(e["rec"]), "lazy": SG.summ(z["rec"])}
        print("GATE", mode, json.dumps({k: v for k, v in out[mode].items() if k not in ("eager", "lazy")}), flush=True)
    (a.out / f"lazy_gate_{int(time.time())}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
