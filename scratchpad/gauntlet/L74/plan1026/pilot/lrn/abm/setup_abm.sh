#!/bin/bash
# LEARNER-SCALE3 A/B tree on 33553 (= LOOP-ASYNC setup_async.sh): /workspace/abm/cb = origin/main pipeline/ + pilot/loop/
# (from /workspace/abm/code.tar, made on the laptop by `git archive -o code.tar origin/main pipeline scratchpad/gauntlet/L74/plan1026/pilot/loop`),
# read-only symlinks into LOOP-INT's /workspace/loop/cb for everything else; run outputs (L68/rl, bench/rl_royale) and the
# facade build dir stay real dirs here.
set -e
CB=/workspace/abm/cb; S=/workspace/loop/cb; LP=scratchpad/gauntlet/L74/plan1026/pilot/loop
df -h /workspace | tail -1
mkdir -p $CB/scratchpad/gauntlet/L68/rl $CB/icebow/data/bench/rl_royale $CB/$LP/jbuild_fe364ceb
tar xf /workspace/abm/code.tar -C $CB
sed -i "s#/workspace/loop/logs#/workspace/abm/logs#g" $CB/$LP/run.sh   # this tree logs under /workspace/abm, not LOOP-INT's dir
grep -q /workspace/loop/logs $CB/$LP/run.sh && { echo "run.sh still writes /workspace/loop/logs"; exit 1; }
link_missing() { for p in $1/*; do n=$(basename "$p"); [ -e "$2/$n" ] || [ -L "$2/$n" ] || ln -s "$p" "$2/$n"; done; }
for d in "" scratchpad scratchpad/gauntlet scratchpad/gauntlet/L68 scratchpad/gauntlet/L74 scratchpad/gauntlet/L74/plan1026 \
         scratchpad/gauntlet/L74/plan1026/pilot icebow icebow/data icebow/data/bench icebow/data/bench/rl_royale; do
  link_missing $S/$d $CB/$d
done
ls -la $CB/icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt
echo SETUP_OK $CB
