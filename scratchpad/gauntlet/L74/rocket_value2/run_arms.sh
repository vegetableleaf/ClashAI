#!/bin/bash
# Run the arms whose seed subsets exist, P jobs at a time (each W workers): the whole VM budget stays ~P*W processes.
#   TREE=t9 OUT=~/rocket_value2/c1 SEEDDIR=~/rocket_value2/seeds1 P=8 W=3 bash run_arms.sh "arm1 arm2 ..." "evo lad"
ARMS=${1:?arms}; CENS=${2:-"evo lad"}
cd ~/rocket_value2
export TREE=${TREE:-t9} OUT SEEDDIR W=${W:-3}
mkdir -p $OUT
for a in $ARMS; do for c in $CENS; do
  [ -s $SEEDDIR/${a}_$c.txt ] && echo "$a $c"
done; done | xargs -P ${P:-8} -L 1 bash vm_one.sh
echo "ALL DONE $(date +%T)" >> $OUT/sim.log
