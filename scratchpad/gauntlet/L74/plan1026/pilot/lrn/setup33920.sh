#!/bin/bash
# LOOP-LRN pod 33920 setup: venvf16 (setup_fin16.sh), icebow/data view (symlinks into cb_mem, own bench/rl_royale), python check
set -Eeuo pipefail
CB=/workspace/lrn/cb; SRC=/workspace/cb_mem/icebow/data
mkdir -p $CB/icebow/data/bench/rl_royale/b0
for p in $SRC/*; do n=$(basename $p); [ "$n" = bench ] || ln -sfn $p $CB/icebow/data/$n; done
for p in $SRC/bench/*; do n=$(basename $p); [ "$n" = rl_royale ] || ln -sfn $p $CB/icebow/data/bench/$n; done
for p in $SRC/bench/rl_royale/*; do n=$(basename $p); [ -e $CB/icebow/data/bench/rl_royale/$n ] || ln -sfn $p $CB/icebow/data/bench/rl_royale/$n; done
mv -f $CB/icebow_b0/b0_clxiii_s3aux_grafted.pt $CB/icebow/data/bench/rl_royale/b0/ 2>/dev/null || true
sha256sum $CB/icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt | cut -c1-8
if [ ! -f /workspace/stepd/fin16/FIN16_OK ]; then
  CB=$CB FIN16_SHA=b5c3510155f7a8c8aeb6b03664f4f5e302d9a109c9b51d3e850fb2552dc5c7c5 FIN16_PIN=3f5676076fa7293de5355fa7c76275ddfbf4322c \
    bash $CB/scratchpad/gauntlet/L74/parity/fin16/setup_fin16.sh || { tail -20 /workspace/stepd/fin16/setup.log; exit 1; }
fi
tail -3 /workspace/stepd/fin16/setup.log
/workspace/venvf16/bin/python -c "import sys; sys.path.insert(0,'/workspace/lrn/d2/stage/pylib'); import jpype, torch; print('jpype', jpype.__version__, 'torch', torch.__version__, torch.cuda.is_available())"
/workspace/venvf16/bin/python -m pyflakes --version || /workspace/venvf16/bin/pip install -q pyflakes==4.0.3
