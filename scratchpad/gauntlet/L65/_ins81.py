p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L65/_sec81.md", encoding="utf-8").read()
a = "### §5cs.80 -- L65 "
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 02:2x UTC -- S3 HAS A MACHINE")
L[163] = ('**2026-09-07 02:3x UTC -- THE SANDBOX LINUX PORT IS WRITTEN AND ITS RISKIEST LINES TEST GREEN on '
          'clashbot-s3 with zero game binaries: launch nesting, adb forward, push+sha, ps matching, and the '
          'GNU-tar-cannot-read-an-APK substitution all verified (§5cs.81). Nested KVM boots an AVD in 35 s '
          '(§5cs.80 G-RESULT). Remaining S3 work is behind ONE owner ruling: may the non-redistributable '
          '1.15 GB runtime be copied to the VM. Box idle; VM billing ~$0.39/h.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
