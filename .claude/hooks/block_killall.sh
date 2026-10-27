#!/usr/bin/env bash
# PreToolUse(Bash): refuse `killall` (owner 10-27) and `pkill -f` (owner 10-27, later). killall kills every process with a
# name; pkill -f matches full command lines and has killed workers' own shells -- the standing rule is to stop processes
# only by exact PID. Both are blocked in command position: start, after ; & | ( or a newline, or right after an opening
# quote (ssh "..." / bash -c '...'), with an optional sudo / timeout / nohup prefix. For pkill, any option cluster with f
# (-f, -9f, -fx) before the next separator. Plain `pkill name` and prose mentions pass. Cases: block_killall_cases.txt.
in=$(cat)
pre='(^|[;&|(]|[\]n|"command":"|[\]"|'"'"')[[:space:]]*((sudo|timeout[[:space:]]+[0-9]+[smh]?|nohup)[[:space:]]+)*'
if printf '%s' "$in" | grep -Eq "${pre}"'killall([.]exe)?([[:space:]]|[\]?"|'"'"'|;|$)'; then
  echo 'Blocked: killall kills every process with that name (owner rule 10-27). Stop processes by exact PID instead.' >&2
  exit 2
fi
if printf '%s' "$in" | grep -Eq "${pre}"'pkill[[:space:]]+([^;&|"'"'"']*[[:space:]])?-[a-zA-Z0-9]*f'; then
  echo 'Blocked: pkill -f matches whole command lines and can kill your own shell (owner rule 10-27). Stop processes by exact PID instead.' >&2
  exit 2
fi
exit 0
