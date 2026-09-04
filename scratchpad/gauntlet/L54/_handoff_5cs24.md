

### §5cs.24 -- EARLY-STOP READ ON c2r AT m35k (2026-09-04, L54, owner-requested): every instrument the run has is flat from 8k to 36k, the >=6-share read fell back to the m20k level (mean 1.3% over 6 seeds, m30k 3.3%) with the SAME signature as m20k (P(play) 0.20, elixir mean 2.5), and the best checkpoint was rewritten at EVAL@36000 on a 30% -> 31% ladder avg-5 that is inside the instrument's noise. Verdict: an early stop is justifiable; the run is NOT collapsed by the standing rule. Decision put to the owner (irreversible); run state recorded here per §7

**Owner ask (18:0x):** "can you eval the PPO run right now to determine whether an early stop is justifiable?"

**What ran.** `cp data/policy_c2r_20260903.pt data/bench/c2r_m35k.pt` (the 17:59 save; the log crossed 36,000 at
18:07, saves are ~12 min apart, so the snapshot is ~35,700 eps -- called m35k). `tools/gate_prior_probe.py` on it,
seeds 0-5 (same instrument, same seeds, same day as §5cs.20's m30k read), ~25 s each beside c2r; outputs
`scratchpad/gauntlet/L54/ge6_c2r_m35k_s0..5.txt`. Plus the run's own log: EVAL lines, per-4k training winrate,
drill pass rate, entropy.

**Run state at the read (recorded before any stop, §7):** 36,100 episodes at 18:11 (0.5 ep/s, 3335W-25120L-11D);
`policy_c2r_20260903_best.pt` rewritten 18:08 at EVAL@36000, ladder(L13-16) avg-5 31%; last periodic save 18:11;
17 python procs, 4.2 GB free, CPU 79%. ETA 40,000 ~ 20:20. Nothing else on the box.

**(a) measured.**
- >=6 share, m35k: 1.1 / 1.6 / 1.4 (s0-2), 1.4 / 0.9 / 1.2 (s3-5), mean 1.3%. m30k (§5cs.20, same instrument):
  3.3 / 5.2 / 2.3, 3.2 / 2.5 / 3.1, mean 3.3%. gatec2_m10k: 2.7 / 3.8 / 2.4. Full c2r trajectory: m5k 3.8/4.0/4.0
  -> m10k 5.0/6.7/4.9 -> m20k 1.5/1.0/1.1 -> m30k 3.3/5.2/2.3 -> m35k 1.1/1.6/1.4. Every m35k seed is above the
  collapse rule's <=1% line except s4 (0.9); the rule needs all three of s0-2 at <=1% -- NOT met.
- The m35k signature is the m20k signature: P(play) mean 0.19-0.20 (m30k 0.16, m20k 0.20), elixir mean 2.45-2.62
  (m30k 2.70-2.94), >=6 plays 11-15 per 2,400 rows (m30k 13-24), x_bow at >=6 5-10 (m30k 8-14). The policy is
  alternating between a spend mode (m20k, m35k) and a hold mode (m10k, m30k); it has visited each twice.
- Internal EVAL (n=150/point, context only): ladder 30,19,30,33,30,27,31,27,23,31,34,33,33 at 12k..36k, avg-5
  28-31; fair 19,12,24,22,21,20,21,17,17,24,21,17,23, avg-5 19-21. The new BEST at 36k is avg-5 30% -> 31% (750
  matches, +-3.4pp): noise-level.
- Training winrate per 4k window: 10.2% (16-20k), 9.7% (28-32k), 8.9% (32-36k). Drill pass-all 47,47,46,46,46,46,
  45,46% at 8k..36k. Entropy 0.05-0.08 throughout. Nothing has moved since 8k on any of these.

**(b) plausible, untested.** Whether m35k's dip is the start of a slide rather than the third visit to the spend
mode -- the only cheap discriminator is the m40k point (~2 h away). Whether 4k more episodes could move a plateau
that has held for 28k -- no instrument here says so; the prior from this run says no.

**(c) contradicted.** "c2r has collapsed" -- no: the rule is not met, and the identical m20k state reversed by m30k.
"Stopping loses the best artifact" -- no: `_best.pt` is written only on a new ladder avg-5 high and was just
rewritten at 36k; a stop at 36k keeps it byte-for-byte.

**Verdict.** An early stop IS justifiable: (1) both the run's own EVAL and the mechanism read are flat over
28k episodes; (2) the best checkpoint is banked and protected; (3) the remaining 3,900 eps are ~10% of the run and
~2 h of a box that blocks oracle step 2 (emulator). What a stop gives up: the m40k mechanism point (wobble vs
slide). My recommendation is to stop now and take the two hours -- but the kill is irreversible, so it is the
owner's call; no kill on my judgement.

**If the owner says stop:** verify 17 python procs before, kill the train-sim-ppo tree, verify 0 after; the
deliverable checkpoints are `_best.pt` (36k, ladder avg-5 31%) and the m35k/m30k snapshots in data/bench; then
run the post-c2r queue (§6) starting with oracle step 2 on the swarm tags. **If continue:** m40k read at ~20:20,
same instrument, seeds 0-5, then the same queue.

**Traps found.** (1) A "new BEST" line is a 750-match ladder avg with +-3.4pp noise -- a 1pp best is not a
finding; read the mechanism probe instead. (2) The snapshot label must come from the save time vs the log
crossing, not from the log line you happen to be looking at (17:59 save = ~35.7k, not 36k).
