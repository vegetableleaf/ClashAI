#!/bin/bash
# Isolated VM code tree for rocket_value2: ~/rocket_value2/DIR = TAR (git archive of pipeline + L68/live_reader + this dir) over
# symlinks to ~/ClashBot data (same recipe as L74/rocket_value/vm_setup.sh).  bash vm_setup2.sh TAR DIR
set -e
T=$1; D=~/rocket_value2/$2; rm -rf $D; mkdir -p $D; cd $D
tar xf $T
rm -rf icebow research hogeq; ln -s ~/ClashBot/icebow icebow; ln -s ~/ClashBot/research research; ln -s ~/ClashBot/hogeq hogeq
for g in ~/ClashBot/scratchpad/*; do b=$(basename "$g"); [ -e "scratchpad/$b" ] || ln -s "$g" "scratchpad/$b"; done
for g in ~/ClashBot/scratchpad/gauntlet/*; do b=$(basename "$g"); [ -e "scratchpad/gauntlet/$b" ] || ln -s "$g" "scratchpad/gauntlet/$b"; done
for L in L68 L69 L70 L73 L74 L68/live_reader L70/gen_v31; do
  for g in ~/ClashBot/scratchpad/gauntlet/$L/*; do b=$(basename "$g"); [ -e "scratchpad/gauntlet/$L/$b" ] || ln -s "$g" "scratchpad/gauntlet/$L/$b"; done
done
find . -path ./icebow -prune -o -path ./research -prune -o -path ./hogeq -prune -o -name "*.py" -type f -print0 | xargs -0 sed -i 's/\r$//'
echo "built $D"
