# ORACLE v4: read-only runtime qualification kit

Status: **prepared for worker execution; no VM run, native build, installation,
target execution, runtime qualification or patch qualification performed here**.
Zero patches qualified. The v3 binding remains unchanged. This ticket forbids
the data writes and direct game calls permitted by the older v3 ticket.

This is normal-original-app observation. It does not establish the upstream
strict no-Surface/app_process host, deterministic stepping, reset, replay
injection, or safe future patching. Those are separate work.

## Files and trust boundary

- `worker.sh`: namespace wrapper for build, preflight, install, install-probe,
  collect. Uses existing `linux/common.sh`; never invokes old `deploy.sh`.
- `build.sh`: copies `android_probe` privately and adds a build target requiring
  `ORACLE_READ_ONLY=ON`. Compiles only `native/oracle_readonly.c`, copied from
  `observer.c`. The original upstream sources are untouched.
- `observer.c`: standalone native external probe; attaches by opening the main
  app's proc memory descriptor **O_RDONLY**, not by ptrace. Reads maps, stat,
  cmdline and bounded memory ranges. There is no target-write command.
- `qualify.py`: APK/signature/version checks, installed-file identity, ELF
  mapping/load-bias resolution, live named JNI symbol lookup, pointer-chain
  polling, bounded existing logcat collection and private failure receipts.
- `review.py`: offline sample review, with separate transition and state evidence.
- `results.schema.json`: result contract. `review.py` also enforces unique,
  complete lifecycle/site IDs (JSON Schema item enums alone cannot do this).
- `test_qualify.py`, `verify.py`, `GATES.md`: offline checks and acceptance ledger.

The upstream probe is a DEX JAR plus JNI SO, **not an installable APK**. Its
`probe-direct`/`serve-direct` paths call `nativeInitGameMain`, which temporarily
patches initializer code and installs a resource-variant replacement;
`nativePumpDataTables`/`nativePumpManager` also write code. Other profiles invoke
game lifecycle methods and are not attach-only substitutes. Merely suppressing
the patch routine would still leave target calls and data writes. The private
read-only build excludes **all** upstream Java/JNI source from its link, rather
than relying on a mutable run-mode branch. Only the external executable is
installed; no probe APK, JAR or bridge SO is loaded into the game.

All private values are read at runtime from:

- `scratchpad/gauntlet/L70/reader/oracle_160402012/runtime-160402012-x86_64.json`
- sibling `artifact_manifest.json` and `v4-readonly.json`.

The supplement records the few field/root facts still expressed only in v3
prose, with hashes of the source disassemblies and the unchanged binding. Its
GameMain singleton is a candidate until the live vtable agrees. No captured
addresses are used as live pointers. No captured analysis ELF is loaded.
Copy the entire private binding directory with the share kit; do not commit it.
Run/build outputs must remain under git-ignored paths, with owner-only creation
permissions. Raw maps, pointers, hashes, logcat and symbol deltas are private.

## Exact environment and deployment order

Use **`system-images;android-31;default;x86_64`**, AOSP Android 12/API 31,
root-capable userdebug/eng, profile `pixel_2`. Do not substitute Google Play,
Google APIs, ARM translation or a different API. This is the image selected by
the existing setup, not a claim that this game build has passed on it.
Compile tools remain platform API 35, build-tools 35.0.0, JDK 17, NDK
27.3.13750724; the standalone probe targets API 31. Python 3.10+ suffices for
this kit. CMake, pip and Gradle are not required. One 4-core/4096-MB AVD fits the
8-vCPU/31-GB VM; use one for this campaign.

The emulator package/system-image revision was not pinned by setup. Retain
SDK `source.properties`, AVD config, emulator version, guest build fingerprint,
KVM acceleration receipt and probe binary hash. Do not download anything during
this qualification run. Missing tools/images are a provisioning handoff.

1. The worker copies the private checkout, unchanged five-split APK directory,
   binding and supplemental evidence over SSH **outside** the sandbox. Host
   internet does not authorize guest network. Keep all emulator/ADB processes
   and build commands inside `cr-oracle-<uid>`, which has loopback only and no
   external routes. Never add veth/NAT/proxy or reuse a host ADB server.
2. Run offline checks below and `bash -n`/ShellCheck on the VM. Boot with the
   existing `linux/boot.sh 1`; it roots the AOSP adbd as part of infrastructure
   setup. Do not root the app, alter SELinux, remount system partitions or change
   app debuggability. Record `readlink /proc/<emulator-or-adb-server-pid>/ns/net`
   versus `/var/run/netns/cr-oracle-<uid>`; both clients/servers must agree. The
   wrapper and collector also reject non-loopback links/routes.
3. Preflight hashes every split, verifies its APK signature and matching signer,
   package/versionCode, and original embedded library SHA. The old manifest
   explicitly lacked package-version verification; this closes it on the VM.
   The exact set is `base.apk`, `split_config.en.apk`, `split_config.hdpi.apk`,
   `split_config.x86_64.apk`, `split_install_time_asset_pack.apk`.
4. Install the entire set in one `adb install-multiple` session on the empty
   qualification AVD, without `-r`, downgrade, clear-data or uninstall. Existing
   app data is a stop, not permission to replace it. Re-read installed split
   hashes and version. A missing update-overlay/download is a recorded gap;
   never substitute captured or reconstructed library bytes.
5. Build and install the external read-only probe. The build flag fails closed;
   no writable bridge is linked. Build outputs are private. A compiler import
   audit rejects debugger, memory-write, dynamic-loader and network imports.
   Inspect imports on the VM; the audit is a guard, not a formal proof of all
   binary behavior. Device installation hash must match the built executable.
6. Launch the unchanged app once using its manifest-resolved normal launcher
   activity. This naturally creates a Surface and normal app data; the
   **observer** does not write target code/data. Do not run any headless profile.
   Capture only the PID returned for the main package, not ancillary services.
   Do not automate login or click through credential/account prompts.
7. Collect short bounded windows during startup and any naturally reachable
   states, then review offline. Start early enough to catch LoadingState;
   post-load polling can miss initialization entirely. An observer failure or
   unexpected app exit is a stop: retain its receipt and normal logcat, do not
   retry by weakening protections. No stop/restart or reset is automated.

From the checkout root, after copying inputs and offline SDK preparation:

```bash
Q=scratchpad/gauntlet/L74/oracle/linux/qualify
P=scratchpad/gauntlet/L70/reader/oracle_160402012
python3 "$Q/test_qualify.py"
python3 "$Q/verify.py"
for f in "$Q"/*.sh; do bash -n "$f"; done
shellcheck -x -P "$Q/.." "$Q"/*.sh
bash "$Q/../boot.sh" 1
bash "$Q/worker.sh" preflight --out "$P/v4-run-preflight"
bash "$Q/worker.sh" install --out "$P/v4-run-install"
bash "$Q/worker.sh" build
bash "$Q/worker.sh" install-probe --out "$P/v4-run-probe-install"
```

Every output directory must be new. No overwrite or deletion is automated.
The build directory is `oracle/.local/qualify-build`; retain it for provenance.
`install` and `install-probe` deploy files, but never attach to or modify a game
process. `collect` does not install, launch, tap, change properties or write
target memory. The user-authorized distinction is deployment versus observation.

For startup, use two worker terminals. In terminal A, start the collector before
launch; wait for `READY_WAITING_FOR_ORIGINAL_APP`. This finishes the relatively
slow APK/installed-file hash checks before the app starts. It then waits for a
unique main-app PID and the original module for a bounded time; it never launches
the app or follows a replacement PID.

```bash
bash "$Q/worker.sh" collect --wait-seconds 120 --seconds 30 --interval 0.1 --out "$P/v4-run-startup"
```

In terminal B (set Q/P as above), resolve and launch normally in the namespace:

```bash
source "$Q/../common.sh"
linux_host
assert_isolated
COMPONENT=$(ns_run "$ADB" -s emulator-5554 shell cmd package resolve-activity --brief \
  -a android.intent.action.MAIN -c android.intent.category.LAUNCHER com.supercell.clashroyale | tr -d '\r' | tail -n 1)
[[ $COMPONENT == com.supercell.clashroyale/* ]] || exit 78
ns_run "$ADB" -s emulator-5554 shell am start -W -n "$COMPONENT"
PID=$(ns_run "$ADB" -s emulator-5554 shell pidof com.supercell.clashroyale | tr -d '\r')
[[ $PID =~ ^[0-9]+$ ]] || exit 78
# After terminal A completes:
python3 "$Q/review.py" "$P/v4-run-startup"
# For a later independent window on the same naturally running app:
bash "$Q/worker.sh" collect --pid "$PID" --seconds 30 --out "$P/v4-run-later"
```

If startup is missed, report it. The collector waits briefly for the module to
map and never inserts an early-launch hook. A manually initiated later
normal launch can be another separately labelled run; do not erase the first.
The interval is a minimum delay, not an achieved sampling rate; timestamps
record actual sampling duration and gaps. Start with 100 ms; faster polling
can perturb timing and still miss short phases.

## Probe list and what each can prove

`P` below means implemented proc polling; `L` means existing unmodified logs;
`H` means optional hardware-only observation subject to the strict rules below.
Review uses **observed state**, **inferred lifecycle**, and **observed execution**
as separate claims. No probe invokes the named routine.

| Binding item | Read-only experiment | Evidence and limit |
|---|---|---|
| `jni_on_load` | P: original installed hashes, ELF PT_LOAD/file-offset bias, loaded GNU dynamic-symbol lookup by exact name, compare bound delta | Establishes live named symbol delta and original backing-file identity, not JNI invocation. Embedded APK mapping offsets are accounted for; no `dlsym` call. |
| `create_game_main` | P: validated GameMain singleton/vptr and context; L: existing native creation marker if present | Constructed GameMain is lifecycle corroboration. Exact CreateGameMain reach needs an existing unambiguous log/trace; never instrument its environment-detection code. Missing evidence stays inferred. |
| `game_main_init` | P: GameMain vptr, init vtable slot and non-null mapped context; loading and manager appear; L: initialization marker | Confirms live receiver/layout and consequences consistent with init; does not prove that entry executed. A before/after context transition plus trusted log is stronger than a post-load pointer. |
| `data_tables_load_range` | P: task table/resources, resource count, range cursor, table-ready byte | Range progression corroborates native loading; seven-argument ABI and wrapper/provider forwarding require H at reviewed ordinary task call site, or existing trace. |
| `data_load_task_start` | P: task phase changes from idle to loading, table-ready initially false | Evidence of task state transition; exact start entry needs L/H. Already-loaded tables do not exercise this path. |
| `data_load_task_pump` | P: same task/root generation, cursor/phase sequence and readiness | Corroborates pump progress; log actual intervals and missed phases. No task/future spoofing. |
| `data_load_task_complete` | P: task's table-ready byte becomes nonzero | Readiness predicate data observed; does not prove the completion routine was called. |
| `loading_state_update` | P: LoadingState vptr, update slot, phase/task/future pointers and ready latch | Live dispatch target and changing state, not observed dispatch execution. Future pointers alone do not prove future completion. |
| `loading_state_complete` | P: complete slot, phase, resource gate and latch; L/H: native transition | Composite completion additionally needs coordinator count and actual future readiness. Those are not auto-decoded/called here; retain gap until native transition or reviewed trace corroborates them. |
| `resource_request_list_constructor` | H/L: naturally occurring map caller; receiver vptr and empty vector after constructor | Stack-local request is too transient for root polling. Must capture a real receiver; no invented heap scan or remote constructor call. |
| `resource_request_list_append` | H: same request before/after both native appends, argument pointers and resource names | Confirms FileName and TileDataFileName association and vector growth; full native argument ABI needs register/stack evidence. |
| `resource_request_list_load` | H/L: original request load and both resolved native payload pointers | Confirms native map request route; merely observing later battle state does not prove this loader. |
| `build_battlefield_cache` | H: native builder arguments and bounded cache row/count/capacity read using bound fields | Link both actual payloads and row instance ID into native cache. Absent object anchors leave this unobserved; do not call getters/builders. |
| `manager_update` | P: native manager global, current/pending type, state pointer/vptr and replay-data pointer | Observed manager transitions corroborate update; H/L needed for exact entry/ABI. Ignore the older reader manager candidate. |
| `battle_load_replay` | P: replay-data pointer and battle/state generation; H/L: outer battle-owned wrapper args/controller ownership | Replay pointer is insufficient to distinguish outer wrapper from inner JSON/controller loader. Capture normal replay transition only; never inject replay JSON or call setters. |
| `state_factory` | P: expected battle type from binding, state type, exact vptr, update slot and valid battle pointer | Corroborates BattleGameState discriminator when a real replay/battle exists. Special replay branches may differ and must remain separately labelled. |
| `battle_core_update` | P: float accumulator, battle tick and logic pointer within the same state/battle generation; H/L: dt/core entry if safely available | Tick increases establish advancement over sampled intervals. Accumulator can increase then wrap/decrease as steps are consumed. No assumption of one call = one tick or monotonic accumulator. |
| `skip_core_and_presentation_flag` | P: module pointer slot -> heap object -> member byte; RW/non-X mapping; object owner equals manager parent | Establishes live storage and sampled values. Null, reallocated or changed roots invalidate comparisons. Only naturally occurring byte changes count; a constant byte is not a failed flag and is not evidence that writes would be safe. |

Repeated roots/starttime checks reject observed races; they cannot exclude ABA
reuse or make multi-read snapshots atomic. Short reads, unmapped memory,
ambiguous load bias, different module identity or read denial stop the run.
The collector never scans arbitrary heaps and reads no saved account data.
Polling currently covers stable lifecycle roots; transient map/request/wrapper
arguments require a separately reviewed H/L observation, and remain explicitly
unobserved if unavailable. This is an honest runtime qualification plan, not a
claim that all eighteen items are automatically confirmed by the collector.

## Hardware observation: optional, disabled by default

No debugger implementation is bundled or auto-launched. Root proc access can
still be denied by Android policy; **do not** use ptrace to work around that.
If attachment/debug-register exposure is known or suspected to activate an
integrity/anti-debug path, mark `SKIPPED_PROTECTION_RISK` and do not attempt it.
Do not inspect, watch, intercept or alter those paths. Do not hide a tracer,
change TracerPid, relax SELinux, change dumpability or disable seccomp.

Only if the worker already has an independently reviewed safe hardware trace
facility on this guest: first prove its mechanism on a worker-owned throwaway
fixture. Require executable/data memory unchanged, hardware debug-register
events only, exact pre/post debug-register restoration and clean detach on
timeout/error. No `break`/`tbreak`, software fallback, uprobes, injected agents,
Frida, expression evaluation, target calls, PC edits, single-step emulation or
register manipulation other than hardware debug state is allowed. Debugger
startup and loader handling can install hidden software breakpoints; inspect
the actual tool behavior, not just its UI's "hardware" label.

Use at most the guest's measured hardware-slot capacity (x86 commonly four).
Capture TID, thread name, PC/module delta, ordinary stack/register arguments,
typed receiver, phase/frame and event time. Install across every relevant
thread including new threads or report missing coverage. Stop/resume overhead
must be recorded; no frozen-thread duration is a gameplay timing measurement.
Calibrate a watchpoint on a naturally advancing battle tick in a separate
window as a positive control. Record watchpoint widths/ranges and dropped
events. Silence in a few watched words is never proof of no battle writes.
Skip startup-only sites if they cannot be reached without debugger launch
hooks; keep their proof incomplete.

## Experiments for each of the ten unproven sites

Common controls: original app, no toggles/flags written, unmodified graphics,
normal naturally reached loading/Home/battle phases. For every run retain
receiver allocation identity, exact thread/PC/stack, phase/frame association,
transitive callees and typed write destinations. Main-thread execution is not
evidence against rendering: game rendering and simulation may share a thread.
Frame correlation is supporting evidence only. Use naturally occurring
foreground/lifecycle states, not forced target state. If the required state is
unreachable offline or without login, stop at that boundary.

| Site ID | Specific read-only experiment and falsifier |
|---|---|
| `renderer_bootstrap_call` | Observe normal initializer's shader bootstrap and registration callees. Type shader registry/Stage receivers and allocator ownership. Record actual resolved virtual targets. Any data-table, map, battle or shared-scheduler mutation makes rendering-only classification fail. Bootstrap is startup-only; late attachment cannot clear it. |
| `renderer_device_block` | Observe Stage creation/device/dimensions/viewport setup, with native allocation identities before/after. Enumerate constructor and virtual-call write targets, not just viewport fields. A gameplay/shared-root write or incomplete block boundary prevents proof. |
| `renderer_objects_block` | Trace normal UI object constructors and registrations against the same Stage, including destruction/refcounts. Distinguish Stage-owned UI from callbacks/registries shared with game state. Any retained battle reference or unknown constructor/registration effect remains unproven. |
| `renderer_late_configure_call` | Correlate viewport diagnostic, Stage receiver and resolved downstream virtual calls with actual presentation frames. Check dimension/viewport destinations and lifecycle effects. An untyped downstream write or gameplay dependency prevents proof. |
| `loading_presentation_call` | Identity must be discovered first at the natural completion boundary, using LoadingState vptr/phase/task/future timeline and ordinary UI receiver stacks. Separate UI drawing from task/future/phase writes. Do not use the rejected adjacent-call pair from v3; any phase/task mutation falsifies the proposed presentation-only identity. |
| `loading_platform_ui_call` | Independently identify actual platform/UI callback from native completion to existing Java/platform logs or reviewed stack, retaining receiver and thread. A LoadingState/task counter writer is not the missing callback. Required loading progress or unknown Java side effects prevent proof. |
| `game_presentation_toggle` | First identify a real native boolean presentation call during normal manager/Home transitions with typed GameMain receiver and observed argument. Exclude rejected version-text/resource-wait candidates. Correlate native field changes without setting the boolean. The shared core scheduling byte is not an equivalent toggle and its suppression would also affect simulation. |
| `home_resolution_block` | During a naturally reached Home, identify exact block extents, viewport/Stage receiver and downstream effects; compare normal later replay transition if accessible. Home absence in one offline run does not prove safe bypass. Any mixed state-transition write or uncertain boundary blocks proof. |
| `home_graphics_create_call` | Independently identify graphics constructor/call under Home with allocation owner, UI-resource provenance and all registration writes. Trace references until teardown. Reachability and strings alone do not identify the call; unknown callbacks or battle writes prevent proof. |
| `headless_resource_variant` | Record every observed caller, resource name/type, native tag and output dependencies for shader/texture AND map/tilemap loads. Type lookup, refcount and allocator destinations. A map/tilemap or shared non-rendering caller falsifies blanket rendering-only scope. Observe native empty/unsupported branches only if they occur; never alter tags/output. |

The already locally proven `renderer_resolution_call` remains a separate
control: confirm loaded receiver/vtable corresponds to the statically bounded
Stage callee. This does not authorize a patch and is not an eleventh unresolved
experiment.

**Promotion rule:** runtime evidence can falsify rendering-only, or strengthen
identity and bound observed effects. To establish rendering-only for all paths,
combine typed runtime receivers/resolved virtual targets with complete static
transitive write/caller coverage. Watchpoint silence, frame-only invocation,
or no battle object at startup cannot establish absence of battle effects.
No result of this read-only ticket qualifies a patch, even if classification
improves. Keep all patch qualification fields false.

## Results and risks

Every action writes a private `result.json`; collection additionally retains
APK receipts, maps, sample JSONL and bounded logcat. `review.py` writes a separate
`review.json`, never overwrites raw results or the binding. JSONL records contain
monotonic start/end times, read addresses/values, and an explicit non-atomic
marker. Preserve null pointers and failures; never turn an absent state into a
zero-valued successful observation. Function execution remains unconfirmed.

No account login is authorized. A fresh offline install may stop before Home,
downloaded assets, battle or replay. The app can require network/server session
and possibly an account for those states; this has not been observed on the VM.
Internet on the host does not change that. Label the observed boundary as
`UNREACHABLE_OFFLINE` or `UNREACHABLE_NO_LOGIN`, without entering credentials,
fetching assets, importing account state, injecting a replay or faking readiness.
Do not infer a login requirement solely from a generic offline error.

Other material risks: emulator/environment rejection; packed/changed live ELF
metadata; SELinux denial despite root adbd; missing original update overlay;
startup missed before attach; polling aliases accumulator cycles; races and
pointer reuse; version/signature mismatch; hardware watchpoint virtualization,
slot and thread limits; perturbation from debugging. Skip rather than bypass.
This collector does not investigate integrity/anti-tamper/anti-debug code.

Linux build/shell checks, Android access and all runtime experiments are worker
acceptance steps. Local offline tests cannot establish them. Leave all changes
uncommitted and retain zero qualified patches.
