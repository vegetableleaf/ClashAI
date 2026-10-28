#!/bin/bash
# LOOP-ASYNC identity lint (33308): overlap ABSENT, the pre-overlap tree (/workspace/async/old) vs the new one
# (/workspace/async/cb), in-process forwards, 3 updates, same seed; then the W16 batch / weights sha lines side by side.
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
O="E=8 G=4 max_updates=3 critic_warmup_updates=1 n_actors=2 save_every=1 stored_values=false screen_entries=2"
for T in old cb; do
  RUN=async_id_$T
  [ -e /workspace/async/$RUN.done ] && continue
  cd /workspace/async/$T && CB=/workspace/async/$T CFG=$L/ref_pilot_noiw.yaml \
    FAST_ARGS="--producers 2 --matches 16 --threads 4 --devices cuda:0" bash $L/run.sh fast $RUN 200-215 $O
  echo "$(date +%T) $RUN rc $?"; touch /workspace/async/$RUN.done
done
for T in old cb; do echo "== $T"; grep -E "W16 u|\] u000" /workspace/loop/logs/async_id_$T.log | cut -c1-160; done
