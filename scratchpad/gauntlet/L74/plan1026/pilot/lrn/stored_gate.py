"""LOOP-LRN gates for (iv) stored_values and the entropy-baseline subsample (lead 10-28), on real crforge records.

    source env.sh; cd $CB; RL_PROFILE=1 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/stored_gate.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep \
        --keep2 /workspace/lrn/id0_freshhead/keep --out /workspace/lrn/stored [--parts ent,a,c,cadence]

Recompute-equivalence: the records get traj["v_old"] = V(s) of the update-start model (value_rows), i.e. what a server
with the learner's weights would store; stored mode then differs from recompute mode only by the lazy anchor (minibatch-
sized ref forwards instead of 512-row chunks) and the entropy baseline (subsample).
  ent      entropy floor's ref_init baseline: full pass vs fixed-seed subsamples, 3 batches, relative error + seconds
  a        one update (u 5): stored vs recompute -> max |diff| of advantages, returns, final weights; both records
  c        3 consecutive updates (u 5, 6, 7) on 3 disjoint ~341-match batches, each mode from the same start
  cadence  stored-mode update seconds at 512 and 1,024 matches (2,048 projected)
"""
import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw, jd, strip  # noqa: E402

TAG = str(int(time.time()))


def learner(cfg, name):
    run = f"lrn_st_{name}_{TAG}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    assert LL.adopt_init_ability_head(L)
    return L


def keep_mask(t):
    k = t["gate_sampled"] | t["played"]
    for key in ("posture_new", "ab_sampled"):
        if key in t:
            k = k | t[key]
    return k


def with_v(L, cfg, res):
    """res + traj["v_old"] = the update-start model's V on every kept row (0 elsewhere: never read)."""
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    v = R.value_rows(L.model, R.to_device(Bn, L.dev)).cpu().numpy()
    out, o = [], 0
    for r in res:
        r = copy.copy(r)
        r["traj"] = dict(r["traj"])
        k = keep_mask(r["traj"])
        vo = np.zeros(len(k))
        vo[k] = v[o:o + int(k.sum())]
        o += int(k.sum())
        r["traj"]["v_old"] = vo
        out.append(r)
    assert o == len(v)
    return out


def run_update(L, u, res, capture):
    L.update = u
    L.rollout = (lambda uu, rs=res: (copy.deepcopy(rs), {"picked": [], "skipped": 0, "actors": {},
                 "league": [{"opp": r["league"]["opp"]["id"], "learner_deck": r["league"].get("learner_deck_name"),
                             "opp_deck": r["league"].get("opp_deck_name"), "side": r["side"]} for r in rs]}))
    real = R.gae_batch

    def spy(model, B, cfg, ctx_head=None):
        st = real(model, B, cfg, ctx_head=ctx_head)
        capture["A"], capture["ret"], capture["v_old"] = (B[k].detach().cpu().numpy().copy() for k in ("A", "ret", "v_old"))
        return st
    R.gae_batch = spy
    try:
        t = time.perf_counter()
        rec, reasons, crash = L.one_update(u)
        capture["wall_s"] = time.perf_counter() - t
    finally:
        R.gae_batch = real
    capture["rec"] = rec
    return rec


def summ(rec):
    return {k: rec.get(k) for k in ("kl_gate", "kl_card", "kl_cell", "clip_frac", "entropy", "entropy_init", "kl_stop",
                                    "steps", "wall_update_s")} | {"l_v": (rec.get("gae") or {}).get("l_v")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--keep2", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--parts", default="ent,a,c,cadence")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    parts = a.parts.split(",")
    base = R.load_config(REPO / a.config, [], smoke=False)
    res1 = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    res2 = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep2.glob("*.rec"))]
    allr = res1 + res2
    batches = [allr[i::3] for i in range(3)]                  # 3 disjoint ~341-match batches
    out = {}
    if "ent" in parts:                                        # item 1: subsample size for the ref_init entropy baseline
        L = learner(base, "ent")
        out["ent"] = []
        for b in batches:
            B = R.to_device(R.collate(b, float(base["adv_clip"]), **collate_kw(base))[0], L.dev)
            t = time.perf_counter()
            full = R.ref_terms(L.ref_init, B, base["tau"], base["T"], T_gate=base.get("T_gate"))["ent"]
            row = {"rows": int(len(B["A"])), "full": full, "full_s": time.perf_counter() - t, "sub": {}}
            for n in (1000, 2000, 5000, 10000, 20000):
                for seed in (0, 1, 2):
                    sub = R.ent_init_rows(B, {"ent_init_rows": n, "seed": seed}, 0)
                    t = time.perf_counter()
                    e = R.ref_terms(L.ref_init, R.row_subset(B, sub), base["tau"], base["T"], T_gate=base.get("T_gate"))["ent"]
                    rel = max(abs(e[h] - full[h]) / abs(full[h]) for h in full if full[h])
                    row["sub"].setdefault(n, []).append({"rel_max": rel, "s": time.perf_counter() - t})
            out["ent"].append(row)
            print("ent", json.dumps({"rows": row["rows"], "full_s": round(row["full_s"], 1),
                                     **{n: [round(x["rel_max"], 4) for x in v] for n, v in row["sub"].items()}}), flush=True)
            del B
        del L
        torch.cuda.empty_cache()
    if "a" in parts:                                          # gate (a): one update, stored vs recompute
        caps = {}
        for name, st in (("recompute", False), ("stored", True)):
            cfg = {**base, "stored_values": st, "ent_init_rows": 20000}
            L = learner(cfg, f"a{name}")
            res = with_v(L, cfg, res1)
            caps[name] = {}
            run_update(L, 5, res, caps[name])
            caps[name]["w"] = {k: v.detach().cpu().double() for k, v in L.model.state_dict().items()}
            print("a", name, json.dumps(summ(caps[name]["rec"]), default=str), flush=True)
            del L
            torch.cuda.empty_cache()
        r, s = caps["recompute"], caps["stored"]
        out["a"] = {"max_abs_A": float(np.abs(r["A"] - s["A"]).max()), "max_abs_ret": float(np.abs(r["ret"] - s["ret"]).max()),
                    "max_abs_v_old": float(np.abs(r["v_old"] - s["v_old"]).max()),
                    "max_abs_weight": max(float((r["w"][k] - s["w"][k]).abs().max()) for k in r["w"]),
                    "weights_identical": all(torch.equal(r["w"][k], s["w"][k]) for k in r["w"]),
                    "recompute": summ(r["rec"]), "stored": summ(s["rec"]),
                    "record_equal_except_entropy_init": jd({k: v for k, v in strip(r["rec"]).items() if k != "entropy_init"})
                    == jd({k: v for k, v in strip(s["rec"]).items() if k != "entropy_init"})}
        print("GATE a", json.dumps({k: v for k, v in out["a"].items() if k not in ("recompute", "stored")}), flush=True)
    if "c" in parts:                                          # gate (c): 3 consecutive updates per mode
        out["c"] = {}
        for name, st in (("recompute", False), ("stored", True)):
            cfg = {**base, "stored_values": st, "ent_init_rows": 20000}
            L = learner(cfg, f"c{name}")
            out["c"][name] = []
            for i, b in enumerate(batches):
                cap = {}
                rec = run_update(L, 5 + i, with_v(L, cfg, b), cap)
                out["c"][name].append(summ(rec))
                print("c", name, 5 + i, json.dumps(summ(rec), default=str), flush=True)
            del L
            torch.cuda.empty_cache()
    if "cadence" in parts:                                    # item 3: stored-mode update seconds vs matches per update
        out["cadence"] = {}
        for n, res in ((512, res1), (1024, allr)):
            cfg = {**base, "stored_values": True, "ent_init_rows": 20000}
            L = learner(cfg, f"cad{n}")
            cap = {}
            rec = run_update(L, 5, with_v(L, cfg, res), cap)
            out["cadence"][n] = {"wall_update_s": rec["wall_update_s"], "steps": rec.get("steps"), "rows": rec["rows"]}
            print("cadence", n, json.dumps(out["cadence"][n]), flush=True)
            del L
            torch.cuda.empty_cache()
    (a.out / f"stored_gate_{TAG}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
