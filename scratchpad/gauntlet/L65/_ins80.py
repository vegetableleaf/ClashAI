p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L65/_sec80.md", encoding="utf-8").read()
a = "### §5cs.79 -- L64v"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 02:1x UTC -- S2 IS DONE")
L[163] = ('**2026-09-07 02:2x UTC -- S3 HAS A MACHINE: clashbot-s3 (n2-standard-8, 34.173.75.16) is RUNNING with '
          '/dev/kvm and 16 vmx flags; the sandbox is NOT Windows-locked (~200 lines of PowerShell orchestration '
          'is the whole port) and a nested-KVM AVD boot test is running on it. HunterCR footage is genuinely '
          'mineable but holds only ~19-34 matches = +0.03 pp on the measured curve; 78-139 video-hours would buy '
          'one doubling (§5cs.80). Two match-counting errors of mine retracted there.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
