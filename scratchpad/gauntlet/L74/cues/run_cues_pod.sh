#!/bin/bash
# Step c pod chain (owner 10-16; STEP_C_SPEC.md): smoke (gae_cue_u250 config, must print SMOKE PASS) -> train gae_cue_u250
# -> graft -> train gae_ctl_u250 -> graft -> live-pool eval of both (L74/mix/live_eval_pod.sh, D3, 960 paired)
# -> touch /workspace/results/CUES_ALL_DONE.  Re-runnable: a finished arm is kept, an interrupted one --resume'd.
#   cd /workspace/clashbot && nohup bash scratchpad/gauntlet/L74/cues/run_cues_pod.sh > /dev/null 2>&1 &
#   env: CB (checkout) PY (python with royalesim 0.1.35) RT (runtime id) WORKERS (gap workers) HEROIW_FORM (hero)
# Logs / configs / shas: /workspace/results/CUES; evals: /workspace/results/LIVEEVAL/cues_gae_{cue,ctl}_u250_*.
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; PY=${PY:-/workspace/venv35/bin/python}; RT=${RT:-20261016-linux}; WORKERS=${WORKERS:-25}
HEROIW_FORM=${HEROIW_FORM:-hero}
RL=icebow/data/bench/rl_royale; LIVE=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt   # graft source = the live u250's own heads
O=/workspace/results/CUES; mkdir -p $O
exec >> $O/run.log 2>&1
trap 'echo "$(date -u +%T) exit_code=$?"' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=$HEROIW_FORM OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start $(git rev-parse --short HEAD) RT=$RT PY=$PY HEROIW_FORM=$HEROIW_FORM WORKERS=$WORKERS"
for A in gae_cue_u250 gae_ctl_u250; do
  [ -f $O/$A.yaml ] || $PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py $A $O/$A.yaml
done
diff <(grep -v '^cue_inputs: true$' $O/gae_cue_u250.yaml) $O/gae_ctl_u250.yaml || { echo "arms differ beyond cue_inputs"; exit 2; }
if [ ! -f $O/SMOKE_PASS ]; then
  rm -rf scratchpad/gauntlet/L68/rl/cues_smoke $RL/cues_smoke
  $PY -m pipeline.rl_royale --config $O/gae_cue_u250.yaml --run cues_smoke --smoke > $O/smoke.log 2>&1 || true
  grep -q "SMOKE PASS" $O/smoke.log || { echo "SMOKE FAILED (see $O/smoke.log)"; exit 3; }
  echo "SMOKE PASS"; touch $O/SMOKE_PASS
fi
for A in gae_cue_u250 gae_ctl_u250; do
  R=rlarm_$A; N=$(grep -E '^max_updates:' $O/$A.yaml | awk '{print $2}'); CK=$RL/$R/${R}_u$(printf '%04d' $N).pt
  if [ ! -f $CK ]; then
    RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
    echo "$(date -u +%T) train $R $RES"
    flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $O/$A.yaml --run $R $RES > $O/${A}_train.log 2>&1 \
      || echo "TRAIN EXIT $? $R"
    cp scratchpad/gauntlet/L68/rl/$R/train_log.jsonl $O/${A}_train_log.jsonl || true
  fi
  [ -f $CK ] || { echo "no final checkpoint $CK"; exit 4; }
  $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $LIVE ${CK%.pt}_grafted.pt
  sha256sum $CK ${CK%.pt}_grafted.pt >> $O/final.sha
done
for A in gae_cue_u250 gae_ctl_u250; do
  R=rlarm_$A; N=$(grep -E '^max_updates:' $O/$A.yaml | awk '{print $2}')
  [ -f /workspace/results/LIVEEVAL/cues_$A.DONE ] || CB=$CB PY=$PY RT=$RT WORKERS=$WORKERS \
    bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none cues_$A $RL/$R/${R}_u$(printf '%04d' $N)_grafted.pt D3
done
touch /workspace/results/CUES_ALL_DONE
echo "$(date -u +%T) CUES_ALL_DONE"
