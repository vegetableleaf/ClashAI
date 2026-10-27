#!/usr/bin/env bash
# build.sh NAME [WT] -- A2c-BP5: installDist of the bp5 worktree into /workspace/pilot/bp5/lib_NAME
WT=${2:-/workspace/pilot/bp5/crforge}; cd $WT
./gradlew --no-daemon -q --max-workers=16 -Pcrforge.cache=/workspace/crforge_cache -Pcrforge.assetSource=file:///workspace/crforge_cache/none :env:installDist > /workspace/pilot/bp5/build_$1.log 2>&1 || { tail -20 /workspace/pilot/bp5/build_$1.log; exit 1; }
rm -rf /workspace/pilot/bp5/lib_$1 && cp -r env/build/install/env/lib /workspace/pilot/bp5/lib_$1 && echo built lib_$1
