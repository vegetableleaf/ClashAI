p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec90.md", encoding="utf-8").read()
a = "### §5cs.89 -- L66h"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 15:0x UTC -- THE BACK-OF-BOARD BIAS")
L[163] = ('**2026-09-07 18:0x UTC -- S3 GATE ANSWERED: the searched teacher FAILS it, and not because of a bug '
          'this time. With all three sampler defects fixed the teacher is 9.478 tiles from the pro vs the student '
          "3.34-3.48, exact cell 0.00 vs 21.9-23.9. The oracle check is what settles it: the nearest candidate "
          'the teacher ACTUALLY EVALUATED sits 1.68 tiles from the pro and the objective rejected it for one 13.5 '
          'tiles away -- reachability is fine, the greedy one-shot rollout objective disagrees with pro doctrine '
          '(§5cs.90). Next: opponent model (rollout currently lets the opponent do nothing), one shard, ~20 min.** '
          'Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
