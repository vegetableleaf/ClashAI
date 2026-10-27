#!/usr/bin/env bash
# PreToolUse(Bash): refuse `killall` (owner 10-27). It kills every process with a name, on the laptop or on a pod through an
# ssh-quoted command -- the standing rule is to stop processes only by exact PID. Blocked in command position: start, after
# ; & | ( or a newline, or right after an opening quote (ssh "..." / bash -c '...'), with an optional sudo / timeout prefix.
# Prose mentions (e.g. in a commit message after other words) pass. Cases: block_killall_cases.txt.
in=$(cat)
if printf '%s' "$in" | grep -Eq '(^|[;&|(]|[\]n|"command":"|[\]"|'"'"')[[:space:]]*((sudo|timeout[[:space:]]+[0-9]+[smh]?|nohup)[[:space:]]+)*killall([.]exe)?([[:space:]]|[\]?"|'"'"'|;|$)'; then
  echo 'Blocked: killall kills every process with that name (owner rule 10-27). Stop processes by exact PID instead.' >&2
  exit 2
fi
exit 0
