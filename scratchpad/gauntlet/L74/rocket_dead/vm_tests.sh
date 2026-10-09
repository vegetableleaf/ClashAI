#!/bin/bash
# NEW-vs-main test classification on the VM: the whole pipeline/tests suite + L68/live_reader tests in ~/rocket_dead/t_new
# (this branch) and ~/rocket_dead/t_main (main 41c551a), same environment. One process per tree, nice.  bash vm_tests.sh
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
for t in t_new t_main; do
  cd ~/rocket_dead/$t
  nice timeout 5400 ~/venv/bin/python -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors \
    pipeline/tests scratchpad/gauntlet/L68/live_reader > ~/rocket_dead/pytest_$t.out 2>&1 &
done
wait
echo DONE >> ~/rocket_dead/pytest_t_new.out
