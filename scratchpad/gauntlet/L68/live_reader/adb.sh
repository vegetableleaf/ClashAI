#!/usr/bin/env bash
# MuMu adb pinned to the one emulator instance used for the live reader (Training Camp only, own-side state).
# Usage: bash scratchpad/gauntlet/L68/live_reader/adb.sh <adb args>
exec "/c/Program Files/Netease/MuMuPlayer/nx_device/15.0/shell/adb.exe" -s 127.0.0.1:16384 "$@"
