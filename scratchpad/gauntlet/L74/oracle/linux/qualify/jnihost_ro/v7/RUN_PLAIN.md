# Running the oracle, in plain steps

This is a plainly-worded companion to `README.md` (which stays as the precise spec). It is the
operational runbook for the native-engine oracle: our own small Android host process loads the real
Clash Royale game library (`libg`, build 160402012) inside an empty Android emulator, steps it, and
reads its state, so DIFFSIM can compare our simulator against the real game.

Nothing here contains addresses, offsets or secrets; those live only in the private, git-ignored
`scratchpad/gauntlet/L70/reader/oracle_160402012/` directory.

## What is already done (2026-10-13)

On the VM `clashbot-oracle-2` (GCP, project `clashbot-oracle`, zone `us-east1-c`):

- the Android SDK, emulator and build tools are installed;
- an empty Android guest (`emulator-5554`, API 32) boots inside a network namespace with **no way
  out** (`cr-oracle-1000`), so the game can never reach the internet;
- the real game (version 160402012, all five APK files, hashes verified) is **installed** in that
  guest — installed only, never launched;
- the host kit is **built** (`ORACLE_V7_BUILD_OK`);
- one staged run has been done. **It stops at the same place every time**, see "Where it stops".

So to make progress you do **not** need to re-provision. You go straight to "Make one attempt".

Connect to the VM:

```bash
ssh -i ~/.ssh/runpod_clashbot clashbot@<oracle-2 IP>
# the IP changes on restart; read it with:
#   C:\Users\benpe\tools\google-cloud-sdk\bin\gcloud.cmd compute instances list --project clashbot-oracle
```

## If you ever start from a blank VM

Run these once, in order, from `~/ClashBot` on the VM. Each is safe to re-run.

1. **Provision** (installs the SDK, emulator and libraries; needs internet, on the host only):
   ```bash
   bash scratchpad/gauntlet/L74/oracle/linux/setup_vm.sh 1
   ```
   If it added you to the `kvm` group, log out and back in once.
2. **Boot the empty guest** (inside the sealed namespace):
   ```bash
   bash scratchpad/gauntlet/L74/oracle/linux/boot.sh 1
   ```
   Wait for `Empty Android guests ready`.
3. **Install the game into the guest** (the five APK files from the private kit; install only):
   ```bash
   source scratchpad/gauntlet/L74/oracle/linux/common.sh
   K=~/ClashBot/share/clashroyale_160402012_kit/apk
   ns_run "$ADB" -s emulator-5554 install-multiple -t \
     $K/base.apk $K/split_config.en.apk $K/split_config.hdpi.apk \
     $K/split_config.x86_64.apk $K/split_install_time_asset_pack.apk
   ```
   Expect `Success`. Confirm it is the right build:
   ```bash
   ns_run "$ADB" -s emulator-5554 shell dumpsys package com.supercell.clashroyale | grep versionCode
   # expect versionCode=160402012 minSdk=32
   ```

## Make one attempt

Each attempt is a single run and cannot be resumed; to try again you start a fresh one.

1. **Build the host kit** (compiles our loader; does not touch the game). If it says
   `BUILD_BLOCKED` with `BUILD_EXISTS_RETAINED`, an old build folder is in the way — move it aside
   and build again:
   ```bash
   B=scratchpad/gauntlet/L74/oracle/.local/jnihost-ro-build-v7
   [ -e "$B" ] && mv "$B" "$B.old_$(date +%s)"
   bash scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/worker.sh build
   # expect: ORACLE_V7_BUILD_OK
   ```
2. **Find the running emulator's process id:**
   ```bash
   pgrep -f 'qemu-system-x86_64.*oracle_160402012_api31_0'
   ```
3. **Run one staged attempt.** `--stage-limit` is how far it is allowed to go; it stops earlier the
   moment anything fails. Start with the first real stage:
   ```bash
   Q=scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7
   bash "$Q/worker.sh" run --emulator-pid <PID> --serial emulator-5554 \
     --stage-limit create_game_main
   ```
   The last line prints `PRIVATE_RUN=<a new folder>`. That folder holds the evidence.
4. **Read the result:**
   ```bash
   bash "$Q/worker.sh" review "<that PRIVATE_RUN folder>"
   ```
   The review tells you the last stage that completed, the stage that blocked, and whether the
   cause is understood.

The stage names, in order, are: `load-only`, `create_game_main`, `game_main_init`,
`data_tables_range`, `data_load_tasks`, `loading_state`, `map_resources`, `battlefield_cache`,
`manager_update`. You raise `--stage-limit` one step at a time as each earlier stage passes.

## Where it stops right now (measured 2026-10-13 17:14 UTC)

The run gets cleanly through loading the library and its startup hook, then **dies the instant it
enters `CreateGameMain`**:

```
last completed stage : jni_on_load
blocking stage       : create_game_main
crash                : java.lang.NullPointerException: read field GameApp.d on a null object
                       -> Fatal signal 6 (SIGABRT), return code 134
```

In plain terms: the game, as it starts, calls its own `GameApp.isEmulator()`, and that reads a
field on a `GameApp` object. We handed it nothing (a null), so it crashes. This is the known,
expected wall, not a new problem.

## The one remaining change (yours to make)

To get past `CreateGameMain` the host must hand the game a real `GameApp` object, so that
`isEmulator()` can run and answer. The owner's decision (2026-10-13) is: answer **truthfully first**
("yes, this is an emulator"), because the VM genuinely is one; only if the game refuses that do you
switch to the "not an emulator" compatibility answer.

The exact design for this — which object to make, which field to set, and how `isEmulator()` reads
it — is already written up in the private, git-ignored file:

```
scratchpad/gauntlet/L70/reader/oracle_160402012/gameapp_re/V8_DESIGN.md
```

This is the step I (Claude) keep getting stopped on by the safety system, which is why it is left to
you. Everything up to and including the run/review loop above is working and verified.

## Rules that stay in force

- **No internet for the game.** It runs only inside the sealed `cr-oracle-1000` namespace. The
  scripts check this before and after every run.
- **One attempt per run.** Do not treat raising `--stage-limit` as "retrying"; each launch is its
  own fresh attempt with its own evidence folder.
- **Keep every attempt's evidence.** The `PRIVATE_RUN` folders are the record of what happened.
- **Stop the VM when idle.** It bills about $0.78/h. Stopping it keeps the disk and everything set
  up; only the IP changes.
  ```bash
  C:\Users\benpe\tools\google-cloud-sdk\bin\gcloud.cmd compute instances stop clashbot-oracle-2 \
    --zone us-east1-c --project clashbot-oracle
  ```
