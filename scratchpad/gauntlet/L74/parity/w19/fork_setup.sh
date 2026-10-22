#!/bin/bash
# W19: Rust toolchain + maturin + the fin15 fork checkout on the pod, then a reference wheel build (warms the cargo cache for
# law rounds) and the cargo gate on fin15 (expect 1966 / 0 / 3).
#   setsid nohup bash fork_setup.sh > /workspace/w19/fork_setup.log 2>&1 < /dev/null &   -> /workspace/w19/FORK_OK
set -euo pipefail
B=/workspace/w19; VPY=/workspace/venvf15/bin/python
[ -x $HOME/.cargo/bin/cargo ] || curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
source $HOME/.cargo/env
$VPY -m pip -q install 'maturin>=1.15,<2.0'
cd $B
[ -d fork ] || git clone -q -b fin15 $B/in/clashbot36_fin15.bundle fork
cd fork; git log --oneline -1
"$VPY" tools/extract_arena.py > /dev/null && "$VPY" tools/extract_cards.py --vintage 2018 > /dev/null \
  && cp data/derived/cards-15.535.json data/derived/cards.json && "$VPY" tools/extract_globals.py > /dev/null && "$VPY" tools/stage_wheel_data.py
CARGO_TARGET_DIR=$B/target nice -n 10 "$VPY" -m maturin build --release -q -j 40 2>&1 | tail -3
ls -la $B/target/wheels/; sha256sum $B/target/wheels/*.whl
cd crates/royalesim
CARGO_TARGET_DIR=$B/gate nice -n 10 cargo test --profile gate --no-fail-fast -j 40 > $B/cargo_fin15.log 2>&1 || true
grep '^test result:' $B/cargo_fin15.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
touch $B/FORK_OK
