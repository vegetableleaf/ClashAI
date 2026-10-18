#!/bin/bash
# Step d pre-flight (pod; memory trainer-edit-preship-check): pyflakes (undefined names) on the shipped tree, then a REAL
# rl_royale --smoke on fin13-linux (venvf13, Hero IW form hero, ROYALE_HEROIW_PRESS unset: the yaml's heroiw_press: live sets it):
#   A  stepd_ctrl.yaml  (CLIII init, kl_heads [card], loose leash, league_exploiters)                       -> K1 card-only leash
#   B  stepd_rebc3.yaml (init gen_v32_s0 = a stand-in for IL-cue-w until D2b lands; kl_ref_card CLIII)       -> IL init + K1 card ref
# league_exploiters.ckpt = CLIII raw in both (a stand-in: Stage 2's s2_all_il_sA_u0130 does not exist yet; same code path).
#   bash stepd_smoke.sh   -> /workspace/stepd/smoke/smoke.log, SMOKE_OK when both print SMOKE PASS
set -uo pipefail
CB=/workspace/cb_stepd; O=/workspace/stepd/smoke; PY=/workspace/venvf13/bin/python; mkdir -p $O; exec >> $O/smoke.log 2>&1
cd $CB; rm -f $O/SMOKE_OK $O/SMOKE_DONE
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
D=scratchpad/gauntlet/L74/stepd/cfg; RL=icebow/data/bench/rl_royale; CL=$RL/rlarm_succ_levels/rlarm_succ_levels_u0065.pt
EX="league_exploiters={ckpt: $CL, decks: scratchpad/gauntlet/L74/mix/decks_live_train.json, share: 0.3}"
echo "$(date -u +%T) smoke start"
$PY -m pyflakes pipeline/{royale_runtime,royale_heroiw,royale_env,e1_eval,rl_royale,search_s0,spell_value,train_gen,eval_gen}.py \
  | grep -i "undefined\|syntax"; echo "pyflakes undefined-name / syntax lines above (none = clean)"
ok=1
for X in A B; do
  rm -rf scratchpad/gauntlet/L68/rl/smoke_stepd_$X $RL/smoke_stepd_$X
done
nice -n 5 $PY -m pipeline.rl_royale --config $D/stepd_ctrl.yaml --run smoke_stepd_A --smoke "$EX" > $O/smoke_A.log 2>&1 &
nice -n 5 $PY -m pipeline.rl_royale --config $D/stepd_rebc3.yaml --run smoke_stepd_B --smoke "$EX" \
  init=icebow/data/pipeline/gen_v32_s0/gen_s0.pt > $O/smoke_B.log 2>&1 &
wait
for X in A B; do
  if grep -q "SMOKE PASS" $O/smoke_$X.log; then echo "smoke $X: PASS"; else echo "smoke $X: FAIL"; tail -20 $O/smoke_$X.log; ok=0; fi
done
grep -h "kl_ref_card\|kl_heads\|heroiw\|IW press\|exploiter" $O/smoke_A.log $O/smoke_B.log | head -20
[ $ok = 1 ] && touch $O/SMOKE_OK
echo "$(date -u +%T) smoke done ok=$ok"; touch $O/SMOKE_DONE
