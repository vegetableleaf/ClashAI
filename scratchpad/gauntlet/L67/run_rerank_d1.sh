#!/bin/bash
# L67n: after DAgger iteration 1 -> retrain (ONE change vs head C: the DAgger shards are added) -> closed-loop A/B
# of head C (pre-DAgger) and head D1C on identical seeds, both slices, then the fixed paired report.
cd /c/Users/benpe/ClashBot
L=scratchpad/gauntlet/L67
PY=./icebow/.venv/Scripts/python.exe
CK=icebow/data/pipeline/s1_icebow_v6lat_s0.pt
until [ -f $L/rr_dag1_0.json ] && [ -f $L/rr_dag1_1.json ] && [ -f $L/rr_dag1_2.json ]; do
  if grep -q Traceback $L/rr_dag1_*.out 2>/dev/null; then echo "DAGGER CRASHED -- chain aborted"; exit 4; fi
  sleep 60
done
echo "dagger done $(date -u +%H:%M)"
$PY $L/rerank_train.py --ckpt $CK --shards $L/rr_0.npz $L/rr_1.npz $L/rr_2.npz $L/rr_dag1_0.npz $L/rr_dag1_1.npz $L/rr_dag1_2.npz \
    --hidden 64 --dropout 0.5 --wd 1e-2 --freeze-emb --lr 1e-3 --tag D1C > $L/rerank_D1C.out 2>&1 || { echo "RETRAIN FAILED"; exit 5; }
grep "^BEST" $L/rerank_D1C.out | cut -c1-300
for H in C D1C; do
  $PY $L/rerank_sim.py --ckpt $CK --head $L/rerank/rerank_head_${H}_s0.pt --matches 12 --seed0 900000 --margin 0.0 --out $L/rerank/sim_${H}_A.json > $L/rerank_sim_${H}_A.out 2>&1 &
  $PY $L/rerank_sim.py --ckpt $CK --head $L/rerank/rerank_head_${H}_s0.pt --matches 12 --seed0 911000 --margin 0.0 --out $L/rerank/sim_${H}_B.json > $L/rerank_sim_${H}_B.out 2>&1 &
done
wait
for H in C D1C; do
  echo "===== head $H ====="
  $PY $L/rerank_ab_report.py --a $L/rerank/sim_${H}_A.json --b $L/rerank/sim_${H}_B.json --label $H 2>&1 | grep -v RuntimeWarning
done
echo "CHAIN_DONE $(date -u +%H:%M)"
