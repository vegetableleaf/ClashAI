#!/usr/bin/env bash
# Read-only adb pull. Never root, remount, push, restart, or change the game.
set -euo pipefail
if [[ $# -gt 1 || ${1:-} == --help ]]; then
  echo "Usage: bash pull_device_update.sh [absolute-device-update-dir]"
  echo "Default: /data/data/com.supercell.clashroyale/update"
  exit 0
fi
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo=$(cd -- "$here/../../../.." && pwd -P)
remote=${1:-/data/data/com.supercell.clashroyale/update}
[[ $remote == /* && $remote != *$'\n'* ]] || { echo 'Expected an absolute device path' >&2; exit 2; }
# Fixed ignored parent, unique fresh destination: a new pull cannot retain files
# removed by the game since an earlier pull. Resolve it before writing.
mkdir -p -- "$here/out"
out=$(cd -- "$here/out" && pwd -P)
[[ $out == "$here/out" ]] || { echo 'Refusing linked output directory' >&2; exit 2; }
dest="$out/device_update_$(date -u +%Y%m%dT%H%M%SZ)_$$"
git -C "$repo" check-ignore -q -- "$dest/update/fingerprint.json" || { echo 'Output must be git-ignored' >&2; exit 2; }
mkdir -- "$dest"
export MSYS_NO_PATHCONV=1
local_dest="$dest/update"
if command -v cygpath >/dev/null 2>&1; then
  local_dest=$(cygpath -m "$local_dest")
fi
bash "$repo/scratchpad/gauntlet/L68/live_reader/adb.sh" pull "$remote" "$local_dest"
[[ -d "$dest/update/csv_logic" ]] || { echo "Pull lacks csv_logic: $dest" >&2; exit 1; }
printf 'Device update: %s\n' "$dest/update"
