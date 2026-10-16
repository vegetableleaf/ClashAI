#!/bin/bash
# RT35 re-baseline (owner 10-16 "Let's do the re-baseline"): the same three checkpoints, same paired seeds 741200 + 742000
# (960 games each), D3 = the live rule stack, on royalesim 0.1.35 (ROYALE_RUNTIME=20261016-linux, /workspace/venv35):
#   live pool (gap.py --census-file L74/mix/decks_live_eval.json)   old: f1u250 580, f1u65 506, r1 427 /960
#   standard set (CAL c censuses, E4 T .1)                          old: f1u250 521, f1u65 467, r1 402 /960
# Serialised on /workspace/cpu.lock; results /workspace/results/RT35/<set>_<name>_<seed>. Ends by stopping the pod ONLY if
# /workspace/AUTOSTOP exists (the lead decides). Compare: python scratchpad/gauntlet/L74/rt35/rt_cmp.py <RT35 dir>
#   nohup bash scratchpad/gauntlet/L74/rt35/rebaseline_pod.sh > /dev/null 2>&1 < /dev/null &      (from CB)
set -Euo pipefail
CB=${CB:-/workspace/cb_rt35}; PY=${PY:-/workspace/venv35/bin/python}; RT=${RT:-20261016-linux}; O=/workspace/results/RT35
RL=icebow/data/bench/rl_royale
mkdir -p $O; exec >> $O/run.log 2>&1
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start RT=$RT PY=$PY CB=$CB"
$PY -c "from pipeline.royale_runtime import activate; s = activate(); print(s['runtime_id'], s['pins'])" || { echo "RUNTIME FAILED"; touch $O/FAILED; exit 2; }
declare -A CK=([f1u250]=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt [f1u65]=$RL/rlarm_gae/rlarm_gae_u0065_grafted.pt
               [r1]=$RL/newsim_r1/newsim_base_r1_final_grafted.pt)
declare -A SHA=([f1u250]=00c845c0 [f1u65]=693889c3 [r1]=fce50ebb)
for N in f1u250 f1u65 r1; do
  [ "$(sha256sum ${CK[$N]} | cut -c1-8)" = ${SHA[$N]} ] || { echo "CKPT MISMATCH $N ${CK[$N]}"; touch $O/FAILED; exit 2; }
done
sha256sum ${CK[@]} > $O/ckpts.sha
for SET in live std; do for N in f1u250 r1 f1u65; do for S in 741200 742000; do
  D=$O/${SET}_${N}_$S
  [ -s $D/D3/matches.jsonl ] && grep -q "^D3:" $D/SUMMARY.txt 2>/dev/null && { echo "skip $D (done)"; continue; }
  rm -rf $D
  echo "$(date -u +%T) $SET $N $S"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt ${CK[$N]} --out $D --arms D3 --seed-start $S \
    --runtime $RT --python $PY --workers ${WORKERS:-16} \
    $([ $SET = live ] && echo --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json) > $D.log 2>&1 \
    && grep -h "^D3:" $D/SUMMARY.txt || echo "GAP EXIT $SET $N $S (see $D.log)"
done; done; done
$PY scratchpad/gauntlet/L74/rt35/rt_cmp.py $O --old-root /workspace/results/RT35_OLD > $O/CMP.txt 2>&1 || true
touch $O/DONE
echo "$(date -u +%T) done"
if [ -e /workspace/AUTOSTOP ]; then
  echo "$(date -u +%T) AUTOSTOP: stopping pod"
  export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=")
  runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
fi
