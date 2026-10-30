#!/bin/bash
# FASTLOOP-FIX (laptop): tar of origin/main's pipeline + loop + obsid, the working copy's loop dir on top (CR stripped), to
# 33903 as POD_TAR; then build the tree there: bash ship_mfl.sh POD_TAR TREE   (e.g. /workspace/mfl/mflf.tar /workspace/mfl/cbf)
set -e
TAR=$1; T=$2; R=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74/plan1026/pilot/loop
S=$(mktemp -d)
git -C $R archive origin/main pipeline $L scratchpad/gauntlet/L74/speed/crforge/obsid | tar -x -C $S
for f in $(cd $R/$L && ls *.py *.java *.sh mfl/*); do mkdir -p $(dirname $S/$L/$f); cp $R/$L/$f $S/$L/$f; sed -i 's/\r$//' $S/$L/$f; done
tar -cf $S.tar -C $S pipeline scratchpad
SSH="ssh -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -p 33903 root@157.157.221.29"
scp -q -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -P 33903 $S.tar root@157.157.221.29:$TAR
scp -q -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -P 33903 $S/$L/mfl/mfl_tree.sh root@157.157.221.29:/workspace/mfl/mfl_tree.sh
$SSH "T=$T A=$T.arch TAR=$TAR bash /workspace/mfl/mfl_tree.sh 2>&1 | tail -2"
rm -rf $S $S.tar
