#!/bin/bash
# Pre-flight checks on the build pod (after setup_troops.sh): pyflakes, check_env.py (tower table + env + draws), smokes
# with the option ABSENT on the HEAD option files (cb_old, twice) vs the edited ones (cb_tt), the arm-C smoke, a forced
# high-rate smoke, and the promotion-eval command on 6 seeds (old vs new absent: cmp; forced). -> $O/CHECKS_DONE
set -uo pipefail
CB=/workspace/cb_tt; OLD=/workspace/cb_old; PY=/workspace/venvf36/bin/python; O=/workspace/results/TT/checks
mkdir -p $O; exec >> $O/checks.log 2>&1
export ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1
TT=scratchpad/gauntlet/L74/troops; FORCE=DaggerDuchess:0.34,Cannoneer:0.33,ChefTower:0.33
echo "$(date -u +%T) checks start"
[ -d $OLD ] || { cp -a $CB $OLD && tar xzf /workspace/in/old4.tgz --no-same-owner -C $OLD; }
cd $CB && $PY -m pyflakes pipeline/{royale_runtime,royale_heroiw,royale_env,e1_eval,rl_royale,search_s0}.py $TT/*.py \
  | grep -i "undefined\|syntax" ; echo "pyflakes undefined-name lines above (none = clean)"
PYTHONPATH=$CB $PY $TT/check_env.py $O/tower_table.json > $O/check_env.out 2>&1; echo "check_env exit $?"
smoke() {  # DIR RUN CONFIG [override]
  (cd $1 && PYTHONPATH=$1 $PY -m pipeline.rl_royale --config $TT/$3 --run $2 --smoke ${4:+"$4"} > $O/$2.log 2>&1)
}
smoke $OLD smoke_old gae_f36_u250.yaml &
smoke $OLD smoke_old2 gae_f36_u250.yaml &
smoke $CB smoke_new gae_f36_u250.yaml &
smoke $CB smoke_tt gae_f36tt_u250.yaml &
smoke $CB smoke_force gae_f36tt_u250.yaml "opp_tower_troops={DaggerDuchess: 0.34, Cannoneer: 0.33, ChefTower: 0.33}" &
(cd $OLD && PYTHONPATH=$OLD $PY $TT/eval_check.py $O/ev_old 6 > $O/ev_old.out 2>&1) &
(cd $CB && PYTHONPATH=$CB $PY $TT/eval_check.py $O/ev_new 6 > $O/ev_new.out 2>&1) &
(cd $CB && PYTHONPATH=$CB $PY $TT/eval_check.py $O/ev_force 6 --opp-tower-troops $FORCE > $O/ev_force.out 2>&1) &
wait
cmp $O/ev_old/rows.json $O/ev_new/rows.json && echo "EVAL rows old == new (option absent): BYTE-IDENTICAL"
for s in smoke_old smoke_old2 smoke_new smoke_tt smoke_force; do echo "$s: $(grep -c 'SMOKE PASS' $O/$s.log) SMOKE PASS"; done
echo "$(date -u +%T) checks done"
touch $O/CHECKS_DONE
