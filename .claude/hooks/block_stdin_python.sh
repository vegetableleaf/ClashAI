#!/usr/bin/env bash
# PreToolUse(Bash): refuse `python -` (script read from stdin). On this laptop an empty or broken heredoc turns it into an
# interactive REPL that hangs the shell (memory: stdin-python-repl-trap; 10+ hangs on the night of 10-16). Matches python /
# python3[.N] / py, bare or as a path, optionally .exe, in command position (start, after ; & | ( or a newline, after
# VAR=x / timeout / nohup / env prefixes), followed by ` -` as its own argument. `python -c`, `-u`, `-m` pass. Commands
# quoted inside ssh "..." (pods, where stdin is a pipe) do not sit in command position and pass.
# The input is the hook's JSON, so a newline in the command is the two characters \n ([\]n: grep 3.0 -E mis-reads \n).
in=$(cat)
pat='(^|[;&|(]|[\]n|"command":")[[:space:]]*(([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*|timeout|nohup|env|time|[0-9]+[smh]?)[[:space:]]+)*([^[:space:];&|"]*[/\])?(python(3([.][0-9]+)?)?|py)([.]exe)?[[:space:]]+-([[:space:]]|[\]n|"|<)'
if printf '%s' "$in" | grep -Eq "$pat"; then
  echo 'Blocked: `python -` (script from stdin) hangs as a REPL on this laptop. Write the script to a file (scratchpad) and run `python file.py`.' >&2
  exit 2
fi
exit 0
