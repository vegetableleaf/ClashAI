#!/usr/bin/env bash
# p_gk.sh MODE(off|on) -- ENG-FIX5 (laptop): re-extract the SME_GK_WALK census records (all FRESH: fresh_prep.sh's 16 flags,
# = r9 OFF) plus SME_GK_WALK=1 for MODE on. Out: ex/gk_<mode>.jsonl
set -euo pipefail
H=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme; O=/c/Users/benpe/ClashBot/.foreman/scratch/engfix5/ex
cd $H/fresh; mode=$1
[ $mode = on ] && G=(SME_GK_WALK=1) || G=()
printf '{"match": "live_play_%s"}\n' 20261028_123045 20261028_135243 20261028_230352 20261029_003649 20261029_020956 > $O/gk.list.jsonl
env SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=1 SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 \
  SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1 SME_TZ_REACH=1 SME_ZAP_DOT=1 \
  SME_RASCAL_EDGE2=1 SME_OWN_PENDCAST=1 "${G[@]}" bash regen_fresh.sh C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3 \
  "$(cygpath -m $O/gk.list.jsonl)" "$(cygpath -m $O/gk_${mode}_crlf.jsonl)" 4 > $O/gk_$mode.log 2>&1
tr -d '\r' < $O/gk_${mode}_crlf.jsonl > $O/gk_${mode}.jsonl; rm $O/gk_${mode}_crlf.jsonl
wc -l $O/gk_${mode}.jsonl
