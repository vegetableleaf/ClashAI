
## L61c (2026-09-05 16:2x-16:4x UTC) -- bcA m2k: PPO erodes the BC init and re-saturates a HEALTHY head in 2,000 matches
- Pro agreement 15.44/46.61 -> 6.47/21.12 (v1) and 15.00/43.51 -> 6.98/20.11 (v2); rails 83.8% (p99 72.7) from p99 9.5 at load.
- Mechanism: bias map untouched (corr 0.9995, |d| mean 0.012); cell_conv.4 grows |d|/|w0| 0.777 -> the board-conditioned
  residual swamps a prior whose max entry is 5.32. Retracts 5cs.34's reading that the frozen head was the CAUSE of the
  circling: it is the consequence of this gradient. (a, one seed)
- Leading hypothesis (b): the sim reward prefers non-pro placement (pro play loses in our sim), so any PPO here erodes any
  pro-like init. Settled by bcB (same init + per-board KL-to-pro-prior) vs bcA at the same m.
- bcA continues to m5k as the control. New instrument L61/read_ckpt.py (both val sets + rails in one call).
