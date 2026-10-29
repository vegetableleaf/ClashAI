#!/usr/bin/env bash
# p_gen.sh MODE(off|on) -- ENG-FIX5 (laptop): re-extract the SME_SAMETICK_GEN census records with r9's OFF flags (dev: dev set,
# tables 16.402.22; FRESH4 / FRESH6: fresh_prep.sh's 16 flags), plus SME_SAMETICK_GEN=1 for MODE on. Out: ex/gen_<set>_<mode>.jsonl
set -euo pipefail
H=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme; O=/c/Users/benpe/ClashBot/.foreman/scratch/engfix5/ex
mkdir -p $O; cd $H/fresh; mode=$1
[ $mode = on ] && G=(SME_SAMETICK_GEN=1) || G=()
printf '{"match": "live_play_%s"}\n' 20261026_090406 20261026_154319 20261026_162012 20261026_175456 > $O/gen_dev.list.jsonl
printf '{"match": "live_play_%s"}\n' 20261028_144727 20261028_152022 20261028_235316 20261029_031310 > $O/gen_fresh.list.jsonl
env SME_HIDDEN_GEN=1 SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_ZAP_DEAD=1 SME_TZ_REACH=1 SME_ZAP_DOT=1 \
  SME_RASCAL_EDGE2=1 SME_OWN_PENDCAST=1 "${G[@]}" bash regen_fresh.sh C:/Users/benpe/crforge_eval/cache/tables/16.402.22 \
  "$(cygpath -m $O/gen_dev.list.jsonl)" "$(cygpath -m $O/gen_dev_${mode}_crlf.jsonl)" 4 > $O/gen_dev_$mode.log 2>&1
env SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=1 SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 \
  SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1 SME_TZ_REACH=1 SME_ZAP_DOT=1 \
  SME_RASCAL_EDGE2=1 SME_OWN_PENDCAST=1 "${G[@]}" bash regen_fresh.sh C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3 \
  "$(cygpath -m $O/gen_fresh.list.jsonl)" "$(cygpath -m $O/gen_fresh_${mode}_crlf.jsonl)" 4 > $O/gen_fresh_$mode.log 2>&1
for s in dev fresh; do tr -d '\r' < $O/gen_${s}_${mode}_crlf.jsonl > $O/gen_${s}_${mode}.jsonl; rm $O/gen_${s}_${mode}_crlf.jsonl; done
wc -l $O/gen_*_${mode}.jsonl
