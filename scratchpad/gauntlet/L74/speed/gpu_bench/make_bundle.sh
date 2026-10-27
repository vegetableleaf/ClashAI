#!/bin/bash
# Build gpu_bench.tgz (run from the repo root): pipeline/ at HEAD + the S4 bench scripts + the live row fixture + the
# CLXIII checkpoint (icebow/data: NEVER committed -- the tarball is a build artifact, kept out of git).
#   bash scratchpad/gauntlet/L74/speed/gpu_bench/make_bundle.sh /path/to/gpu_bench.tgz
set -euo pipefail
OUT=${1:?output tarball path}
T=$(mktemp -d); B=$T/gpu_bench; mkdir -p "$B"
git archive HEAD pipeline | tar x -C "$B"
S=scratchpad/gauntlet/L74/speed
mkdir -p "$B/$S/results" "$B/icebow/data/models/ICEBOW"
cp $S/s4_bench.py $S/model_scale.py $S/shape_probe.py "$B/$S/"
cp $S/gpu_bench/bench_gpu.sh "$B/"
cp $S/results/live_batch1.pt "$B/$S/results/"
cp pipeline/policy_server.py pipeline/batched_rollout.py pipeline/fast_obs.py "$B/pipeline/"   # working-tree versions
cp pipeline/tests/test_fast_obs.py "$B/pipeline/tests/"
cp icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt "$B/icebow/data/models/ICEBOW/"
(cd "$B" && sha256sum icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt > MANIFEST.sha256)
tar czf "$OUT" --owner=0 --group=0 -C "$T" gpu_bench
rm -rf "$T"
ls -la "$OUT"
