#!/bin/bash
# L74 pod setup (2026-10-13): repo snapshot + venv33 (royalesim 0.1.33 / royalegym 0.1.23) + the RoyaleSim fork build.
# Laptop first copies repo.tgz, overlay.tgz, data.tgz and this file to /workspace/in/, then on the pod:
#   nohup bash /workspace/in/pod_setup_l74.sh > /dev/null 2>&1 &      -> /workspace/setup.log, /workspace/SETUP_OK on success
# Re-runnable: finished steps are skipped.
set -Eeuo pipefail
exec >> /workspace/setup.log 2>&1
trap 'echo "SETUP FAILED line $LINENO (exit $?)"; touch /workspace/SETUP_FAILED' ERR
rm -f /workspace/SETUP_FAILED
IN=/workspace/in; CB=/workspace/clashbot; FORK_BASE=${FORK_BASE:-cacb700}
SRC=$CB/research/ext/Royale/RoyaleSim
echo "start $(date -u)"
if [ ! -d $CB/pipeline ]; then
  mkdir -p $CB
  for f in $IN/repo.tgz $IN/overlay.tgz $IN/data.tgz $IN/extra_*.tgz; do [ -e "$f" ] && tar xzf "$f" --no-same-owner -C $CB; done
fi
if [ ! -x /workspace/venv33/bin/python ]; then
  uv venv -q --seed -p /usr/bin/python3 /workspace/venv33
  uv pip install -q -p /workspace/venv33/bin/python royalesim==0.1.33 royalegym==0.1.23 'maturin>=1.15,<2' \
      numpy msgspec pytest psutil orjson pyyaml jsonschema
fi
ls /workspace/wheelhouse/royalegym-0.1.23-*.whl 2>/dev/null || \
  /workspace/venv33/bin/python -m pip download -q --no-deps royalegym==0.1.23 -d /workspace/wheelhouse
[ -e "$HOME/.cargo/env" ] || curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y -q --profile minimal
source "$HOME/.cargo/env"
if [ ! -d $SRC/.git ]; then
  mkdir -p "$(dirname $SRC)"
  git clone -q https://github.com/RoyaleGym/RoyaleSim.git $SRC
  git -C $SRC checkout -q -b clashbot $FORK_BASE
fi
cargo fetch --locked --manifest-path $SRC/crates/royalesim/Cargo.toml
[ -e $CB/research/ext/Royale-fork/build_manifest.json ] || \
  WHEELHOUSE=/workspace/wheelhouse BUILD_JOBS=24 bash $CB/scratchpad/gauntlet/L74/parity/build_fork.sh
echo "done $(date -u)"
touch /workspace/SETUP_OK
