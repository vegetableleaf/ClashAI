**GAUNTLET L65 — footage verdict + VM is live. Two questions at the bottom.**

**Your footage is good — my earlier objection does not apply to it.** Portrait full-screen (888×1920 / 592×1280, 60 fps), fixed camera, whole board in frame, card hand + next card + elixir bar all visible, and the game prints its own deploy label at the placement ring ("Ice Wizard lvl 16") — free card-identity ground truth. **96% of the runtime is live battle** (you cut the menus), which is unusually high yield.

**But there is ~50× too little of it. Measured:** 19 matches (lower bound) to ~34 (upper) across the 96.7 minutes — about 170 s of battle per match. Against our 1,638-replay corpus that is +1.2–2.1%, which on the slope we measured last night (+1.50 pp per corpus *doubling*) is worth **+0.03 pp**. **One doubling would take 78–139 hours of this footage.**

**Two errors of mine, retracted:** my first match counter said "1 match per file" — wrong, because it looked for menu gaps and you cut the menus out; the opponent name in `HunterCR_1` cycles through four different players inside that single "match". The fix I wrote next was *also* wrong: it needed a name-crop change above 0.12, while real name changes measure 0.09. Both were thresholds I never calibrated against their own noise. Third version works.

**VM: up and nested virt is real.** Your quota error was my fault — I read the *regional* N2_CPUS (200) and told you no request was needed; the binding cap was the *global* CPUS_ALL_REGIONS = 12. `n2-standard-8` costs you nothing: $300 buys ~6,100 core-hours either way. Confirmed on the box: 8 vCPU, 31 GB RAM, `/dev/kvm` present, 16 `vmx` flags, `kvm-ok` passes. A VM core is 0.79× this box's on integer, 0.56× on float — but uncontended, against a local box that has been pinned at 90–100% all night.

**Sandbox port is small.** A survey with file:line citations says it is not Windows-locked in any deep sense: it runs the real `libg.so` inside a stock Android AVD, no Windows binary anywhere in the execution path, no Python dependencies at all. The entire port is ~200 lines of PowerShell orchestration — **half a day to a day**. Right now I'm booting a stock AVD on the VM to test nested KVM, which needs zero game files and can kill the cloud plan cheaply if it fails.

---
**Q1 — can you supply ~80–140 hours of footage like this?** If HunterCR is a channel you can pull from at that scale, mining becomes a real scaling lever and I'll build it. If these 3 files are what exists, mining them buys +0.03 pp for days of work and I'd rather spend those days on S3. **Answer with roughly how many hours you can get.**

**Q2 — may I copy the game runtime to the VM?** The sandbox needs ~1.15 GB of game binaries (APKs + `libg.so` + DataTables) that are explicitly *non-redistributable* — the sandbox repo ships none of it. Putting files you obtained legally onto a cloud VM you control is plausibly fine, but it's your call and your account, not a default I should take for you. **Yes / no.** If no, S3 search runs on this box only and the VM gets stopped so it stops billing.

**Cost:** ~35 min. Running: AVD boot test on the VM. §5cs.80.
