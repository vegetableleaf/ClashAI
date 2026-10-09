#!/bin/bash
# Run arm PAIRS one after the other (each pair = 2 arms x 2 censuses x W workers): bash chain.sh TREE OUT "base rv9" "plc9 de9" ...
# Arm flags: $HOME/rocket_value2/$TREE/scratchpad/gauntlet/L74/rocket_value2/arms.txt (or ARMFILE).
export TREE=$1 OUT=$2; shift 2
export W=${W:-7}
cd ~/rocket_value2
for pair in "$@"; do
  ARMS="$pair" bash ~/rocket_value2/vm_ab2.sh
  echo "pair done: $pair $(date +%T)" >> $OUT/chain.log
  mv $OUT/sim.log $OUT/sim_$(echo $pair | tr ' ' '_').log 2>/dev/null
done
echo CHAIN_DONE >> $OUT/chain.log
