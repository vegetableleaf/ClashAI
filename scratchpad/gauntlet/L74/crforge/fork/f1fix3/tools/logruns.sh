#!/usr/bin/env bash
cd /workspace/pilot/f1fix
for m in 20261022_112113 20261027_204937; do rm -f /workspace/f1fix3/add_$m.log; ONLY=live_play_$m WORKERS=2 F1=1 bash runH.sh logrun_$m /workspace/crforge_cache/tables/16.402.22 /workspace/f1fix3/rg1/rg_lp3.jsonl /workspace/f1fix3/rg1/frames SME_LIB=/workspace/f1fix3/lib_ctl2/tickprobe/lib F1FIX3_LOG=/workspace/f1fix3/add_$m.log; done
for m in 20261023_022345 20261023_061811; do rm -f /workspace/f1fix3/add_$m.log; ONLY=live_play_$m WORKERS=2 bash runH.sh logrun_$m /workspace/crforge_cache/tables/16.402.22 /workspace/f1fix3/rg1/rg_ram.jsonl /workspace/f1fix3/rg1/frames SME_LIB=/workspace/f1fix3/lib_ctl2/tickprobe/lib F1FIX3_LOG=/workspace/f1fix3/add_$m.log; done
echo all done > /workspace/f1fix3/logruns.done
