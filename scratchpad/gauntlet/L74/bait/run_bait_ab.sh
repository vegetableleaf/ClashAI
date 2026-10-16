#!/bin/bash
# B6 stage A on a pod (10-16): bait_gae + ONE change = the LEARNED Hero Valkyrie press (rl_royale ability_head: imitation
# warm start from the v2 rule, then PPO), learner deck fixed by bait_rl.py. run_bait.sh's chain with arm bait_gae_ab:
#   unit tests -> bait_rl --smoke (start only on SMOKE PASS) -> train 65 -> graft OLD's heads -> bait_eval 960 pairs
#   (741200 + 742000) for the trained model AND bait_gae u65 grafted (BASE, sha-checked), both with --ability-stats
#   (press outcomes per match) -> bait_summary.py -> SUMMARY.txt -> stop the pod ONLY if /workspace/AUTOSTOP exists.
# Defaults RT35 (ROYALE_RUNTIME 20261016-linux, /workspace/venv35). bait_gae itself trained on 20261012-linux (its
# checkpoint's rl.runtime): for a strict one-change A/B run with RT=20261012-linux PY=/workspace/venv33/bin/python.
#     nohup setsid bash scratchpad/gauntlet/L74/bait/run_bait_ab.sh > /dev/null 2>&1 &        (CB = this checkout)
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; PY=${PY:-/workspace/venv35/bin/python}; RT=${RT:-20261016-linux}
RUN=${RUN:-bait_gae_ab}; O=/workspace/results/$RUN
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
INIT=$RL/newsim_base_main/newsim_base_main_u0060.pt; B=scratchpad/gauntlet/L74/bait
BASE=$RL/bait_gae/bait_gae_u0065_grafted.pt; BASE_SHA=19309b90d5d2999d5fb47b67e652d7c715fa43a9be6cb9b733ee9b24d87d8b2b
mkdir -p $O; exec >> $O/run.log 2>&1
autostop() {
  [ -e /workspace/AUTOSTOP ] || { echo "$(date -u +%T) no /workspace/AUTOSTOP: pod left running"; return 0; }
  echo "$(date -u +%T) AUTOSTOP: stopping the pod"
  export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=")
  runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
}
trap 'rc=$?; echo "exit_code=$rc" > $O/DONE; autostop' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start $RUN (runtime $RT, $PY)"
for f in $OLD $INIT $BASE; do [ -f $f ] || { echo "missing $f"; exit 2; }; done
[ "$(sha256sum $BASE | awk '{print $1}')" = "$BASE_SHA" ] || { echo "BASE sha256 is not $BASE_SHA"; exit 2; }
sha256sum $OLD $INIT $BASE | sed 's/ \*/  /' > $O/inputs.sha
$PY $B/test_bait.py
T=pipeline.tests.test_ability_head   # the offline classes (the engine ones were measured on the laptop's pinned runtime)
$PY -m unittest $T.TestConfig $T.TestHead $T.TestSampler $T.TestLearner > $O/test_ability_head.out 2>&1 \
  || { tail -n 30 $O/test_ability_head.out; exit 3; }
$PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py bait_gae_ab $O/$RUN.yaml
N=$(grep -E '^max_updates:' $O/$RUN.yaml | awk '{print $2}')
if [ ! -e $O/SMOKE_OK ]; then
  ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY $B/bait_rl.py --config $O/$RUN.yaml --run smoke_$RUN --smoke \
    > $O/smoke.out 2>&1 || true
  grep -q "SMOKE PASS" $O/smoke.out || { echo "$(date -u +%T) SMOKE NOT PASSED -- training not started"; tail -n 30 $O/smoke.out; exit 3; }
  grep "ability_head warm start" $O/smoke.out || true
  echo "$(date -u +%T) SMOKE PASS"; touch $O/SMOKE_OK
fi
echo "$(date -u +%T) train $RUN to $N updates"
ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY $B/bait_rl.py --config $O/$RUN.yaml --run $RUN > $O/train.log 2>&1
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/ || true
grep "ability_head warm start" $O/train.log > $O/warm_start.txt || true
CK=$RL/$RUN/${RUN}_u$(printf '%04d' $N).pt; [ -f $CK ] || { echo "no final checkpoint $CK"; exit 3; }
G=${CK%.pt}_grafted.pt
$PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $OLD $G > $O/graft.log 2>&1
sha256sum $CK $G | sed 's/ \*/  /' > $O/final.sha
for NAME in trained:$G bait_gae_u65:$BASE; do for S in 741200 742000; do
  echo "$(date -u +%T) eval ${NAME%%:*} $S"
  flock /workspace/cpu.lock $PY $B/bait_eval.py --ckpt ${NAME#*:} --out $O/EV_${NAME%%:*}_$S --seed-start $S \
    --workers ${WORKERS:-25} --python $PY --runtime $RT --extra=--ability-stats > $O/EV_${NAME%%:*}_$S.log 2>&1
done; done
$PY $B/bait_summary.py $O/SUMMARY.txt trained=$O/EV_trained_741200,$O/EV_trained_742000 \
  bait_gae_u65=$O/EV_bait_gae_u65_741200,$O/EV_bait_gae_u65_742000 > $O/summary.out 2>&1
echo "$(date -u +%T) done"
