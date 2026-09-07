p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec87.md", encoding="utf-8").read()
a = "### §5cs.86 -- L66e"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 07:0x UTC -- MINING IS OVER")
L[163] = ('**2026-09-07 09:0x UTC -- S3 SEARCH TEACHER BUILT AND RUNNING THE FULL BENCH (497/500 states, 46 min '
          'on 4 VM slots). Its FIRST GATE RUN IS INVALID -- 24 near-fixed candidates made the 0.3-tile criterion '
          'unreachable by construction, so the 0.0% measures my sampler not search (§5cs.87 D). Student baseline '
          'on these states: cell 21.9/23.9/21.9, card 60.8-64.4. Coarse-to-fine refine re-run in flight.** '
          'Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
