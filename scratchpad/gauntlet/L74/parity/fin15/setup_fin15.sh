#!/bin/bash
# fin15-linux runtime on a training pod (stepd/setup_fin13.sh pattern): the RoyaleSim fork at fin15 (parity/fin15/FIN15.md) in
# /workspace/venvf15, a hard-link copy of /workspace/venvf36 (torch / royalegym bytes shared; only royalesim is replaced, so venvf36
# is never written through a link).
#   FREEZE=1 bash setup_fin15.sh   the wheel is in /workspace/in/fin15/: install + freeze the manifest (the first pod; copy the
#                                  printed manifest to parity/fin15/build_manifest_fin15.json and commit it)
#   bash setup_fin15.sh            any pod: install /workspace/in/fin15/royalesim-*.whl (the SAME bytes: its sha256 must be FIN15_SHA)
#                                  and check it against the shipped manifest
#   -> /workspace/stepd/fin15/setup.log, FIN15_OK (activate() under ROYALE_RUNTIME=fin15-linux passed + a 600-tick icebow battle)
# Train on it: in stepd_chain.sh (or any launcher) use /workspace/venvf15/bin/python and ROYALE_RUNTIME=fin15-linux where it
# says venvf13 / fin13-linux.
set -Eeuo pipefail
O=/workspace/stepd/fin15; mkdir -p $O; exec >> $O/setup.log 2>&1
trap 'echo "FIN15 SETUP FAILED line $LINENO (exit $?)"; touch $O/FAILED' ERR
rm -f $O/FAILED $O/FIN15_OK
CB=${CB:-/workspace/cb_stepd}; V=/workspace/venvf15; PY=$V/bin/python; F=scratchpad/gauntlet/L74/parity/fin15
SRCV=${SRCV:-/workspace/venvf36}; [ -d $SRCV ] && [ ! -L $SRCV ] || { echo "SRCV $SRCV is not a real venv dir"; false; }
FIN15_SHA=${FIN15_SHA:?the fin15 wheel sha256 from FIN15.md}
FIN15_PIN=${FIN15_PIN:?the fin15 fork commit (40 hex) from FIN15.md}
echo "start $(date -u)"
W=$(ls /workspace/in/fin15/royalesim-*.whl | head -1)
echo "$FIN15_SHA  $W" | sha256sum -c -
# the wheel reads its BUILD checkout's data/derived when that directory exists (the hide_run trap): no fin15 build checkout here
[ ! -e /workspace/w8/src_rsfork_fin15 ] || { echo "a fin15 build checkout exists on this pod: remove /workspace/w8/src_rsfork_fin15 first"; false; }
[ -x $PY ] || cp -al $SRCV $V    # SRCV = a real venv dir (never a symlink: cp -a would copy the link and the install would write through it)
uv pip install -q -p $PY --no-deps --reinstall --link-mode=copy $W
$PY -c "import importlib.metadata as m; print({k: m.version(k) for k in ('royalesim', 'royalegym', 'torch', 'numpy')})"
cd $CB
if [ -n "${FREEZE:-}" ]; then
  PYTHONDONTWRITEBYTECODE=1 $PY -I $F/freeze_fin15.py $O/build_manifest_fin15.json scratchpad/gauntlet/L74/rt35/build_manifest.json $W $FIN15_PIN
  cp $O/build_manifest_fin15.json $F/build_manifest_fin15.json
fi
ROYALE_RUNTIME=fin15-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 $PY $F/smoke_fin15.py
[ -n "${SKIP36:-}" ] || ROYALE_RUNTIME=fork36-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  $SRCV/bin/python -c "from pipeline.royale_runtime import activate; s = activate(); print('venvf36 intact', s['pins'])"
echo "done $(date -u)"
touch $O/FIN15_OK
