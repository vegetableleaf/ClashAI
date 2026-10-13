# ORACLE v2: stopped before a runnable port

> Historical report. ORACLE v3 supersedes this stop interpretation and binding;
> see [V3_REPORT.md](V3_REPORT.md) and `verify_v3.py` for current evidence and checks.

Status: **STOPPED at a mixed native tick/presentation control requirement.**
The earlier blanket prohibition on executable-memory changes is superseded.
No network, target execution, patch application, APK installation or commit was
performed. This is an incomplete port, not a native acceptance result.

Verification: the offline evidence/privacy check passes. Bash failed before
parsing with `CreateFileMapping` / Win32 error 5; shellcheck was not available.
Shell syntax and VM behavior remain unverified. GATES_V2.md records four evidence
or contract gates met and two implementation gates abandoned at the user's stop
condition; these counts do not represent a successful port.

## Stop evidence

In `research/ext/cr-native-sandbox/android_probe/native/jni_bridge.cpp`, the
controlled stepping implementation explicitly describes a shared gate that
suppresses both the core simulation call and HUD/result callbacks (lines
2481-2486). It calls the core directly (2510), writes that gate, calls the outer
battle update, and restores the prior gate value (2525-2529). Initialization and
manager pumping also set the gate (3039-3044 and 3987-3990).

This is a data write controlling native tick dispatch, not just a rendering
instruction patch. A literal port therefore appears to need a modification
outside the allowed presentation-only class. The user's explicit stop condition
applies. No target address for that gate was derived or transplanted. This does
not demonstrate an integrity bypass, a target runtime failure, or that every
possible headless implementation must use it. A different implementation would
need evidence that it preserves native tick/state-machine behavior within the
existing boundary.

Two additional operations require classification before any future port:
`discard_pending_game_action` clears any nonzero action and two flags (2389-2425),
although its comment discusses an OpenURL case; and stepping stops calling the
outer update at a terminal threshold or clock stall (2517-2523). Neither has
target equivalence proof here. These are review findings, not assertions that
the pending action is a battle command or that either is anti-tamper code.

The bridge's `RTLD_NOLOAD` attachment is real, but `JniHost.java` first performs
`System.load` in its own `app_process`. Successful normal-app loading in the
captured process does not establish successful host loading in that process.
The named CreateGameMain body includes environment-detection behavior; none was
modified and no requirement to bypass it was demonstrated.

## Per-item evidence

All numerical values and disassembly are private under
`scratchpad/gauntlet/L70/reader/oracle_160402012/`. The file
`runtime-160402012-x86_64.json` uses the upstream binding envelope and records
`deployable: false`; unresolved values are null, with no old-build fallback.
It is a partial evidence binding, **not an installable binding**. The C++ bridge
hardcodes its constants; merely writing the upstream-style JSON does not port it.

Confidence refers to static identity, never runtime qualification.

| Requested item | Confidence/status | Evidence and limit |
|---|---|---|
| JNI_OnLoad-to-base delta | High static | Captured dynamic table, GNU hash and named defined dynamic symbol; recovered function entry agrees. No live dlsym check. |
| CreateGameMain | High static | Exact named JNI export, matching recovered entry and complete symbol-sized disassembly with JNI/assets/string setup. Host callability untested. |
| GameMain::init | Unresolved | GameMain source-path and initAssetTree/loadAssets lambda strings identify a neighborhood, not the initializer or its patch blocks. |
| DataTables range load | Medium candidate | Direct pump call uses table receiver, seven arguments, quarter-range calculation, cursor and boolean completion branch. Callee body not independently reviewed before stop. |
| Data load tasks | Medium-high candidates | Start references `datatables-init`, tests readiness and starts pump; pump loads ranges and advances phases; completion tail-calls the same readiness predicate. Target task layout differs and remains unqualified. |
| LoadingState update/completion | Unresolved | No target mapping established before stop. |
| Map resource request chain | Unresolved | No constructor/append/load mapping established before stop; native map preservation not proved. |
| Battlefield cache | Unresolved | No target cache-builder mapping established before stop. |
| Manager update | Unresolved | No receiver/layout/update equivalence established before stop. |
| Outer replay loader | Unresolved | No qualified outer-loader mapping; no substitution with inner JSON loader. |
| BattleGameState type | Unresolved | Old documented type is not accepted as target evidence. |
| Battle core Tick | Unresolved | No target tick mapping; mixed dispatch-gate requirement triggered the stop. |

The supplied export has 74,565 recovered functions but only 493 selected
decompilations. Those selections target buff/ability keywords. Ghidra's recovered
CreateGameMain body was shorter than its dynamic-symbol extent; captured EH-frame
and symbol extents were used for additional disassembly. A recovered entry or
truncated decompilation is not whole-function proof. All eleven retained capture
region hashes were verified before reading them. No bytes were decrypted by this
investigation; analysis-only ELF carriers copy already captured bytes.

## Patch-site classification

The caller column below identifies the **upstream bridge caller**, not a proven
target native caller. For every row, target callers/strings/write effects and
original-byte guards remain unresolved. Thus **zero target sites qualify** for
patching. Old comments and names alone cannot prove absence of battle-state writes.

| Site | Upstream caller | Documented role/lifetime | Target classification proof |
|---|---|---|---|
| Renderer bootstrap call | nativeInitGameMain | Rendering; temporary | Unresolved; no patch emitted |
| Renderer device block | nativeInitGameMain | Rendering; temporary | Unresolved; no patch emitted |
| Renderer resolution call | nativeInitGameMain | Rendering; temporary | Unresolved; no patch emitted |
| Renderer objects block | nativeInitGameMain | Rendering; temporary | Unresolved; no patch emitted |
| Renderer late-configure call | nativeInitGameMain | Rendering; temporary | Unresolved; no patch emitted |
| Loading presentation call | nativePumpDataTables | Presentation; temporary | Unresolved; no patch emitted |
| Loading platform UI call | nativePumpDataTables | Presentation; temporary | Unresolved; no patch emitted |
| Game presentation toggle | nativePumpManager | Presentation; temporary | Unresolved; no patch emitted |
| Home resolution block | nativePumpManager | Rendering; temporary | Unresolved; no patch emitted |
| Home graphics creation call | nativePumpManager | Rendering; temporary | Unresolved; no patch emitted |
| Resource-variant shim | nativeInitGameMain | Rendering variants; persistent | Unresolved, including native map/tilemap exclusion |

Separately, the shared core/presentation gate is **mixed tick control in upstream
source**, with high confidence about the source operation and no target mapping.
It cannot meet the requested presentation-only proof.

## Blockers and script status

Deployment/health remain fail-closed with exit 78 because the explicit stop
condition was reached. Their diagnostic now states the v2 mixed-tick reason;
they were not converted into launchers consuming unqualified addresses. Removing
those guards or presenting the partial binding as deployable would violate the
current ticket. The complete native ABI, catalog, loader and patch classifications
also remain unqualified. No runnable trace acceptance harness was produced.

ACCEPTANCE.md now uses the refined patch boundary. It retains all upstream suites,
two identical same-seed traces as the minimum comparison within the ten-reset and
ten-cold-process campaign, cold-versus-reset matching, and seed/action negative
controls. None has run; old-build certificates remain inapplicable.

## Exact offline VM run order at this stop

Prerequisites: private checkout and inputs, Python, Bash, shellcheck and the SDK
already present on the VM. No transfer or provisioning command is authorized by
this no-network ticket. Do not run the historical online `setup_vm.sh` instructions.

```bash
cd /path/to/private/ClashBot
O=scratchpad/gauntlet/L74/oracle
P=scratchpad/gauntlet/L70/reader/oracle_160402012
git check-ignore -v "$P/runtime-160402012-x86_64.json" "$P/v2_evidence.json"
python3 "$O/verify_v2.py"
for f in "$O"/linux/*.sh; do bash -n "$f"; done
shellcheck -x -P "$O/linux" "$O"/linux/*.sh
bash "$O/linux/deploy.sh"
# Expected: BLOCKED_TICK_CONTROL, exit 78. STOP; do not install or launch game code.
```

There is no valid native VM launch order for this partial binding. Once a complete
port satisfies the existing boundary, the required order is: prove namespace/KVM
isolation; build/hash the private target bridge and JAR; verify/install original
matching splits; verify loaded identity/byte guards; start the qualified direct
service; run the translated smoke and cold-core suite; run the three upstream
Python suites; freeze a target fixture/action schedule; score same-seed run A and
B; compare every canonical frame; compare cold start against in-process reset;
complete the ten-reset/ten-cold campaign and both negative controls. The existing
Python suite commands, from the sandbox root inside the isolated namespace, are:

```bash
python scripts/accept_full_card_catalog.py --port 37031
python scripts/accept_native_card_forms.py --port 37031
python scripts/accept_match_rules.py --port 37031
```

These final three commands are a future acceptance contract, not instructions to
run the old bridge with the new APK. See ACCEPTANCE.md for fixture/schema details.
