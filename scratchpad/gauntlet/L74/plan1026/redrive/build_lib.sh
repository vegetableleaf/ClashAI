#!/usr/bin/env bash
# build_lib.sh FORK_DIR REF OUT_DIR -- P2-RD1: build crforge `:env:installDist` of REF (a clean `git worktree`, the fork's
# working tree is not touched) into OUT_DIR/lib, and write OUT_DIR/BUILD.json (fork sha, ref, jar sha256s). Run on the
# pod that holds the fork (F635c: pod 30408, /workspace/f635/crforge_fork, cache /workspace/f635/crforge_cache).
set -euo pipefail
FORK=$1; REF=$2; OUT=$3; CACHE=${CRFORGE_CACHE:-/workspace/f635/crforge_cache}
SHA=$(git -C "$FORK" rev-parse "$REF^{commit}")
WT=/tmp/rd_build_$SHA
[ -d "$WT" ] || git -C "$FORK" worktree add --detach "$WT" "$SHA" >/dev/null
( cd "$WT" && ./gradlew --no-daemon -q --max-workers=8 -Pcrforge.cache="$CACHE" -Pcrforge.assetSource=file://$CACHE/none :env:installDist )
mkdir -p "$OUT"; rm -rf "$OUT/lib"; cp -r "$WT/env/build/install/env/lib" "$OUT/lib"
git -C "$FORK" worktree remove --force "$WT"
{ printf '{"crforge_sha": "%s", "ref": "%s", "jars": {' "$SHA" "$REF"
  sep=""; for j in "$OUT"/lib/*.jar; do printf '%s"%s": "%s"' "$sep" "$(basename "$j")" "$(sha256sum "$j" | cut -c1-64)"; sep=", "; done
  printf '}}\n'; } > "$OUT/BUILD.json"
cat "$OUT/BUILD.json"
