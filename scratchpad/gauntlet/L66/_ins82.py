p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec82.md", encoding="utf-8").read()
a = "### §5cs.81 -- L65c"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 02:3x UTC -- THE SANDBOX LINUX PORT")
L[163] = ('**2026-09-07 04:0x UTC -- RUNTIME IS ON THE VM (libg.so sha matches byte-for-byte, owner granted Q2) '
          'and the channel holds 441.6 h / 1,382 videos. Deck identifier built (4 passes, 3 wrong); the 12-video '
          'pilot is DISCARDED -- 20 s clips cannot show an 8-card deck, measured: known-icebow footage reads '
          '0.558 at 20 s vs 0.625 at 180 s, and frame count changes nothing (§5cs.82). Paired 180 s re-run in '
          'flight.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
