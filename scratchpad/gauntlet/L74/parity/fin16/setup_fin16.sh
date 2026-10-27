#!/bin/bash
# fin16-linux runtime on a training pod (parity/fin15/setup_fin15.sh pattern): the RoyaleSim fork at fin16 (FIN16.md) in
# /workspace/venvf16, a hard-link copy of /workspace/venvf15 (torch / royalegym bytes shared; only royalesim is replaced with
# --link-mode=copy, so venvf15 is never written through a link; its manifest is re-checked at the end).
#   FREEZE=1 bash setup_fin16.sh   first pod: install + freeze the manifest (copy it to parity/fin16/build_manifest_fin16.json)
#   bash setup_fin16.sh            any pod: install /workspace/in/fin16/royalesim-*.whl (sha256 must be FIN16_SHA), check it
#                                  against the shipped manifest
#   -> /workspace/stepd/fin16/setup.log, FIN16_OK (activate() under ROYALE_RUNTIME=fin16-linux + a 600-tick icebow battle)
# Train on it: /workspace/venvf16/bin/python and ROYALE_RUNTIME=fin16-linux where a launcher says venvf15 / fin15-linux.
set -Eeuo pipefail
O=/workspace/stepd/fin16; mkdir -p $O; exec >> $O/setup.log 2>&1
trap 'echo "FIN16 SETUP FAILED line $LINENO (exit $?)"; touch $O/FAILED' ERR
rm -f $O/FAILED $O/FIN16_OK
CB=${CB:?a code tree with pipeline/ and parity/fin16/}; V=/workspace/venvf16; PY=$V/bin/python; F=scratchpad/gauntlet/L74/parity/fin16
SRCV=${SRCV:-/workspace/venvf15}; [ -d $SRCV ] && [ ! -L $SRCV ] || { echo "SRCV $SRCV is not a real venv dir"; false; }
FIN16_SHA=${FIN16_SHA:?the fin16 wheel sha256 from FIN16.md}
FIN16_PIN=${FIN16_PIN:?the fin16 fork commit (40 hex) from FIN16.md}
echo "start $(date -u)"
W=$(ls /workspace/in/fin16/royalesim-*.whl | head -1)
echo "$FIN16_SHA  $W" | sha256sum -c -
# the wheel reads its BUILD checkout's data/derived when that directory exists (FIN15.md "Trap")
! ls -d /workspace/f16/src_fin16 > /dev/null 2>&1 || { echo "the fin16 build checkout /workspace/f16/src_fin16 exists here: move it first"; false; }
[ -x $PY ] || cp -al $SRCV $V
uv pip install -q -p $PY --no-deps --reinstall --link-mode=copy $W
$PY -c "import importlib.metadata as m; print({k: m.version(k) for k in ('royalesim', 'royalegym', 'torch', 'numpy')})"
cd $CB
if [ -n "${FREEZE:-}" ]; then
  PYTHONDONTWRITEBYTECODE=1 $PY -I $F/freeze_fin16.py $O/build_manifest_fin16.json scratchpad/gauntlet/L74/rt35/build_manifest.json $W $FIN16_PIN
  cp $O/build_manifest_fin16.json $F/build_manifest_fin16.json
fi
ROYALE_RUNTIME=fin16-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 $PY $F/smoke_fin16.py
ROYALE_RUNTIME=fin15-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  $SRCV/bin/python -c "from pipeline.royale_runtime import activate; s = activate(); print('venvf15 intact', s['pins'])"
echo "done $(date -u)"
touch $O/FIN16_OK
