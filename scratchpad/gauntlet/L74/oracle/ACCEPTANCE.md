# Native acceptance contract — not executed

Target: original build160402012, x86_64, exact hashed private inputs. A source audit,
successful boot, open TCP port or repeatable host hash is insufficient. All gates
below are required. Current deployment status and evidence are in V3_REPORT.md.

## Identity and isolation

1. Retain SDK/emulator/system-image/NDK/JDK revisions, CPU/KVM check, source and
   bridge/JAR hashes, APK versionCode/signatures/member hashes, and full asset
   overlay manifest. Compare installed splits and loaded original libg with these
   inputs. Require versionCode exactly160402012; a matching package name is not enough.
2. Preserve integrity/protection code and all native battle-logic bytes. The v3
   boundary permits scheduling/control DATA flags and direct calls to unmodified
   game functions. It also permits individually proven presentation patches:
   retain target callers, strings, complete affected control flow and write-effect
   evidence showing no battle-state writes. Verify original bytes before every
   patch; restore temporary edits and original page permissions after the call,
   including failure paths. A proven rendering-variant shim may remain only for
   its qualified oracle lifetime and must restore on teardown;
   map/tilemap requests must still use the native resource chain. Stop on a
   forbidden-kind requirement, byte mismatch or unsupported ABI. The shared
   tick/presentation DATA gate is allowed; its target location and receiver/call
   semantics still require evidence. Never decrypt/unpack independently or load
   the captured analysis image in place of the real original module.
3. Start the emulator in the loopback-only namespace, before installing/running
   game code. Retain namespace links/routes and running-process namespace identity.
   Before game execution, test failed outbound connections from a disposable
   process in that namespace to IPv4, IPv6 and VM metadata addresses. Keep ADB
   and API clients inside it. Repeat structural checks after the run. No game-server
   connection, account login, download or service port exposed to the host network.

## Upstream acceptance, requalified for the target

Translate all checks from `scripts/smoke.ps1` and `accept_direct_core.ps1`: toolchain,
private runtime hashes, AOSP root/API/ABI, exact package version, required lifecycle,
tables/maps ready, coherent native state, six opening towers, tick0 through100,
observation scope, native phase, RNG and known opening state. The existing
150535029 goldens are not target expectations. New fixtures and independently
established expectations must be reviewed before the scored run.

With a qualified target bridge/catalog and Python >=3.11, invoke the sandbox's
own suites **inside the namespace**, from the sandbox root, with a private
CR_SANDBOX_DATA directory:

```bash
python scripts/accept_full_card_catalog.py --port 37031
python scripts/accept_native_card_forms.py --port 37031
python scripts/accept_match_rules.py --port 37031
```

Require no failed or silently omitted standard cards/forms; expected coverage is
the target catalog's independently derived membership, not the old 122/41/16.
Exercise champion/hero abilities, wrong-side/dead handles, rejected commands,
in-process reset, native regulation/overtime/elixir changes, native tiebreak and
reset after terminal. Keep native acceptance/rejection results; do not emulate them
in Python. Validate optional buff/area observations separately, including timer
direction, source/controller ownership and distinct Hero Ice Wizard body/cubes.

## Reproducible replay experiment

Create one private fixture from `examples/eight-card-bootstrap.json` using the
target-qualified catalog and `native_core.decks.build_replay`. Pin all replay
fields including deck order, levels, forms, arena, accounts and `rndSeed=42`.
Freeze the fixture SHA256. Use the same inputs for every run; no wall-clock-driven
decisions. Record the exact API requests in order alongside responses.

For a meaningful scripted battle, freeze a schedule of successful native plays
for both sides at chosen ticks (plus one rejected illegal play) from a separate
qualification run. Include at least one troop attack, spell damage and tower-HP
change. Store absolute tick, side, deck index, coordinates and native expected
result. The scored runs replay this schedule unchanged. Do not select convenient
actions adaptively during a scored run or accept empty battle traces.

1. Start a fresh qualified service. `ping`, `status`, then `reset` with the full
   replay and the same explicit warmup (zero for this test). Use `reset`, not the
   legacy `load_replay` bootstrap-adoption optimization.
2. Observe tick0. Require coherent state and six correctly identified towers.
3. Submit scheduled actions at their pinned ticks, side0 then side1 for equal
   ticks. Advance with `step_trace`, batches of at most64, never skipping an action
   boundary. The wire response's `result.initial_frame` and `result.frames` must
   be complete. Reach tick1200 and save all1,201 observations plus action receipts.
   The fixture must be qualified not to terminate early; early termination fails.
4. Check every preterminal step advances exactly one tick and one50ms native update;
   frame counts/tick continuity must match. Check state schema/counts/coherence,
   native unit/HP changes and the scheduled command results. A host sleep is not
   a simulator step. Time20Hz refers to simulation time, not real-time throughput.
5. Repeat ten times using native in-process `reset`; then repeat across ten fresh
   service processes. Also repeat on the second isolated instance when N=2.
   Destroy only processes created for the test, identified by namespace/serial,
   exact command and private slot directory.

Comparison must be independent of the bridge's `state_hash`: save raw private
responses, then canonicalize using a **reviewed explicit schema**. Preserve tick,
RNG, every gameplay field, native results and ordered path nodes; key entities by
generation ID and convert pointer relationships to those IDs. Exclude only
documented ASLR addresses, transport/performance timestamps and counters. Never
drop every `id` key: some are logical IDs. Unknown fields fail schema review; do
not silently omit extensions. Hash each canonical frame with SHA256, compare all
frames byte for byte and report the first differing path/tick. Also record native
hashes and their declared coverage; a false certificate flag remains false.

Run a negative control with `rndSeed=43`: RNG must change at initialization and
the chosen fixture must yield at least one different canonical gameplay frame.
Run another control with one scheduled action omitted: the corresponding action
receipt and downstream trace must differ. If either control cannot detect the
perturbation, the comparator/fixture is not accepted. These controls expose cached
responses and comparisons that discard relevant fields.

PASS only if identity, the refined patch boundary, isolation, upstream suites, all
same-seed trace comparisons and both negative controls pass. Persist a private
receipt with input hashes, environment, run IDs, per-run trace digests, coverage,
command outcomes and failures. Missing observations are failures, not zeros.
This establishes reproducibility for the pinned fixture and assets, not universal
game equivalence or agreement with a live server.
