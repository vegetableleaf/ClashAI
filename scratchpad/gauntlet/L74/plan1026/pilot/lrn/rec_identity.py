"""LOOP-REC converter test + LOOP-LRN learner identity + the 512-match update timing, on REAL rl_royale crforge records.

    source env.sh; cd $CB; RL_PROFILE=1 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/rec_identity.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --out /workspace/lrn/id1 [key=value ...]

1. capture: an rl_royale Learner's own ``rollout(0)`` (sample_matchups + the ActorPool on crforge) -> E x G results;
   each -> loop_records.from_result(wver 0) -> put() into OUT/spool (and OUT/keep, a copy for re-runs: --reuse).
2. LOOP-REC: collate(results) vs collate(to_result(decode(file))) for every file: per-key batch shas, the collate stats,
   rollout_monitors and league_monitors must be byte-identical (json).
3. LOOP-LRN: two FRESH learners from the same config (rl_royale.Learner with rollout() returning the captured results;
   loop_learner.LoopLearner reading the spool), both with B0's ability head, run update 0 (critic warm-up) and then a
   policy update (update counter set to critic_warmup_updates; records re-tagged to that version): model / ability head
   / Adam state shas and the update records (wall clocks dropped) must be equal. Deterministic CUDA (set here).
Writes OUT/result.json; prints PASS / FAIL lines. RL_PROFILE=1 logs each update's profile (rl_royale W16).
"""
import argparse
import copy
import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402

WALL = ("wall_rollout_s", "wall_update_s", "wall_save_s", "wall_total_s", "time", "actor_s_per_match",
        "actor_gpu_peak_mb", "learner_gpu_peak_mb", "ckpt", "spool")


def jd(x):
    return json.dumps(R._py(x), sort_keys=True)


def strip(rec):
    return {k: v for k, v in rec.items() if k not in WALL}


def sd_sha(L):
    out = {"model": R.batch_sha(L.model.state_dict()), "ability_head": R.batch_sha(L.ability_head.state_dict())}
    for name, opt in (("opt", L.opt), ("ability_opt", L.ability_opt)):
        st = opt.state_dict()["state"]
        out[name] = R.batch_sha({f"{k}.{m}": v[m] for k, v in st.items() for m in ("exp_avg", "exp_avg_sq")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reuse", action="store_true", help="skip the capture: records from OUT/keep")
    ap.add_argument("--capture-only", action="store_true", help="stop after the LOOP-REC test (learner_device=cpu is fine)")
    ap.add_argument("overrides", nargs="*")
    a = ap.parse_args()
    cfg = R.load_config(REPO / a.config, a.overrides, smoke=False)
    keep, spool = a.out / "keep", a.out / "spool"
    res_out = {"config_sha": R.config_sha(cfg), "E": cfg["E"], "G": cfg["G"]}
    tag = str(int(time.time()))
    a.out.mkdir(parents=True, exist_ok=True)

    def learner(cls, name, **kw):
        run = f"lrn_{name}_{tag}"
        for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
            d.mkdir(parents=True, exist_ok=True)
        return cls(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False, **kw)

    if not a.reuse:
        L0 = learner(R.Learner, "cap")
        L0.start_actors()
        t = time.perf_counter()
        results, _ = L0.rollout(0)
        res_out["capture_s"] = time.perf_counter() - t
        L0.actors.close()
        keep.mkdir(parents=True, exist_ok=True)
        for r in results:
            LR.put(keep, LR.from_result(r, 0))
        del L0
        files = sorted(keep.glob("*.rec"))
        B1, st1 = R.collate(results, float(cfg["adv_clip"]), **collate_kw(cfg))
        back = [LR.to_result(LR.decode(p.read_bytes())) for p in files]
        B2, st2 = R.collate(back, float(cfg["adv_clip"]), **collate_kw(cfg))
        k1, k2 = {k: R.batch_sha({k: v}) for k, v in B1.items()}, {k: R.batch_sha({k: v}) for k, v in B2.items()}
        mon = (lambda rs: jd({"roll": R.rollout_monitors(rs, cfg["tau"], cfg.get("T_gate") or cfg["T"]),
                              "league": R.league_monitors(rs)}))
        ok = k1 == k2 and jd(st1) == jd(st2) and mon(results) == mon(back)
        res_out["rec"] = {"matches": len(results), "rows": int(len(B1["A"])), "batch_sha": R.batch_sha(B1),
                          "batch_sha_records": R.batch_sha(B2), "keys": len(k1), "identical": ok,
                          "bytes_per_record_mean": sum(p.stat().st_size for p in files) / len(files),
                          "differing_keys": sorted(k for k in k1 if k1[k] != k2.get(k))}
        print(("PASS" if ok else "FAIL"), "LOOP-REC collate + monitors byte-identical:", res_out["rec"], flush=True)
        del B1, B2, back
        if a.capture_only:
            (a.out / "result_rec.json").write_text(json.dumps(res_out, indent=1, default=str))
            return
    files = sorted(keep.glob("*.rec"))
    results = [LR.to_result(LR.decode(p.read_bytes())) for p in files]
    assert len(files) == int(cfg["E"]) * int(cfg["G"]), f"{len(files)} records != E x G (skipped rollouts?)"
    warm =int(R.adv_cfg(cfg)["critic_warmup_updates"])
    res_out["updates"] = {}
    for u in (0, warm):
        L1 = learner(R.Learner, f"rl{u}")
        L2 = learner(LL.LoopLearner, f"loop{u}", spool=spool, weights=a.out / "weights")
        for L in (L1, L2):
            assert LL.adopt_init_ability_head(L)
            L.update = u
        L1.rollout = (lambda uu, rs=results: (copy.deepcopy(rs), {"picked": [], "skipped": 0, "actors": {},
                      "league": [{"opp": r["league"]["opp"]["id"], "learner_deck": r["league"].get("learner_deck_name"),
                                  "opp_deck": r["league"].get("opp_deck_name"), "side": r["side"]} for r in rs]}))
        if spool.exists():
            shutil.rmtree(spool)
        spool.mkdir(parents=True)
        for p in files:                                      # the spool copy, re-tagged to the version in force
            rec = LR.decode(p.read_bytes())
            rec["wver"][:] = u
            LR.put(spool, rec)
        out = {}
        for name, L in (("rl_royale", L1), ("loop", L2)):
            t = time.perf_counter()
            rec, reasons, crash = L.one_update(u)
            out[name] = {"wall_s": time.perf_counter() - t, "wall_update_s": rec["wall_update_s"], "sha": sd_sha(L),
                         "rec": jd(strip(rec)), "reasons": reasons, "crash": crash, "steps": rec.get("steps"),
                         "kl_stop": rec.get("kl_stop"), "rows": rec["rows"],
                         "gpu_peak_mb": rec["learner_gpu_peak_mb"]}
        same = out["rl_royale"]["sha"] == out["loop"]["sha"] and out["rl_royale"]["rec"] == out["loop"]["rec"]
        res_out["updates"][u] = {"identical": same, **{n: {k: v for k, v in o.items() if k != "rec"} for n, o in out.items()},
                                 "rec_equal": out["rl_royale"]["rec"] == out["loop"]["rec"]}
        print(("PASS" if same else "FAIL"), f"LOOP-LRN update {u} ({'critic warm-up' if u < warm else 'policy'}) "
              f"same weights / Adam / record:", json.dumps(res_out["updates"][u], default=str), flush=True)
        if not out["rl_royale"]["rec"] == out["loop"]["rec"]:
            r1, r2 = json.loads(out["rl_royale"]["rec"]), json.loads(out["loop"]["rec"])
            print("  record keys differing:", sorted(k for k in set(r1) | set(r2) if r1.get(k) != r2.get(k)), flush=True)
        if L1.actors is not None:
            L1.actors.close()
        del L1, L2
        torch.cuda.empty_cache()
    (a.out / "result.json").write_text(json.dumps(res_out, indent=1, default=str))


def collate_kw(cfg):
    """Learner.one_update's collate arguments (the parts these configs use)."""
    ac = R.adv_cfg(cfg)
    kw = {"advantage": ac["advantage"]}
    if ac["shaping"] in R.RS.STATE_PHI_MODES:
        kw["shaping"] = {"mode": ac["shaping"], "gamma": ac["gae_gamma"], "params": {k: ac[k] for k in R.STATE_PHI_KEYS}}
    elif ac["shaping"] == "tower_crown":
        kw["shaping"] = {"gamma": ac["gae_gamma"], "w_tower": ac["shaping_w_tower"], "w_crown": ac["shaping_w_crown"]}
    if ac["advantage"] == "gae" and ac["gae_gamma_unit"] == "tick":
        kw["gamma_tick"] = ac["gae_gamma_tick"]
    for k, f in (("spell", R.spell_cfg), ("crown", R.crown_cfg), ("habit", R.HT.habit_cfg)):
        if f(cfg) is not None:
            kw[k] = f(cfg)
    return kw


if __name__ == "__main__":
    main()
