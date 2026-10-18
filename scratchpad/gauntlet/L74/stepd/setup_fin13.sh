#!/bin/bash
# Step d R1 (pod): the fin13-linux runtime = RoyaleSim fork clashbot36 head a697d1f9 in /workspace/venvf13, a hard-link copy of
# /workspace/venvf36 (torch / royalegym bytes shared; only royalesim is replaced, so venvf36 is never written through a link).
#   BUILD=1 nice -n 19 bash setup_fin13.sh   build the wheel here from /workspace/in/clashbot36_a697d1f9.bundle + freeze the manifest
#   FREEZE=1 bash setup_fin13.sh             the wheel is already in /workspace/in/fin13/: install + freeze
#   bash setup_fin13.sh                      a second pod: install /workspace/in/fin13/royalesim-*.whl (the SAME bytes) and
#                                            check it against the shipped manifest (stepd/build_manifest_fin13.json)
#   -> /workspace/stepd/fin13/setup.log, FIN13_OK (activate() under ROYALE_RUNTIME=fin13-linux passed)
set -Eeuo pipefail
O=/workspace/stepd/fin13; mkdir -p $O /workspace/results; exec >> $O/setup.log 2>&1
trap 'echo "FIN13 SETUP FAILED line $LINENO (exit $?)"; touch $O/FAILED' ERR
rm -f $O/FAILED $O/FIN13_OK
CB=${CB:-/workspace/cb_stepd}; V=/workspace/venvf13; PY=$V/bin/python; SD=scratchpad/gauntlet/L74/stepd
echo "start $(date -u)"
if [ -n "${BUILD:-}" ]; then
  [ -e /workspace/results/fork_fin13.DONE ] || BRANCH=clashbot36 BUNDLE=/workspace/in/clashbot36_a697d1f9.bundle \
    FORKDIR=/workspace/fork13 bash $CB/scratchpad/gauntlet/L74/parity/night1016/fork_build.sh fin13
  mkdir -p /workspace/in/fin13; cp /workspace/fork13/crates/royalesim/target/wheels/*.whl /workspace/in/fin13/
fi
# the wheel reads its BUILD checkout's data/derived whenever that directory exists (card_table_source() then != 'embedded';
# the fork36 hide_run trap): drop the checkout + its cargo target once the wheel is copied (also the disk rule)
[ -n "${BUILD:-}${FREEZE:-}" ] && rm -rf /workspace/fork13 /workspace/rsfork_fin13
W=$(ls /workspace/in/fin13/royalesim-*.whl | head -1)
echo "wheel $W $(sha256sum $W | cut -c1-16)"
[ -x $PY ] || cp -al /workspace/venvf36 $V
uv pip install -q -p $PY --no-deps --reinstall --link-mode=copy $W
$PY -c "import importlib.metadata as m; print({k: m.version(k) for k in ('royalesim', 'royalegym', 'torch', 'numpy')})"
cd $CB
if [ -n "${BUILD:-}${FREEZE:-}" ]; then
  PYTHONDONTWRITEBYTECODE=1 $PY -I $SD/freeze_fin13.py $O/build_manifest_fin13.json scratchpad/gauntlet/L74/rt35/build_manifest.json $W
  cp $O/build_manifest_fin13.json $SD/build_manifest_fin13.json
fi
ROYALE_RUNTIME=fin13-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  $PY -c "from pipeline.royale_runtime import activate; s = activate(); print(s['runtime_id'], s['pins'], s['card_table'])"
ROYALE_RUNTIME=fork36-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  /workspace/venvf36/bin/python -c "from pipeline.royale_runtime import activate; s = activate(); print('venvf36 intact', s['pins'])"
echo "done $(date -u)"
touch $O/FIN13_OK
