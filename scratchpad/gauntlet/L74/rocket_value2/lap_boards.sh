#!/bin/bash
# Laptop: BASE with every board logged (rv2_boards_s0.py) on the seeds the VM never finished; 3 processes, evo then lad.
#   bash lap_boards.sh OUTDIR MISSING_EVO_FILE MISSING_LAD_FILE
O=$1
cd /c/Users/benpe/ClashBot/.claude/worktrees/agent-a67f26ceb5d77048a
export WRAP=scratchpad/gauntlet/L74/rocket_value2/rv2_boards_s0.py
bash scratchpad/gauntlet/L74/rocket_value2/lap_one.sh base evo $(cat $2) $O 3
bash scratchpad/gauntlet/L74/rocket_value2/lap_one.sh base lad $(cat $3) $O 3
echo BOARDS_DONE >> $O/sim.log
