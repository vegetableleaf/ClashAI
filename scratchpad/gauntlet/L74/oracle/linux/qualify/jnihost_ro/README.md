# ORACLE v5: private read-only JniHost qualification

Status: worker kit, not a runtime qualification. The local verification receipt
records offline tests and compilation only. No client, libg or emulator was run
while preparing this kit. Leave everything uncommitted.

## Contract and exact stopping point

The worker starts only `app_process /system/bin royale.nativehost.JniHost` with
our private DEX and observer. `GameApp` is the upstream Java descriptor/context
shell, not the installed GameApp Activity or Application. No `am start`, monkey,
APK dex loading, account login, service, Surface, replay, battle or frame loop.
The installed original library enters through `System.load` and the VM's real
`JNI_OnLoad`; the observer never calls that export itself.

The sequence is:

1. Load the observation-only bridge; emit a before/after marker.
2. `System.load` the installed libg, then read module base and JNI delta.
3. Obtain the installed package's assets using upstream ActivityThread context
   creation. Use flags zero to exclude installed client code.
4. Bind the upstream context shell; call `TitanApplication.nOnNativeLibrariesLoaded()`.
5. Call `GameApp.nOnApplicationCreate()`.
6. Call `GameApp.createGameMain(...)` through its normal registered JNI method.
   Arguments use the upstream descriptor/display configuration, fresh host
   scratch directories and actual available disk space. Observe GameMain if
   published. A null pointer remains absent, never a successful object.
7. Exit before `nativeInitResources` and `nativeInitGameMain`. No hidden extra
   init function, scheduled task or retry follows this marker.

Only observation reads exist in the bridge: `dlopen` with `RTLD_NOLOAD`, `dlsym`,
`dladdr`, then read-only `/proc/self/mem` reads of the candidate GameMain slot
and its vtable for identity. The vtable check is not exported as extra state.
There is no write API, target function-pointer call, protection change, code
patch, debugger, unpacker or decryptor. Reads are not atomic. The real native
initializers naturally mutate their own objects/files; this is allowed native
initialization, not a claim that libg is a pure function. No data flags are set.

The original upstream bridge is copied for provenance but **never compiled or
loaded**. Its broad runtime observation and all mutating APIs are excluded.
The binding and v4 supplement supply only three private observation constants;
hashes tie these to the existing private evidence. They are static candidates,
not independently confirmed live addresses.

### Why the copy differs from upstream

Upstream `GameApp.isEmulator()` returns false. This private copy returns true
because this worker exclusively accepts the AOSP emulator. Android properties,
root status, verified-boot state, proc files and security policy remain intact.
`getAPKPath()` returns the actual installed source path when the shell exists;
otherwise it stops with a host-contract error.

Upstream ApplicationUtilBase, QuagoManager, BatteryMonitor, ThermalMonitor and
SnowplowTitan have synthetic device values or no-op adapter methods. The private
build preserves their native declarations, but concrete public callbacks stop
with `HOST_UNSUPPORTED_CALLBACK` instead of fabricating results or suppressing
an attestation path. A volatile latch also stops the next host stage if native
code clears that Java exception. This is a host limitation, never evidence that
libg itself refused. Do not replace that failure with a permissive adapter.
Other upstream UI/offline-service shells are retained; no property-hiding code
or new success response is introduced. Upstream sources remain unchanged.

The maximal implemented profile is upstream's minimal initialization, with a
conservative cap before direct resources. Upstream direct resource setup is
call-only but uses many old-version private entry points and constructs native
strings; this kit does not pretend those bindings are ported to the installed
version. A successful minimal profile therefore does **not** prove that the
very next call needs a patch. Direct resource callability is unmeasured.
The subsequent GameMain initializer is the known upstream patch boundary.

## Worker run order (Linux x86_64, offline)

All SDK/JDK/NDK/system-image inputs and Python `jsonschema` (offline tests only)
must already exist. Do not run online SDK
setup, download dependencies, fetch assets, connect a remote ADB endpoint or
relax SELinux. The installed exact split set must already match the private
artifact manifest. Do not invoke v4's full-client launch/collection workflow.

From the repository root:

```bash
Q=scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro
# Optional: only when an ORACLE guest is not already running, boot the existing
# offline AVD. This script contains no client launch or SDK installation.
bash scratchpad/gauntlet/L74/oracle/linux/boot.sh 1

# Parse the small shell wrapper on the worker before using it.
bash -n "$Q/worker.sh"
python3 "$Q/test_jnihost_ro.py"
python3 "$Q/verify.py"
bash "$Q/worker.sh" build

# Use the actual owned qemu-system-x86_64 PID, not an adb PID or unrelated guest.
# The existing .local/emulator-5554.launcher-pid is a candidate; verify it with ps.
bash "$Q/worker.sh" run --emulator-pid "$ORACLE_EMULATOR_PID" --serial emulator-5554

# Read the new private run's result.json, review.json and captured command logs.
# Optional read-only re-review; RUN is that private run directory.
bash "$Q/worker.sh" review "$RUN"
```

The existing boot script's historical AVD name contains an old API label; its
live API check must still report 32. Reuse an existing correctly isolated guest
when available. Neither this kit nor its review stops shared emulator services.
Do not boot from an untrusted snapshot that starts the client. If the client is
already running, v5 blocks without stopping it.

The wrapper checks the kit's loopback-only namespace. Inside it the collector
checks IPv4 and IPv6 routes, the exact emulator PID/port/AVD, ownership and
network-namespace identity. The only allowed interface is `lo`; every route
must use it. Host ADB connectivity is explicitly local to that namespace.
Emulator guest NAT may exist, but its QEMU process has no external interface or
route. Do not attach a veth, proxy, VPN, forwarded device or external backend.
The emulator must have been launched in this namespace with the kit's boot
script, not migrated from an online namespace with inherited external sockets.
The collector checks isolation again immediately before and after the host.
No outside service may reconfigure this namespace during the attempt.

The collector verifies the installed package version and exact APK split
hashes. If PackageManager installed an ordinary native file, its hash must
match. Otherwise it selects the matched installed APK member and asks Android's
standard linker to map it directly. This route is selected before launch; there
is no extraction, reconstructed ELF, captured-image loading, manual decryption
or alternate load attempt. A compressed/unmappable member is a linker failure
and STOP, never permission to unpack it. APK-member identity comes from the
verified whole-APK digest plus the private member manifest, not a new member
extraction. The backing file is hashed again afterwards.

Only our own observer and DEX are pushed, into a fresh private guest scratch
directory. Each guest artifact is hash-checked. The native observer has only
system-library dependencies. Stock guest `timeout` gives the entire host 45
seconds; the ADB wait is capped at 60 seconds. Success explicitly exits the host
to end any native threads. Failure never runs a cleanup native callback.

`ATTEMPT.json` is created exclusively in the private build before launch. A
second attempt from that build is rejected. Do not delete the latch, use another
build to evade it, or retry a suspected refusal. Nothing here starts an automatic
repair or fallback path. Guest logs and scratch files remain for review.

## Files and private outputs

- `JniHost.java`, `observer.cpp`: offset-free host and read-only observer.
- `build.py`: private upstream copy, conservative adapter changes, Java/DEX and
  Android shared-library compilation, imports/exports/dependency audit.
- `common.py`, `run.py`, `worker.sh`: identity, isolation and one-attempt collection.
- `results.schema.json`, `review.py`: result schema and evidence-bound review.
- `test_jnihost_ro.py`, `verify.py`, `GATES.md`, `VERIFICATION.json`: offline checks.

Private build: `scratchpad/gauntlet/L74/oracle/.local/jnihost-ro-build/`.
Private observations:
`scratchpad/gauntlet/L70/reader/oracle_160402012/runtime_qualification/jnihost_ro/`.
The code verifies git-ignore coverage and rejects tracked/out-of-checkout output
paths. Build manifests, private header, source copy, binaries, commands, process
paths, logcat, pointers, hashes of target artifacts and manual findings remain
there. Public source contains no target offsets or target hashes.

## Classification and presentation-site review

| Outcome | Evidence and decision |
|---|---|
| **(a)** | Exact ordered before/after/observation sequence, matching JNI delta, successful process exit, intact identity and isolation receipts, ending at the explicit minimal-init boundary. Report the last completed stage and actual GameMain status. No rendering failure is claimed. |
| **(b)** | Explicit diagnostic attributable to **libg's own refusal**, reviewed against the same attempt's output. STOP. No property, Java contract, loader, integrity, anti-debug or anti-tamper workaround. |
| **(c)** | Diagnostic/source attribution demonstrates a rendering dependency at the recorded failed stage. Report the evidenced site IDs from the map below. STOP before any patch; no site becomes patch-qualified. |
| `blocked` | Missing toolchain/identity/isolation, unsupported host callback, security denial or collection failure. No runtime cause is inferred. |
| `unclassified` | Generic crash, signal, timeout, linkage/registration error, obfuscated exception or incomplete sequence. Retain progress, mark cause unknown, STOP and report. Never guess (b) or (c). |

The current kit cannot reach the later direct-resource/GameMain/loading/Home
steps. The following is an **upstream source map**, not evidence that the
installed version requires any of these patches. A rendering failure before
that boundary needs its own attribution; do not assign all eleven sites to it.

| Upstream step | Presentation sites referenced there |
|---|---|
| GameMain init renderer setup | `renderer_bootstrap_call`, `renderer_device_block`, `renderer_resolution_call`, `renderer_objects_block`, `renderer_late_configure_call` |
| Resource variant selection (shim installed by nativeInitGameMain) | `headless_resource_variant` |
| Loading completion | `loading_presentation_call`, `loading_platform_ui_call` |
| Manager/Home presentation | `game_presentation_toggle`, `home_resolution_block`, `home_graphics_create_call` |

Source basis: upstream `android_probe/java/royale/nativehost/JniHost.java`,
`android_probe/native/jni_bridge.cpp` (`nativeCreateGameMain`, `nativeInitResources`,
`nativeInitGameMain`, `nativePumpManager`, `nativeInitManager`), and
`docs/SANDBOX_RUNTIME_TECHNICAL.zh-CN.md` sections 9-11. The build preserves their
hashes privately. Existing private binding evidence is not promoted by this map.

To attribute (b)/(c), write an ignored private finding JSON with `kind`
(`libg_refusal` or `rendering_dependency`), `origin: "libg"`, `reviewer`,
`rationale`, `result_sha256`, `stage` equal to the result's failed stage, and
`evidence` containing `file`, `sha256`, one-based inclusive `line_start` and
`line_end`, and the exact `excerpt`. The evidence file must be that attempt's
host stdout or stderr. For (c), also provide `site_group` (a key in the review's
upstream map), nonempty `site_ids` and `site_mapping_basis` explaining the
source/runtime connection. Then run:

```bash
bash "$Q/worker.sh" review "$RUN" --finding "$PRIVATE_FINDING"
```

This writes `review-attributed.json`; it never overwrites the raw result, prior
review or binding. Hash/line matching authenticates the cited receipt, while
causal attribution remains the named reviewer's judgment. A manual finding
cannot override a host/isolation error. No review authorizes another run.

## Risks and limits

The upstream Java descriptor set targets an older runtime. A new registration
contract may fail at JNI_OnLoad; report it without inventing missing methods or
loading the protected client's classes. libg may independently refuse the host.
The truthful/fail-closed adapters can stop initialization earlier than upstream's
permissive stubs. Assets supplied by the installed package may be insufficient
offline. No assets are downloaded and no account state is imported.

This probe deliberately does not port direct-resource bindings, test rendering
patches or exercise battle behavior. A successful (a) qualifies only this
bounded init path. Null/unreadable/unverified GameMain is retained explicitly.
File hashes do not prove runtime memory never changes itself; no whole-module
memory dump or decryption is attempted. SDK/NDK compilation proves syntax/linking,
not Linux process launch, Android JNI registration, init success or patch safety.
Local Bash syntax execution is recorded separately from offline compiler checks;
the worker must perform its `bash -n` check before use.
