#!/bin/bash
# gate48.sh RUN U -- succ48 final gate, pod-local: graft RUN's uU checkpoint (as ckpt_eval.sh), then board-recorded evals of it
# with the NO-hazard livecal (cb_stepd): E4 (gap D3) and the calibrated I u40 (decide 20, tau .2) on the 4 seed blocks, via
# push_cal/gate_eval.sh (same command as the CLX-with-hazard baselines clx_rb / pushcal iu40_d20t20 + clxhaz_cal).
# Beside a trainer: LOCK=/workspace/cpu_b.lock. Output /workspace/pushcal/ev/g48_RUN_uU_{e4,cal}/; DONE file at the end.
set -uo pipefail
RUN=$1; U=$(printf %04d $2); CB=/workspace/cb_stepd; P=/workspace/venvf15/bin/python; R=rlarm_$RUN
CK=$CB/icebow/data/bench/rl_royale/$R/${R}_u$U.pt; U250=icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt
G=${CK%.pt}_grafted.pt; TAG=g48_${RUN}_u$U; X=/workspace/pushcal; mkdir -p $X
cd $CB || exit 1
[ -f $G ] || $P scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $U250 $G > $X/$TAG.graft.log 2>&1 || { echo "graft failed" > $X/$TAG.FAIL; exit 5; }
sha256sum $CK $G > $X/$TAG.sha
printf "%s\n" "${TAG}_e4|e4||741200 742000 743000 744000" "${TAG}_cal|iu40|--opp-decide-every 20 --opp-tau 0.2|741200 742000 743000 744000" > $X/q_$TAG.txt
G=$G LOCK=${LOCK:-/workspace/cpu_b.lock} WORKERS=${WORKERS:-26} bash $X/gate_eval.sh $X/q_$TAG.txt > $X/$TAG.log 2>&1
touch $X/$TAG.DONE
