p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
sec = open("scratchpad/gauntlet/L66/_sec84.md", encoding="utf-8").read()
a = "### §5cs.83 -- L66b"
assert s.count(a) == 1
s = s.replace(a, sec + "\n\n" + a, 1)
L = s.split("\n")
assert L[163].startswith("**2026-09-07 04:4x UTC -- DECK IDENTIFIER CALIBRATED")
L[163] = ('**2026-09-07 05:3x UTC -- FIRST ENGINE SLOT RUNNING ON LINUX: start_direct_service.sh returns '
          '{"ready": true, "mode": "serve-direct", "slot": 0, "port": 37031} on clashbot-s3 in 14.2 s, libg.so '
          'loading and serving inside a nested-KVM AVD. No line of the port needed repair; the one trap was that '
          'installing the APKs lives in worker.py, not the start script (§5cs.84). Engine THROUGHPUT is the next '
          'measurement. 100-video icebow sweep running in parallel.** Previous line: ' + L[163])
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("ok")
