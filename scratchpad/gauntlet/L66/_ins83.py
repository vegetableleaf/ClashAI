p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec83.md", encoding="utf-8").read()
a = "### §5cs.82 -- L66 "
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 04:0x UTC -- RUNTIME IS ON THE VM")
L[163] = ('**2026-09-07 04:4x UTC -- DECK IDENTIFIER CALIBRATED AND ITS FIRST TRUE POSITIVE FOUND: NYAWcJcGU3E '
          'scores 0.730 (all 8 cards 0.73-0.83) vs known-icebow controls 0.625/0.670/0.687 and 8 other-deck '
          'videos at 0.500-0.565; threshold 0.60, gap 0.06. Same video read 0.545 under the discarded 20 s '
          'pilot -- it INVERTED a positive. Hit rate 1/9 = 11% with 95% band 2-43% = 9-192 icebow hours vs the '
          '78-139 h a doubling needs, so a 100-video sweep is running (§5cs.83).** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
