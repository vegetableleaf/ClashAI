#!/usr/bin/env bash
# S3 phase 2 on pod 32657 (/workspace/cfspeed), after grid2.sh: crforge's VectorEnv as shipped (Java and through its own
# Python package), the observation cost (cf_obs.py) and the full-loop prototype (cf_loop.py). CPU only.
# Run: nohup ./phase2.sh <grid2 pid> > runs/phase2.log 2>&1 &
set -uo pipefail
cd /workspace/cfspeed
while kill -0 "$1" 2>/dev/null; do sleep 5; done
L=crforge/env/build/install/env/lib T=crforge_cache/tables/16.402.22 P=/workspace/venvf15/bin/python
env_run() {  # label envs threads decisionTicks warmSteps minMatches xmx
  java -Xmx"$7" -XX:ActiveProcessorCount="$3" -cp "$L/*:build" CfSpeed env $T decks.tsv "$2" "$3" "$4" 0.3 "$5" "$6" \
    > "runs/$1.json" 2> "runs/$1.err"; cat "runs/$1.json"
}
env_run v_768x48_d10 768 48 10 1500 6000 8g
env_run v_768x48_d5  768 48  5 3000 6000 8g
env_run v_16x1_d10    16  1 10 6000  200 2g
# crforge-env's own Python benchmark (JPype, its mirror decks, random open actions in numpy), decisions of 10 ticks
PYTHONPATH=/workspace/cfspeed/pylib:/workspace/cfspeed/crforge/python $P -m crforge_env.bench --install crforge/env/build/install/env \
  --tables $T --engine ladder --counts 64 768 --threads 48 --steps 400 --repeats 3 --decision-ticks 10 \
  --json runs/py_bench_t48.json > runs/py_bench_t48.out 2>&1; cat runs/py_bench_t48.out
PYTHONPATH=/workspace/cfspeed/pylib:/workspace/cfspeed/crforge/python $P -m crforge_env.bench --install crforge/env/build/install/env \
  --tables $T --engine ladder --counts 1 16 --threads 1 --steps 2000 --repeats 3 --decision-ticks 10 \
  --json runs/py_bench_t1.json > runs/py_bench_t1.out 2>&1; cat runs/py_bench_t1.out
# our observation: P1 / P2 / P3 + identity
$P -I cf_obs.py --envs 16 --steps 600 --warm-steps 600 --out runs/obs.json > runs/obs.out 2>&1; tail -5 runs/obs.out
# full loop, CPU side (48 Java threads in all + the Python server thread)
$P -I cf_loop.py --envs 2048 --cohorts 2 --threads 24 --warm 60 --seconds 90 --out runs/loop_n2048_c2_t24.json
$P -I cf_loop.py --envs 512  --cohorts 2 --threads 24 --warm 60 --seconds 90 --out runs/loop_n512_c2_t24.json
$P -I cf_loop.py --envs 2048 --cohorts 1 --threads 48 --warm 60 --seconds 90 --out runs/loop_n2048_c1_t48.json
$P -I cf_loop.py --envs 4096 --cohorts 2 --threads 24 --warm 60 --seconds 90 --out runs/loop_n4096_c2_t24.json
echo PHASE2_DONE
