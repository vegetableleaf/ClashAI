#!/usr/bin/env bash
# RECON-7 FRESH12 driver (pod 33903, tree /workspace/smeR6, CPUs 226-237 = runR.sh's default). Runs after
#   python3 recon/r6_mk_sets.py /workspace/smeR6/data f12 :
#   gate (all, flags-on inputs) ; v3 (all, flags-off) ; RECON-5 = RECON_CYC=1 on the affected records ; RECON-5 + forms = RECON_CYC=1 RECON_FORM=1 on affected + form-residual records ;
#   RECON-5 + RECON-7 = RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80 on r7_pick.py's set (cycform + a BarbLog card + a v3 round-39 search) ;
#   ASSIGN-off guards on the reader-hidden records (gate, v3, r7). Every record outside a flagged set takes no flagged path: its row is the v3 row (RECON.md 12.7 / 14.4).
# Steps whose runs/<step>.log says done are skipped; a half-done step: delete runs/<step> first. Ends with F12_DONE in runs/f12_drive.log.
#   restart: cd /workspace/smeR6 && (nohup bash sme/recon/r7_drive_f12.sh > drive_f12.out 2>&1 < /dev/null &)
export R=/workspace/smeR6
S=$R/sme/recon/runR.sh; D=$R/data/f12
ok() { grep -q "^done $1" $R/runs/$1.log 2>/dev/null; }
ok f12_gate || WORKERS=3 SME_THREADS=4 bash $S f12_gate gate $D/on_u.jsonl $D/frames
ok f12_v3 || WORKERS=4 SME_THREADS=3 bash $S f12_v3 recon $D/off_u.jsonl $D/frames
ok f12_cyc_aff || WORKERS=4 SME_THREADS=3 bash $S f12_cyc_aff recon $D/off_aff.jsonl $D/frames RECON_CYC=1
ok f12_cycform || WORKERS=4 SME_THREADS=3 bash $S f12_cycform recon $D/off_cycform.jsonl $D/frames RECON_CYC=1 RECON_FORM=1
[ -s $D/off_r7.jsonl ] || python3 $R/sme/recon/r7_pick.py $D $R/runs/f12_v3/recon_results.jsonl
ok f12_r7 || WORKERS=4 SME_THREADS=3 bash $S f12_r7 recon $D/off_r7.jsonl $D/frames RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80
ok f12_gate_a0 || WORKERS=3 SME_THREADS=4 bash $S f12_gate_a0 gate $D/on_hidden_u.jsonl $D/frames SME_HIDDEN_ASSIGN=0
ok f12_v3_a0 || WORKERS=3 SME_THREADS=4 bash $S f12_v3_a0 recon $D/off_hidden_u.jsonl $D/frames SME_HIDDEN_ASSIGN=0
ok f12_r7_a0 || WORKERS=3 SME_THREADS=4 bash $S f12_r7_a0 recon $D/off_r7_hidden.jsonl $D/frames RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80 SME_HIDDEN_ASSIGN=0
echo F12_DONE >> $R/runs/f12_drive.log
