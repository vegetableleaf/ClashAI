# Bounded asynchronous capture successor

October6, original synchronous capture preserved FAILED in236e38d:42unit tests
passed;24cases/42forwards exact; median9.786750/p9512.199670ms overhead versus
original2/5ms floors. Serialization/write median7.971400ms motivates separating
disk work from the decision thread. No change to policy, reader or metric floors.

Ownership: root common.py/qualify.py/replay.py/entry.py/runner.py/docs;
capture worker async_capture.py only; test worker test_async.py only; reviewer
read-only. No tests/inference until root registration and serial inspected chain.

Reuse frozen capture tensor hooks/schema/decoder with bounded writer successor.
Queue capacity2 plus at most1 in-flight record; no unbounded executor. Immutable
detached snapshots; monotonically allocated submitted IDs. Submit never waits on
disk. Full queue disables capture explicitly and leaves policy decisions intact.
Writer errors propagate to capture status only; all previously committed records
remain index/hash verified. Pending failures/exclusions are visible, never relabeled
committed. Flush/close bounded, explicit; outside decision timing. Daemon exit may
leave uncommitted records, which loader rejects. No external or policy actions.

Process cap128records/64MiB storage; reserve conservative serialized upper bounds
including metadata and index before enqueue, enforce original actual byte cap in
writer. No new records after any cap/failure. Bounded memory uses at most3 snapshots,
each already bounded by original limits. Preserve original exact decision exception
behavior and default captureOFF. Enforce qualified checkpoint/settings/source/env.

Frozen workload exactly original24cases/fixtures/R1e/CPU4, same initial observer
state and4warmups. Reuse original OFF control arrays/case decisions; never repeat
completed OFF inference. New ON only must reproduce original saved inputs/kwargs/
allheads/decisions/observer/RNG/weights. Queue flush before offline loader checks
occurs outside decision call; report writer/flush separately, plus fixed burst
backpressure tests. Same median<=2ms,p95<=5ms,max<=20ms critical-path overhead.
Fresh replay of new actual records before entry --check, no altered-input inference.

Original record replay may complete separately without rerunning collection or
waiving original latency failure. Preserve all original sources and receipts.
No live activation, match launch, model learning, new checkpoint or model report.
