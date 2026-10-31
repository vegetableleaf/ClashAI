#!/bin/bash
# ROLLOUT-SPEED after final.sh: (1) compare.py under MPS (graphs + local-forward + CELLS1 + SHARDS 3) = exactness under
# MPS, (2) fastloop.start_mps smoke (the --mps flag's function: daemon up, a CUDA process joins, quit).
cd /workspace/rs || exit 1
. ./env.sh
O=/workspace/rs/out; LOG=$O/chain.log
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
until grep -q "final done" $LOG; do sleep 10; done
until ( set -o noclobber; echo "ROLLOUT-SPEED $(date -u +%FT%TZ) final2: compare under MPS + start_mps smoke (~20 min, incl. a steady-state fastloop run)" > /workspace/BENCH_LOCK ) 2>/dev/null; do sleep 15; done
rm -f cb/$L/fastloop.py && cp in/fastloop.py cb/$L/fastloop.py
(export CUDA_MPS_PIPE_DIRECTORY=/workspace/rs/mps_pipe CUDA_MPS_LOG_DIRECTORY=/workspace/rs/mps_log
 nvidia-cuda-mps-control -d
 cd cb && FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 timeout 1500 taskset -c 6-13 $PY -u $L/compare.py ../in/pa3_G.pkl $O/cmp_mps_all3.json \
   --device cuda --in-flight 8 --matches 8 --threads 4 --runtime-here --server graphs --local-forward > $O/cmp_mps_all3.log 2>&1
 echo quit | nvidia-cuda-mps-control)
say "compare mps_all3 rc $? $($PY -c "import json; d=json.load(open('$O/cmp_mps_all3.json')); print(d['identical_matches'], '/', d['matches'], d['lp_maxdiff_before_divergence'], d.get('v_old'))" 2>&1 | tail -1)"
(cd cb/$L && timeout 120 $PY -c "
import subprocess, torch, fastloop
fastloop.start_mps('/workspace/rs/mps2')
x = torch.ones(8, device='cuda').sum().item()
q = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name', '--format=csv,noheader'], capture_output=True, text=True).stdout
print('start_mps smoke: cuda sum', x, '| mps-server listed:', 'mps' in q.lower(), '|', q.strip().replace(chr(10), '; '))
" > $O/start_mps_smoke.log 2>&1)
say "start_mps smoke rc $? $(tail -1 $O/start_mps_smoke.log); daemons left: $(pgrep -c nvidia-cuda-mps)"
say "steady-state run (rs_steady: critic_warmup_updates=1, full stack, fastloop --mps) start"
FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 bash fl.sh rs_steady 6-33 "--producers 32 --matches 16 --threads 1 --devices cuda:0 --server graphs --local-forward --overlap 1 --mps /workspace/rs/mps5" \
  max_updates=5 split_attn=true trunk_graph=256 screen_entries=1 critic_warmup_updates=1
say "steady done: $(grep 'fastloop\] u\|Traceback\|Error' $O/rs_steady/loop.log | tail -6 | tr '\n' '|')"
say "final2 done"
unlock
