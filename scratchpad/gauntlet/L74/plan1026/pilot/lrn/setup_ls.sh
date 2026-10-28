# LEARNER-SCALE tree on 33308: /workspace/lscale/cb = copies of pipeline + my lrn scripts, read-only symlinks into
# LOOP-INT2's /workspace/loop/cb for everything else; run outputs (L68/rl, icebow/data/bench/rl_royale) stay real dirs here.
set -e
CB=/workspace/lscale/cb; S=/workspace/loop/cb
mkdir -p $CB/scratchpad/gauntlet/L74/plan1026/pilot/lrn $CB/scratchpad/gauntlet/L68/rl $CB/icebow/data/bench/rl_royale /workspace/lscale/out
link_missing() { for p in $1/*; do n=$(basename "$p"); [ -e "$2/$n" ] || [ -L "$2/$n" ] || ln -s "$p" "$2/$n"; done; }
[ -d $CB/pipeline ] || cp -r $S/pipeline $CB/pipeline
link_missing $S $CB
link_missing $S/scratchpad $CB/scratchpad
link_missing $S/scratchpad/gauntlet $CB/scratchpad/gauntlet
link_missing $S/scratchpad/gauntlet/L68 $CB/scratchpad/gauntlet/L68
link_missing $S/scratchpad/gauntlet/L74 $CB/scratchpad/gauntlet/L74
link_missing $S/scratchpad/gauntlet/L74/plan1026 $CB/scratchpad/gauntlet/L74/plan1026
link_missing $S/scratchpad/gauntlet/L74/plan1026/pilot $CB/scratchpad/gauntlet/L74/plan1026/pilot
for f in $S/scratchpad/gauntlet/L74/plan1026/pilot/lrn/*; do n=$(basename $f); [ -e $CB/scratchpad/gauntlet/L74/plan1026/pilot/lrn/$n ] || cp $f $CB/scratchpad/gauntlet/L74/plan1026/pilot/lrn/; done
link_missing $S/icebow $CB/icebow
link_missing $S/icebow/data $CB/icebow/data
link_missing $S/icebow/data/bench $CB/icebow/data/bench
link_missing $S/icebow/data/bench/rl_royale $CB/icebow/data/bench/rl_royale
cat > $CB/scratchpad/gauntlet/L74/plan1026/pilot/lrn/env_ls.sh <<'EOT'
export CB=/workspace/lscale/cb PY=/workspace/venvf16/bin/python
export PYTHONPATH=$CB:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge \
  CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.635.3 \
  CRFORGE_FACADE_BUILD=/workspace/loop/cb/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild_fe364ceb CUBLAS_WORKSPACE_CONFIG=:4096:8
EOT
echo SETUP_OK; ls -la $CB | head -20
