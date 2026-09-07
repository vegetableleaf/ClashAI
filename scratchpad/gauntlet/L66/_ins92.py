p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec92.md", encoding="utf-8").read()
a = "### §5cs.91 -- L66j"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 18:4x UTC -- OPPONENT-MODEL HYPOTHESIS IS DEAD")
L[163] = ('**2026-09-07 19:4x UTC -- HORIZON HYPOTHESIS DEAD TOO, AND INFORMATIVELY: the rollout SATURATES '
          '(h1200 and h2400 choose identically in 18/18; 9.09 -> 8.35 tiles then nothing), so the objective is '
          'not short-sighted. ALL THREE cheap explanations are now eliminated (unit term, opponent, horizon) on '
          'top of the oracle check. What remains is a rebuild (search over action SEQUENCES) or a change of plan '
          '(pro agreement may be the wrong gate for a search teacher) -- posted to the owner, §5cs.92. VM idle '
          'and billing; left up because I cannot restart it.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
