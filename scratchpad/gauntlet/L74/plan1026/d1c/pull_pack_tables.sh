#!/usr/bin/env bash
# pull_pack_tables.sh DEST -- D1-C: read-only copy of the game's csv_logic / csv_client / data_manifest files from the
# installed APK splits on the MuMu device (127.0.0.1:16384), streamed with `adb exec-out unzip -p` (nothing is written
# on the device; no root, no restart). The device's update/ folder (pull_device_update.sh) overrides these per file.
set -euo pipefail
DEST=$1
export MSYS_NO_PATHCONV=1
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ADB="bash $here/../../../L68/live_reader/adb.sh"
dir=$($ADB shell pm path com.supercell.clashroyale | tr -d '\r' | sed -n 's/^package://p' | head -1 | xargs dirname)
mkdir -p "$DEST"
for apk in $($ADB shell ls "$dir" | tr -d '\r' | grep '\.apk$'); do
  for f in $($ADB shell unzip -l "$dir/$apk" | tr -d '\r' | awk '{print $NF}' \
             | grep -E '^assets/(csv_logic|csv_client)/.*[^/]$|^assets/data_manifest\.toml$'); do
    mkdir -p "$DEST/$apk/$(dirname "${f#assets/}")"
    $ADB exec-out unzip -p "$dir/$apk" "$f" > "$DEST/$apk/${f#assets/}"
  done
done
find "$DEST" -type f | wc -l
