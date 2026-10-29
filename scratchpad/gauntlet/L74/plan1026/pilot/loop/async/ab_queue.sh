#!/bin/bash
# LOOP-ASYNC A/B queue on 33308 (/workspace/async/cb): overlap 0 vs 1 x seeds, one run at a time, then ab_eval.
# usage: [XO="k=v ..."] setsid nohup bash ab_queue.sh TAG "SEEDS" > /workspace/async/ab_TAG.out 2>&1 &
# Each run: ref_pilot_noiw + E 32 x G 4 (128 matches / update), 8 updates, critic warm-up 1, save_every 1, server eager,
# 2 producers x 64 in flight. Records: only records_u0000.pkl kept (the held-out B0 batch for the OTHER seed).
TAG=$1; SEEDS=${2:-"1028 2029"}
CB=/workspace/async/cb; L=scratchpad/gauntlet/L74/plan1026/pilot/loop; OUT=/workspace/async/ab_$TAG
CFG=$L/ref_pilot_noiw.yaml
O="E=32 G=4 max_updates=8 critic_warmup_updates=1 n_actors=2 save_every=1 proagree_every=1000 screen_entries=2 ${XO:-}"   # XO: extra k=v (v2: ppo_decoupled=2.0)
mkdir -p $OUT; cd $CB || exit 1
for S in $SEEDS; do for M in 0 1; do
  RUN=async_${TAG}_s${S}_m$M; REC=$OUT/rec_$RUN
  [ -e $OUT/$RUN.done ] && continue
  mkdir -p $REC
  echo "$(date +%T) start $RUN; mem $(cat /sys/fs/cgroup/memory/memory.usage_in_bytes); gpu $(nvidia-smi --query-gpu=memory.used --format=csv,noheader | head -1)"
  ( while true; do find $REC -name 'records_u*.pkl' ! -name 'records_u0000.pkl' -mmin +0.1 -delete 2>/dev/null; sleep 10; done ) &
  PR=$!
  ( while true; do echo "$(date +%s) $(cat /sys/fs/cgroup/memory/memory.usage_in_bytes) $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader | head -1 | tr -d ' ') $(cat /proc/loadavg | cut -d' ' -f1)"; sleep 5; done ) > $OUT/$RUN.samples &
  SM=$!
  CB=$CB CFG=$CFG FASTLOOP_RECORDS=$REC FAST_ARGS="--producers 2 --matches 64 --threads 4 --devices cuda:0 --server eager --overlap $M --out $OUT/$RUN" \
    bash $L/run.sh fast $RUN 200-231 $O seed=$S
  echo "$(date +%T) end $RUN rc $?"
  kill $PR $SM
  find $REC -name 'records_u*.pkl' ! -name 'records_u0000.pkl' -delete
  cp /workspace/loop/logs/$RUN.log $OUT/ && touch $OUT/$RUN.done
done; done
# held-out: each seed's arms on the other seed's u0 (B0-played) records
set -- $SEEDS
if [ $# -ge 2 ]; then
  for S in $SEEDS; do H=$( [ $S = $1 ] && echo $2 || echo $1 )
    /workspace/venvf16/bin/python -u $L/async/ab_eval.py --config $CFG --held $OUT/rec_async_${TAG}_s${H}_m0/records_u0000.pkl \
      --arm m0=icebow/data/bench/rl_royale/async_${TAG}_s${S}_m0 --arm m1=icebow/data/bench/rl_royale/async_${TAG}_s${S}_m1 \
      --out $OUT/eval_s$S.json $O seed=$S
  done
fi
echo "$(date +%T) QUEUE DONE"
