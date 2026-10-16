#!/bin/bash
# T1 (round-2 plan, owner 10-16 "Yes"): the F1 recipe (mkcfg arm gae) trained to 500 updates, one seed per pod, on
# RoyaleSim 0.1.35 (RT 20261016-linux, venv35 -- L74/rt35/setup_rt35.sh first). Chain: smoke -> train 500 -> graft + live-pool
# D3 (960 paired) at u150 / u250 / u350 / u500 -> standard D1 + D3 (960) at u500 -> SUMMARY -> DONE (the pod watchdog,
# L74/deploy/pod_watchdog.sh, stops the pod after a grace period).
#   CB=/workspace/cb_xx t1_chain.sh SEED      results /workspace/results/t1_sSEED   (RT / PY / WORKERS env override)
set -Eeuo pipefail
S=$1; CB=${CB:-/workspace/clashbot}; PY=${PY:-/workspace/venv35/bin/python}; RT=${RT:-20261016-linux}; W=${WORKERS:-15}
RUN=t1_s$S; O=/workspace/results/$RUN; mkdir -p $O; exec >> $O/run.log 2>&1
trap 'echo "exit_code=$?" > $O/DONE' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
echo "$(date -u +%T) $RUN on $RT ($PY), workers $W"
$PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py gae $O/$RUN.yaml
$PY -m pipeline.rl_royale --config $O/$RUN.yaml --run ${RUN}_smoke --smoke seed=$S > $O/smoke.out 2>&1 || true
grep -q "SMOKE PASS" $O/smoke.out || { echo "$(date -u +%T) SMOKE FAILED"; tail -n 20 $O/smoke.out; exit 3; }
echo "$(date -u +%T) smoke pass; training"
ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $O/$RUN.yaml --run $RUN \
  seed=$S max_updates=500 > $O/train.log 2>&1
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/ || true
for U in 150 250 350 500; do
  CK=$RL/$RUN/${RUN}_u$(printf '%04d' $U).pt; G=${CK%.pt}_grafted.pt
  [ -f $CK ] || { echo "missing $CK"; continue; }
  $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $OLD $G > $O/graft_u$U.log 2>&1
  sha256sum $CK $G >> $O/ckpts.sha
  echo "$(date -u +%T) live-pool eval u$U"
  CB=$CB RT=$RT PY=$PY O=$O/LIVE WORKERS=$W bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none ${RUN}_u$U $G D3
done
CK=$RL/$RUN/${RUN}_u0500.pt; G=${CK%.pt}_grafted.pt
for SD in 741200 742000; do
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/D1_$SD --arms D1 --seed-start $SD \
    --runtime $RT --python $PY --workers $W > $O/D1_$SD.log 2>&1 || echo "GAP EXIT D1 $SD"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $O/D3_$SD --arms D3 --seed-start $SD \
    --runtime $RT --python $PY --workers $W > $O/D3_$SD.log 2>&1 || echo "GAP EXIT D3 $SD"
done
{ echo "$RUN ($RT): $(head -1 $O/ckpts.sha 2>/dev/null | cut -c1-16)"
  for d in $O/LIVE/*_7*/ $O/D?_*/; do [ -d $d ] && echo "== $(basename $d)" && { grep -hE "^D[0-3]:" $d/SUMMARY.txt || true; }; done; } > $O/SUMMARY.txt
echo "$(date -u +%T) done"
