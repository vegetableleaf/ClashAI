#!/usr/bin/env bash
# ENG-SME sync 20261028: TickProbe lib of 0a1a18e9 = build_main.sh REF OUT tp with patch 0002 ported to the index-loop drainRemovable
set -euo pipefail
FORK=/workspace/f635/crforge_fork; CACHE=/workspace/f635/crforge_cache; P=/workspace/f635c
SHA=$(git -C $FORK rev-parse 0a1a18e94fdd04139197273f6ec1ff21d6f912ad^{commit}); WT=/tmp/cfsync_build_${SHA:0:8}_tp; OUT=/workspace/crforge_main/${SHA:0:8}/tickprobe
git -C $FORK worktree remove --force $WT 2>/dev/null || rm -rf $WT
git -C $FORK worktree add --detach $WT $SHA >/dev/null
cd $WT
git apply $P/clashbot-bp_0001_TickProbe.patch
git apply --include='core/src/main/java/org/crforge/core/battle/TickProbe.java' $P/clashbot-bp_0002_TickProbeDrain.patch
F=core/src/main/java/org/crforge/core/battle/EntityHolder.java
[ "$(grep -c '^        list.remove(i);$' $F)" = 1 ] || { echo "ANCHOR NOT UNIQUE"; exit 3; }
sed -i 's/^        list.remove(i);$/        list.remove(i);\n        TickProbe.tell("drain", -1, entity.getId());/' $F
git diff > /dev/shm/s4/tickprobe_0a1a18e9.diff
./gradlew --no-daemon -q --max-workers=4 -Pcrforge.cache=$CACHE -Pcrforge.assetSource=file://$CACHE/none :env:installDist
mkdir -p $OUT; rm -rf $OUT/lib; cp -r env/build/install/env/lib $OUT/lib
cd /; git -C $FORK worktree remove --force $WT
cd $OUT && sha256sum lib/*.jar > SHA256SUMS
{ printf '{"crforge_sha": "%s", "ref": "%s", "tickprobe": true, "tickprobe_port": "0002 drain after list.remove(i)", "jars": {' $SHA 0a1a18e9
  sep=""; while read -r h f; do printf '%s"%s": "%s"' "$sep" "${f#lib/}" "$h"; sep=", "; done < SHA256SUMS; printf '}}\n'; } > BUILD.json
echo "built $OUT core $(grep core-1.0 SHA256SUMS | cut -c1-16)"
