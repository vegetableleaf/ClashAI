#!/usr/bin/env bash
# Linux port of scripts/stop_direct_service.ps1. Same JSON shape out, same guest effect: kill the slot's
# JniHost processes and drop its adb forward. Called by native_core/worker.py:345-349.
set -euo pipefail

SERIAL=emulator-5554; PORT=37031; SLOT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --serial) SERIAL=$2; shift 2;;
    --port) PORT=$2; shift 2;;
    --slot) SLOT=$2; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
: "${CR_SANDBOX_ADB:?Missing CR_SANDBOX_ADB; source runtime.env.sh first}"
ADB=$CR_SANDBOX_ADB
REMOTE_ROOT="/data/local/tmp/cr-native-direct-$SLOT"

# Match on all three of class, this slot's root, and the subcommand -- matching on the class alone would
# kill every slot's engine, which is how a "restart slot 2" turns into an outage on slots 0-7.
PIDS=$("$ADB" -s "$SERIAL" shell "ps -A -o PID,ARGS" 2>/dev/null | tr -d '\r' \
  | awk -v r="$REMOTE_ROOT" '$0 ~ /royale\.nativehost\.JniHost/ && index($0, r) && /serve-direct/ {print $1}' || true)
for p in $PIDS; do "$ADB" -s "$SERIAL" shell "kill '$p' 2>/dev/null || true" >/dev/null 2>&1 || true; done
"$ADB" -s "$SERIAL" forward --remove "tcp:$PORT" >/dev/null 2>&1 || true

python3 - "$SLOT" "$PORT" "$(echo "$PIDS" | tr '\n' ' ')" <<'PY'
import json, sys
slot, port, pids = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({"stopped": True, "slot": int(slot), "port": int(port),
                  "pids": [int(p) for p in pids.split()]}))
PY
