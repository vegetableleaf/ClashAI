#!/usr/bin/env bash
# PreToolUse(Bash): refuse Python reading its script from stdin. On this laptop an empty or broken heredoc turns it into an
# interactive REPL that hangs the shell (memory: stdin-python-repl-trap; 10+ hangs on the night of 10-16). Blocked, in command
# position (start, after ; & | ( or a newline, after VAR=x / timeout / nohup / env prefixes):
#   1. python / python3[.N] / py, bare or as a path, optionally .exe, followed by ` -` as its own argument;
#   2. the same through a shell variable: `$PY -`, `"${PY}" -` (10-17: a worker's `$PY - 2>/dev/null` slipped past rule 1);
#   3. an interpreter or variable with NO script at all (only redirections, then the command ends): `python;`, `$PY 2>/dev/null;`.
# `python -c`, `-u`, `-m`, `$PY file.py`, ssh-quoted pod commands and prose mentions pass. Cases: block_stdin_python_cases.txt.
# The input is the hook's JSON, so a newline in the command is the two characters \n ([\]n: grep 3.0 -E mis-reads \\n), an inner
# quote is \" and the command's end is a bare " followed by , or }.
in=$(cat)
cp='(^|[;&|(]|[\]n|"command":")[[:space:]]*(([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*|timeout|nohup|env|time|[0-9]+[smh]?)[[:space:]]+)*'
interp='([^[:space:];&|"]*[/\])?(python(3([.][0-9]+)?)?|py)([.]exe)?'
var='[\]?"?[$][{]?[A-Za-z_][A-Za-z0-9_]*[}]?[\]?"?'
dash='[[:space:]]+-([[:space:]]|[\]n|"|<)'
bare='([[:space:]]+[0-9]?[<>]+&?[^[:space:];&|"]*)*[[:space:]]*([;&|]|[\]n|"[,}])'
if printf '%s' "$in" | grep -Eq "$cp($interp|$var)($dash|$bare)"; then
  echo 'Blocked: Python reading its script from stdin (`python -`, `$PY -`, or an interpreter with no script) hangs as a REPL on this laptop. Write the script to a file (scratchpad) and run `python file.py`.' >&2
  exit 2
fi
exit 0
