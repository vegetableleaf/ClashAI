#!/bin/bash
# Q4 parity-fix SIM arms (econ2): live checkpoint towerref_w2 + deployed options (calib.sh), opponent gen v1 T .3, v3 960
# paired (seeds 0:480 x evo + lad), isolated ~/econ2/repo_hero (hero_patch.py + the own_ability fix).
#   A = base (LR_HERO_IW unset: byte-identical observation)   B = hero IW form + 'unknown' token (live pre-fix)
#   C = hero IW form + known token (the fix)
cd ~/econ2/econ2
export REPO=/home/clashbot-gauntlet/econ2/repo_hero SEEDS=${SEEDS:-0:480} WORKERS=${WORKERS:-16}
ARM=hA bash calib.sh
LR_HERO_IW=unknown ARM=hB bash calib.sh
LR_HERO_IW=known ARM=hC bash calib.sh
echo HERO_DONE >> ~/econ2/sim/sim.log
