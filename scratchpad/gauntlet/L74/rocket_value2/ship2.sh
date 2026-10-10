#!/bin/bash
# Ship HEAD of this worktree to the VM tree ~/rocket_value2/$1 (default t2) and optionally run pytest on the given files.
#   bash ship2.sh t2 pipeline/tests/test_rocket_value2.py
T=${1:-t2}; shift
SSH="ssh -i $HOME/.ssh/clashbot_gcp clashbot-gauntlet@34.148.91.90"
TMP=${TMPDIR:-/tmp}
git archive HEAD pipeline scratchpad/gauntlet/L68/live_reader scratchpad/gauntlet/L74/rocket_value2 -o $TMP/rv2_$T.tar
scp -q -i $HOME/.ssh/clashbot_gcp $TMP/rv2_$T.tar clashbot-gauntlet@34.148.91.90:~/rocket_value2/rv2_$T.tar
scp -q -i $HOME/.ssh/clashbot_gcp scratchpad/gauntlet/L74/rocket_value2/vm_setup2.sh clashbot-gauntlet@34.148.91.90:~/rocket_value2/
$SSH "cd ~/rocket_value2 && sed -i 's/\r\$//' vm_setup2.sh && bash vm_setup2.sh ~/rocket_value2/rv2_$T.tar $T > /dev/null"
if [ -n "$1" ]; then
  $SSH "cd ~/rocket_value2/$T && export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= && nice -n 10 ~/venv/bin/python -m pytest -q -p no:cacheprovider $* 2>&1 | tail -40"
fi
