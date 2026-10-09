#!/bin/bash
# BASE with every decision's board logged (rv2_boards_s0.py): the main censuses (EVO + ladder, 12 workers each) and the air-heavy pool
# (122 opponent decks with a Balloon or Lava Hound, 8 workers).  TREE=t6 bash launch_boards.sh
cd ~/rocket_value2
export TREE=${TREE:-t6}
export WRAP=scratchpad/gauntlet/L74/rocket_value2/rv2_boards_s0.py
export ARMFILE=$HOME/rocket_value2/$TREE/scratchpad/gauntlet/L74/rocket_value2/arms.txt
rm -rf boards boards_air; mkdir -p boards boards_air
( OUT=$HOME/rocket_value2/boards ARMS=base W=12 nohup bash vm_ab3.sh > boards_nohup.out 2>&1 & )
( OUT=$HOME/rocket_value2/boards_air ARMS=base W=8 CENSUSES=evo EVO=$HOME/rocket_value2/air_census.json nohup bash vm_ab3.sh > boards_air_nohup.out 2>&1 & )
echo started
