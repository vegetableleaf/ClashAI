
### §5cs.20 -- THE m30k READ: c2r HAS NOT COLLAPSED (2026-09-04, L50). >=6 share 3.3% over 6 seeds vs the gatec2_m10k reference 3.0%; the m20k dip reversed

**Pre-registered rule (owner, §6 ruling 2026-09-03 23:3x):** COLLAPSE = greedy/sampled-gate >=6 share <=1% on all 3 seeds
while gatec2_m10k reads ~3% on the same probe the same day; the m30k read is decisive. Instrument =
`tools/gate_prior_probe.py` (sampled gate, 6 envs x 400 steps, env seeds 4242+i, `--seed 0/1/2`), the same one as
L44/L46. Snapshot: `data/policy_c2r_20260903.pt` copied to `data/bench/c2r_m30k.pt` at 14:56 after the first checkpoint
save past 30,000 (log line 30050; waiter `scratchpad/gauntlet/L50/m30k_wait_probe.sh`, `wait.txt`). Probe files
`scratchpad/gauntlet/L50/ge6_c2r_m30k_s0..5.txt`, `ge6_gatec2_m10k_s0..2.txt`.

**(a) measured, same instrument, same day:**
| ckpt | seed | P(play) mean | elixir mean | >=6 share | plays <3 / 3-5 / >=6 |
|---|---|---|---|---|---|
| c2r_m30k | 0 | 0.163 | 2.76 | 3.3% | 55 / 159 / 20 |
| c2r_m30k | 1 | 0.164 | 2.94 | 5.2% | 54 / 158 / 21 |
| c2r_m30k | 2 | 0.161 | 2.70 | 2.3% | 54 / 182 / 13 |
| c2r_m30k | 3 (disjoint) | 0.156 | 2.72 | 3.2% | |
| c2r_m30k | 4 (disjoint) | 0.163 | 2.71 | 2.5% | |
| c2r_m30k | 5 (disjoint) | 0.161 | 2.92 | 3.1% | |
| gatec2_m10k | 0 | 0.170 | 2.80 | 2.7% | 54 / 171 / 23 |
| gatec2_m10k | 1 | 0.173 | 2.91 | 3.8% | 52 / 183 / 23 |
| gatec2_m10k | 2 | 0.172 | 2.73 | 2.4% | 58 / 182 / 23 |
- c2r_m30k >=6 share: mean 3.3%, band 2.3-5.2 over 6 seeds; reference mean 3.0%, band 2.4-3.8. No seed at or below
  1%. **The collapse rule is NOT tripped.** P(play) on affordable rows 0.185-0.188 vs 0.195-0.204 -- c2r is, if
  anything, slightly less trigger-happy than its init. Mean play cost 2.67-2.72 vs 2.65-2.71. Card mix at >=6: x_bow
  8-10 of 13-21 plays on every c2r seed.
- gatec2_m10k reproduces EXACTLY its L46 read (2.7/3.8/2.4): the probe is deterministic at fixed seeds, so "same
  day" is a formality for this instrument; the disjoint-seed run (3/4/5) is what gives the band.
- The whole c2r trajectory on this instrument, >=6 share, seeds 0/1/2: m5k 3.8/4.0/4.0 (L46) -> m10k 5.0/6.7/4.9
  (L46) -> m20k 1.5/1.0/1.1 (L46) -> m30k 3.3/5.2/2.3. P(play) mean 0.16 -> 0.15 -> 0.20 -> 0.16. The m20k point
  was a dip that reversed, not the start of the 18k-style slide (§5bf: >=6 -> 0 and it stayed there).
- Internal EVAL (n=150, not a discriminator, context only): ladder 31 / 27 / 23 / 31% at 24/26/28/30k (avg-5 30 /
  30 / 28 / 28), fair 21 / 17 / 17 / 24%.

**What it means.** Under `ppo_gate_prior_coef` + the schema-2 pressure table, the sampled gate has held the bank at the
init's level for 20,000 episodes past the point where the un-priored run (§5bf) had already collapsed. That is the
mechanism holding, (a) measured. It does NOT establish that the policy is improving (the >=6 share is flat, not
rising, and pros sit at 2.4-3.0% quiet / 6.6-8.6% pressure -- the run is at the quiet level, not the pressure level);
it does not establish anything about live play; and the drill suite's per-drill split at m30k was not re-read.

**Decision.** No restart. c2r continues to its `--matches 40000` (log at 30,775 at 15:17, 0.5 ep/s -> ends ~20:30).
Nothing was changed. The owner-queued sim-parity oracle step 1 (§6 ruling 2026-09-04) is next; the drill-predicate
fix (§5cs.19) and the hogeq gate-prior mirror arm (§5cs.18) wait for c2r to end.

**Traps.** (1) A Bash-tool background job with a long wait must be launched detached (`Start-Process sh.exe`); the first
waiter survived `TaskStop` and briefly ran twice -- check `Win32_Process` for the script name and kill the duplicate
tree (done; c2r's 17 procs untouched). (2) The snapshot must wait for the checkpoint file's mtime to advance past the
30k log line, or it is the pre-30k save.
