#!/bin/bash
# The tests that touch decision_options / live_gen_v2, NEW (tree $1) vs MAIN (tree $2), same VM environment; failures are diffed.
#   bash vm_tests2.sh t7 tmain   -> ~/rocket_value2/pytest_{t7,tmain}.out and f_*.txt
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
T="pipeline/tests/test_live_options.py pipeline/tests/test_xbow_dead_lane.py pipeline/tests/test_public_decision_audit.py
   pipeline/tests/test_own_ability_hero_iw.py pipeline/tests/test_log_barrel.py pipeline/tests/test_live_decision_options.py
   pipeline/tests/test_live_anti_leak.py pipeline/tests/test_lethal_rocket.py pipeline/tests/test_identity_ext.py
   pipeline/tests/test_gate_threatened.py pipeline/tests/test_gate_decode.py pipeline/tests/test_expert_diagnostics.py
   pipeline/tests/test_decision_options.py pipeline/tests/test_branching.py pipeline/tests/test_branch_r4.py
   pipeline/tests/test_afford_ticks.py scratchpad/gauntlet/L68/live_reader"
for t in $1 $2; do
  ( cd ~/rocket_value2/$t; nice -n 10 ~/venv/bin/python -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors $T \
      > ~/rocket_value2/pytest_$t.out 2>&1; echo DONE >> ~/rocket_value2/pytest_$t.out
      grep -E "^(FAILED|ERROR)" ~/rocket_value2/pytest_$t.out | sed 's/ - .*//' | sort > ~/rocket_value2/f_$t.txt ) &
done
wait
echo "new-only failures:"; comm -13 ~/rocket_value2/f_$2.txt ~/rocket_value2/f_$1.txt
echo "main-only failures:"; comm -23 ~/rocket_value2/f_$2.txt ~/rocket_value2/f_$1.txt
tail -1 ~/rocket_value2/pytest_$1.out; tail -1 ~/rocket_value2/pytest_$2.out
