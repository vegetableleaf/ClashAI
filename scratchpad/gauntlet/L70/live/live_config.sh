#!/bin/bash
# Shared selection only; sourcing this file has no emulator or gameplay side effects.
# load_live_config [deck]: deck = icebow|bait; default = contents of $L/LIVE_DECK, else icebow (owner 2026-10-10).
# icebow -> DECK_ARGS empty (defaults: $L/CKPT_OVERRIDE + $L/LIVE_OPTIONS); bait -> the bait specialist's own two files.
load_live_config() {
  PY=icebow/.venv/Scripts/python.exe
  HAND_READER_EFFECTIVE="${HAND_READER:-$(tr -d '\r\n' < "$L/HAND_READER_ENABLED" 2>/dev/null || printf 0)}"
  case "$HAND_READER_EFFECTIVE" in
    0) LIVE_ENTRY=scratchpad/gauntlet/L68/live_reader/live_play.py ;;
    1) LIVE_ENTRY=scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/live_play_hand_v4.py ;;
    *) echo "refusing: HAND_READER must be 0 or 1" >&2; return 2 ;;
  esac
  LIVE_DECK_EFFECTIVE="${1:-$(tr -d '\r\n' < "$L/LIVE_DECK" 2>/dev/null)}"
  LIVE_DECK_EFFECTIVE="${LIVE_DECK_EFFECTIVE:-icebow}"
  DECK_ARGS=()
  case "$LIVE_DECK_EFFECTIVE" in
    icebow) ;;
    bait)
      for f in CKPT_OVERRIDE LIVE_OPTIONS; do
        [ -f "$L/bait/$f" ] || { echo "refusing: deck bait needs $L/bait/$f (missing)" >&2; return 2; }
      done
      DECK_ARGS=(--ckpt-override-file "$L/bait/CKPT_OVERRIDE" --live-options-file "$L/bait/LIVE_OPTIONS") ;;
    *) echo "refusing: deck must be icebow or bait (got '$LIVE_DECK_EFFECTIVE')" >&2; return 2 ;;
  esac
  CKPT_ARGS=()
  if [ -n "${CKPT:-}" ]; then CKPT_ARGS=(--ckpt "$CKPT"); fi
}
