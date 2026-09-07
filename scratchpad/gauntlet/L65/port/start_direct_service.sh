#!/usr/bin/env bash
# Linux port of scripts/start_direct_service.ps1 (cr-native-sandbox). Byte-for-byte same guest state.
#
# Why this file exists: the sandbox is not Windows-locked -- everything touching the game's code is
# Android/Linux already, and the whole Windows surface is ~200 lines of PowerShell orchestration around
# adb (scratchpad/gauntlet/L65/sandbox_portability.md section 2). This is the larger half of that.
#
# It prints the SAME JSON object on success as the .ps1, so native_core/worker.py can call it unchanged
# apart from swapping the interpreter (worker.py:57-58, :286-287) and dropping the .exe suffixes
# (worker.py:76,:80).
#
# THE TRAP THE SURVEY NAMED, and where it is handled: the launch string is quote-nested three deep --
# `nohup sh -c "cd ... && exec env CLASSPATH=... app_process ..." >log 2>&1 </dev/null &`, and that whole
# thing is then one argument to `adb shell`, which re-parses it in the guest's shell. Get it wrong and the
# service starts and instantly exits, and the only diagnostic is the in-guest service.log. Handled below by
# building the inner command with single quotes only (no $ or backtick can survive to the guest shell) and
# passing the outer string as ONE argv element to adb.
#
# A SECOND TRAP, NOT in the survey and specific to Linux, found while porting: the .ps1 calls `tar.exe` on
# the ASSET PACK APK (start_direct_service.ps1:110). Windows' tar.exe is bsdtar/libarchive, which reads zip
# archives -- and an APK is a zip. GNU tar, the default on Ubuntu, CANNOT read a zip and fails with
# "This does not look like a tar archive". So that one call becomes `unzip -o -j`, not `tar -xf`. A
# mechanical .ps1 -> .sh transliteration would produce a script that dies at exactly that line.
#
# usage: start_direct_service.sh [--serial emulator-5554] [--port 37031] [--slot 0] [--ready-timeout 300]
#        env: CR_SANDBOX_ADB CR_SANDBOX_RUNTIME_DIR CR_SANDBOX_BASE_APK CR_SANDBOX_ASSETS
#             CR_SANDBOX_ASSET_PACK_APK CR_SANDBOX_DATA   (same names as runtime.env.ps1)
set -euo pipefail

SERIAL=emulator-5554; PORT=37031; SLOT=0; READY=300; BOOTSTRAP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --serial) SERIAL=$2; shift 2;;
    --port) PORT=$2; shift 2;;
    --slot) SLOT=$2; shift 2;;
    --ready-timeout) READY=$2; shift 2;;
    --bootstrap) BOOTSTRAP=$2; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

need() { eval "v=\${$1:-}"; [ -n "$v" ] || { echo "Missing $1; source runtime.env.sh first" >&2; exit 2; }; }
for v in CR_SANDBOX_ADB CR_SANDBOX_RUNTIME_DIR CR_SANDBOX_BASE_APK CR_SANDBOX_ASSETS \
         CR_SANDBOX_ASSET_PACK_APK CR_SANDBOX_DATA; do need "$v"; done

ADB=$CR_SANDBOX_ADB
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[ -n "$BOOTSTRAP" ] || BOOTSTRAP="$PROJECT_ROOT/examples/eight-card-bootstrap.json"
JAR="$PROJECT_ROOT/artifacts/lifecycle-probe.jar"
BRIDGE="$PROJECT_ROOT/artifacts/libnative_core_probe.so"
ASSET_ARCHIVE="$PROJECT_ROOT/artifacts/runtime-assets.tar"
REMOTE_ROOT="/data/local/tmp/cr-native-direct-$SLOT"
EVIDENCE_ROOT="$CR_SANDBOX_DATA/worker"
ASSET_OVERLAY="$EVIDENCE_ROOT/runtime-assets-overlay"

for f in "$ADB" "$JAR" "$BRIDGE" "$CR_SANDBOX_BASE_APK" "$CR_SANDBOX_ASSET_PACK_APK" \
         "$BOOTSTRAP" "$CR_SANDBOX_RUNTIME_DIR/libg.so"; do
  [ -f "$f" ] || { echo "Missing direct-worker input: $f" >&2; exit 2; }
done
[ -d "$CR_SANDBOX_ASSETS" ] || { echo "Missing runtime asset directory: $CR_SANDBOX_ASSETS" >&2; exit 2; }
mkdir -p "$EVIDENCE_ROOT" "$ASSET_OVERLAY"

adb_() { "$ADB" -s "$SERIAL" "$@"; }
adb_ok() { "$ADB" -s "$SERIAL" "$@" 2>/dev/null || true; }

remote_sha() { adb_ok shell "sha256sum '$1' 2>/dev/null || true" | tr -d '\r' | awk '{print $1}'; }

push_verified() {                      # $1 local, $2 remote -- skip if the guest already holds the bytes
  local h; h=$(sha256sum "$1" | awk '{print $1}')
  [ "$(remote_sha "$2")" = "$h" ] && return 0
  adb_ push "$1" "$2.upload" >/dev/null
  [ "$(remote_sha "$2.upload")" = "$h" ] || { echo "Remote hash mismatch: $2.upload" >&2; exit 1; }
  adb_ shell "mv -f '$2.upload' '$2' && chmod 0666 '$2'" >/dev/null
}

# one newline-delimited JSON round trip to the service; prints the reply line, empty on failure
json_req() {
  python3 - "$1" "$2" <<'PY' 2>/dev/null || true
import json, socket, sys
port, op = int(sys.argv[1]), sys.argv[2]
try:
    s = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    s.settimeout(2.0)
    s.sendall((json.dumps({"op": op}) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        c = s.recv(4096)
        if not c:
            break
        buf += c
    s.close()
    sys.stdout.write(buf.decode().strip())
except Exception:
    pass
PY
}

service_pids() {
  adb_ok shell "ps -A -o PID,ARGS" | tr -d '\r' \
    | awk -v r="$REMOTE_ROOT" '$0 ~ /royale\.nativehost\.JniHost/ && index($0, r) && /serve-direct/ {print $1}'
}

adb_ shell "mkdir -p '$REMOTE_ROOT'" >/dev/null
for so in "$CR_SANDBOX_RUNTIME_DIR"/*.so; do
  push_verified "$so" "$REMOTE_ROOT/$(basename "$so")"
done
push_verified "$JAR" "$REMOTE_ROOT/lifecycle-probe.jar"
push_verified "$BRIDGE" "$REMOTE_ROOT/libnative_host_bridge.so"
push_verified "$CR_SANDBOX_BASE_APK" "$REMOTE_ROOT/base.apk"
push_verified "$BOOTSTRAP" "$REMOTE_ROOT/bootstrap-replay.json"

tar -cf "$ASSET_ARCHIVE" -C "$CR_SANDBOX_ASSETS" .
# APK is a ZIP: GNU tar cannot read it (see header). -j flattens, so re-create the two parent dirs.
rm -rf "$ASSET_OVERLAY/locations" "$ASSET_OVERLAY/tilemaps"
mkdir -p "$ASSET_OVERLAY/locations" "$ASSET_OVERLAY/tilemaps"
unzip -o -j "$CR_SANDBOX_ASSET_PACK_APK" "assets/locations/training_arena.csv" -d "$ASSET_OVERLAY/locations" >/dev/null
unzip -o -j "$CR_SANDBOX_ASSET_PACK_APK" "assets/tilemaps/tilemap.csv" -d "$ASSET_OVERLAY/tilemaps" >/dev/null
tar -rf "$ASSET_ARCHIVE" -C "$ASSET_OVERLAY" "locations/training_arena.csv" "tilemaps/tilemap.csv"
push_verified "$ASSET_ARCHIVE" "$REMOTE_ROOT/runtime-assets.tar"
adb_ shell "mkdir -p '$REMOTE_ROOT/assets' && tar -xf '$REMOTE_ROOT/runtime-assets.tar' -C '$REMOTE_ROOT/assets'" >/dev/null

for p in $(service_pids); do adb_ok shell "kill '$p' 2>/dev/null || true" >/dev/null; done
adb_ok forward --remove "tcp:$PORT" >/dev/null
adb_ forward "tcp:$PORT" "tcp:$PORT" >/dev/null

# Single quotes only inside INNER: nothing here is expanded by the guest shell. INNER is embedded in
# LAUNCH's double quotes, and LAUNCH is passed to adb as ONE argument -- the guest shell re-parses it once.
INNER="cd '$REMOTE_ROOT' && exec env CLASSPATH='$REMOTE_ROOT/lifecycle-probe.jar:$REMOTE_ROOT/base.apk' LD_LIBRARY_PATH='$REMOTE_ROOT' app_process /system/bin royale.nativehost.JniHost '$REMOTE_ROOT' serve-direct '$PORT'"
LAUNCH="nohup sh -c \"$INNER\" >'$REMOTE_ROOT/service.log' 2>&1 </dev/null &"
adb_ shell "$LAUNCH" >/dev/null

DEADLINE=$(( $(date +%s) + READY ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  PING=$(json_req "$PORT" ping)
  case "$PING" in
    *'"ok"'*true*|*'"ok": true'*|*'"ok":true'*)
      STATE=$(json_req "$PORT" status)
      PIDS=$(service_pids | tr '\n' ' ')
      python3 - "$SLOT" "$PORT" "$SERIAL" "$REMOTE_ROOT" "$PIDS" "$STATE" <<'PY'
import json, sys
slot, port, serial, root, pids, state = sys.argv[1:7]
try:
    st = json.loads(state).get("state")
except Exception:
    st = None
print(json.dumps({"ready": True, "mode": "serve-direct", "slot": int(slot), "port": int(port),
                  "serial": serial, "remote_root": root,
                  "guest_pids": [int(p) for p in pids.split()], "state": st}))
PY
      exit 0;;
  esac
  sleep 0.25
done
echo "Direct service did not become ready" >&2
adb_ok shell "tail -n 120 '$REMOTE_ROOT/service.log'" >&2
exit 1
