#!/usr/bin/env bash
# RECON-7 inertness: the RECON-7 code with NO new key (RECON_LATE / RECON_ROUNDS absent) on 10 FRESH9 + 8 dev records must give the stored RECON-5 + forms rows
# (counts, first divergence, edits) byte for byte; then the same records with RECON_LATE=1 RECON_ROUNDS=80 (a record without a BarbLog card must not change).
export R=/workspace/smeR6
S=$R/sme/recon/runR.sh; D=/workspace/smeR4/data
F9=$(python3 /workspace/smeR5/pick.py /workspace/smeR4/runs/f9_cyc_aff/recon_results.jsonl 10)
DV=$(python3 /workspace/smeR5/pick.py /workspace/smeR4/runs/d49_cyc2/recon_results.jsonl 8)
echo $F9 $DV
(ONLY=$F9 WORKERS=3 SME_THREADS=2 bash $S r7_in_f9 recon $D/f9/off.jsonl $D/f9/frames RECON_CYC=1 RECON_FORM=1 &
ONLY=$DV WORKERS=3 SME_THREADS=2 bash $S r7_in_dev recon $D/dev49.jsonl $D/pa_frames RECON_CYC=1 RECON_FORM=1 &
wait)
(ONLY=$F9 WORKERS=3 SME_THREADS=2 bash $S r7_inL_f9 recon $D/f9/off.jsonl $D/f9/frames RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80 &
ONLY=$DV WORKERS=3 SME_THREADS=2 bash $S r7_inL_dev recon $D/dev49.jsonl $D/pa_frames RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80 &
wait)
echo INERT_DONE >> $R/runs/r7_inert.log
