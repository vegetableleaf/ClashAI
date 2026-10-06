# Exact public decision capture

Registered successor to NEXT_DECISION_CAPTURE_20261006.md, October 6.
Owner canonical R1e remains active; no loaded source/process/configuration change.
No model learning, new checkpoint, native match, taps or live launch in this leaf.

## Contract and ownership

Root owns support.py, entry.py, test_entry_capture.py, qualify.py, replay.py,
runner.py, PLAN/METRICS/GATES/REVIEW.
Capture worker owns only capture.py. Test worker owns only test_capture.py.
Independent reviewer is read-only. All checks run serially under root control,
with the common development_iteration_1 chain lock across qualification/replay.
No worker executes checks before root freezes and commits the reviewed sources.

C1: CaptureStore(directory, manifest, max_records=128, max_bytes=67108864)
creates an exclusive directory, binds schema/checkpoint/sources/settings. Its
decide(pilot, frame) invokes pilot.decide exactly once; temporarily wraps row
and hooks the existing torch model to copy the exact CPU feature4 input tensors,
conditioning kwargs and every head from each actual forward. No extra forward.
Restore methods/hooks in finally; actual decision exceptions propagate. Any
capture validation/storage error disables capture once and leaves policy behavior.
Strict whitelist schemas for batch, heads, row info, public bodies/projectiles,
chosen decision, source/settings/CPU environment. Never serialize an unrestricted
frame or opponent private block. Independent detached copies preserve bytes.

C2: Each complete record is an uncompressed NPZ with JSON metadata stored as
uint8, numeric tensor arrays only, checksums, atomic commit and committed index.
load_record(path, expected_manifest) rejects corrupt/truncated/wrong manifest or
schema records. Record caps apply across matches; no unbounded queue. Default
captureOFF. Existing two forwards including affordable WAIT retained, one for
no-affordable. Masked card/wait negative infinities allowed.

C3: Separate generated entry wraps only canonical real-decision call, leaves
warmup unchanged. Capture requires explicit --capture-character-identity and an
optional fresh --capture-dir; OFF delegates without capture. Both fixed arms use
the already qualified IdentityPilot; qualification covers this combined entry.
Canonical-pilot capture stays unqualified/disabled. Production files stay.

C4: Fixed fixture engineering workload: 24 public synthetic frames derived from
existing test_live_mem FRAME, deterministic two sides/elixir/clock/unit cases,
including Hero/body/cube names and incoming public projectile where supported.
Original public observer runs normally. No expert labels or model selection.
CaptureOFF/ON decisions, heads, weights, observer state/RNG/forward counts exact.
Fresh CPU4 R1e replays every saved batch/head and derives chosen action exactly.

C5: Fixed paired workload timing after four warmups, 24 pairs in alternating
OFF/ON order. Added capture median<=2ms,p95<=5ms,max<=20ms. Record copy,
serialization and total timings independently of decision-pair system noise.
Failure remains failed; no relaxed budget or unchanged retry. Capture activation
and strategic benefit remain outside this engineering qualification.

C6: Independent read-only review of privacy/source bindings/records/raw results
and exact process receipts, including explicit positive/corruption controls.
Only after replay passes may a separately registered altered-input comparison
proceed. No assumption of complete old observer history from current tensors.
