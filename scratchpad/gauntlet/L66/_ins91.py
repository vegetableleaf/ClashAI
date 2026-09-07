p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec91.md", encoding="utf-8").read()
a = "### §5cs.90 -- L66i"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 18:0x UTC -- S3 GATE ANSWERED")
L[163] = ('**2026-09-07 18:4x UTC -- OPPONENT-MODEL HYPOTHESIS IS DEAD: replaying the opponent\'s real plays '
          'through the rollout made pro agreement slightly WORSE (9.48 vs 9.09 tiles, closer in only 3/18 '
          'states), so the leading explanation from §5cs.90 C is eliminated (§5cs.91). S3 gate remains answered '
          'and failed; cause is the objective; no cheap hypothesis left for what the scoring rule should be. '
          'Next candidates: horizon sweep (one flag, one shard), then the question of whether pro agreement is '
          'the right target at all -- an owner call.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
