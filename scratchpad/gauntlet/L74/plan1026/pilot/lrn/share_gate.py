"""LOOP-LRN gate for the shared no-grad pass (rl_royale one_update, kl_ref_refresh_every 1): the same update on the same
records with the shared pass (default) and with it off (share_ref_value False = the two-pass code) must give bit-identical
weights, Adam states and update record. Also logs both RL_PROFILE timings, and how long the ref_init entropy pass takes.

    source env.sh; cd $CB; RL_PROFILE=1 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/share_gate.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep [--u 5]
"""
import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.allow_tf32 = False                     # as rl_royale's learner_deterministic block (8c58db4)
torch.backends.cuda.matmul.allow_tf32 = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import jd, lazy_off, strip, sd_sha  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--u", type=int, default=5)
    a = ap.parse_args()
    cfg = lazy_off(R.load_config(REPO / a.config, [], smoke=False))   # identity gate: lazy OFF (LRN.md)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    tag, out = str(int(time.time())), {}
    for name, share in (("two_pass", False), ("shared", True)):
        run = f"lrn_share_{name}_{tag}"
        for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
            d.mkdir(parents=True, exist_ok=True)
        L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
        assert LL.adopt_init_ability_head(L)
        L.update, L.share_ref_value = a.u, share
        L.rollout = (lambda uu, rs=res: (copy.deepcopy(rs), {"picked": [], "skipped": 0, "actors": {},
                     "league": [{"opp": r["league"]["opp"]["id"], "learner_deck": r["league"].get("learner_deck_name"),
                                 "opp_deck": r["league"].get("opp_deck_name"), "side": r["side"]} for r in rs]}))
        t = time.perf_counter()
        rec, reasons, crash = L.one_update(a.u)
        out[name] = {"wall_s": time.perf_counter() - t, "wall_update_s": rec["wall_update_s"], "sha": sd_sha(L),
                     "rec": jd(strip(rec)), "kl_stop": rec.get("kl_stop"), "crash": crash, "reasons": reasons}
        print(name, {k: v for k, v in out[name].items() if k != "rec"}, flush=True)
        del L
        torch.cuda.empty_cache()
    same = out["two_pass"]["sha"] == out["shared"]["sha"] and out["two_pass"]["rec"] == out["shared"]["rec"]
    if out["two_pass"]["rec"] != out["shared"]["rec"]:
        r1, r2 = json.loads(out["two_pass"]["rec"]), json.loads(out["shared"]["rec"])
        print("record keys differing:", sorted(k for k in set(r1) | set(r2) if r1.get(k) != r2.get(k)), flush=True)
    print(("PASS" if same else "FAIL"), f"shared pass bit-identical at update {a.u}", flush=True)
    (a.keep.parent / f"share_gate_u{a.u}.json").write_text(json.dumps({**out, "identical": same}, indent=1, default=str))


if __name__ == "__main__":
    main()
