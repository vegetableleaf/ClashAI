"""Split `git diff -U0 FILE` into hunks; keep the ones whose changed lines match PATTERN; write a patch applicable to HEAD
(git apply --cached --unidiff-zero) and HEAD's file with only those hunks applied (for pod tests of exactly the commit).

    python my_hunks.py FILE PATTERN OUT.patch OUT_FILE
"""
import re
import subprocess
import sys

path, pat, out_patch, out_file = sys.argv[1:5]
diff = subprocess.run(["git", "diff", "-U0", "--", path], capture_output=True, text=True, check=True).stdout
head_lines, hunks, cur = [], [], None
for line in diff.splitlines(keepends=True):
    if line.startswith("@@"):
        cur = [line]
        hunks.append(cur)
    elif cur is None:
        head_lines.append(line)
    else:
        cur.append(line)
mine = [h for h in hunks if any(re.search(pat, x) for x in h[1:] if x[:1] in "+-")]
# old-file line numbers stay valid (each hunk is relative to HEAD); new-file numbers are recomputed by git apply
open(out_patch, "w", newline="").write("".join(head_lines) + "".join("".join(h) for h in mine))
src = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, check=True).stdout.decode("utf-8")
lines = src.splitlines(keepends=True)
for h in reversed(mine):                                   # apply bottom-up so earlier line numbers stay put
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", h[0])
    start, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
    old = [x[1:] for x in h[1:] if x.startswith("-")]
    new = [x[1:] for x in h[1:] if x.startswith("+")]
    at = start - 1 if n else start                         # n == 0: insertion AFTER line `start`
    assert [x.rstrip("\r\n") for x in lines[at:at + n]] == [x.rstrip("\r\n") for x in old], (h[0], old, lines[at:at + n])
    lines[at:at + n] = new
open(out_file, "w", encoding="utf-8", newline="").write("".join(lines))
print(f"{len(mine)}/{len(hunks)} hunks kept")
