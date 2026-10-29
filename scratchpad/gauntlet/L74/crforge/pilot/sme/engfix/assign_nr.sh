#!/usr/bin/env bash
# assign_nr.sh -- pod 32657: SME_HIDDEN_ASSIGN 0 vs 1 on every record with a reader_hidden window (sme11g, lib 5e8089a4)
cd /workspace/pilot/engfix2 || exit 1
L=/workspace/crforge_main/5e8089a4/tickprobe/lib
run() { WORKERS=3 taskset -c 28-53 bash runG.sh "$1" "$2" "$3" "$4" SME_LIB=$L SME_HIDDEN_ASSIGN=$5; }
for a in 0 1; do
  run EFA_dev_$a /workspace/crforge_cache/tables/16.402.22 /workspace/pilot/engfix2/h_dev.jsonl /workspace/pilot/sme_live/frames2 $a
  run EFA_f1_$a /workspace/crforge_cache/tables/16.635.3 /workspace/pilot/engfix2/h_fresh1.jsonl /workspace/pilot/fresh/fresh1/frames $a
  grep 083923 h_f.jsonl > h_f2.jsonl; grep -v 083923 h_f.jsonl > h_f4.jsonl
  run EFA_f2_$a /workspace/crforge_cache/tables/16.635.3 /workspace/pilot/engfix2/h_f2.jsonl /workspace/pilot/fresh2/frames $a
  run EFA_f4_$a /workspace/crforge_cache/tables/16.635.3 /workspace/pilot/engfix2/h_f4.jsonl /workspace/pilot/fresh4/frames $a
done
for r in dev f1 f2 f4; do for a in 0 1; do
  python3 -c "import json,sys
for l in open('runs/EFA_${r}_$a/results.jsonl'):
    x=json.loads(l); print('EFA_${r}_$a', x['match'][10:], x['counts'], x['first_div'], 'missed', x.get('plants',{}).get('missed'))"
done; done
echo ASSIGN_NR_DONE
