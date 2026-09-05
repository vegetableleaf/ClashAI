
### §5cs.39 -- L61c (2026-09-05 16:2x-16:4x UTC): bcA m2k READ -- PPO ERODES THE BC INIT FAST AND RE-SATURATES THE HEAD FROM A HEALTHY START: pro agreement 15.44/46.61 -> **6.47/21.12** (v1 sim boards) and 15.00/43.51 -> **6.98/20.11** (v2 engine boards) in 2,000 matches; rails 83.8% of masked cells |raw|>8 (p99 72.7) after loading at p99 9.5. Mechanism: the BIAS MAP is untouched (corr 0.9995 with its init, |d| mean 0.012) -- it is `cell_conv.4` that grows (relative |d| 0.777) until the board-conditioned residual swamps a prior whose largest entry is 5.32. So the collapse is NOT "the head starts at the rails" (that was the §5cs.34 reading): a healthy head put there by BC re-saturates under this sim's PPO gradient within 2k matches

Instruments: `L61/read_ckpt.py <ckpt>` (new: pro agreement on BOTH val sets + rails, one call), snapshot
`data/bench/bcA_m2k.pt` (sha e3b30e70..., matches=2000, byte-identical copy of `policy_bcA_20260905.pt` at
16:35 UTC). References carried forward from §5cs.36/§5cs.37 (same instruments, same val rows): init
`bc_bias_native_s0` 15.44/46.61 (v1) and 15.00/43.51 (v2); c2r_best 3.49/11.75 and 2.78/11.10; board-blind
prior 13.65/40.04 and 12.08/37.66. (a) one training seed.

| read | v1 top-1/top-5 | v2 top-1/top-5 | rails frac | conv4 growth |
|---|---|---|---|---|
| BC init (m0) | 15.44 / 46.61 | 15.00 / 43.51 | ~0.0 (p99 9.5 at load) | -- |
| bcA m2k | **6.47 / 21.12** | **6.98 / 20.11** | **0.838** (p99 72.7, mean 20.2) | \|d\|/\|w0\| 0.777 |
| c2r_best (§5cs.34/37) | 3.49 / 11.75 | 2.78 / 11.10 | 0.922 (p99 62) | -- |
Per card at m2k (v1): the_log 18.2/51.0 and tesla 20.0/31.4 survive; knight 0.0/5.6, x_bow 0.0/39.6,
tornado 0.0/6.9 -- the same cards the old checkpoint zeroed. Weight-level diff vs the init: bias map |d| mean
0.012 / max 0.552, correlation 0.9995 (PPO barely touches it -- it is one parameter per (card, cell) fed only
by the cells actually played); `cell_conv.0/2` relative |d| 0.11, `cell_conv.4` **0.777**, absmax 0.33 -> 0.42.

**What this establishes.** (a) The IL init alone does not survive contact with this sim's PPO: 2,000 matches
(~45 min) take it from 3.5x the old checkpoint's pro agreement to 1.9x, and the head is back at the rails.
(a) The rail guard is not the fix and never was: the head arrives healthy (p99 9.5) and re-saturates anyway.
(c) **Retraction of the §5cs.34 reading** that "PPO has been pushing on a head that cannot move" as the
explanation of the circling: the frozen head is a CONSEQUENCE of this gradient, not only a starting condition.
The gradient itself drives the cell logits to the rails, and it points away from pro placement.
(b) Untested but now the leading hypothesis: the sim's reward genuinely prefers non-pro placement (pro play
loses in our sim -- 26.1% crowns-parity, §5ay), so any PPO on this sim erodes any pro-like init. Measurement
that would settle it: bcB (same init + per-board KL-to-pro-prior on the cell head) vs bcA at the same m; if
the KL coefficient large enough to hold agreement also collapses the sim reward, the sim and pro play are
in direct conflict and the sim -- not the init, not the head -- is what has to change.

**Decision.** bcA keeps running to m5k as the control half of the pair (killing it would leave bcB unattributable
-- the E/G lesson, §5cs.35). bcB = the same init plus the KL term, one change, launched when the trainer code is
ready and the box has room (bcA 12 workers, crawl, Nucleo; 9.9 GB free at bcA's launch).
