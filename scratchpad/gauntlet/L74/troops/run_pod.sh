#!/bin/bash
# L74 troops pod chain (10-17).  run_pod.sh ARM [NAME CKPT ...]
#   ARM = f36 (arm B: the gae control recipe on the fork engine) | f36tt (arm C: B + opponent tower troops, live rates)
#         | none (no training: only evaluate the NAME CKPT pairs)
#   train rlarm_gae_ARM_u250 (65 updates from u250 raw, Hero IW, scratchpad/gauntlet/L74/troops/gae_ARM_u250.yaml)
#   -> graft from u250 -> evals of it (name ARM) and of each NAME CKPT pair, all on THE SAME eval: fork36-linux, D3, seeds
#   741200 + 742000 (960 paired), L74/mix/live_eval_pod.sh. First tt_NAME (opponent tower troops at the live rates,
#   RATES), then ttx_NAME (troop SLICE: every opponent fields a troop in the live troop mix 6 / 6 / 3 of 15 -- the powered
#   comparison). Results /workspace/results/LIVEEVAL_TT.
#   env: WORKERS (gap workers, default 26), NICE (training niceness, default 0).  Always touches /workspace/results/TT_DONE.
set -Eeuo pipefail
A=$1; shift
CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; RT=fork36-linux
RL=icebow/data/bench/rl_royale; LIVE=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt; R=rlarm_gae_${A}_u250
O=/workspace/results/TT; mkdir -p $O; exec >> $O/run.log 2>&1
trap 'echo "$(date -u +%T) exit_code=$?"; touch /workspace/results/TT_DONE' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start ARM=$A evals: $* RT=$RT NICE=${NICE:-0} WORKERS=${WORKERS:-26}"
EV=()
if [ "$A" != none ]; then
  CFG=scratchpad/gauntlet/L74/troops/gae_${A}_u250.yaml; CK=$RL/$R/${R}_u0065.pt
  if [ ! -f $CK ]; then
    RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
    echo "$(date -u +%T) train $R $RES"
    flock /workspace/cpu.lock nice -n ${NICE:-0} $PY -m pipeline.rl_royale --config $CFG --run $R $RES > $O/${A}_train.log 2>&1 \
      || echo "TRAIN EXIT $?"
    cp scratchpad/gauntlet/L68/rl/$R/train_log.jsonl $O/${A}_train_log.jsonl || true
  fi
  [ -f $CK ] || { echo "no final checkpoint $CK"; exit 4; }
  [ -f ${CK%.pt}_grafted.pt ] || $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $LIVE ${CK%.pt}_grafted.pt
  sha256sum $CK ${CK%.pt}_grafted.pt >> $O/final.sha
  EV=($A ${CK%.pt}_grafted.pt)
fi
EV+=("$@")
LIVE_RATES=$(cat scratchpad/gauntlet/L74/troops/RATES); SLICE=DaggerDuchess:0.4,Cannoneer:0.4,ChefTower:0.2
for kind in "tt $LIVE_RATES" "ttx $SLICE"; do
  set -- $kind
  for ((i = 0; i < ${#EV[@]}; i += 2)); do
    N=${1}_${EV[i]}; C=${EV[i+1]}
    [ -f /workspace/results/LIVEEVAL_TT/$N.DONE ] || EXTRA="--opp-tower-troops $2" CB=$CB PY=$PY RT=$RT \
      O=/workspace/results/LIVEEVAL_TT WORKERS=${WORKERS:-26} bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none $N $C D3
  done
done
echo "$(date -u +%T) TT chain done"
