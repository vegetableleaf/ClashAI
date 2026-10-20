#!/bin/bash
# O1 full build on the laptop (single process each step, below-normal priority via the python scripts' own setting where present).
#   bash scratchpad/gauntlet/L74/opp_model/o1_build.sh   -> out/o1_corpus, out/o1_{train,holdout}.npz, out/o1_*_v32.npz, o1_check.out
set -euo pipefail
cd "$(dirname "$0")/../../../.."
PY=icebow/.venv/Scripts/python.exe; O=scratchpad/gauntlet/L74/opp_model/out
rm -rf $O/o1_corpus
$PY -I scratchpad/gauntlet/L74/opp_model/o1_records.py > $O/o1_records.log 2>&1
for s in train holdout; do
  $PY -m pipeline.dataset_gen --feature-version 5 --corpus $O/o1_corpus/$s --out $O/o1_$s.npz --workers 1 --val-pct 0 \
      --v3val-npz $O/none.npz > $O/o1_dataset_$s.log 2>&1
done
$PY -I scratchpad/gauntlet/L74/opp_model/o1_finalize.py > scratchpad/gauntlet/L74/opp_model/o1_check.out 2>&1
sha256sum $O/o1_train_v32.npz $O/o1_holdout_v32.npz > $O/o1_v32.sha
echo O1_DONE
