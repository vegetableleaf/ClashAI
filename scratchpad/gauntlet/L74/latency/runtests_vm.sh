#!/bin/bash
# L74: NEW-vs-main test classification on the VM. $1 = tree under ~/afford (base = main 0a777d5, mine = this branch).
# pipeline/tests (collection errors continue) + the live_reader tests, each collection-error file again on its own.
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
cd ~/afford/$1
timeout 3000 nice ~/venv/bin/python -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors \
  pipeline/tests scratchpad/gauntlet/L68/live_reader > ../pt_$1_all.out 2>&1
for f in $(grep "^ERROR " ../pt_$1_all.out | awk '{print $2}' | sed 's/::.*//' | sort -u); do
  echo "== $f" >> ../pt_$1_each.out
  timeout 1500 nice ~/venv/bin/python -m pytest -q -p no:cacheprovider -rfE $f >> ../pt_$1_each.out 2>&1
done
echo DONE >> ../pt_$1_each.out
