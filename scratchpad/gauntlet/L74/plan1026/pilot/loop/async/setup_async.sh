# LOOP-ASYNC tree on 33308: setup_async.sh CB -- copies of pipeline + the loop dir (incl. jbuild), read-only symlinks into
# LOOP-INT2's /workspace/loop/cb for everything else; run outputs (L68/rl, icebow/data/bench/rl_royale) stay real dirs here.
set -e
CB=$1; S=/workspace/loop/cb; LP=scratchpad/gauntlet/L74/plan1026/pilot/loop
mkdir -p $CB/scratchpad/gauntlet/L68/rl $CB/icebow/data/bench/rl_royale $CB/scratchpad/gauntlet/L74/plan1026/pilot
link_missing() { for p in $1/*; do n=$(basename "$p"); [ -e "$2/$n" ] || [ -L "$2/$n" ] || ln -s "$p" "$2/$n"; done; }
[ -d $CB/pipeline ] || cp -r $S/pipeline $CB/pipeline
[ -d $CB/$LP ] || { cp -r $S/$LP $CB/$LP; rm -rf $CB/$LP/__pycache__ $CB/$LP/jbuild; }
for d in "" scratchpad scratchpad/gauntlet scratchpad/gauntlet/L68 scratchpad/gauntlet/L74 scratchpad/gauntlet/L74/plan1026 \
         scratchpad/gauntlet/L74/plan1026/pilot icebow icebow/data icebow/data/bench icebow/data/bench/rl_royale; do
  link_missing $S/$d $CB/$d
done
echo SETUP_OK $CB
