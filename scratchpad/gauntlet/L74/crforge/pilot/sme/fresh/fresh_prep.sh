#!/usr/bin/env bash
# fresh_prep.sh LIST.tsv OUTDIR -- ENG-SME (laptop): a frozen FRESH list -> SME inputs + frames, with the extractor flags
# frozen for FRESH3+ (FRESH2 used it with SME_ZAP_CHAIN1=0, the default before d4c7b44): regen_fresh.sh's v29 set + SME_HIDDEN_GEN=1 (v30, SME-F1FIX) + SME_TOWER_ZAP=1 (ENG-SME) + SME_ZAP_CHAIN1=1 (ENG-SME fix 1)
# + ENG-FIX (FRESH4+, SME.md section 8; ENG-FIX_2b: 0 regressions on dev/FRESH1/2/3): SME_TOMB_HERO SME_BB_RISE SME_OWN_SPAWN SME_OWN_NEARDEAD; + SME_OWN_BODYPT (FRESH5+, ENG-FIX_5: 0 regressions); + SME_SPELL_KING SME_HIDDEN_CHILD (FRESH6+, ENG-FIX2_1 r6: 134 changed, 1 fixed, 0 regressions), + SME_NEAR_BIGGER2 (FRESH6+, ENG-FIX3: FRESH1-5 2 changed records, 101018 fixed, 171948 same; dev 0), + SME_ZAP_DEAD (FRESH7+, ENG-FIX4 r7: ON field gate 1 changed record of 312 (FRESH5 021310), which goes 1660 + 105 div -> 1765 / 1765 exact (EF3_zd_1, byte-identical input)),
# tables 16.635.3 (build 160635001). Writes OUTDIR/{inputs_all.jsonl, inputs_rngfree.jsonl, frames/, live_sha256.txt, prep.txt}
# (LF line endings). The extractor and tables shas go to prep.txt for the freeze file.
set -euo pipefail
L=$(realpath "$1"); O=$(realpath -m "$2"); mkdir -p "$O"
H=$(cd "$(dirname "$0")" && pwd); R=/c/Users/benpe/ClashBot; PY=$R/icebow/.venv/Scripts/python.exe
T="C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3"
cd "$H" && SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=${SME_ZAP_CHAIN1:-1} SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1 bash regen_fresh.sh "$T" "$(cygpath -m "$L")" "$(cygpath -m "$O")/inputs_crlf.jsonl" 4 > "$O/regen.log" 2>&1
tr -d '\r' < "$O/inputs_crlf.jsonl" > "$O/inputs_all.jsonl" && rm "$O/inputs_crlf.jsonl"
grep '"rng_free": true' "$O/inputs_all.jsonl" > "$O/inputs_rngfree.jsonl" || true
cd $R && python -I scratchpad/gauntlet/L74/crforge/pilot/sme/live_frames.py --inputs "$O/inputs_rngfree.jsonl" \
  --live-dir scratchpad/gauntlet/L68/live_reader --out "$O/frames" > "$O/frames.log" 2>&1
for m in $(grep -v '^#' "$L" | cut -f1); do sha256sum scratchpad/gauntlet/L68/live_reader/$m.jsonl | sed 's/ \*/  /'; done > "$O/live_sha256.txt"
X=scratchpad/gauntlet/L74/crforge/pilot
{ echo "list $(sha256sum "$L" | cut -c1-64) $(grep -vc '^#' "$L") matches"
  echo "repo HEAD $(git rev-parse HEAD)"
  for f in $X/extract/extract.py $X/sme/mech_rules.py $X/sme/bp_rules.py $X/sme/live_frames.py $X/sme/regen_inputs.py \
           $X/sme/fresh/regen_fresh.py $X/sme/fresh/regen_fresh.sh $X/sme/bp9/order_inputs.py $X/sme/sme_live.py \
           scratchpad/gauntlet/L74/parity/fights.py scratchpad/gauntlet/L74/parity/core.py; do
    echo "file $f $(git hash-object $f) $(git diff --quiet HEAD -- $f && echo committed || echo DIRTY)"; done
  echo "tables $T $(cd "$T" && cat $(ls) | sha256sum | cut -c1-64)"
  echo "flags regen_fresh.sh + SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 SME_ZAP_CHAIN1=${SME_ZAP_CHAIN1:-1} SME_TOMB_HERO=1 SME_BB_RISE=1 SME_OWN_SPAWN=1 SME_OWN_NEARDEAD=1 SME_OWN_BODYPT=1 SME_SPELL_KING=1 SME_HIDDEN_CHILD=1 SME_NEAR_BIGGER2=1 SME_ZAP_DEAD=1"
  echo "inputs_all $(sha256sum < "$O/inputs_all.jsonl" | cut -c1-64) $(wc -l < "$O/inputs_all.jsonl")"
  echo "inputs_rngfree $(sha256sum < "$O/inputs_rngfree.jsonl" | cut -c1-64) $(wc -l < "$O/inputs_rngfree.jsonl")"
  echo "frames $(cd "$O/frames" && cat $(ls) | sha256sum | cut -c1-64) $(ls "$O/frames" | wc -l) files"
  echo "skips $(grep -c '^SKIP' "$O/regen.log" || true)"; grep '^SKIP' "$O/regen.log" || true
} > "$O/prep.txt"
cat "$O/prep.txt"
