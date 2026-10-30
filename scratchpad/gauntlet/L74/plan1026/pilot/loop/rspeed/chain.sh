#!/bin/bash
# ROLLOUT-SPEED 31892 chain (after rs_lf_on): OFF arm, graphs proof run, compares (graphs / F3 / F2'), bench sweep.
cd /workspace/rs || exit 1
. ./env.sh
O=/workspace/rs/out; LOG=$O/chain.log
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
cp -n cb/scratchpad/gauntlet/L68/rl/rs_lf_on/fast_msg_u0000_*.pkl in/pilot_u0000.pkl
lock "chain: OFF arm, graphs fastloop, compares, bench sweep (CPUs 6-33, GPU)"
if [ -z "$SKIP_FL" ]; then
say "OFF arm start"; bash fl.sh rs_lf_off2 6-33 "--producers 16 --matches 32 --threads 2 --devices cuda:0 --server eager" max_updates=1 screen_entries=1
say "OFF arm done: $(grep 'fastloop\] u' $O/rs_lf_off2/loop.log | tail -1)"
say "graphs arm start"; bash fl.sh rs_lf_graphs 6-33 "--producers 16 --matches 32 --threads 2 --devices cuda:0 --server graphs --local-forward" max_updates=3 screen_entries=1
say "graphs arm done: $(grep 'fastloop\] u\|Traceback\|capture' $O/rs_lf_graphs/loop.log | tail -5 | tr '\n' '|')"
fi
cmp() {   # NAME ENV... -- compare args
  local n=$1; shift; local envs=(); while [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  say "compare $n start"
  (cd cb && env "${envs[@]}" timeout 3000 taskset -c 6-13 $PY -u $L/compare.py ../in/pa3_G.pkl $O/cmp_$n.json --device cuda \
     --in-flight 8 --matches 8 --threads 4 --runtime-here "$@" > $O/cmp_$n.log 2>&1)
  say "compare $n rc $? $($PY -c "import json; d=json.load(open('$O/cmp_$n.json')); print(d['identical_matches'], '/', d['matches'], d['lp_maxdiff_before_divergence'], d.get('v_old'))" 2>&1 | tail -1)"
}
cmp graphs_lf X=1 -- --server graphs --local-forward
cmp cells1 FASTLOOP_CELLS1=1 -- --server eager --local-forward
cmp shards3 FASTLOOP_SHARDS=3 -- --server eager --local-forward
cmp all3 FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 -- --server graphs --local-forward
bench() {  # NAME "ENV..." bench args
  local n=$1 e=$2; shift 2
  say "bench $n start"
  (cd cb && env $e timeout 1200 taskset -c 6-33 $PY -u $L/bench.py ../in/pilot_u0000.pkl $O/bench_$n.json --warm 75 --seconds 150 "$@" > $O/bench_$n.log 2>&1)
  say "bench $n rc $? $($PY -c "import json; d=json.load(open('$O/bench_$n.json')); print(round(d['matches_per_h']), 'matches/h', d['gpu_util_mean'], 'stage/match', {k: round(v, 3) for k, v in d['stage_s_per_match'].items()})" 2>&1 | tail -1)"
}
B="--devices cuda:0 --local-forward"
bench e_16x32x2 "X=1" --producers 16 --matches 32 --threads 2 --server eager $B
bench g_16x32x2 "X=1" --producers 16 --matches 32 --threads 2 --server graphs $B
bench gc_16x32x2 "FASTLOOP_CELLS1=1" --producers 16 --matches 32 --threads 2 --server graphs $B
bench gcs_16x32x2 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 16 --matches 32 --threads 2 --server graphs $B
bench gcs_24x32x1 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 24 --matches 32 --threads 1 --server graphs $B
bench gcs_8x64x3 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 8 --matches 64 --threads 3 --server graphs $B
say "chain done"
unlock
