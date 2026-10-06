# Unchanged floors

R1eSHA76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd,
CPU4/eval/IdentityPilot/argmax/tau.35/handOFF/anti-leakOFF.
24originalfixed cases,4warmups,42expectedforwards; reused OFF references bound.
Exact input/conditioning/head/decision/observer/RNG/weights byte gate. No epsilon.
Submission plus copying/hook critical-path overhead median<=2ms,p95<=5ms,max<=20ms.
Report async write/flush timings separately; cannot hide decision-thread work there.
Storage128records/64MiB, queue2plusonewriter; queue saturation/failure disables only
capture; actual policy exceptions propagate. Commit/index checks identical original.
No throughput or current-client timing claim from offline fixture timing alone.
