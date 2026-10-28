# fill /workspace/lrn/cb with read-only symlinks into cb_mem for everything my tree does not carry (outputs stay real dirs)
set -e
CB=/workspace/lrn/cb; S=/workspace/cb_mem
link_missing() { for p in $1/*; do n=$(basename "$p"); [ -e "$2/$n" ] || [ -L "$2/$n" ] || ln -s "$p" "$2/$n"; done; }
link_missing $S $CB
link_missing $S/scratchpad $CB/scratchpad
link_missing $S/scratchpad/gauntlet $CB/scratchpad/gauntlet
rm -f $CB/scratchpad/gauntlet/L68; mkdir -p $CB/scratchpad/gauntlet/L68/rl
link_missing $S/scratchpad/gauntlet/L68 $CB/scratchpad/gauntlet/L68
rm -f $CB/scratchpad/gauntlet/L68/rl 2>/dev/null || true; mkdir -p $CB/scratchpad/gauntlet/L68/rl
ls -la $CB | head -30; ls -la $CB/scratchpad/gauntlet/L68 | head
