#!/bin/bash
# One-change RL arm vs rltest_ctrl (REWARD_ARCHITECTURE.md steps 1-2). On a pod set up by pod_setup_l74.sh + pod1014b.sh stage:
#   nohup bash scratchpad/gauntlet/L74/rlarms/run_rlarm.sh gae|opp > /dev/null 2>&1 &
# Train (r1's training condition: normal Ice Wizard), graft OLD's heads (as r1 was deployed), then score on the standard
# 960 pairs: D1 (plain greedy) and D3 (deployed stack, Hero IW + live press). Control rows: pods1013/rltest ctrl60*.
set -Eeuo pipefail
CB=/workspace/clashbot; PY=/workspace/venv33/bin/python; ARM=$1; RUN=rlarm_$ARM; O=/workspace/results/$RUN
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
mkdir -p $O
exec >> $O/run.log 2>&1
trap 'echo "exit_code=$?" > $O/DONE' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
$PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py $ARM $O/$RUN.yaml
N=$(grep -E '^max_updates:' $O/$RUN.yaml | awk '{print $2}'); N4=$(printf '%04d' $N)
echo "$(date -u +%T) train $RUN to $N updates"
ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $O/$RUN.yaml --run $RUN > $O/train.log 2>&1
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/ || true
CK=$RL/$RUN/${RUN}_u$N4.pt; [ -f $CK ] || { echo "no final checkpoint $CK"; exit 3; }
G=${CK%.pt}_grafted.pt
$PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $OLD $G > $O/graft.log 2>&1
sha256sum $CK $G > $O/final.sha
for S in 741200 742000; do
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/D1_$S --arms D1 --seed-start $S \
    --workers ${WORKERS:-25} > $O/D1_$S.log 2>&1
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $O/D3_$S --arms D3 --seed-start $S \
    --workers ${WORKERS:-25} > $O/D3_$S.log 2>&1
done
{ echo "$RUN: $(grep -c . $O/train_log.jsonl 2>/dev/null) log rows, final $(cut -c1-16 $O/final.sha | head -1)"
  for d in $O/D?_*/; do echo "== $(basename $d)"; grep -E "^D[0-3]:" $d/SUMMARY.txt; done; } > $O/SUMMARY.txt
echo "$(date -u +%T) done"
