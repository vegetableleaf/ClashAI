# Sandbox portability survey -- can cr-native-sandbox run on Ubuntu 22.04 x86-64?

Read-only survey. Nothing run, installed, or modified. Subject:
`C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox` (vendored, upstream
`github.com/IMAX9D/cr-native-sandbox`, MIT for the *source only*). All file:line refs are relative
to that directory unless prefixed.

## 1. What the sandbox actually is

**It runs the real game's native x86_64 code, headless, inside a stock Android emulator (AVD).**
Not a reimplementation, not box64/qemu-user, not a Python rewrite of the battle logic.

- `README.md` L3: "基于原版 Android x86_64 `libg.so` 的无界面《皇室战争》标准 1v1 沙盒" -- headless
  1v1 sandbox on the *stock* `libg.so`. L21: "仓库**不包含 GUI、AI、模型或学习代码**".
- README section `extracted-assets\`: "这些文件由原版 `libg.so` 解析，不是 Python 重写的战斗数据"
  -- the CSV DataTables are parsed by the original `libg.so`, not by Python.
- The AVD is **AOSP Android 31 x86_64** (`system-images;android-31;default;x86_64`), created by
  `scripts/bootstrap.ps1`, pinned 4 vCPU / 4 GB / 10 GB data (README 1.5). Google Play images are
  rejected because `adb root` is required.
- Execution model: **host x86_64 -> hypervisor (WHPX today, KVM on Linux) -> Android 31 x86_64
  system image -> `app_process` -> `libg.so` at 20 Hz.** The game's own code executes natively on
  the host CPU (x86_64 guest on x86_64 host). The emulator supplies the Android *userland/OS*, not
  CPU emulation.
- `native_core/worker.py:147-155` is the only emulator launch:
  `emulator -avd royale_worker_api31 -port 5554 -no-window -no-audio -no-boot-anim -no-snapshot
  -gpu swiftshader_indirect -accel on -memory 4096 -cores 4`.

### Binaries, and where they come from
All from a **Runtime ZIP the user must obtain legally themselves** --
`cr-native-sandbox-runtime-150535029.zip`, SHA-256 `82b2e79e...c4310`, explicitly not in the GitHub
repo (README 1, README 9). Contents (README 1.3): 5 split APKs; 14 x86_64 `.so` (`libg.so` = battle
core, SHA-256 `fa6704b8...246ba`, plus `libc++_shared`, `libfmod`, `libfmodstudio`,
`libsupercell_clashroyale`, `libflutter`, `libsentry*`, ...); 383 DataTables CSVs under
`csv_client/` + `csv_logic/`; and `assets/locations/training_arena.csv` +
`assets/tilemaps/tilemap.csv` pulled from the asset pack. Frozen: game `15.535.29`, runtime
`150535029`, Android x86_64, 20 Hz, observation protocol `public-observe-v6` (README 8).
`pull_apks_bluestacks.sh` is an alternate acquisition path off a BlueStacks install.

### What "port 37031" is
A **host TCP port that `adb forward` maps into the guest**, where a headless Java+JNI service
listens and speaks newline-delimited JSON.

- `scripts/start_direct_service.ps1:141-142` -- `adb forward --remove tcp:$Port`, then
  `adb forward tcp:$Port tcp:$Port`.
- `start_direct_service.ps1:145` is the engine launch itself:
  `cd '$RemoteRoot' && exec env CLASSPATH='<lifecycle-probe.jar>:<base.apk>'
  LD_LIBRARY_PATH='$RemoteRoot' app_process /system/bin royale.nativehost.JniHost '$RemoteRoot'
  serve-direct '$Port'` -- the repo's own `royale.nativehost.JniHost` class, which reaches `libg.so`
  through `libnative_host_bridge.so` (pushed from `artifacts/libnative_core_probe.so`,
  `start_direct_service.ps1:104`). `$RemoteRoot` = `/data/local/tmp/cr-native-direct-<slot>`
  (`:22`).
- Client is plain Python sockets: `native_core/client.py:36-37` (`host="127.0.0.1"`, `port=37031`).
- Slots: `native_core/worker.py:66-67`, `service_base_port=37031`, `direct_base_port=38031`; slot N
  = port 37031+N, 1..8 workers. `worker.py:205-225` (`configure_direct_ports`) additionally maps
  38031+N straight through emulator NAT (`adb emu redir add`), bypassing the adb proxy.
- So **one engine slot = one `JniHost serve-direct` process inside the one shared AVD**, one port
  each. `research/sandbox_tools/replay_batch.py:83` merely defaults `--port 37031` and passes it to
  `replay_drive.drive(...)` (`:124`), one TCP session per replay tag; it has no platform-specific
  code of its own.

## 2. Platform dependence

### Windows-specific
1. **All orchestration is PowerShell** -- 12 `.ps1` in `scripts/` plus `runtime.env.ps1`, with no
   shell equivalent. `native_core/worker.py:57-58`
   `shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"`, invoked at
   `worker.py:286-287` (start service) and `:345-349` (stop). **The Python worker cannot start an
   engine slot without PowerShell.** This is the one hard dependency.
2. **`.exe` hard-coded, unguarded**: `worker.py:76` `sdk_root / "platform-tools" / "adb.exe"`;
   `worker.py:80` `sdk_root / "emulator" / "emulator.exe"`.
3. **NDK host triple**: `scripts/build_bridge.ps1:8-9`
   `toolchains\llvm\prebuilt\windows-x86_64\bin\clang++.exe` + matching sysroot. The *target* is
   already `x86_64-linux-android$ApiLevel` (`:20`) -- only the host half is Windows.
4. **JDK tool paths**: `scripts/build_probe.ps1:13-14` `bin\javac.exe`, `bin\java.exe`.
5. **`tar.exe`**: `start_direct_service.ps1:108,110,113` (build asset tar, extract 2 CSVs from the
   asset-pack APK, append them).
6. **Win32 CIM calls**: `scripts/doctor.ps1:154-172` -- WHPX state and
   `(Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled`; `:196` `Get-PSDrive`.
   Diagnostics only.
7. **Hard-coded `C:\` defaults**: `runtime.env.example.ps1:18` `C:\Android\Sdk`, `:23`
   `C:\Program Files\Eclipse Adoptium\jdk-17`, `$env:LOCALAPPDATA` at `:27,:42`. These are
   *template defaults the user edits*, not baked into code -- `worker.py:27-37` deliberately
   resolves every path from `CR_SANDBOX_*` env vars "with no personal fallback".
8. **The vendored `.venv/` is a Windows venv** (`.venv/Lib/site-packages`, `Scripts/python.exe`);
   `research/sandbox_tools/replay_drive.py:22` documents invoking it that way.
9. `worker.py:54` `subprocess.CREATE_NO_WINDOW` -- already guarded by `if os.name == "nt"`, non-issue.
   `worker.py:518-519` -- error text says `. .\runtime.env.ps1`, cosmetic.

### Already POSIX-friendly
- **Everything inside the guest is Linux already.** Android *is* Linux: the guest half of
  `start_direct_service.ps1` is `sh -c`, `mkdir -p`, `tar -xf`, `nohup`, `kill`, `sha256sum`,
  `ps -A -o PID,ARGS`, `app_process`. Unchanged by a Linux host.
- **No Windows binary is anywhere in the execution path.** I verified `runtime/x86_64-libs/libg.so`
  and `artifacts/libnative_core_probe.so` are both ELF64 (`7f 45 4c 46 02 ...`), and
  `artifacts/lifecycle-probe.jar` contains `classes.dex` -- i.e. already dexed for Android. The
  host never loads `libg.so`; there is no host-side native code at all.
- Grepping `os.name|sys.platform|win32|\.exe|C:\\` over `native_core scripts tests examples` hits
  **only** `worker.py` (54, 57-58, 76, 80, 518-519) and three "dot-source runtime.env.ps1" strings
  in `scripts/accept_*.py`. `client.py`, `env.py`, `deployment.py`, `card_catalog.py`, `decks.py`,
  `data/`, all of `tests/` and all four `scripts/*.py` have zero platform branches.
- `research/sandbox_tools/replay_batch.py` is fully portable -- `Path(__file__).resolve()`,
  no subprocess, no drive letters.
- `pyproject.toml` declares **no dependencies at all**: pure stdlib, Python >=3.11. (`:17` claims
  `Operating System :: Microsoft :: Windows`, but that is metadata, not a technical constraint.)
- `pull_apks_bluestacks.sh` is already bash (its `ADB=`/`SB=` at :12-13 are Windows paths).
- Emulator, SDK, platform-tools, NDK and JDK 17 all ship first-class Linux builds.

## 3. What a Linux port would require

**(a) Trivially portable.** `client.py`, `env.py`, `deployment.py`, `card_catalog.py`, `decks.py`,
`data/`, `tests/`, `scripts/*.py`, `replay_batch.py` -- no changes. `worker.py:76,80` -- drop the
`.exe` (~2 lines). Venv -- `python3.11 -m venv .venv && pip install -e .`, no wheels to fight.
Config -- `runtime.env.ps1` becomes `runtime.env.sh` exporting the same `CR_SANDBOX_*` vars, which
`worker.py` already reads. **And the two host-independent prebuilt artifacts can simply be copied**
(`artifacts/lifecycle-probe.jar` 24 KB dex; `artifacts/libnative_core_probe.so` 1.1 MB, built for
`x86_64-linux-android23`), which removes host JDK 17 and NDK from the critical path entirely for a
runtime-only deployment. If you did want to rebuild, `build_bridge.ps1:8-9` needs
`windows-x86_64` -> `linux-x86_64` -- a 2-line change.

**(b) Needs work.**
- **Rewrite `start_direct_service.ps1` (175 lines) + `stop_direct_service.ps1` (25) as shell**, and
  point `worker.py:286-287,345-349` at them. This is the only genuinely required piece. Mechanical:
  `Get-FileHash` -> `sha256sum`, `tar.exe` -> `tar`, and `Invoke-JsonRequest` (`:77-97`, a raw TCP
  JSON-line round-trip) -> a few lines of Python. **Half a day to a day.**
  *Risky part:* the launch string at `:145-146` is quote-nested three deep
  (`nohup sh -c "cd ... && exec env CLASSPATH=... app_process ..." >log 2>&1 </dev/null &`). Wrong
  quoting yields a service that starts and instantly exits, whose only diagnostic is
  `tail /data/local/tmp/cr-native-direct-0/service.log` (README 7). Budget debugging here.
- **Rewrite `bootstrap.ps1` (97) and `doctor.ps1` (233)** for the Linux SDK layout
  (`sdkmanager`/`avdmanager` shell scripts, not `.bat`); `doctor.ps1:154-172` becomes a `/dev/kvm`
  check. Convenience/diagnostics, **half a day, deferrable**. Same for `smoke.ps1` (137) and
  `accept_direct_core.ps1` (129).
- **Nested KVM is the real unknown.** On Linux `-accel on` (`worker.py:152`) means KVM, and the
  target box is itself a VM with nested virtualisation on -- so this is the Android emulator's KVM
  inside a guest. Nested KVM works but is slower than bare metal and is a classic flakiness site.
  **Untested for this workload; I have no measurement either way.** Benchmark it first rather than
  assuming. The AVD is pinned to 4 vCPU / 4 GB (`worker.py:68-69`), so 8 vCPU / 31 GB comfortably
  hosts one AVD; whether it usefully hosts two is likewise untested.
- `-gpu swiftshader_indirect` (`worker.py:151`) needs the emulator's bundled SwiftShader plus the
  usual `libpulse`/`libGL` shared libs on a headless Ubuntu image -- a couple of `apt` packages.

**(c) Blocked / artifact risk.** **Nothing is technically blocked** -- every binary in play is
already an Android x86_64 ELF. The one real constraint is **legal/practical**: the 1.1 GB runtime
is not redistributable (README 9 -- the repo ships no APK/`.so`/assets, "Runtime 由使用者自行合法
取得", and the MIT licence explicitly excludes the third-party game binaries). Copying your own
legally obtained files onto a Linux VM you control is one thing; a shared/cloud host or any repo is
a different question. **Flagging, not ruling.** Separately, the version freeze is unforgiving
(`libg.so` must hash `fa6704b8...246ba`, re-verified against `bindings/runtime-manifest.json`);
hashes are platform-independent so the freeze transfers intact, but no newer APK can substitute.

## 4. Asset / data dependencies (measured with `du`/`ls`)

| What | Where now | Size | Runtime? |
| --- | --- | ---: | --- |
| 5 split APKs | `runtime/apks/` | **964 MB** (asset pack 886 MB, `split_config.x86_64` 78 MB, `base` 47 MB) | Yes -- `adb install-multiple`; asset pack also yields `training_arena.csv` + `tilemap.csv` (`start_direct_service.ps1:110-111`) |
| 14 x86_64 `.so` | `runtime/x86_64-libs/` | **75 MB** (`libg.so` 28 MB) | Yes -- pushed to `/data/local/tmp/cr-native-direct-<slot>/` each start |
| 383 DataTables CSVs | `runtime/extracted-assets/` | **4.6 MB**, 385 files | Yes -- tarred to `artifacts/runtime-assets.tar` (4.0 MB), unpacked in-guest |
| Prebuilt artifacts | `artifacts/` | 1.1 MB + 24 KB + 108 KB | Yes -- but copyable (see 3a) |
| Card catalog | `native_core/data/live_card_catalog.json` | 154 KB | Yes -- committed, no action |
| Android SDK + system image + AVD | `C:\Android\Sdk`, `%LOCALAPPDATA%\Android\avd` | several GB | Yes -- **re-download on Linux, do not copy** |
| Replay corpus for `replay_batch.py` | `icebow/data/royaleapi/crawl2/` (`battles.csv`, `plays_ext.csv`, `plays_ext_i1.csv`, `payloads/`) | **89 MB** | Yes, for replay driving (`replay_drive.py:39,142,146`) |

**Total to move: ~1.15 GB runtime + ~89 MB replay corpus.** `runtime/`, `artifacts/`, `.venv/`,
`runtime.env.ps1` and `*.so`/`*.apk`/`*.jar` are all in `.gitignore` -- none of it is in git, so the
move is an rsync/scp, not a clone. Secrets: the ClashBot side has files under `*/data/` paths (e.g.
an `icebow/data/` webhook file named in project memory) -- **the path exists; I did not open or list
its contents, and none of it is needed by the sandbox.**

## Bottom line
Not Windows-locked in any deep sense. Everything touching the game's code is Android/Linux already;
the Windows layer is *orchestration only* -- ~200 lines of PowerShell wrapping `adb`, plus `.exe`
suffixes in two properties. Real work: one rewritten start/stop script pair (half a day to a day,
quoting is the trap), the SDK/AVD bootstrap (deferrable), and the **untested** question of how the
Android emulator's KVM behaves nested inside this VM. The binding constraint is the
non-redistributable 1.1 GB runtime bundle -- a licensing question, not an engineering one.

STATUS: complete
