#!/usr/bin/env bash
# RECON-6 FRESH11 driver (pod 33903, tree /workspace/smeR5, CPUs 226-237 = runR.sh's default). Runs after recon/r6_mk_sets.py /workspace/smeR5/data f11 :
#   gate (all, flags-on inputs) ; v3 (all, flags-off) ; RECON-5 = RECON_CYC=1 on the affected records ; RECON-5 + forms = RECON_CYC=1 RECON_FORM=1 on affected + form-residual records ;
#   ASSIGN-off guards on the reader-hidden records (gate, v3, cycform). Every record outside a flagged set takes no flagged path: its row is the v3 row (RECON.md 12.7).
# Steps whose runs/<step>.log says done are skipped; a half-done step: delete runs/<step> first. Ends with F11_DONE in runs/f11_drive.log.
#   restart: cd /workspace/smeR5 && (nohup bash sme/recon/r6_drive_f11.sh > drive_f11.out 2>&1 < /dev/null &)
export R=/workspace/smeR5
S=$R/sme/recon/runR.sh; D=$R/data/f11
ok() { grep -q "^done $1" $R/runs/$1.log 2>/dev/null; }
ok f11_gate || WORKERS=3 SME_THREADS=4 bash $S f11_gate gate $D/on_u.jsonl $D/frames
ok f11_v3 || WORKERS=4 SME_THREADS=3 bash $S f11_v3 recon $D/off_u.jsonl $D/frames
ok f11_cyc_aff || WORKERS=4 SME_THREADS=3 bash $S f11_cyc_aff recon $D/off_aff.jsonl $D/frames RECON_CYC=1
ok f11_cycform || WORKERS=4 SME_THREADS=3 bash $S f11_cycform recon $D/off_cycform.jsonl $D/frames RECON_CYC=1 RECON_FORM=1
ok f11_gate_a0 || WORKERS=3 SME_THREADS=4 bash $S f11_gate_a0 gate $D/on_hidden_u.jsonl $D/frames SME_HIDDEN_ASSIGN=0
ok f11_v3_a0 || WORKERS=3 SME_THREADS=4 bash $S f11_v3_a0 recon $D/off_hidden_u.jsonl $D/frames SME_HIDDEN_ASSIGN=0
ok f11_cycform_a0 || WORKERS=3 SME_THREADS=4 bash $S f11_cycform_a0 recon $D/off_cycform_hidden.jsonl $D/frames RECON_CYC=1 RECON_FORM=1 SME_HIDDEN_ASSIGN=0
echo F11_DONE >> $R/runs/f11_drive.log
