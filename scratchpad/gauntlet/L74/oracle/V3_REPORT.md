# ORACLE v3: lifecycle derived; deployment remains gated

Status: **static derivation advanced; not deployable**. The v2 tick-control stop
is superseded. Scheduling/control DATA writes and direct calls to the game's
unmodified functions are allowed. Battle-logic bytes, integrity/anti-tamper/
anti-debug code, independent unpacking/decryption, and analysis-image substitution
remain forbidden. No such operation, network access, target execution or commit
was performed. Changes are uncommitted.

The private binding is
`scratchpad/gauntlet/L70/reader/oracle_160402012/runtime-160402012-x86_64.json`.
The prior binding is preserved with a `.v2.json` suffix. Private values, captured
bytes, disassembly, field evidence and precise observation locations remain in
that ignored directory. `v3_evidence.json` binds the evidence to its inputs.
The public verifier is `verify_v3.py`; the older reports/verifiers describe their
historical states, not the current binding.

Confidence below means **static identity or structure**, never observed runtime
success. All eighteen required lifecycle entries have high static confidence,
including the scheduling locator. This does not qualify all presentation sites
or make the hardcoded upstream bridge target-compatible.

| Item | Confidence | Public evidence summary |
|---|---|---|
| JNI base delta / CreateGameMain | High static identity | Named captured dynamic symbols and symbol-sized native body; preserved from v2. Original host callability untested. |
| GameMain::init | High static identity | GameMain vtable, context store, asset-tree call and initialization sequence agree. Captured unwind extent recovers the body missing from the short exported function range. |
| DataTables range load | High static structural | Seven-argument task call reaches a wrapper inserting the address of a provider object; implementation clamps the range, initializes named DataTables rows, finalizes at completion and returns range completion. |
| Data-load start / pump / complete | High static structural | Named data-init task, start-to-pump edge, range cursor/phase transitions and shared table-readiness predicate independently agree. |
| LoadingState update / complete | High static structural | Same native state vtable; update drives tasks, futures and phases consumed by the completion predicate, including resource readiness and the ready latch. |
| Map request constructor / append / load | High static structural | Two independent native callers construct a request, append FileName and TileDataFileName, load, resolve both payloads and destroy the request. Callee bodies and request vtable corroborate the sequence. |
| Battlefield cache | High static structural | Native callers supply both resolved map payloads and row instance ID; builder and bounds-checked reader agree on the changed cache layout. |
| Manager update | High static structural | GameMain frame caller, pending-state transition, factory and state virtual dispatch agree. Target manager fields differ from upstream and an earlier reader candidate. |
| Outer replay loader | High static structural | Native battle initialization calls a battle-owned wrapper that creates the replay controller, delegates loading and restores wrapper state. Controller and inner JSON loaders are identified separately. |
| BattleGameState type | High static structural | Replay setter, decoded factory switch, constructor and battle-state vtable agree on the discriminator; the old value was not assumed. |
| Battle core Tick | High static structural | Outer dispatch gate, fixed-step accumulator, tick diagnostic, underlying battle update and tick getter agree. Early returns and accumulated steps mean one call is not automatically one tick. |
| Shared scheduling flag | High static locator; live storage unverified | Allocation/destruction and repeated core/callback gates identify a byte in a heap control object reached through a module global pointer. It is **not a directly writable module-relative byte**. |

The map chain remains native. No inner-loader substitution, old-layout fallback,
or captured-image loading path was introduced. The binding includes supplemental
getters, resource destructor, replay setter and field evidence needed to explain
the requested identities; it remains an evidence document, not a runtime loader.

## Eleven presentation/shim sites

Classification and patch readiness are separate. **One site has a local
presentation-only proof; five are likely rendering with incomplete proof; five
are unresolved. Zero patches are qualified or emitted.** Candidate byte prefixes
are private evidence, not complete patch guards or permission to replace a block.

| Site | Classification / confidence | Callers, strings and write evidence; alternative considered |
|---|---|---|
| Renderer bootstrap call | Likely rendering; medium-high site identity | GameMain init calls shader bootstrap with GPUSkinned, Shadow, Distortion and sampler vocabulary. Transitive registration/allocation writes remain untyped. Existing-Stage early return skips only construction, not this whole path. |
| Renderer device block | Likely rendering; medium-high site identity | GameMain init creates Stage with builtin-stage shader names and configures dimensions/viewport. Virtual-call and constructor effects remain incomplete. Preinitialized Stage avoids only its constructor. |
| Renderer resolution call | **Presentation-only local proof; high static** | GameMain init passes the shader-owning Stage receiver. Complete callee makes no calls and writes only Stage scale/dimensions, with a scalar constant read. No battle-object writes occur in that bounded callee. Live receiver correspondence and loaded byte guard remain unverified. |
| Renderer objects block | Likely rendering; medium site identity | GameMain init allocates/registers UI receivers in Stage. Constructor, registration and block boundaries lack complete write-effect proof. Unmodified initialization/attachment is a candidate alternative, not a qualified no-Surface route. |
| Renderer late-configure call | Likely rendering; medium-high site identity | GameMain init reaches Stage::setViewport diagnostics. Downstream and virtual effects remain untyped. Existing-Stage state does not prove the call unnecessary. |
| Loading presentation call | Unresolved | Full LoadingState update mixes UI, futures, tasks and phase writes. A tempting adjacent-call match was rejected because it mutates a receiver counter and loading phase. Native completion/polling or attachment after loading is an investigated alternative; neither qualifies this site. |
| Loading platform UI call | Unresolved | Same rejected pair; target UI callback identity remains unknown. Shared battle scheduling flag is not proven to cover LoadingState. Observe the actual loading-completion call chain. |
| Game presentation toggle | Unresolved | Version-text drawing and a resource-load/wait helper were rejected as matches. Shared scheduling DATA is allowed for the proven battle branch, but is not yet a replacement for this old toggle. |
| Home resolution block | Unresolved | Home constructor/UI-resource strings and Stage-using methods give a neighborhood, not safe block boundaries. Investigate whether native replay transition can avoid Home graphics while keeping Home code intact. |
| Home graphics creation call | Unresolved | Same incomplete Home caller/receiver evidence. No absence-of-battle-writes proof. Native replay transition plus scheduling control is a candidate alternative requiring observation. |
| Resource-variant shim | Likely rendering; high dispatch identity, incomplete scope proof | Unique upstream guard match and texture-filter/mipmap caller strings identify the decoder. Helpers perform lookup/refcount/allocation writes; all-caller and map/tilemap exclusion are unproved. Native empty/unsupported variant data has a zero-output branch, but blanket tag mutation is not justified. |

For the five initializer sites, the examined early-return/data conditions do not
provide a demonstrated flag that suppresses all rendering initialization. The
allowed battle scheduling flag must not be generalized to unrelated loading or
Home paths. Attachment after ordinary app initialization is only an investigative
alternative: it does not establish the upstream strict no-Surface host contract.

## Deployable: no — exact missing evidence and implementation

1. **Scheduling storage and lifetime.** The supplied module capture excludes the
   pointed-to heap object. After normal original-app loading, read the pointer
   slot, referent mapping permissions, owner and flag byte; compare the owner with
   the manager's independently identified parent member, not the manager itself.
   Repeat across native replay creation, reset and teardown. Establish safe
   threading/lifetime handling before a bridge writes and restores this byte.
   Allocation and static locator are already established; a direct global-byte
   write is specifically incorrect.
2. **Bootstrap/device/objects/late-configure effects.** Resolve remaining virtual
   callees and mutable write destinations from native Stage/UI receiver snapshots
   and passive call observations; complete the transitive static review. A finite
   runtime trace alone cannot prove absence of battle writes on unobserved paths.
3. **Resolution patch readiness.** Confirm the live receiver is the same native
   Stage, compare the full loaded call bytes and establish restoration/error-path
   handling. Its bounded presentation classification is already supported.
4. **Two loading, toggle and two Home identities.** Observe native loading-complete
   and manager/replay transitions, recording state pointers, vtables, call stacks,
   argument types and write destinations. Reconcile those observations with full
   function extents to select the actual callbacks or prove that the allowed
   native transition omits them. Do not spoof task/future readiness.
5. **Resource-variant exclusion.** Resolve decoder callers and resource types,
   including graphics and map/tilemap requests. Prove map data uses a preserved
   native route and identify a rendering-only data alternative or guarded shim.
   Any shim needs verification and restoration, including its teardown path.
6. **Live receiver/ABI qualification.** Read the GameMain/context and native state
   vtables; observe task/table/resource readiness; follow both map payloads into
   the cache; confirm manager fields, replay wrapper arguments/ownership and core
   accumulator/tick relationships. Each private entry and field supplies its exact
   locations and settling observation. These are live qualification gaps, not
   missing static lifecycle function identities.
7. **Target bridge and original-module host.** Port the hardcoded C++ constants,
   data locators, field/ownership assumptions, command/ability and observation
   APIs, catalog and reset path; build/hash private outputs. Normal-app loading
   does not prove JniHost's separate app_process can load the original module.
   That must be observed without any protection change. Broad pending-action
   discard, reset pointer detachment and terminal/stall shortcuts from upstream
   are not automatically qualified by the scheduling clarification. Static or
   runtime observation cannot substitute for this implementation work.

Native smoke, catalog/forms/rules, deterministic stepping and reset acceptance
remain **not run**. They follow a qualified implementation; they are not inferred
from static confidence or old-build certificates.

## Scripts and verification

`deploy.sh` and `health.sh` now use `binding_status.py` and report
`BLOCKED_BINDING_INCOMPLETE`, explicitly allowing scheduling DATA operations.
The preflight lists missing qualification without printing private values and
returns **78**. A manifest with `deployable: true` cannot activate the unported
launcher. `health.sh --infrastructure` still reports only infrastructure and ends
at the native gate. There is no unsafe override.

`verify_v3.py` checks ignored/untracked evidence, public address leakage with a
positive control, retained evidence/source/export/capture hashes, required item
and site coverage, Python syntax, shell line endings, and eight preflight cases
including malformed/missing/spoofed bindings. Results are in VERIFICATION_V3.json.
This is offline verification, not native acceptance.

**Shell verification handoff:** Git Bash failed before parsing with
CreateFileMapping / Win32 error 5; shellcheck is unavailable here. Python exit-78
behavior is checked independently. Linux shell syntax, actual shell execution and
VM behavior must be checked on the VM; they are not claimed verified locally.

## Offline VM run order

Use a VM with the private checkout, unchanged matching APK splits/assets and
SDK/JDK/NDK/system image already available locally. No network transfer,
provisioning or historical `setup_vm.sh` invocation belongs to this ticket.

First, perform the checks that are runnable now:

```bash
cd /path/to/private/ClashBot
O=scratchpad/gauntlet/L74/oracle
P=scratchpad/gauntlet/L70/reader/oracle_160402012
git check-ignore -v "$P/runtime-160402012-x86_64.json" "$P/v3_evidence.json"
python3 "$O/verify_v3.py"
for f in "$O"/linux/*.sh; do bash -n "$f"; done
shellcheck -x -P "$O/linux" "$O"/linux/*.sh
set +e
bash "$O/linux/deploy.sh"
rc=$?
set -e
test "$rc" -eq 78
# Expected: BLOCKED_BINDING_INCOMPLETE. No oracle install or launch follows.
```

Then follow this qualification order; later steps are conditional, not an
instruction to execute the old bridge with the new APK:

1. Boot the already-provisioned empty AOSP guest with `boot.sh 1`; verify KVM,
   loopback-only namespace links/routes and emulator/ADB process namespace.
   `health.sh --infrastructure 1` must clearly say infrastructure-only and still
   return 78 at the native gate. Keep every subsequent ADB/client process inside
   the isolated namespace.
2. Verify unchanged original splits/version/signatures/assets against the private
   manifest. Observe the **real original app** loading normally in that offline
   guest. If loading requires downloads, login, unpacking or protection changes,
   stop. Never install or load the captured analysis ELF.
3. Perform the read-only observations above, in order: module identity/base;
   GameMain and data loading; map request/cache; manager/state/replay wrapper;
   scheduling object's storage/lifetime; core dispatch and presentation callers.
   Use existing passive/emulator observations without executable-byte hooks or
   anti-debug changes. If that capability is unavailable, retain the corresponding
   gap. These probes are specified in the private binding, not implemented here.
4. Reconcile probe evidence and finish presentation proofs or allowed alternatives;
   then implement/build/hash the target bridge and qualify its own original-module
   loading path. Verify byte guards and restoration logic before any patch.
5. Only after those requirements qualify, implement/enable deployment and launch
   the target service in the namespace. Run translated smoke and direct-core
   checks, then the three upstream Python suites from the sandbox root:

   ```bash
   python scripts/accept_full_card_catalog.py --port 37031
   python scripts/accept_native_card_forms.py --port 37031
   python scripts/accept_match_rules.py --port 37031
   ```

6. Freeze the target replay/action fixture; compare every canonical frame for
   two same-seed runs, cold start versus in-process reset, the full ten-reset /
   ten-cold-process campaign and seed/action negative controls in ACCEPTANCE.md.
   Retain failures and identity receipts. No native PASS is issued before this.
