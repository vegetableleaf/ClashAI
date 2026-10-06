#!/bin/bash
# Shared selection only; sourcing this file has no emulator or gameplay side effects.
load_live_config() {
  PY=icebow/.venv/Scripts/python.exe
  HAND_READER_EFFECTIVE="${HAND_READER:-$(tr -d '\r\n' < "$L/HAND_READER_ENABLED" 2>/dev/null || printf 0)}"
  case "$HAND_READER_EFFECTIVE" in
    0) LIVE_ENTRY=scratchpad/gauntlet/L68/live_reader/live_play.py ;;
    1) LIVE_ENTRY=scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/live_play_hand_v4.py ;;
    *) echo "refusing: HAND_READER must be 0 or 1" >&2; return 2 ;;
  esac
  CKPT_ARGS=()
  if [ -n "${CKPT:-}" ]; then CKPT_ARGS=(--ckpt "$CKPT"); fi
}
