#!/bin/bash
# sync_tree.sh PATHS... -- ship the working-tree (or REF=HEAD) version of the given repo paths into pod 32657
# /workspace/cf3/cfh (a hard-link copy of cfp: extracted files are NEW inodes, LF endings), then print their shas.
#   REF=HEAD sync_tree.sh pipeline scratchpad/gauntlet/L74/plan1026/cf      or      sync_tree.sh pipeline/cf_credit.py
set -e
cd /c/Users/benpe/ClashBot
SSH="ssh -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -p 32657 root@157.157.221.29"
if [ -n "$REF" ]; then SRC="git archive $REF $*"; else SRC="tar -c $*"; fi
$SRC | $SSH 'cd /workspace/cf3/cfh && tar -xv --no-same-owner | grep -E "[.](py|yaml|sh)$" | xargs sed -i "s/\r$//"'
$SSH 'cd /workspace/cf3/cfh && sha256sum pipeline/cf_credit.py pipeline/rl_royale.py pipeline/e1_eval.py pipeline/search_s0.py | cut -c1-16,65-'
