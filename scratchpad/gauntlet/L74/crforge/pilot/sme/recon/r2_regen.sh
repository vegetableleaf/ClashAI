#!/usr/bin/env bash
# RECON-2: re-extract the RNG-free records of FRESH2-8 with the current extractor, flags OFF (regen_fresh.sh = v29 base)
# and flags ON (fresh_prep.sh's 20 SME_* flags), tables 16.635.3, 2 workers (shared laptop).
set -u
X=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme; O=/c/Users/benpe/ClashBot/.foreman/scratch/recon2
T="C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3"
FL="SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=1 SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1 SME_TZ_REACH=1 SME_ZAP_DOT=1 SME_RASCAL_EDGE2=1 SME_OWN_PENDCAST=1 SME_ZD_BLDG=1 SME_SAMETICK_GEN=1 SME_GK_WALK=1 SME_ZD_SINGLE=1"
cd $X/fresh
for n in 2 3 4 5 6 7 8; do
  if [ $n -le 3 ]; then L=/c/Users/benpe/ClashBot/.foreman/scratch/a2/sme/fresh$n/inputs_rngfree.jsonl; else L=$X/engfix/fresh$n/inputs_rngfree.jsonl; fi
  for mode in off on; do
    [ -s $O/$mode/f$n.jsonl ] && continue
    if [ $mode = on ]; then E="env $FL"; else E=env; fi
    $E bash regen_fresh.sh "$T" "$(cygpath -m $L)" "$(cygpath -m $O/$mode)/f${n}_crlf.jsonl" 2 > $O/$mode/f$n.log 2>&1
    tr -d '\r' < $O/$mode/f${n}_crlf.jsonl > $O/$mode/f$n.jsonl && rm $O/$mode/f${n}_crlf.jsonl
    echo "$(date +%T) f$n $mode $(wc -l < $O/$mode/f$n.jsonl)" >> $O/regen_all.log
  done
done
echo DONE >> $O/regen_all.log
