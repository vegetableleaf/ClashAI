# Frozen qualification metrics

CPU-only selected R1e31u0155, four torch threads, eval, original argmax/tau.35,
anti-leakOFF/handOFF. Original checkpoint hash 76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd.
All actual 16 feature4 batch tensors and all gate/value/card/wait/g/cell heads,
conditioning and chosen decisions must be byte-identical. Include original
affordability inputs, grid, card vocabulary, raw/model tick, match/capture IDs.
No optimizer/backward/weight changes or model-strength claim.

Caps:128 records/64MiB per process; strict source/checkpoint/environment manifest.
Four warmups,24 fixed paired decisions; alternating execution order. Capture's
own added wall time median<=2ms,p95<=5ms,max<=20ms; also report paired total deltas
without using negative noisy differences to conceal instrument overhead.
Storage/copy/time cap failure is explicit and disables only capture. Decisions
and model exceptions retain original semantics. A failed numerical/budget gate
cannot be waived by good values elsewhere. Exactness has no tolerance.
