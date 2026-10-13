# ORACLE v6: APK-aware, load-only JniHost

Status: an offline-built worker kit, not Android runtime qualification. See
`VERIFICATION.json` for measured checks. No client, libg, emulator or network was
run during v6 preparation. Changes are intentionally uncommitted.

## Contract and class ownership

The worker starts only `app_process /system/bin royale.nativehost.JniHost`.
Its CLASSPATH contains **only** `jnihost-ro.jar`, with our JniHost class. There
are no upstream GameApp/TitanApplication descriptor shells in either built DEX.
No package context, Application, Activity, service, asset initialization, native
startup routine, game loop, replay or battle is invoked by this host.

The collector reads the installed package's exact base and split APK paths using
`pm path`, verifies their hashes/version against the private manifest, and reads
the native library directory from `dumpsys package`. Base comes first, then
sorted splits; paths must share the same installation root. `nativeLibraryDir`
with an ABI suffix and `legacyNativeLibraryDir` without one are accepted only
when they agree on the installed x86_64 directory.

The host constructs `dalvik.system.PathClassLoader` with:

- DEX path: our separate `jnihost-loader.jar`, installed base APK, every split.
- Native search path: installed native directory, each installed APK's
  `!/lib/x86_64` directory, then our private guest scratch directory (observer).
- Parent: `JniHost.class.getClassLoader()`; context loader is also set to this child.

The child stub is loaded without initialization using `Class.forName(..., false,
loader)`. Its defining loader must equal the new loader or the host stops with
`HOST_STUB_PARENT_SHADOW`. The stub is intentionally absent from the parent DEX.
Static invocation then initializes only our stub, which has no static initializer.
All load calls occur in `royale.nativehost.AppLibraryLoader`:
`System.load` for our observer, optional dependency preloads, then exactly one
`System.loadLibrary("g")`. Android invokes JNI_OnLoad; we never call it manually.

This follows the documented [PathClassLoader constructor](https://developer.android.com/reference/dalvik/system/PathClassLoader)
and [JNI_OnLoad class lookup semantics](https://github.com/android/ndk/wiki/JNI).
It supplies classes and native lookup paths, but is not a full application
context. The FMOD failure's missing-class diagnosis is still **untested**.

The observer is loaded through the same child as libg, so its `RTLD_NOLOAD`
lookup uses that native namespace. The only exported JNI method is the stub's
`nativeRead`. It uses `dlopen(RTLD_NOLOAD)`, `dlsym`, `dladdr` and read-only
`/proc/self/mem` reads to check the JNI delta and candidate GameMain identity.
No bridge write API, patch, protection change, captured-image load, unpacking,
decryption, native function-pointer call or fabricated environment value exists.
Original app APKs/libraries/data are never modified by our code. Only our host
artifacts and receipts are written to fresh private scratch locations.

## Exact host run order

1. `class_loader`: construct the APK-aware loader and verify the stub's defining
   loader. Record APK/native paths and preload mode in a private event.
2. `observer_load`: load our read-only observer through the child stub.
3. `dependency_preload`: default is an explicit no-op, recorded as zero loads.
   With the opt-in flag, call `System.load` for each validated dependency in order.
4. `jni_on_load`: the stub calls `System.loadLibrary("g")`; record return and
   module/JNI/GameMain observation. An absent GameMain remains absent.
5. `stop_after_library_load`: emit the boundary and exit. No subsequent native
   init or client lifecycle method is called, even after success.

Any exception, signal, timeout, unsupported callback or missing class ends the
single attempt. Do not invent missing JNI methods or call protection to fix it.
If evidence establishes libg's own refusal, STOP with outcome **(b)**. No spoofing,
emulator hiding, integrity/anti-debug bypass, SELinux relaxation or network to
Supercell is permitted. The host does not reference or probe `dzmxszrox`.

## Worker commands (existing isolated Linux x86_64 emulator)

All JDK/SDK/NDK/system-image inputs and Python `jsonschema` must already exist.
Do not download tools/assets, launch the full client, or connect remote ADB.
Use the existing kit's loopback-only network namespace and API 32 guest. If no
owned guest exists, use `linux/boot.sh 1` only with a trusted offline AVD that
does not auto-start the client. An already running client blocks collection;
the worker never stops it or shared emulator services.

From the repository root:

```bash
Q=scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro
bash -n "$Q/worker.sh"
python3 "$Q/test_jnihost_ro.py"
python3 "$Q/verify.py"
bash "$Q/worker.sh" build
# Confirm the actual owned QEMU PID, namespace, port and oracle_ AVD first.
bash "$Q/worker.sh" run --emulator-pid "$ORACLE_EMULATOR_PID" --serial emulator-5554
# RUN is the newly created private result directory printed/recorded by the worker.
bash "$Q/worker.sh" review "$RUN"
```

Default build: `scratchpad/gauntlet/L74/oracle/.local/jnihost-ro-build-v6/`.
The new build path separates incompatible v5 artifacts; it does not authorize
retries after refusal. The collector verifies build/source hashes, pushes only
our two DEX jars and observer, checks guest hashes, and enforces a 45-second
stock guest timeout plus a 60-second ADB wait. APK and native backing identities
are checked again after collection. Network checks before and after require
only `lo`, loopback routes, matching process network namespaces and owned QEMU.
No outside service may change that namespace during the attempt.

`ATTEMPT.json` is written exclusively before the sole launch. Reusing an
attempted build fails before device access. Do not delete its latch, switch
flags or manufacture another build to retry a suspected refusal. Logs and
scratch artifacts remain for review; no cleanup callback runs on failure.

### Explicit preload fallback (default off)

Merely having `preload.txt` in the private build has **no effect**. To select it
before an independently authorized first attempt, add `--preload-dependencies`
to `worker.sh run`. This is a compatibility option, never an automatic second
attempt after a failed class-loader load. The class-loader route remains active.

The file lists the statically reviewed DT_NEEDED closure, one basename per line,
deepest dependency first: libc++_shared, SCID, FMOD, FMOD Studio, Sentry and
Sentry Android (use their actual `lib*.so` names). Names must be unique, limited to those six reviewed siblings, and present
in the private native manifest; libg and unrelated libraries are rejected. Missing/invalid files block;
nothing is silently skipped. Installed native files are hash-checked; otherwise
only the verified APK member is selected for the standard Android linker.
There is no extraction or retry if that member cannot be mapped. The selected
paths, file digest and native backing hashes are private receipts.

## Classes touched and risks

**Directly touched by the stub:** `royale.nativehost.AppLibraryLoader`,
`java.lang.Object`, `java.lang.String` and `java.lang.System` (including array
forms). It references no app class, constructs no app object, and has no static
initializer. The observer can create only a platform `java.lang.IllegalStateException`.

**Host framework classes:** `dalvik.system.PathClassLoader`, `java.lang.Class`,
`ClassLoader`, `Thread`, `System`, `String`, `Object`, `Throwable`, `Exception`,
`IllegalArgumentException`, `IllegalStateException`, reflection `Method` and
`InvocationTargetException`, `java.util.Arrays`, `org.json.JSONObject`,
`android.os.Process`, plus compiler/runtime support such as `StringBuilder`
and `java.io.PrintStream`. No client Application, Activity, protection or SDK
class is explicitly loaded, instantiated or invoked by host/stub code.

**Indirect execution is not proven absent.** Native constructors/JNI_OnLoad may
resolve and initialize app classes such as `org.fmod.*`, Sentry or SCID classes;
the actual transitive set is unmeasured. Their static initializers may load more
libraries, expect app context, write their own state, spawn threads or refuse.
Making APK classes available does not itself initialize every APK class. We do
not proactively look up those SDK classes. DT_NEEDED maps native dependencies;
it does not promise that each dependency's Java-facing JNI_OnLoad is invoked.
Explicit preloading does invoke the VM load path for each selected dependency.

This is read-only instrumentation, **not a side-effect sandbox for arbitrary
native initializers**. Offline network isolation prevents external connections,
but the loader cannot guarantee native code never attempts file writes or
transitive protection access. If receipts show a prohibited path or refusal,
stop; do not call, suppress, stub, patch or spoof it. In particular never inspect
or call `dzmxszrox` to repair a load. No runtime qualification is claimed here. Local Git Bash could not start
(Win32 error 5), so `bash -n worker.sh` must be checked on the Linux worker.

## Review and private evidence

Events are `ORACLE_V6`, schema version 2. v5 records cannot be promoted to v6
success. Success requires the exact ordered load-only event sequence, verified
child loader and matching paths/mode, preload count, JNI identity, exit zero,
and intact identity/isolation receipts. A review never authorizes another run.

| Outcome | Evidence and decision |
|---|---|
| **(a)** | Load and observation returned; stopped at the load-only boundary. GameMain absence is valid. No application, engine or rendering qualification. |
| **(b)** | Receipt-bound manual attribution to libg's own refusal. STOP. |
| **(c)** | Receipt-bound rendering attribution at the actual failing stage. STOP; no patches qualified. |
| `blocked` | Host/precondition/identity/isolation failure. Do not infer libg refusal. |
| `unclassified` | Generic crash, timeout, bad JNI version, missing class, registration failure or incomplete sequence. Cause unknown; STOP. |

To attribute (b)/(c), use an ignored finding JSON: `kind` (`libg_refusal` or
`rendering_dependency`), `origin: "libg"`, `reviewer`, `rationale`,
`result_sha256`, `stage` matching the failed stage, and `evidence` with `file`,
`sha256`, one-based inclusive `line_start`/`line_end`, exact `excerpt` from this
attempt's stdout/stderr. For (c), include `site_group`, nonempty `site_ids`, and
`site_mapping_basis`. Run `worker.sh review "$RUN" --finding "$PRIVATE_FINDING"`.
It writes `review-attributed.json` without replacing the original result/review.
Hash/line checks authenticate the receipt; causal attribution is the reviewer's
judgment. A host error cannot be overridden with a refusal finding.

The retained upstream presentation-site map is historical source context only;
v6 calls none of these steps and qualifies no patch:

| Upstream step | Site IDs |
|---|---|
| GameMain renderer | `renderer_bootstrap_call`, `renderer_device_block`, `renderer_resolution_call`, `renderer_objects_block`, `renderer_late_configure_call` |
| Resource variant | `headless_resource_variant` |
| Loading completion | `loading_presentation_call`, `loading_platform_ui_call` |
| Manager/Home | `game_presentation_toggle`, `home_resolution_block`, `home_graphics_create_call` |

Private runtime receipts remain under
`scratchpad/gauntlet/L70/reader/oracle_160402012/runtime_qualification/jnihost_ro/`.
Private builds contain the generated binding header, binaries, command logs and
source/artifact hashes. Public code/docs/tests remain offset-free. `build.py`
checks DEX class separation and observer exports/imports; `run.py` collects once;
`review.py` and `results.schema.json` describe load-only evidence;
`test_jnihost_ro.py`, `verify.py`, `GATES.md` and `VERIFICATION.json` record offline
verification. Compilation and mocked-device tests do not prove Android native
namespace resolution, FMOD/Sentry/SCID registration, or successful libg loading.
