#!/bin/bash
# Shared selection only; sourcing this file has no emulator or gameplay side effects.
# load_live_config [deck]: deck = icebow|bait; default = contents of $L/LIVE_DECK, else icebow (owner 2026-10-10).
# icebow -> DECK_ARGS empty (defaults: $L/CKPT_OVERRIDE + $L/LIVE_OPTIONS); bait -> the bait specialist's own two files.
load_live_config() {
  # owner 10-16: local opt-in for the merged reader (git-ignored file; delete it to go back to the v2 reader)
  [ -f icebow/data/reader_notes/merged/live_env.sh ] && . icebow/data/reader_notes/merged/live_env.sh
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
  # emote spam: LIVE_EMOTES env (start_live.sh --emotes) or the persisted $L/LIVE_EMOTES file; default off
  LIVE_EMOTES_EFFECTIVE="${LIVE_EMOTES:-$(tr -d '
' < "$L/LIVE_EMOTES" 2>/dev/null)}"
  LIVE_EMOTES_EFFECTIVE="${LIVE_EMOTES_EFFECTIVE:-off}"
  if [ "$LIVE_EMOTES_EFFECTIVE" = on ]; then DECK_ARGS+=(--emote-spam on --emote-interval-s 3.0); fi
  # fast consecutive plays (owner 10-12): no restraint (tau delta 0); default ON, start_live.sh --no-fast-plays turns them off
  LIVE_FAST_EFFECTIVE="${LIVE_FAST:-$(tr -d '
' < "$L/LIVE_FAST" 2>/dev/null)}"
  LIVE_FAST_EFFECTIVE="${LIVE_FAST_EFFECTIVE:-on}"
  if [ "$LIVE_FAST_EFFECTIVE" = on ]; then DECK_ARGS+=(--pipeline-decisions --pipeline-tau-delta 0); fi
  CKPT_ARGS=()
  if [ -n "${CKPT:-}" ]; then CKPT_ARGS=(--ckpt "$CKPT"); fi
}
