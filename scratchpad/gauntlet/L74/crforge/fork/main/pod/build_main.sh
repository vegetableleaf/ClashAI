#!/usr/bin/env bash
# build_main.sh REF OUT [tp] -- CF-MAIN (pod 30408): crforge :env:installDist of fork REF in a throwaway detached worktree
# (no working tree is touched) into OUT/lib. tp = clashbot-bp TickProbe 0001 + 0002 applied for this build only (SME).
# Writes OUT/BUILD.json (fork sha, ref, tickprobe, jar sha256s) and OUT/SHA256SUMS (check: cd OUT && sha256sum -c SHA256SUMS).
set -euo pipefail
REF=$1; OUT=$2; TP=${3:-}
FORK=/workspace/f635/crforge_fork; CACHE=/workspace/f635/crforge_cache; P=/workspace/f635c
SHA=$(git -C $FORK rev-parse "$REF^{commit}"); WT=/tmp/cfmain_build_${SHA:0:8}${TP:+_tp}
git -C $FORK worktree remove --force $WT 2>/dev/null || rm -rf $WT
git -C $FORK worktree add --detach $WT $SHA >/dev/null
cd $WT
[ "$TP" = tp ] && { git apply $P/clashbot-bp_0001_TickProbe.patch; git apply $P/clashbot-bp_0002_TickProbeDrain.patch; }
./gradlew --no-daemon -q --max-workers=16 -Pcrforge.cache=$CACHE -Pcrforge.assetSource=file://$CACHE/none :env:installDist
mkdir -p $OUT; rm -rf $OUT/lib; cp -r env/build/install/env/lib $OUT/lib
cd /; git -C $FORK worktree remove --force $WT
cd $OUT && sha256sum lib/*.jar > SHA256SUMS
{ printf '{"crforge_sha": "%s", "ref": "%s", "tickprobe": %s, "jars": {' $SHA $REF $([ "$TP" = tp ] && echo true || echo false)
  sep=""; while read -r h f; do printf '%s"%s": "%s"' "$sep" "${f#lib/}" "$h"; sep=", "; done < SHA256SUMS; printf '}}\n'; } > BUILD.json
echo "built $OUT core $(grep core-1.0 SHA256SUMS | cut -c1-16)"
