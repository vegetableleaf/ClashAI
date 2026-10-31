#!/bin/bash
# setup_Lc.sh CODE_TGZ -- POD 33308 side (L-RESUME 10-31): /workspace/loopL for the pilot2_L continuation (run pilot2_Lc), in the
# PRO pods' /workspace/loop layout, WITHOUT touching the lead's /workspace/loop/cb or /workspace/pgate2:
#  cb/  = a copy of /workspace/loop/cb (c714d63 + gate files) whose pipeline/ + scratchpad/gauntlet/L74/ are replaced by
#         CODE_TGZ (git archive of the code commit; its training code == 930adf2's, what pilot2_L ran);
#  every artifacts.tsv entry (cb/, crforge/, pylib/) from the local store by sha256 (= pod_boot step 5); the venv/ entry is
#  skipped (venvf16's royalegym / royalesim RECORDs must equal engine16's);
#  init b0_full_v2_tgt.pt <- /workspace/pgate2/ck/p2init.pt; resume state pilot2_Lc_latest.pt <- pilot2_L_latest.pt (after u34,
#  optimizer + update counter + rng inside; rl_royale --resume does not check the stored run name).
set -euo pipefail
W=/workspace/loopL; S=/workspace/loop_stage/store; T=$1
sha() { sha256sum < "$1" | cut -c1-64; }
[ -e $W/cb ] && { echo "$W/cb exists"; exit 1; }
for p in royalegym-0.1.23 royalesim-0.1.36; do
  cmp /workspace/venvf16/lib/python3.12/site-packages/$p.dist-info/RECORD /workspace/loop_stage/engine16/$p.dist-info/RECORD
done
mkdir -p $W
cp -a /workspace/loop/cb $W/cb
rm -rf $W/cb/pipeline $W/cb/scratchpad/gauntlet/L74
tar xzf $T -C $W/cb
n=0
while IFS=$'\t' read -r s dest _; do
  [ -z "$s" ] || [ "${s:0:1}" = "#" ] && continue
  case $dest in venv/*) continue ;; esac
  [ "$(sha $S/$s)" = "$s" ] || { echo "store copy of $dest has the wrong sha"; exit 1; }
  if [ "${dest: -1}" = / ]; then mkdir -p $W/$dest && tar xzf $S/$s -C $W/$dest
  else mkdir -p "$(dirname $W/$dest)" && cp $S/$s $W/$dest && [ "$(sha $W/$dest)" = "$s" ] || { echo "$dest sha"; exit 1; }; fi
  n=$((n + 1))
done < $W/cb/scratchpad/gauntlet/L74/plan1026/pilot/ops/artifacts.tsv
R=$W/cb/icebow/data/bench/rl_royale
cp /workspace/pgate2/ck/p2init.pt $R/b0/b0_full_v2_tgt.pt
[ "$(sha $R/b0/b0_full_v2_tgt.pt)" = cdde779a6ca58090bde79a238f072ee8d330ccf38c5c0707ef7b5a3dd9b12119 ] || { echo "init sha"; exit 1; }
mkdir -p $R/pilot2_Lc
cp /workspace/pgate2/ck/pilot2_L_latest.pt $R/pilot2_Lc/pilot2_Lc_latest.pt
[ "$(sha $R/pilot2_Lc/pilot2_Lc_latest.pt)" = 490271e5fccc2a210698dd042e1c8c71f14c06e24c7b5938c6c1fc81e4701c4e ] || { echo "resume sha"; exit 1; }
echo "SETUP_LC OK: $n artifacts verified, init + resume state sha-checked, tree $W/cb"
