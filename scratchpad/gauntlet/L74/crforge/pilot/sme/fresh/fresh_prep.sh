#!/usr/bin/env bash
# fresh_prep.sh LIST.tsv OUTDIR -- ENG-SME (laptop): a frozen FRESH list -> SME inputs + frames, with the extractor flags
# frozen for FRESH2 (2026-10-28): regen_fresh.sh's v29 set + SME_HIDDEN_GEN=1 (v30, SME-F1FIX) + SME_TOWER_ZAP=1 (ENG-SME),
# tables 16.635.3 (build 160635001). Writes OUTDIR/{inputs_all.jsonl, inputs_rngfree.jsonl, frames/, live_sha256.txt, prep.txt}
# (LF line endings). The extractor and tables shas go to prep.txt for the freeze file.
set -euo pipefail
L=$(realpath "$1"); O=$(realpath -m "$2"); mkdir -p "$O"
H=$(cd "$(dirname "$0")" && pwd); R=/c/Users/benpe/ClashBot; PY=$R/icebow/.venv/Scripts/python.exe
T="C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3"
cd "$H" && SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1 bash regen_fresh.sh "$T" "$(cygpath -m "$L")" "$(cygpath -m "$O")/inputs_crlf.jsonl" 4 > "$O/regen.log" 2>&1
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
  echo "flags regen_fresh.sh + SME_HIDDEN_GEN=1 SME_TOWER_ZAP=1"
  echo "inputs_all $(sha256sum < "$O/inputs_all.jsonl" | cut -c1-64) $(wc -l < "$O/inputs_all.jsonl")"
  echo "inputs_rngfree $(sha256sum < "$O/inputs_rngfree.jsonl" | cut -c1-64) $(wc -l < "$O/inputs_rngfree.jsonl")"
  echo "frames $(cd "$O/frames" && cat $(ls) | sha256sum | cut -c1-64) $(ls "$O/frames" | wc -l) files"
  echo "skips $(grep -c '^SKIP' "$O/regen.log" || true)"; grep '^SKIP' "$O/regen.log" || true
} > "$O/prep.txt"
cat "$O/prep.txt"
