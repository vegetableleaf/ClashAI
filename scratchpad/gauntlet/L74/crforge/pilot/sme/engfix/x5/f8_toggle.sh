#!/usr/bin/env bash
# f8_toggle.sh -- ENG-FIX5 (laptop): FRESH8 extracted with fresh_prep.sh's 19 flags minus ONE of the seven new ones (each in
# turn), to count each flag's FRESH8 firings (records that differ from the frozen inputs). Out: ex/f8_minus_<FLAG>.jsonl
set -uo pipefail
H=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme; O=/c/Users/benpe/ClashBot/.foreman/scratch/engfix5/ex
ALL="SME_HIDDEN_GEN SME_TOWER_ZAP SME_ZAP_CHAIN1 SME_TOMB_HERO SME_BB_RISE SME_OWN_SPAWN SME_OWN_NEARDEAD SME_OWN_BODYPT SME_SPELL_KING SME_HIDDEN_CHILD SME_NEAR_BIGGER2 SME_ZAP_DEAD SME_TZ_REACH SME_ZAP_DOT SME_RASCAL_EDGE2 SME_OWN_PENDCAST SME_ZD_BLDG SME_SAMETICK_GEN SME_GK_WALK"
cd $H/fresh
for drop in SME_TZ_REACH SME_ZAP_DOT SME_RASCAL_EDGE2 SME_OWN_PENDCAST SME_ZD_BLDG SME_SAMETICK_GEN SME_GK_WALK; do
  fl=(); for f in $ALL; do [ $f = $drop ] || fl+=($f=1); done
  env "${fl[@]}" bash regen_fresh.sh C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3 \
    "$(cygpath -m $H/fresh/FRESH8.tsv)" "$(cygpath -m $O/f8_minus_${drop}_crlf.jsonl)" 4 > $O/f8_minus_$drop.log 2>&1
  tr -d '\r' < $O/f8_minus_${drop}_crlf.jsonl > $O/f8_minus_$drop.jsonl; rm -f $O/f8_minus_${drop}_crlf.jsonl
  echo "done $drop $(wc -l < $O/f8_minus_$drop.jsonl)"
done
echo TOGGLE_DONE
