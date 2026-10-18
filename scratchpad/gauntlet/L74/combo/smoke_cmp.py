"""Compare the three combo smokes' UPDATE-0 records (smoke.sh): off_old (git-HEAD modules) vs off_new (this code, key absent)
must match on every rollout monitor AND every pre-step critic number (same init, same rollouts, same batch); on (key on) vs
off_new must match on the rollout monitors (the tracker is measurement only) and differ in the reward-dependent numbers.
Update 1 is not compared: after one optimiser step on the GPU the weights need not be bit-equal. On a GPU learner the
critic numbers of two processes can differ at ~1e-10 (float noise), so they are compared to TOL; with learner_device=cpu
(two files: OFF_OLD OFF_NEW) they must be bit-equal.
    python smoke_cmp.py OFF_OLD.jsonl OFF_NEW.jsonl ON.jsonl
    python smoke_cmp.py OFF_OLD_CPU.jsonl OFF_NEW_CPU.jsonl        exact, rollout + critic + losses of update 0"""
import json
import sys

ROLLOUT = ("matches", "winrate", "plays_per_min", "plays_per_match", "card_mix", "rows", "rows_played", "rows_gate",
           "decisions", "groups", "mixed_groups", "mean_abs_A", "draws", "opp_plays_per_min")
CRITIC = ("adv_mean", "adv_std", "ret_mean", "v_mean", "explained_var", "value_target_outside_share", "value_mae")


def u0(path):
    return next(json.loads(s) for s in open(path, encoding="utf-8") if '"type": "update"' in s and '"update": 0,' in s)


TOL = 1e-8
if len(sys.argv) == 3:                      # CPU twins: every number of update 0, bit for bit
    a, b = (u0(p) for p in sys.argv[1:3])
    keys = ROLLOUT + ("kl_gate", "kl_card", "kl_cell", "l_pg", "entropy", "clip_frac", "ratio_mean", "grad_norm_mean")
    diff = {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}
    diff.update({f"gae.{k}": (a["gae"].get(k), b["gae"].get(k)) for k in CRITIC + ("l_v", "l_v_first")
                 if a["gae"].get(k) != b["gae"].get(k)})
    print("cpu off_old vs off_new update 0:", "bit-identical" if not diff else "DIFFERS " + json.dumps(diff))
    print("SMOKE_CMP_CPU", "PASS" if not diff else "FAIL")
    sys.exit(0 if not diff else 1)
old, new, on = (u0(p) for p in sys.argv[1:4])
ok = True
for name, a, b, keys, want_same in (("off_old vs off_new rollout", old, new, ROLLOUT, True),
                                    ("off_old vs off_new critic", old["gae"], new["gae"], CRITIC, True),
                                    ("on vs off_new rollout", on, new, ROLLOUT, True),
                                    ("on vs off_new critic", on["gae"], new["gae"], ("adv_mean", "ret_mean"), False)):
    close = (lambda x, y: x == y or (isinstance(x, float) and isinstance(y, float) and abs(x - y) <= TOL * max(1.0, abs(x))))
    diff = {k: (a.get(k), b.get(k)) for k in keys if not close(a.get(k), b.get(k))}
    good = (not diff) if want_same else bool(diff)
    ok &= good
    print(f"{name}: {'identical' if not diff else 'DIFFERS ' + json.dumps(diff)} -> {'OK' if good else 'BAD'}")
print("on: spell monitors", json.dumps(on.get("spell")), "| gae phi_share", on["gae"].get("phi_share"),
      "critic_scale", on["gae"].get("critic_scale"), "adv_r1_diff", on["gae"].get("adv_r1_diff"))
print("off_new has no spell key:", "spell" not in new, "| no residual critic:", "critic_scale" not in new["gae"])
ok &= "spell" not in new and "critic_scale" not in new["gae"] and "spell" in on
print("SMOKE_CMP", "PASS" if ok else "FAIL")
