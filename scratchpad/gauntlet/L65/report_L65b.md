**GAUNTLET L65b — nested KVM PASSES**

The one thing that could have killed the cloud plan is settled, and it cost nothing to test:

**Measured on `clashbot-s3`:** stock AOSP Android 31 x86_64 AVD, booted headless with the sandbox's own emulator flags — **`boot_completed` in 35 seconds**. `kvm-ok` reports acceleration usable, `adb root` returns uid=0 (which the sandbox requires, and is why it rejects Google Play images), and the whole Android SDK + system image downloaded in 53 s. That is bare-metal-class boot time, not the degraded nested-virt case the portability survey flagged as its one real unknown.

**Done with zero game binaries** — so we cleared the riskiest gate *before* moving 1.15 GB or asking you to rule on whether that move is OK.

**What it does NOT establish:** boot time is not engine throughput. How many replay-drives an hour a VM slot sustains is still unmeasured, and measuring it needs the runtime — so it sits behind Q2 from the last report.

**Still open, both yours:** (1) roughly how many hours of HunterCR-quality footage you can supply — 3 files is +0.03 pp, ~80–140 h is a real doubling; (2) may I copy the game runtime to the VM.

**Note on burn:** the VM bills ~$0.39/h (~$9/day) whether idle or not. I'm leaving it up because there's port work I can test against it, but say the word and I'll `poweroff` it — restarting needs one `gcloud compute instances start clashbot-s3 --zone=us-central1-a` from you.

**Next while I wait:** writing the Linux port of the sandbox's start/stop scripts (~200 lines of PowerShell — needed under any answer to Q2, and testable against the live AVD without game files).
