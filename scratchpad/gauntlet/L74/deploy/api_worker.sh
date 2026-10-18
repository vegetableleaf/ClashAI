#!/bin/bash
# api_worker.sh PROFILE PROMPT_FILE LOG [claude args...] : run a HEADLESS Claude Code worker (claude -p) billed to the Anthropic
# API key of PROFILE in C:\Users\benpe\.anthropic_key.txt (lines "name: key"; owner 10-18: bz-northwestern, bz-personal), not
# to the interactive session's subscription. The key goes only into the child's environment: never echoed, logged or written.
# Launch long workers detached via WMI (see memory windows-background-jobs-orphan) so they survive the lead session.
set -u
P=$1; PF=$2; LOG=$3; shift 3
KF=/c/Users/benpe/.anthropic_key.txt
K=$(awk -v p="$P" -F': *' '$1 == p {print $2; exit}' "$KF" | tr -d '\r\n ')
[ -n "$K" ] || { echo "no key for profile '$P' in $KF" >> "$LOG"; exit 2; }
cd /c/Users/benpe/ClashBot || exit 1
echo "$(date '+%F %T') start profile=$P prompt=$PF" >> "$LOG"
ANTHROPIC_API_KEY="$K" claude -p "$(cat "$PF")" --permission-mode bypassPermissions "$@" >> "$LOG" 2>&1
echo "$(date '+%F %T') exit $?" >> "$LOG"
