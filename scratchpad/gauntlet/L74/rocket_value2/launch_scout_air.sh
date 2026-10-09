#!/bin/bash
# Scout (BASE + shadow triggers of every variant) on the air-heavy opponent pool: 122 census decks holding a Balloon or Lava Hound
# (air_answer's make_air_census.py), seeds 0:240, one job.  bash launch_scout_air.sh
cd ~/rocket_value2
mkdir -p scout_air
export TREE=t4 OUT=$HOME/rocket_value2/scout_air ARMS="base" W=${W:-8} CENSUSES="evo"
export EVO=$HOME/rocket_value2/air_census.json
export WRAP=scratchpad/gauntlet/L74/rocket_value2/rv2_scout_s0.py
export SCOUT_VARIANTS=$HOME/rocket_value2/t4/scratchpad/gauntlet/L74/rocket_value2/variants.json
export ARMFILE=$HOME/rocket_value2/t4/scratchpad/gauntlet/L74/rocket_value2/arms_all.txt
nohup bash vm_ab3.sh > scout_air_nohup.out 2>&1 &
echo started
