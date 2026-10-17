#!/bin/bash
# L74 troops pod setup (10-17): checkout /workspace/cb_tt (repo_tt.tgz + data_rl.tgz + ckpts.tgz, sha-checked) and the
# fork36-linux runtime /workspace/venvf36 = the 10-12 venv33 pins (constraints_1012.txt) + torch 2.11.0+cu128 +
# royalegym 0.1.23 (PyPI) + the ClashBot RoyaleSim fork wheel (branch clashbot36, bc2bf9d).
#   BUILD=1 bash setup_troops.sh   build the wheel here (parity/night1016/fork_build.sh) and freeze the manifest
#   FREEZE=1 bash setup_troops.sh  wheel already in /workspace/in (built by hand): install + freeze the manifest
#   bash setup_troops.sh           use /workspace/in/royalesim-*.whl + the shipped manifest (a second pod: same bytes)
#   -> /workspace/troops/setup.log, /workspace/troops/SETUP_OK (activate() under ROYALE_RUNTIME=fork36-linux passed)
set -Eeuo pipefail
mkdir -p /workspace/troops /workspace/results; exec >> /workspace/troops/setup.log 2>&1
trap 'echo "SETUP FAILED line $LINENO (exit $?)"; touch /workspace/troops/SETUP_FAILED' ERR
rm -f /workspace/troops/SETUP_FAILED /workspace/troops/SETUP_OK
IN=/workspace/in; CB=/workspace/cb_tt; V=/workspace/venvf36; PY=$V/bin/python; TT=scratchpad/gauntlet/L74/troops
export UV_HTTP_TIMEOUT=600
echo "start $(date -u)"
if [ ! -d $CB/pipeline ]; then
  mkdir -p $CB
  tar xzf $IN/repo_tt.tgz --no-same-owner -C $CB
  tar xzf $IN/data_rl.tgz --no-same-owner -C $CB && (cd $CB && sha256sum -c --quiet $IN/data.sha) && echo DATA_OK
  tar xzf $IN/ckpts.tgz --no-same-owner -C $CB && (cd $CB && sha256sum -c $IN/ckpts.sha)
fi
if [ -n "${BUILD:-}" ]; then
  BRANCH=clashbot36 BUNDLE=$IN/clashbot36_bc2bf9d.bundle FORKDIR=/workspace/fork36 \
    bash $CB/scratchpad/gauntlet/L74/parity/night1016/fork_build.sh f36
  W=$(ls /workspace/fork36/crates/royalesim/target/wheels/*.whl | head -1); cp $W $IN/
fi
W=$(ls $IN/royalesim-*.whl | head -1); echo "wheel $W $(sha256sum $W | cut -c1-16)"
[ -x $PY ] || uv venv -q --seed -p /usr/bin/python3 $V
uv pip install -q -p $PY -c $CB/$TT/constraints_1012.txt royalegym==0.1.23 'maturin>=1.15,<2' numpy msgspec pytest \
    psutil orjson pyyaml jsonschema pyflakes
$PY -c "import torch, sys; sys.exit(torch.__version__ != '2.11.0+cu128')" 2>/dev/null || \
  uv pip install -q -p $PY "torch==2.11.0+cu128" --index-url https://download.pytorch.org/whl/cu128
uv pip install -q -p $PY --no-deps --reinstall $W
$PY -c "import importlib.metadata as m; print({k: m.version(k) for k in ('royalesim', 'royalegym', 'torch', 'numpy')})"
cd $CB
if [ -n "${BUILD:-}${FREEZE:-}" ]; then
  PYTHONDONTWRITEBYTECODE=1 $PY -I $TT/freeze_fork36.py $TT/build_manifest_fork36.json scratchpad/gauntlet/L74/rt35/build_manifest.json $W
fi
ROYALE_RUNTIME=fork36-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  $PY -c "from pipeline.royale_runtime import activate; s = activate(); print(s['runtime_id'], s['pins'], s['card_table'])"
$PY -c "import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0))"
echo "cpu quota: $(cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || true)"
echo "done $(date -u)"
touch /workspace/troops/SETUP_OK
