#!/usr/bin/env bash
# r2b_drive.sh -- RECON-2 second pass on 33903, CPUs 226-237: generator v2 (recon.py: opponent-spell +-500 grid, repress) in its
# own tree /workspace/smeR2 (the baseline r2_* runs stay pre-v2). Waits for r2_drive's R2_DONE, then:
#  r2v2_a  recon, flags off, the records r2_fail + r2_rest left not strictly exact   (best number first)
#  r2v2_a_abl  ablate.py on r2v2_a
#  r2v2_a0 recon, flags off, reader_hidden records, SME_HIDDEN_ASSIGN=0              (ASSIGN guard)
#  r2v2_b  recon, flags off, the other records (a v2 search must not lose an exact match)
# Restart = rerun; steps whose log says done are skipped; a half-done step: delete runs/<step>* in smeR2 first.
A=/workspace/smeR; export R=/workspace/smeR2; D=$A/data/r2; F=$A/data/allframes; S=$R/sme/recon/runR.sh
while ! grep -q R2_DONE $A/runs/r2_drive.log; do sleep 60; done
mkdir -p $R/runs
python3 $R/sme/recon/r2b_split.py $A/runs $D > $R/runs/split.log
ok() { grep -q "^done $1" $R/runs/$1.log 2>/dev/null; }
ok r2v2_a || WORKERS=4 SME_THREADS=3 bash $S r2v2_a recon $D/off_v2a.jsonl $F
ok r2v2_a_abl || WORKERS=4 SME_THREADS=3 RARGS="--runs $R/runs/r2v2_a" bash $S r2v2_a_abl ablate $D/off_v2a.jsonl $F
ok r2v2_a0 || WORKERS=4 SME_THREADS=3 bash $S r2v2_a0 recon $D/off_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
ok r2v2_b || WORKERS=4 SME_THREADS=3 bash $S r2v2_b recon $D/off_v2b.jsonl $F
echo R2B_DONE >> $R/runs/r2b_drive.log
