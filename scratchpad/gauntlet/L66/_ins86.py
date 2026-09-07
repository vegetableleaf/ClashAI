p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec86.md", encoding="utf-8").read()
a = "### §5cs.85 -- L66d"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 06:3x UTC -- THE VM DRIVES REPLAYS")
L[163] = ('**2026-09-07 07:0x UTC -- MINING IS OVER (owner: no account risk; my verdict on anonymous mining: '
          'NOT worth it -- best case +0.3 to +0.5 pp for ~46 h of throttled downloading plus an unbuilt pipeline '
          'and an unmeasured quality discount, §5cs.86). Engine slots scale 2.68x at 4 slots = 3,400 matches/h, '
          '~12x this box. S3 IS THE WORK NOW: building the search teacher against the 500-state gate '
          '(pipeline/s3_bench.py).** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
