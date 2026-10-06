# Fixed replay checks

- R1e checkpoint SHA256: 76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd.
- Two sets of 24 committed records, each with 42 saved forwards. Paired exact
  equality permits one fresh sequence of 42 model calls. No repeated OFF/ON
  collection or warmup calls. Expect six no-affordable cases and six PLAY cases.
- Exact shape, dtype and bytes for all 16 input tensors, conditioning tensors and
  every head. Preserve negative infinity padding and signed zero. No tolerances.
- Every paired metadata field matches except its manifest SHA, which is validated
  against its own manifest. Both original case summaries and independent scalar
  action reconstruction must agree with record metadata for all 24 pairs.
- Exact checkpoint file, source, runtime/settings/thread and original-reference
  bindings. CPU, four Torch threads, EVAL; every parameter gradient remains None.
  Initial/final state hashes match both prior initial/final state hashes; Python,
  NumPy and Torch RNG state is unchanged across forwards.
- Three positive action controls: no-affordable WAIT, affordable WAIT, and PLAY.
  Three malformed-manifest controls reject schema, checkpoint hash and source
  changes. One signed-zero corruption is rejected by the byte comparator.
- Four prior receipts reconcile their exact command vectors, working directory,
  exit/matched status and normalized-text output SHA. Both qualification failures
  remain failures. The new receipt is separate.
- Existing synchronous overhead median/p95/max: 9.786750/12.199670/12.854100 ms.
  Existing async overhead: 2.917800/4.975245/5.381200 ms. Original median <=2 ms,
  p95 <=5 ms, max <=20 ms floors stay unchanged. No new timing qualification.
- Explicit output: original_latency_pass=false, async_latency_pass=false,
  live_eligible=false, new_model=false. Engineering Training Camp fixtures support
  no Icebow spending, opponent-push defense or trophy-climbing claims.
