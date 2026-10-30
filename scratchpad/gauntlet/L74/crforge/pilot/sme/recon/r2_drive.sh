#!/usr/bin/env bash
# r2_drive.sh -- RECON-2 (10-30) pod 33903 queue, CPUs 226-237. Inputs in $R/data/r2/ (laptop build_sets.py: flags-off /
# flags-on re-extractions of the 151 scored strict-fresh FRESH2-8 matches), frames = $R/data/allframes (links to
# data/freshN/frames). Steps are skipped when their run log says done (restart = rerun this script):
#  1 r2_fail   recon search, flags off, the 37 not-strictly-exact records          (item 2)
#  2 r2_abl    ablate.py on r2_fail's kept adds                                      (item 2 precision)
#  3 r2_rest   recon search, flags off, the other 114                                (item 3)
#  4 r2_gate   gate (sme_live), flags on, all 151                                    (item 3 hand-rule pipeline)
#  5 r2_*_a0   both pipelines on the reader_hidden records with SME_HIDDEN_ASSIGN=0  (ASSIGN guard)
R=/workspace/smeR; D=$R/data/r2; F=$R/data/allframes; S=$R/sme/recon/runR.sh
mkdir -p $F; for n in 2 3 4 5 6 7 8; do for f in $R/data/fresh$n/frames/*.jsonl; do ln -sf $f $F/; done; done
ok() { grep -q "^done $1" $R/runs/$1.log 2>/dev/null; }
ok r2_fail || WORKERS=4 SME_THREADS=3 bash $S r2_fail recon $D/off_fail.jsonl $F
ok r2_abl || WORKERS=4 SME_THREADS=3 RARGS="--runs $R/runs/r2_fail" bash $S r2_abl ablate $D/off_fail.jsonl $F
ok r2_rest || WORKERS=4 SME_THREADS=3 bash $S r2_rest recon $D/off_rest.jsonl $F
ok r2_gate || WORKERS=3 SME_THREADS=4 bash $S r2_gate gate $D/on_all.jsonl $F
ok r2_gate_a0 || WORKERS=3 SME_THREADS=4 bash $S r2_gate_a0 gate $D/on_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
ok r2_recon_a0 || WORKERS=4 SME_THREADS=3 bash $S r2_recon_a0 recon $D/off_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
echo R2_DONE >> $R/runs/r2_drive.log
