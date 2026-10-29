#!/bin/bash
# sync_tree.sh PATHS... -- ship the working-tree (or REF=HEAD) version of the given repo paths into a tree on pod 32657
# (/workspace/cf3/$TREE_NAME, default cfh: a hard-link copy of cfp, so extracted files are NEW inodes; LF endings), print shas.
#   REF=HEAD sync_tree.sh pipeline scratchpad/gauntlet/L74/plan1026/cf      or      TREE_NAME=cfh2 sync_tree.sh pipeline/cf_credit.py
# A tree a run is using must not be re-synced mid-run (a restarted actor would import the new file): make a copy
# (`cp -al cfh cfh2`) and run the next experiment from it.
set -e
cd /c/Users/benpe/ClashBot
T=${TREE_NAME:-cfh}
SSH="ssh -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -p 32657 root@157.157.221.29"
if [ -n "$REF" ]; then SRC="git archive $REF $*"; else SRC="tar -c $*"; fi
$SRC | $SSH "cd /workspace/cf3/$T && tar -xv --no-same-owner | grep -E '[.](py|yaml|sh|json)\$' | xargs sed -i 's/\\r\$//'"
$SSH "cd /workspace/cf3/$T && sha256sum pipeline/cf_credit.py pipeline/rl_royale.py pipeline/e1_eval.py pipeline/search_s0.py | cut -c1-16,65-"
