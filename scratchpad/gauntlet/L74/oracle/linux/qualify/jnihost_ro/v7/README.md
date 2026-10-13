# ORACLE v7: direct native stages, zero patches

Status: **offline implementation; v7 Android attempt not executed here**. This
Windows workspace has no in-scope isolated Linux guest, and the ticket forbids
network access to the GCP worker. Do not interpret compilation, synthetic tests,
or the existing v6 outcome (a) as an observed v7 result. See `VERIFICATION.json`
and `GATES.md` for measured checks and the outstanding runtime gate. No commits.
[`REVIEW.md`](REVIEW.md) separates the verified v6 baseline, v7 offline work,
runtime unknowns and required handoff.

The parent directory retains the v6 host and review unchanged. Use **this**
directory's `worker.sh`, `build.py`, `run.py`, and `review.py` for v7. Artifacts
live under the ignored oracle `.local/jnihost-ro-build-v7/`; results live under
the ignored private binding directory's `runtime_qualification/jnihost_v7/`.
No original APK, native library, binding, v6 receipt, shared process or guest
configuration is edited.

## Stage ceiling and stop rule

`run --stage-limit NAME` selects an **inclusive ceiling in a single process**.
Default: `load-only`, preserving the v6 execution boundary. The complete choice
list, in order, is:

```text
load-only
create_game_main
game_main_init
data_tables_range
data_load_tasks
loading_state
map_resources
battlefield_cache
manager_update
```

Each stage runs once, in order, only after the preceding stage passes its
postconditions. Do not run increasing ceilings as a series of attempts. Select
the requested ceiling before the one authorized launch. `ATTEMPT.json` is
created exclusively immediately before launch; the collector refuses reuse,
including flag changes or another stage limit. Native dispatch also rejects
out-of-order/repeated stages and latches caught failure. Creating another build
is not authorization to retry. A reviewed libg refusal is **STOP (b)**.

There is no patch implementation, target data write, forged readiness,
scheduling-flag write, client Application/Activity, protection call, emulator
hiding, network client, credential handling, replay load or battle loop. Native
functions can modify their own state; that is the authorized initialization,
not read-only target execution. Instrumentation only reads target memory.

The first exception, missing prerequisite, unverified receiver, incomplete
native result, or bounded-poll exhaustion stops the attempt. Native signals
terminate the process; the existing stock guest watchdog kills a hung host.
Neither path retries or calls later stages. There is no cleanup target callback
on failure. Observer-owned request storage is passed to the real constructor;
no object bytes/vtable are synthesized. Normal request destruction happens only
after successful cache construction, using the native destructor.

## Evidence and call sequence

Source order is the lifecycle list in
[`SANDBOX_RUNTIME_TECHNICAL.zh-CN.md`, section 10](../../../../../../../../research/ext/cr-native-sandbox/docs/SANDBOX_RUNTIME_TECHNICAL.zh-CN.md).
Arguments and ABIs are taken from the named functions in
[`jni_bridge.cpp`](../../../../../../../../research/ext/cr-native-sandbox/android_probe/native/jni_bridge.cpp).
Those are older-build source evidence, **not target addresses or runtime proof**.
Target identities/layouts come from the ignored
`scratchpad/gauntlet/L70/reader/oracle_160402012/runtime-160402012-x86_64.json`
and its hash-bound `v4-readonly.json`. `binding.py` projects them into a private
`runtime-binding.json` consumed at runtime; compiled code contains enum indices
only. Build receipts bind the target manifest, private binding evidence, and
the exact upstream native/Java/lifecycle files used for this implementation.

| Stage | Actual call and arguments | Required observations / evidence |
|---|---|---|
| `load-only` | Parent v6 loader design: verified child `PathClassLoader`, observer load, optional explicit dependency preload, one `System.loadLibrary("g")`. Android calls JNI_OnLoad. | Live JNI delta equals binding; GameMain absent/identified/unknown remains explicit. Existing v6 receipt is outcome (a); v7 has not run. |
| `create_game_main` | Private `create_game_main` entry with the upstream JNI signature: environment, child stub class, real AssetManager, private data/cache/external paths, actual available bytes and framework display metrics, upstream graphics API selection, external-files path, **null Activity**. | Full returned string is logged; nonempty result stops. GameMain must identify against target vtable. `entries.create_game_main` and upstream `nativeCreateGameMain` are static evidence. |
| `game_main_init` | `GameMain::init(game, context)` directly, with context read from target GameMain; no helper-field assumptions or initializer patches. | Identified GameMain, nonnull context; post-call GameMain/loading phase/table readiness snapshot. Target entry plus `v4-readonly` context field. |
| `data_tables_range` | `DataTables::loadRange(tables, resources, 0, 0, 0, 0, resource_count)`; seven-argument wrapper, not the eight-argument implementation. | Manager current state must have target LoadingState vtable; task/table/resources must exist, count positive, task phase untouched. Native true result and independently read table-ready byte required. `v3_data.json`, target task/collection/readiness fields. |
| `data_load_tasks` | Native task start, then completion predicate; if incomplete, native pump and repeat, up to 1024 checks with the upstream 5 ms delay. | Same LoadingState task/table receiver and original task phase. Completion and observed tables ready are required. Pump's boolean is not interpreted as overall completion. Target start/pump/complete entries and upstream `nativePumpDataTables`. |
| `loading_state` | Native `LoadingState::update(state, 0.05f)`, then native completion predicate; at most 512 iterations, 5 ms apart. | Verified state vtable, phase before/after, task and tables ready; native completion must become true. No future/latch/gate forcing and no loading patches. Target update/complete entries and fields. |
| `map_resources` | Select a live Location through a separately evidenced read-only recipe. Native FileName and TileDataFileName getters; real request constructor; append both strings with upstream sentinel options and false flag; load; native string resolver for primary then secondary. | Native request vtable and both nonnull payloads. Target constructor ABI supplies storage size. Resolver's target evidence shows it performs the resource lookup/readiness check itself, so no old native-string layout is reproduced. `v3_leaf2/result.json`. |
| `battlefield_cache` | Native cache-root getter and row instance-ID getter; `build(cache, primary, secondary, id)`; native Location battlefield getter; native request destructor. | Cache exists, ID nonnegative/in bounds, returned battlefield equals the independently read cache row. Target cache rows/count fields; payload addresses and row ID retained. No old cache-layout fallback. |
| `manager_update` | One native `manager_update(manager, 0.05f)` after the earlier stages, with no presentation toggle, scheduling flag or Home patches. | Before/after GameMain, manager, LoadingState/phase and table snapshots; call return, no JNI exception. This is not replay/battle qualification. Target manager entry and current-state field. |

The observer records monotonic times and GameMain/context/manager/loading/task/
table state at each native stage, including before and after calls. Unknown
phase/readiness is JSON null, never false success. Table receiver reuse after
LoadingState changes is explicitly marked `tables_from_saved_receiver`; these
are non-atomic observations, not a proof of lifetime or concurrency safety.
Map payloads/cache/battlefield/instance ID are recorded when available.

Every native subcall flushes a separate `ORACLE_V7_CALL` before/after record.
A crash inside init thus retains `GameMain::init` as the interrupted call, even
without a Java exception. `ORACLE_V7` records contain stage-relative elapsed
time; subcall elapsed time is exact for calls that return. For abrupt failure,
the last timestamp is only a lower bound; `timing_complete` is false. Collector
wall duration includes ADB overhead and is not substituted for native duration.

### Upstream prerequisites that cannot be silently ported

The upstream Java host creates client shells and runs a separate resource,
asset/path, clock and singleton prelude before direct GameMain initialization;
it also pumps the manager before DataTables. Its native bridge writes resource
gate state and patches rendering paths. Those behaviors are **not** authorized
by v7 and the supplied target binding does not resolve the entire prelude.
This host follows the ticket's requested lifecycle list. It never invents the
missing singleton/context/task, mounts fabricated strings, borrows old offsets,
or moves manager calls earlier to make prerequisites pass. A missing GameMain,
context or loading task is a real first **host prerequisite blocker**, not
evidence that a rendering patch or protection workaround is needed.

The Create call cannot exactly reproduce the upstream Activity argument without
violating this ticket. It passes null, records that fact, uses a real framework
AssetManager over verified splits, and leaves client callbacks unsupported.
The graphics API integer is the upstream caller's requested mode, not a claim
that a GL context exists. Display metrics/free space are read from the actual
framework/filesystem; upstream's fabricated constants are not copied.

The supplied target binding identifies map functions but does **not** identify
a Location-row selection path. The default runtime binding records
`location_recipe: null`; if earlier stages succeed, `map_resources` stops with
`HOST_LOCATION_RECIPE_MISSING` before any map call. A future independently
reviewed private recipe can be supplied **before the authorized attempt** via
`build --location-recipe PRIVATE_JSON`. It must contain `global_rva`, ordered
pointer-read `offsets`, `vtable_rva`, nonempty `rationale`, and private relative
`evidence` paths mapped to SHA-256 hashes. All values stay private. Build and
collection revalidate the evidence; the runtime verifies the selected row's
vtable. No captured absolute heap pointer or arbitrary default row is accepted.
This extension point is a disclosed qualification gap, not a claim that map
selection has been derived or tested.

## Review classification and presentation attribution

`review.py` authenticates stored output hashes, re-parses the raw transcript,
and checks token/PID, monotonic time, exact ordered stage prefix, subcall pairing,
ceiling, loader/JNI identity, success postconditions and boundary. Synthetic
success in a result object cannot override its actual host transcript. Evidence
missing after a postflight identity/isolation failure remains blocked even if
the native calls returned. Reports include `stage_reached`, `last_completed`,
`blocking_stage`, `interrupted_call`, per-stage evidence, `candidate_sites`, and
`attributed_sites` separately.

| Classification | Meaning |
|---|---|
| `a` | This attempt reached its selected ceiling. A load-only ceiling proves only loading. |
| `b` | Receipt-bound reviewer attribution to libg's own refusal. STOP. |
| `c` | Receipt-bound reviewer attribution to a presentation dependency at the failing stage. STOP; zero patches applied or qualified. |
| `blocked` | Missing host prerequisite, invalid receipt, input drift or isolation failure. |
| `unclassified` | Crash, timeout, native incomplete result or unsupported callback with no established cause. STOP. |

The candidate map below preserves [v3 classification](../../../../V3_REPORT.md)
and the v4/v6 presentation groups. **Candidate means source context, not observed
causation.** Five sites remain unresolved; no failure is automatically assigned
to a patch site merely because it occurred during init.

| Stage/group | Candidate site IDs | Retained classification |
|---|---|---|
| GameMain / `game_main_init` | `renderer_bootstrap_call`, `renderer_device_block`, `renderer_resolution_call`, `renderer_objects_block`, `renderer_late_configure_call` | Resolution has local presentation-only static proof; the other four are likely rendering with incomplete effects proof. |
| Resource-dependent stages / `resource_variant` | `headless_resource_variant` | Likely rendering; all-caller/map exclusion incomplete. |
| LoadingState / `loading_completion` | `loading_presentation_call`, `loading_platform_ui_call` | Unresolved target identities; rejected adjacent-call guess is not reused. |
| Manager/Home / `manager_home` | `game_presentation_toggle`, `home_resolution_block`, `home_graphics_create_call` | Unresolved target identities. |

For manual (b)/(c), retain an ignored finding JSON with `kind` (`libg_refusal`
or `rendering_dependency`), `origin: "libg"`, `reviewer`, `rationale`, the
`result_sha256`, and `stage` exactly matching the blocking stage. `evidence`
contains one receipt's `file`, `sha256`, inclusive one-based `line_start` and
`line_end`, and exact `excerpt`. Evidence must come from this attempt's host
stdout/stderr or PID-filtered logcat. For (c), also supply `site_group`, nonempty
`site_ids`, and `site_mapping_basis` explaining the actual diagnostic/stack-to-
site correspondence. Cross-stage site groups are rejected. Hash and line checks
authenticate the source; the causal judgment is manual and is labeled as such.
A generic GL-related string or null pointer is not itself a proof of a patch
requirement. Host failures cannot be promoted to libg refusal.

## One authorized attempt: run order

Use the already-provisioned, owned Linux x86_64 API-32 oracle guest and existing
loopback-only namespace from v6. All toolchains/APKs/assets must already be local.
Do not provision, transfer/download assets, connect remote ADB, start a client,
change namespace connectivity, or stop shared services. Confirm the actual owned
QEMU PID, oracle AVD and emulator port before running. The collector checks them
and rejects an already running client.

From the private checkout root **on that worker**, inside its established setup:

```bash
Q=scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7
bash -n "$Q/worker.sh"
python3 "$Q/test_v7.py"
python3 "$Q/verify.py"
bash "$Q/worker.sh" build

# Exactly ONE launch. Explicit ceiling allows the full requested prefix;
# the first unmet prerequisite/failure stops earlier. No automatic retries.
set +e
bash "$Q/worker.sh" run --emulator-pid "$ORACLE_EMULATOR_PID" \
  --serial emulator-5554 --stage-limit manager_update
attempt_rc=$?
set -e
# Read PRIVATE_RUN=... from the collector output even when attempt_rc is 78.
# Set RUN to that exact new result directory; never a previous receipt.
bash "$Q/worker.sh" review "$RUN"
```

`--preload-dependencies` retains the v6 explicit opt-in contract and defaults
off. Its existing reviewed six-library whitelist, manifest validation and order
remain unchanged. Do not select it as an automatic fallback after failure.
Without `--stage-limit`, the one attempt ends after library loading; do not then
reuse it with a higher ceiling. Post-attempt review never launches the host.

For a justified private attribution, run only:

```bash
bash "$Q/worker.sh" review "$RUN" --finding "$PRIVATE_FINDING"
```

It creates a new attributed review and preserves the original receipts. The
review does not authorize follow-up execution, patches, retries or deployment.

## Files, tests and remaining risks

`JniHost.java` controls lifecycle and observations; `AppLibraryLoader.java` owns
the child-loader entry points; `observer.cpp` calls the unmodified native entries
and reads memory. `binding.py` projects the private runtime configuration;
`build.py` compiles/hashes both DEX files and the observer; `run.py` collects once;
`review.py` and `results.schema.json` validate evidence. `test_v7.py` exercises
synthetic receipts and mocked collection; `verify.py` checks public privacy and
forbidden source patterns with positive controls. These tests never execute libg.
The compiled import/export and DEX ownership checks complement source checks;
neither proves behavior of indirect native callees. Standard-library memory-copy
imports used for observer-owned C++ exceptions are not target-write APIs.

The target ABIs/receiver lifetime remain statically supported and runtime
unqualified. Native initializers can create threads, write their own files,
initialize real APK classes, invoke unsupported callbacks, attempt network
access blocked by isolation, or refuse. No GL context is provided, and rendering
failure is expected to be possible. A long-running native call cannot be
interrupted at an internal presentation instruction without instrumentation
beyond this ticket; the watchdog stops the process, then review attributes the
receipt if justified. Unknown transitive side effects remain unknown. The
one-attempt latch is build-local operational discipline, not a global authority
service. An authorized worker attempt and actual site attribution remain open.
