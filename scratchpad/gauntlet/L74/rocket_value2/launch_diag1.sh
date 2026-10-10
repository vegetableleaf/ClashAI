#!/bin/bash
# Diagnosis run on the iteration-1 code tree: rv9 with full-board windows around its Rocket fires, and BASE with windows at the same times.
cd ~/rocket_value2
printf 'base\nrv9 --rocket-value 9\n' > arms_iter1.txt
export TREE=iter1 ARMS="base rv9" W=6 OUT=$HOME/rocket_value2/diag1 WRAP=scratchpad/gauntlet/L74/rocket_value/rv2_diag_s0.py
export ARMFILE=$HOME/rocket_value2/arms_iter1.txt TIMES=$HOME/rocket_value2/times_rv9_
nohup bash vm_ab2.sh > diag1_nohup.out 2>&1 &
echo started
