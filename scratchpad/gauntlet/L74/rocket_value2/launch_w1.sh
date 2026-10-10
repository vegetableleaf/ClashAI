#!/bin/bash
# wave 1: pairs of arms, one pair after the other (base is already running from the first launch)
cd ~/rocket_value2
export W=6
nohup bash chain.sh t2 $HOME/rocket_value2/w1 "rv9 plc9" "de9 de9_e9" "de9_idle de9_lead" "de11 de7_e9" "de9_e8" > chain_w1b.nohup 2>&1 &
echo started
