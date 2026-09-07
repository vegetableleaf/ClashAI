p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec85.md", encoding="utf-8").read()
a = "### §5cs.84 -- L66c"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 05:3x UTC -- FIRST ENGINE SLOT")
L[163] = ('**2026-09-07 06:3x UTC -- THE VM DRIVES REPLAYS 5.0x FASTER THAN THIS BOX on identical work '
          '(2.48 vs 12.52 s/match, both 17 files x 240 frames): 100k matches = 69 VM-hours / ~$27 on one slot, '
          'so COMPUTE IS NO LONGER THE S3 CONSTRAINT (§5cs.85). Multi-slot scaling untested. YouTube bot '
          'detection stopped the sweep at 11/100 -- getting past it needs the owner\'s account cookies, a new '
          'question. Icebow hit rate now 1/20 = 5% [0.9-23.6%] = 22 h [4-104] vs the 78-139 h a doubling needs: '
          'evidence has moved AGAINST video mining as a scaling lever.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
