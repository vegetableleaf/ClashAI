#!/bin/bash
# Bait-deck RL for the owner's friend (owner 10-16: "start bait training on one of the pods"). Arm gae's recipe (F1: GAE,
# critic warm-up, PFSP-hard league, init newsim_base_main_u0060, 65 updates, save every 5) with the LEARNER deck fixed to
# the friend's deck (bait_rl.py; opponents/decks/sides/seeds drawn as arm gae draws them). Chain:
#   unit test -> rl_royale --smoke (start only on SMOKE PASS) -> train 65 -> graft OLD's heads (run_rlarm2.sh's graft)
#   -> bait_eval.py 960 pairs (741200 + 742000) for u65_g, the bait live model (wk_bait_u0060_g) and the init grafted
#   -> bait_summary.py -> SUMMARY.txt -> stop the pod ONLY if /workspace/AUTOSTOP exists (the lead decides; never created here).
#     nohup setsid bash scratchpad/gauntlet/L74/bait/run_bait.sh > /dev/null 2>&1 &        (CB = this checkout)
set -Eeuo pipefail
CB=${CB:-/workspace/cb_bait}; PY=/workspace/venv33/bin/python; RUN=${RUN:-bait_gae}; O=/workspace/results/$RUN
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
INIT=$RL/newsim_base_main/newsim_base_main_u0060.pt; LIVE=$RL/wk_bait/wk_bait_u0060_g.pt; B=scratchpad/gauntlet/L74/bait
mkdir -p $O; exec >> $O/run.log 2>&1
autostop() {
  [ -e /workspace/AUTOSTOP ] || { echo "$(date -u +%T) no /workspace/AUTOSTOP: pod left running"; return 0; }
  echo "$(date -u +%T) AUTOSTOP: stopping the pod"
  export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=")
  runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
}
trap 'rc=$?; echo "exit_code=$rc" > $O/DONE; autostop' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start $RUN"
for f in $OLD $INIT $LIVE; do [ -f $f ] || { echo "missing $f"; exit 2; }; done
sha256sum $OLD $INIT $LIVE > $O/inputs.sha
$PY $B/test_bait.py
$PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py bait_gae $O/$RUN.yaml
N=$(grep -E '^max_updates:' $O/$RUN.yaml | awk '{print $2}')
if [ ! -e $O/SMOKE_OK ]; then
  ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY $B/bait_rl.py --config $O/$RUN.yaml --run smoke_$RUN --smoke \
    > $O/smoke.out 2>&1 || true
  grep -q "SMOKE PASS" $O/smoke.out || { echo "$(date -u +%T) SMOKE NOT PASSED -- training not started"; tail -n 30 $O/smoke.out; exit 3; }
  echo "$(date -u +%T) SMOKE PASS"; touch $O/SMOKE_OK
fi
echo "$(date -u +%T) train $RUN to $N updates"
ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY $B/bait_rl.py --config $O/$RUN.yaml --run $RUN > $O/train.log 2>&1
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/ || true
CK=$RL/$RUN/${RUN}_u$(printf '%04d' $N).pt; [ -f $CK ] || { echo "no final checkpoint $CK"; exit 3; }
G=${CK%.pt}_grafted.pt; IG=$RL/$RUN/init_newsim_base_main_u0060_grafted.pt
$PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $OLD $G > $O/graft.log 2>&1
$PY scratchpad/gauntlet/L74/weekend/graft_generic.py $INIT $OLD $IG >> $O/graft.log 2>&1
sha256sum $CK $G $IG > $O/final.sha
for NAME in trained:$G live_bait:$LIVE init:$IG; do for S in 741200 742000; do
  echo "$(date -u +%T) eval ${NAME%%:*} $S"
  flock /workspace/cpu.lock $PY $B/bait_eval.py --ckpt ${NAME#*:} --out $O/EV_${NAME%%:*}_$S --seed-start $S \
    --workers ${WORKERS:-25} > $O/EV_${NAME%%:*}_$S.log 2>&1
done; done
$PY $B/bait_summary.py $O/SUMMARY.txt trained=$O/EV_trained_741200,$O/EV_trained_742000 \
  live_bait=$O/EV_live_bait_741200,$O/EV_live_bait_742000 init=$O/EV_init_741200,$O/EV_init_742000 > $O/summary.out 2>&1
echo "$(date -u +%T) done"
