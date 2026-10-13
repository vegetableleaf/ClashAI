# ORACLE: Linux/KVM port for 160402012

> ORACLE v3 supersedes the original and v2 boundaries below. Scheduling/control
> DATA writes, direct unmodified game calls and proven presentation patches are
> allowed. See [V3_REPORT.md](V3_REPORT.md) for current findings, private binding
> status and offline VM run order. The original audit below is historical, including its
> blanket code-write prohibition and online SDK provisioning instructions.

Status: **BLOCKED at native deployment; infrastructure preparation and static audit only.**
Changes are uncommitted. No VM connection, emulator launch, APK installation, game
execution, protection modification, live-process operation or networked sandbox
test occurred in this ticket. No target VM address/connection was supplied.

## Stop condition and evidence

The premise that this sandbox executes a wholly unmodified loaded library is not
true for its documented `serve-direct` path. The original APK files can remain
unchanged while the host modifies executable memory:

- `android_probe/README.md`, Surface rule, explicitly allows version-specific
  presentation bypasses.
- `android_probe/java/royale/nativehost/JniHost.java:194` routes both direct
  profiles through `nativeInitGameMain` (call at line 205).
- `android_probe/native/jni_bridge.cpp:2945` describes five guarded presentation
  edits during initialization. Lines 3005–3037 make code writable, modify it,
  execute initialization, restore bytes, and restore permissions.
- The same method at lines 3045–3085 installs a **persistent resource-variant
  code replacement**. It saves bytes for comparison but does not restore them.
- `nativePumpDataTables` and `nativePumpManager` also contain loading/home
  presentation code writes (around lines 3824 and 4032).

These are observed code modifications, **not evidence of a protection/integrity
bypass**. Whether 160402012 would require such a bypass is unknown. The supplied
constraint also requires an unmodified app/libg, so this port does not transplant
those patches, relax byte guards, replace the library with the captured image,
or start any sandbox profile. There is no skip-check/unsafe override.

`deploy.sh` and native `health.sh` deliberately return **78** with this blocker.
They are stop receipts, not completed deployment/acceptance implementations.
`setup_vm.sh` and `boot.sh` implement preparation of **empty Android guests**.
The unresolved outcome is a native referee for 160402012, not just Linux tooling.

## Source identity and private evidence

Sandbox checkout HEAD: `81e5dffab764324033889970bba8a57494857cde`.
It already had an uncommitted JNI area-effect timer correction before this work;
that file and every upstream file were left untouched. The local API document
also describes unverified buff/area extensions; the v6 label does not certify them.
Exact source hashes, every constant and numeric source site are in the private
inventory. This avoids relying on the smaller bindings JSON as a complete list.

Private directory (already covered by repository ignore rules):
`scratchpad/gauntlet/L70/reader/oracle_160402012/`.

| File | Meaning |
|---|---|
| `derive.py` | Standard-library-only static inventory, APK member hashing, ELF symbol inspection and export normalization; no binary execution |
| `inventory.json` | 101 constant declarations, 3,224 numeric source lines, symbol/signature sites and source hashes; deliberately over-inclusive |
| `artifact_manifest.json` | Five APK hashes, 14 x86_64 library hashes and 423 selected APK asset members; package versionCode still needs aapt/installed-package verification |
| `candidate_values.json` | Reader-derived observation candidates, eight static function leads checked against recovered function entries, normalized string-reference leads; NOT installable bindings |
| `derivation_receipt.json` | Input hashes, counts, image identity, privacy and non-execution scope |

The supplied archive's libg digest was measured and matches the owner's
`79c4e485…918c2` fingerprint. Full value is private. The captured analysis image
has a different hash and must never be substituted for the original library.
The export contains **74,565 recovered functions and 493 selected
decompilations**, not 74,565 decompiled functions. Absolute addresses and generated
function names are normalized using the module base recorded in `analysis.json`;
function-entry/RVA consistency was checked for every recovered function.

The simple ELF section-based dynamic-symbol inspection found no `JNI_OnLoad` or
matching GameApp export. This is a bounded negative result, not proof that the
normal app loader cannot initialize it. The upstream dlsym-based bootstrap has
not been established for this build. Do not work around it with a decrypted image.

## Windows deployment, in order, and Linux equivalents

| Step | Existing Windows implementation | Linux equivalent / qualification |
|---|---|---|
| 1 | Git, Python >=3.11, JDK17, SDK command-line tools; WHPX/Hyper-V | Ubuntu22.04 x86_64, usable `/dev/kvm`; JDK17; SDK Linux tools; explicit `emulator -accel-check`. Ubuntu's system Python3.10 can run preparation/derivation, but native bindings require separately provisioned Python >=3.11 |
| 2 | Create venv; `pip install -e .` | Use a Python >=3.11 venv and install sandbox editable only after the native blocker is resolved; no need to run `worker.py` to build Python code |
| 3 | Verify runtime ZIP digest; expand into empty `runtime/` | Verify all private inputs before extraction; isolate a new 160402012 runtime directory. Never merge it into the old runtime |
| 4 | Dot-source `runtime.env.ps1` | Export SDK/JDK/AVD paths in `linux/common.sh`; keep runtime manifests, inputs and logs private |
| 5 | `bootstrap.ps1`: licenses, SDK, rootable AVD | `setup_vm.sh N` uses exact packages listed below and `avdmanager create avd` |
| 6 | `prepare_runtime.ps1`: extract libraries and tables/map | Read original APK ZIP members; hash every file; retain complete matching dependencies and overlay provenance. Static `derive.py` inventories but does not create a runtime |
| 7 | `freeze_runtime.ps1`, `doctor.ps1` | Compare against a separately reviewed build-specific manifest; old hashes are rejection criteria, not values to overwrite until deployment passes |
| 8 | `build_probe.ps1`, `build_bridge.ps1` | JDK `javac` + D8 JAR, NDK Linux clang++ commands below. The probe is a **DEX JAR plus JNI SO, not an installable probe APK** |
| 9 | `native_core.worker` launches rootable headless AVD | `boot.sh N` creates isolated empty guests; console ports spaced by two. Upstream `worker.py` hardcodes `.exe` and PowerShell and cannot simply be invoked on Linux |
| 10 | `adb root`; install all five APK splits | Future authorized native path: `adb -s SERIAL install-multiple -r -t` with all five matching files, then verify installed versionCode and split hashes, not merely package presence |
| 11 | `start_direct_service.ps1`: hash-check/push libs, JAR, bridge, base APK, replay and asset tar | Equivalent ADB operations must run inside the isolated namespace, use atomic temporary uploads and verify SHA256 before rename; this stage is blocked |
| 12 | Forward TCP, launch `app_process`, poll ping/status | Same Android command/classpath/LD_LIBRARY_PATH; no system-service APK is involved. `serve-direct` reaches the prohibited code writes, so no Linux launcher is emitted |
| 13 | Smoke, full-card/forms/match-rule suites and ten cold probes | See ACCEPTANCE.md. Old golden hashes, RNG and tower values cannot certify the new build |
| 14 | Stop only owned slots; optionally stop owned AVD | No broad `pkill`, no unrelated emulator shutdown. Preparation does not touch existing host ADB or live-game sessions |

Exact SDK package IDs from `scripts/bootstrap.ps1`:

```text
platform-tools
emulator
platforms;android-35
build-tools;35.0.0
ndk;27.3.13750724
system-images;android-31;default;x86_64
```

Guest: AOSP Android12/API31, x86_64, **default**, not a Play image. Compile API35
is distinct from guest API31 and JNI minimum API23. AVD device profile `pixel_2`,
four cores, 4096MiB, 10G data. Port mapping: instance i uses console
`5554+2*i`, ADB `5555+2*i`, future service `37031+i`. N is limited to 1 or 2 on
the specified 8-vCPU VM; start with 1. Upstream can place multiple service slots
in a single guest; these scripts deliberately assign one future slot per guest.

Boot flags preserve the documented baseline:

```text
-no-window -no-audio -no-boot-anim -no-snapshot
-gpu swiftshader_indirect -accel on -memory 4096 -cores 4
```

The SDK emulator package is not version-pinned upstream. Preparation records the
installed revision. Current Android docs deprecate `swiftshader_indirect` starting
with emulator36.4.9; if the installed revision rejects it, stop and qualify an
explicit renderer change rather than silently changing it. KVM availability must
be proven on this VM; merely seeing the device node is insufficient.
Sources: [Android acceleration](https://developer.android.com/studio/run/emulator-acceleration),
[sdkmanager](https://developer.android.com/tools/sdkmanager),
[avdmanager](https://developer.android.com/tools/avdmanager).

Build translation, for review after a compatible native path exists:

```bash
# B is a new PRIVATE build directory; S is the sandbox source directory.
mkdir -p "$B/classes"
mapfile -d '' sources < <(find "$S/android_probe/java" -name '*.java' -print0)
javac --release 8 -g -classpath "$ANDROID_SDK_ROOT/platforms/android-35/android.jar" \
  -d "$B/classes" "${sources[@]}"
mapfile -d '' classes < <(find "$B/classes" -name '*.class' -print0)
java -cp "$ANDROID_SDK_ROOT/cmdline-tools/latest/lib/r8.jar" com.android.tools.r8.D8 \
  --debug --min-api 23 --lib "$ANDROID_SDK_ROOT/platforms/android-35/android.jar" \
  --output "$B/lifecycle-probe.jar" "${classes[@]}"
NDK="$ANDROID_SDK_ROOT/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64"
"$NDK/bin/clang++" --target=x86_64-linux-android23 -std=c++20 -fPIC -shared \
  -O2 -g -Wall -Wextra -Werror -I"$NDK/sysroot/usr/include" \
  "$S/android_probe/native/jni_bridge.cpp" -ldl -o "$B/libnative_core_probe.so"
```

This translates the existing build, **not** its compatibility. The unchanged
bridge is for 150535029 and may not be loaded with 160402012. Upstream renames the
SO on device to `libnative_host_bridge.so`. Its service uses a slot-specific
directory under `/data/local/tmp/`, JAR plus base APK in CLASSPATH, all matching
SO dependencies in LD_LIBRARY_PATH, and Java main `royale.nativehost.JniHost`.

## Build-specific dependency register

All **values**, per-site offsets, byte sequences and candidates live only in the
private files above. This public register gives the complete identified families
and derivation procedure. The lexical inventory captures unnamed literals as
well as the named constants; it is a review checklist, not a claim that grep can
prove an ABI correct.

| Family / source | What must change or be revalidated for 160402012 | How to derive / stop rule |
|---|---|---|
| APK set and runtime ZIP; `bindings/runtime-manifest.json` | Package/game version, ABI, all file sizes/hashes, ZIP digest, member set | Hash original five splits and every native/asset member. Use `aapt2 dump badging` and `apksigner verify --print-certs` for each split, then installed `dumpsys package`/pulled split hashes. No build assertion from directory name alone |
| Runtime dependencies | All 14 old SO names, SONAME/DT_NEEDED closure, load order, libc++/FMOD/Titan components | Inspect each target ELF and the normal package loader. Target inventory also contains 14 libraries; count equality does not prove compatibility |
| Java/JNI bootstrap | GameApp/Titan declarations and descriptors, callbacks, package context, `CreateGameMain`, `JNI_OnLoad`, dynamic-loader base convention | Compare original APK Java declarations and native registration/imports, then a permitted unmodified initialization path. Minimal Titan/Quago/service stubs must not suppress integrity checks |
| All named native address constants; both bindings files | Manager globals/init/update, state factory, replay setters/outer loader/controller, core and outer update, command constructors/executors, account/player/hand/ability accessors, selection/deployment, alloc/free/string/JSON | Follow current constructors/callers/string xrefs and prove signatures, receiver types, ownership and return codes. Normalize each export address. No global address delta, no old-RVA fallback |
| Resource startup constants | Thread options, clocks, singleton, stage/battle-data roots, asset-system init/get/prepare/roots/mounts, save/cache/temp getters, loader, task pump, table load, location fields, request-list ctor/append/load/dtor, cache construction | Trace resource and table loaders plus arena/tilemap requests in the exact build. Existing 493-function selection leaves large gaps |
| Presentation guards/shims | Renderer/device/resolution/object/late configuration, loading/platform UI, home graphics and resource-variant byte guards | **Blocked.** Inventory original sites only. Do not derive replacements or transplant patches under this ticket |
| Native object layouts | Manager/state/battle/logic fields, root/context chain, game/helper fields, table-ready flags and allocation sizes | Constructors, stores, getters and recorded observations must agree. Reader root/context traversal does not prove it is the same C++ manager object used by the sandbox |
| Replay/string/JSON ABI | Native strings, JSON object ownership, account IDs, native deck entries, levels/forms, outer-loader behavior and RNG seed | Trace parser/constructor/destructor and outer replay initialization. Preserve `rndSeed` and replay content; do not swap in inner JSON loader because towers happen to appear |
| Commands and grids | Command allocation size and fields, vtable destructor slot, execution flags, ability opcode/result codes, hand index, side/account mapping, selection temporary layout | Derive constructors/executors/validator in target; preserve native refusal. Recheck arena scaling, grid layout, legal-placement behavior |
| Native observations | Entity arrays/counts/strides, generation/type/side/position/definition/level, components, HP, behavior/targets, attack/move/collision/path fields, projectile/effect vtables and timers | Inventory all literal reads, widths, bitfields, vtable indices and bounds. Reader notes give candidates for a subset, not a replacement bridge. Recheck empty/invalid/incoherent behavior |
| Buffs and areas | Buff manager/entry/data layout, ownership, source/controller, duration/stacking/shield semantics and area lifetime/radius | Phase2 static getter/ctor/update evidence; correlate independently. Reader proves a remaining-time interpretation. Existing local bridge partly corrects it; old prose remains stale |
| Players/abilities | Player pointers, hand/cycle/elixir/refill, action slots/body membership, charges/cooldown/pending/cast state, costs and enum names | Target player/action routines and table loaders. Phase2 state-code vocabulary differs from old sandbox mapping. Do not reinterpret absent data as ready |
| Tick/RNG/hash/terminal | RNG representation, 50ms update contract, phase/command-gate fields, tiebreak/terminal latch, pointer-free hash coverage | Derive from target updates and validate trace. Local extension emits fields outside existing v6 certificate coverage; host hash alone is insufficient |
| Assets / catalogs | Old 383 tables plus two maps; target 421 table members plus two maps; device-update overlay; card/form/ability catalogs | Hash and keep compressed source vs decoded/overlaid data distinct. Preserve repeated sections/inheritance. Native row IDs must come from actual registry/selector evidence, not text row order |
| `native_core/card_catalog.py`, `decks.py`, `env.py`, `deployment.py` | Catalog version/form IDs/costs, level range, form flags, category mappings, result/ability state names, arena and tower masks, termination interpretation | Build a new catalog from target native data and pinned assets; test raw native API separately from convenience/enrichment rules |
| `native_core/worker.py`, acceptance scripts/examples/docs | Frozen opening tower HP/RNG/hash, standard card/evo/hero counts, replay schema, duration/elixir phases, all revision claims | Preserve old certificate only for 150535029. Establish a reviewed 160402012 fixture and expected values before acceptance; never tune expectations to make failed runs pass |

The old ZIP is documented as five APKs, 14 libraries and 383 tables, plus README
and checksum files; maps reside in the asset pack and are added during deployment.
This checkout's runtime is an unpacked local directory (no bundle README or
SHA256SUMS present), with the measured old libg fingerprint and the old counts.
It is not evidence that an original ZIP checksum was verified here.

`FINDINGS.md` supplies previously observed projectile/effect/form candidates.
`re_phase2/FINDINGS_P2.md` supplies static buff/ability candidates and expressly
disclaims live validation of those additions. The device-update overlay described
there is needed to match the owner's live content, including Hero Ice Wizard;
the APK alone is a reproducible build baseline, not the fully established live
asset set. Reconstruct the overlay from retained verified inputs offline; never
download it by launching the sandbox online.

## Safe worker commands on the VM

Run as the non-root VM login user in a private checkout. Transfer private inputs
through the owner's existing secure channel; no publication or remote commit.
Install the official Linux SDK Command-line Tools ZIP into
`$HOME/Android/Sdk/cmdline-tools/latest` first, verifying its separately obtained
official checksum. That is the same manual prerequisite as upstream. Provision
Python >=3.11 separately before any future native-binding installation.

```bash
cd /path/to/private/ClashBot
export ANDROID_SDK_ROOT="$HOME/Android/Sdk"
O=scratchpad/gauntlet/L74/oracle
P=scratchpad/gauntlet/L70/reader/oracle_160402012
git check-ignore -v "$P/derive.py" "$P/candidate_values.json" "$O/.local/logs/setup.log"
python3 "$P/derive.py"             # offline static evidence only
for f in "$O"/linux/*.sh; do bash -n "$f"; done
bash "$O/linux/setup_vm.sh" 1      # host downloads; no guest/game runs
# Log out and back in if setup added this user to the kvm group.
shellcheck -x -P "$O/linux" "$O"/linux/*.sh
bash "$O/linux/boot.sh" 1          # optional: one EMPTY offline Android guest
bash "$O/linux/health.sh" --infrastructure 1
# health exits 78 even if infrastructure passes: native acceptance is blocked.
bash "$O/linux/deploy.sh"           # exits 78 before build, push, install or launch
```

For two guests use `2` consistently in setup/boot/infrastructure checks. Logs are
appended under `oracle/.local/logs/`; emulator logs are per serial. Re-running
preparation reuses matching AVDs, checks image identity, does not wipe data, and
rejects conflicting ports. The scripts do not delete namespaces or stop guests.

The named Linux namespace `cr-oracle-<uid>` contains only loopback, with no veth,
default route, host proxy or host ADB server. Namespace structure is asserted
before launch and after boot. The emulator's guest NAT cannot reach the VM's
external NIC or metadata service from that namespace. ADB/client work must run
inside it; a future localhost service must never be exposed on the host NIC.
Host SDK provisioning is online; sandbox execution must remain isolated from its
first instruction. This design is source-reviewed, **not VM-tested** here.

## Verification and remaining work

See `VERIFICATION.json` for current local checks. Git Bash failed to start on this
Windows sandbox with `CreateFileMapping ... Win32 error 5`, so no local `bash -n`,
shellcheck, KVM, AVD, native build or acceptance pass is claimed.

To unblock native work, first establish a documented, unmodified-code path that
can provide stepping and replay behavior on 160402012. A visible/offscreen app
lifecycle is not automatically a deterministic referee and has not been qualified.
Do not continue by implementing protection bypasses. If such a path exists, finish
the private ABI and asset/catalog derivation, independently review every candidate,
then implement deployment and run ACCEPTANCE.md in the isolated VM. This ticket
does not authorize changing the constraints to permit the observed patches.
