#!/usr/bin/env bash
# RECON-4: FRESH9 extraction on the laptop with 2 workers (shared machine): fresh_prep.sh's gate extraction (flags ON, 20 flags)
# into OUT/on, then the same raw logs with flags OFF (regen_fresh.sh v29 base) into OUT/off. LIST = fresh/FRESH9.tsv.
#   bash recon/r4_prep.sh fresh/FRESH9.tsv OUTDIR      (run from sme/)
set -euo pipefail
L=$(realpath "$1"); O=$(realpath -m "$2"); mkdir -p "$O/on" "$O/off"
H=$(cd "$(dirname "$0")/.." && pwd); R=/c/Users/benpe/ClashBot
T="C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3"
FL="SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=1 SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1 SME_TZ_REACH=1 SME_ZAP_DOT=1 SME_RASCAL_EDGE2=1 SME_OWN_PENDCAST=1 SME_ZD_BLDG=1 SME_SAMETICK_GEN=1 SME_GK_WALK=1 SME_ZD_SINGLE=1"
cd "$H/fresh"
if [ ! -s "$O/on/inputs_all.jsonl" ]; then
  env $FL bash regen_fresh.sh "$T" "$(cygpath -m "$L")" "$(cygpath -m "$O")/on/in_crlf.jsonl" 2 > "$O/on/regen.log" 2>&1
  tr -d '\r' < "$O/on/in_crlf.jsonl" > "$O/on/inputs_all.jsonl" && rm "$O/on/in_crlf.jsonl"
  grep '"rng_free": true' "$O/on/inputs_all.jsonl" > "$O/on/inputs_rngfree.jsonl" || true
  echo "$(date +%T) on done $(wc -l < "$O/on/inputs_all.jsonl") all, $(wc -l < "$O/on/inputs_rngfree.jsonl") rngfree" >> "$O/prep.log"
fi
cd "$R" && python -I scratchpad/gauntlet/L74/crforge/pilot/sme/live_frames.py --inputs "$O/on/inputs_rngfree.jsonl" \
  --live-dir scratchpad/gauntlet/L68/live_reader --out "$O/frames" > "$O/frames.log" 2>&1
echo "$(date +%T) frames done $(ls "$O/frames" | wc -l)" >> "$O/prep.log"
if [ ! -s "$O/off/inputs_all.jsonl" ]; then
  cd "$H/fresh"
  bash regen_fresh.sh "$T" "$(cygpath -m "$O")/on/inputs_rngfree.jsonl" "$(cygpath -m "$O")/off/in_crlf.jsonl" 2 > "$O/off/regen.log" 2>&1
  tr -d '\r' < "$O/off/in_crlf.jsonl" > "$O/off/inputs_all.jsonl" && rm "$O/off/in_crlf.jsonl"
  echo "$(date +%T) off done $(wc -l < "$O/off/inputs_all.jsonl")" >> "$O/prep.log"
fi
echo DONE >> "$O/prep.log"
