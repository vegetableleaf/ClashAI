export R=/workspace/smeR3
S=$R/sme/recon/runR.sh; F=/workspace/smeR/data/allframes
WORKERS=4 SME_THREADS=3 bash $S v3_dev recon $R/data/off_all151.jsonl $F
WORKERS=4 SME_THREADS=3 bash $S v3_a0 recon /workspace/smeR/data/r2/off_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
echo V3DEV_DONE >> $R/runs/v3_drive.log
