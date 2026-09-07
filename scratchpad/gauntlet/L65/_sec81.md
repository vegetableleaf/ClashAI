### §5cs.81 -- L65c (2026-09-07 02:0x-02:3x UTC): **the sandbox's Linux port is written and its two riskiest lines are TESTED GREEN on the VM, using zero game binaries. A tar assumption of mine was load-bearing and is now verified rather than asserted; a patch of mine was broken and was caught by reading it back**

**A. What was built.** `scratchpad/gauntlet/L65/port/` -- `start_direct_service.sh` (the 175-line PowerShell launcher), `stop_direct_service.sh` (25), `worker_linux.patch.py` (four platform branches in `native_core/worker.py`, idempotent, `--check` mode), `runtime.env.sh.example`. The port lives in scratchpad because the sandbox sits under `research/ext/`, which this project never commits; the patch script applies it to the working tree on demand. **Not applied yet** -- the Windows path is what drives corpora today and there is no reason to touch it before the runtime question is settled.

**B. The launch nesting is green (a), `scratchpad/gauntlet/L65/port/_port_probe.sh` run on clashbot-s3.** The survey named this as the trap: `nohup sh -c "cd ... && exec env CLASSPATH=... app_process ..." >log 2>&1 </dev/null &`, handed to `adb shell` as one argument and re-parsed by the guest shell, fails as a service that starts and instantly exits with no diagnostic but an in-guest log. Tested with `env` and `sleep` standing in for `app_process`, on the live AVD:

| check | result |
|---|---|
| `CLASSPATH` arrives intact in the guest | yes, both paths, `:`-joined |
| `LD_LIBRARY_PATH` arrives intact | yes |
| backgrounded process survives the adb session closing | yes |
| `service_pids()` awk matcher finds it by class + root + subcommand | yes, pid 2281 |
| `adb forward tcp:37031` round trip | established, listed |
| `push` + host/guest sha256 agreement (`push_verified`) | yes |

So the real launch differs from the tested one only in which binary is exec'd.

**C. A load-bearing assumption of mine, verified not asserted (a).** The `.ps1` runs `tar.exe -xf <asset-pack>.apk` (`start_direct_service.ps1:110`). Windows' `tar.exe` is bsdtar/libarchive, which reads zip archives -- and an APK is a zip. I claimed GNU tar cannot, and replaced that one call with `unzip`. Tested on the VM against a real zip: **GNU tar 1.34 fails, `unzip` works.** The claim holds, and a mechanical `.ps1 -> .sh` transliteration would have died at exactly that line with "This does not look like a tar archive". This trap is not in the portability survey.

**D. My own patch was broken, caught by reading it back (c).** The first draft of edit 3 wrapped the existing `command = [...]` in `if os.name == "nt":` and stopped -- which leaves `command` **undefined on Linux**, the exact platform the patch exists for. `--check` reported "4 anchors matched" and told me nothing about it, because an anchor matching is not the same as a replacement being correct. Fixed by replacing the whole block including both branches. **The general lesson, which is the same one as §5cs.80 D: a check that only confirms the thing you already believed is not a test.**

**E. What is still unmeasured and why (b).** Engine throughput per VM slot -- replay-drives per hour against the local box's 11.24 s/match median -- cannot be measured without the game runtime, which is behind the owner's ruling in §5cs.80 H. Everything cheaper than that ruling has now been done: nested KVM (§5cs.80 G-RESULT, 35 s boot), the adb mechanics, the launch quoting, the asset-extraction path. What remains is `sdkmanager`/`avdmanager` bootstrap (deferrable convenience) and the first real engine start.
