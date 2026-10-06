# Capture timing review

The synchronous attempt and asynchronous successor are preserved in commits
236e38d and 1f433fc. Both completed all 24 fixed cases with exact inputs, outputs,
decisions, observer state and unchanged weights. Both failed the unchanged 2 ms
median overhead limit. Capture remains disabled in the owner's live process.

| Recorded interval | Synchronous median ms | Asynchronous median ms |
| --- | ---: | ---: |
| Hook/row copying and validation | 1.520350 | 2.105000 |
| Serialization or submission/schema | 7.971400 | 0.305750 |
| Total capture overhead | 9.786750 | 2.917800 |

The asynchronous outer admission/cleanup median was 0.023550 ms. Its p95 was
4.975245 ms and maximum 5.381200 ms; these met the original 5/20 ms limits.
All 24 submitted records committed, and the writer closed with no pending records
or exclusions. The measurements include the existing owner worker's environment;
they do not establish the cause of scheduling variation between attempts.

Read-only source review identifies repeated per-tensor finite scans, repeated
cumulative byte sums, and another schema traversal before enqueueing. The saved
timers aggregate these operations and cannot assign each a measured cost. A future
separately registered successor could keep the strict public whitelist, structural
bounds, dtype/device/layout checks and detached copies on the decision path, then
validate immutable snapshot contents in the writer before any record commits.
The original loader, checksums and rejection behavior must remain. No savings are
assumed, no inputs may be cached across forwards, and no third speed trial is
registered by this note.

The immediate remaining evidence step is a separately registered fresh CPU4 R1e
replay of both saved archives. It must preserve both failed latency verdicts.
These fixtures use a Training Camp deck and contain no enemy troop push; exact
replay supplies engineering evidence. Tactical Icebow spending requires a separate
coherent public scenario set and complete resource/outcome sequences.
