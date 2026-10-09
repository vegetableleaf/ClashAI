#!/bin/bash
# Full forked-mechanic runs, ONE hold of /workspace/cpu.lock (lead slots it):
#   nohup flock /workspace/cpu.lock bash pod_queue.sh > /workspace/results/mech_fork/queue.out 2>&1 &
# JOBS = "MECH:CENSUS:FROM:TO ..." (default below); W workers each; MECH_CHECK=1 A-replay per worker process.
R=/workspace/results/mech_fork; W=${W:-28}
declare -A WT=([sneaky]=/workspace/wt_fork_sl [patience]=/workspace/wt_fork_pt [rocket_tower]=/workspace/wt_fork_rt)
JOBS=${JOBS:-"sneaky:evo:0:240 sneaky:lad:0:240 rocket_tower:evo:0:240 rocket_tower:lad:0:240 patience:evo:0:240 patience:lad:0:240"}
for j in $JOBS; do
  IFS=: read m c a b <<< "$j"
  o=$R/full_${m}_${c}_${a}_${b}
  [ -f $o/summary.json ] && continue
  rm -rf $o
  echo "[$(date +%T)] start $j"
  (cd ${WT[$m]} && bash scratchpad/gauntlet/L74/mechanic_fork/run_mech.sh $m $o $a:$b $W $c 1 > $o.log 2>&1)
  echo "[$(date +%T)] done $j rc=$? $(wc -l < $o/matches.jsonl) matches"
done
echo "[$(date +%T)] QUEUE DONE"
