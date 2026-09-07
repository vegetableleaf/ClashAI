p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec88.md", encoding="utf-8").read()
a = "### §5cs.87 -- L66f"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 09:0x UTC -- S3 SEARCH TEACHER BUILT")
L[163] = ('**2026-09-07 13:0x UTC -- S3 GATE IS NOT ANSWERED. The sampler defect is fixed (23 -> 85 distinct '
          'cells) and the gate still fails identically: teacher exact-cell 0.00 vs student 21.9-23.9, mean '
          'distance 12.56 tiles. Cause is a real back-of-board bias (median py 5.5 vs pro 39.0, 53% in its own '
          'back third); my unit-hp explanation is CONTRADICTED by a v2 damage-only score, and the tie-break '
          'explanation is UNTESTED. No "search disagrees with pros" claim is licensed. Next: per-candidate '
          'score dump on ~10 states (§5cs.88 F).** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
