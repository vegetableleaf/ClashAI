#!/bin/bash
# O1b: the O1 build with projectile spells labelled at their TARGET (o1_records.py --spell-targets). Same split, same code path.
#   bash scratchpad/gauntlet/L74/opp_model/o1b_build.sh -> out/o1b_corpus, out/o1b_{train,holdout}{,_v32}.npz, o1b_check.out
set -euo pipefail
cd "$(dirname "$0")/../../../.."
PY=icebow/.venv/Scripts/python.exe; O=scratchpad/gauntlet/L74/opp_model/out
rm -rf $O/o1b_corpus
$PY -I scratchpad/gauntlet/L74/opp_model/o1_records.py --spell-targets --out $O/o1b_corpus > $O/o1b_records.log 2>&1
for s in train holdout; do
  $PY -m pipeline.dataset_gen --feature-version 5 --corpus $O/o1b_corpus/$s --out $O/o1b_$s.npz --workers 1 --val-pct 0 \
      --v3val-npz $O/none.npz > $O/o1b_dataset_$s.log 2>&1
done
$PY -I scratchpad/gauntlet/L74/opp_model/o1_finalize.py --prefix o1b --remap-only > scratchpad/gauntlet/L74/opp_model/o1b_check.out 2>&1
sha256sum $O/o1b_train_v32.npz $O/o1b_holdout_v32.npz > $O/o1b_v32.sha
echo O1B_DONE
