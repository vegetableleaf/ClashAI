p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec89.md", encoding="utf-8").read()
a = "### §5cs.88 -- L66g"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 13:0x UTC -- S3 GATE IS NOT ANSWERED")
L[163] = ('**2026-09-07 15:0x UTC -- THE BACK-OF-BOARD BIAS WAS A TIE-BREAK ARTIFACT: ~40% of candidates tie at '
          'the max and "first wins" resolved every plateau to the lowest cy (median winner cy == median lowest '
          'cy offered). Random tie-breaking cuts back-third placements 7/18 -> 2/18 but distance only 9.88 -> '
          '9.09 tiles vs the student 3.34-3.48, so it is a PARTIAL fix (§5cs.89). Full-bench run (tie-break, '
          'horizon 400, nohup setsid, 4 slots) IN FLIGHT -- that is the number that counts. Gate still not '
          'answered.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
