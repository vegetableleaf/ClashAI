p = "HANDOFF.md"
s = open(p, encoding="utf-8").read()
anchor = "**H. The blocker that is the owner's to decide, not mine.**"
assert s.count(anchor) == 1
add = ("**G-RESULT (a), `~/kvm_test.json` on clashbot-s3.** The nested-KVM unknown is settled: the stock AOSP 31 "
       "x86_64 AVD booted headless with `worker.py`'s exact flags in **35 seconds** (`boot_completed=1`), `kvm-ok` "
       "reports acceleration usable, `adb root` succeeds (uid=0, which the sandbox requires and is why Google Play "
       "images are rejected), and the whole Android SDK + system image pulled in 53 s. That is bare-metal-class "
       "boot time, not the degraded nested-virt case the survey warned about. **The cloud plan survives its "
       "riskiest test, and it was tested with zero game binaries.** What this does NOT establish: emulator boot is "
       "not engine throughput -- how many replay-drives per hour a VM slot sustains is unmeasured and needs the "
       "runtime, i.e. it is behind the question in H.\n\n")
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(anchor, add + anchor, 1))
print("ok")
