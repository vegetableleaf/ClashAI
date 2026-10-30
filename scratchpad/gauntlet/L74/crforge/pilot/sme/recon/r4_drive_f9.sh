export R=/workspace/smeR3
S=$R/sme/recon/runR.sh; D=$R/data/f9; F=$D/frames
python3 - <<'EOF'
import json
on = [l for l in open('/workspace/smeR3/data/f9/on.jsonl') if json.loads(l).get('reader_hidden')]
ms = {json.loads(l)['match'] for l in on}
open('/workspace/smeR3/data/f9/on_hidden.jsonl', 'w').writelines(on)
open('/workspace/smeR3/data/f9/off_hidden.jsonl', 'w').writelines(l for l in open('/workspace/smeR3/data/f9/off.jsonl') if json.loads(l)['match'] in ms)
EOF
while ! grep -q V3DEV_DONE $R/runs/v3_drive.log 2>/dev/null; do sleep 60; done
ok() { grep -q "^done $1" $R/runs/$1.log 2>/dev/null; }
ok f9_gate || WORKERS=3 SME_THREADS=4 bash $S f9_gate gate $D/on.jsonl $F
ok f9_v3 || WORKERS=4 SME_THREADS=3 bash $S f9_v3 recon $D/off.jsonl $F
ok f9_gate_a0 || WORKERS=3 SME_THREADS=4 bash $S f9_gate_a0 gate $D/on_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
ok f9_v3_a0 || WORKERS=4 SME_THREADS=3 bash $S f9_v3_a0 recon $D/off_hidden.jsonl $F SME_HIDDEN_ASSIGN=0
echo F9_DONE >> $R/runs/f9_drive.log
