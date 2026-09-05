
### §5cs.46 -- L62g (2026-09-05 18:5x-19:1x UTC): **RETRACTION AND KILL -- THE PLAY GATE COLLAPSED IN BOTH ENGINE-PPO ARMS, AND §5cs.45's "the KL arm beats the init" DOES NOT MEAN WHAT IT SAID.** Owner watched `engA_kl_m253` in sim-view and reported it "rarely playing cards"; measured, that is an understatement: **0.12 plays/match vs the init's 36.2 on the same instrument, and its gate probability NEVER crosses the 0.25 deploy threshold (max 0.2326 over 710 decisions)** -- the gate head has gone nearly state-independent and parks just below tau. The pro-agreement metric could not see it: `read_ckpt.py` scores the per-card CELL map conditional on a play, and never touches the gate. Pair KILLED at m=422 (owner's ruling, 19:04 UTC); relaunching with the sim trainer's gate prior restored in BOTH arms.

Measured by the lead this loop with `scratchpad/gauntlet/L62/gate_probe.py` (new) and `clashrl.cli policy-stats`
(16 matches, seed 4242, `--size 432`, greedy, sim); raw JSON `L62/pstats_engA_{kl_m0,kl_m253,ctrl_m250}.json`.
(a) unless marked.

**A. The measurement (one instrument, three checkpoints -- sim, greedy, the deploy rule `sigmoid(g1-g0) > 0.25`).**

| checkpoint | plays/match | p(play) mean / p90 / **max** | frac > tau | affordable cards/decision | elixir at play |
| --- | --- | --- | --- | --- | --- |
| init `engA_kl_m0` (= BC init) | **36.19** | 0.1875 / 0.3073 / **0.6307** | 0.220 | 1.11 (59% have >=1) | 3.61 |
| `engA_ctrl_m250` (kl 0) | 1.12 | 0.0924 / 0.2236 / **0.3440** | 0.036 | 3.75 (100%) | 8.44 |
| `engA_kl_m253` (kl 0.3) | **0.12** | 0.1554 / 0.2325 / **0.2326** | **0.000** | 3.98 (100%) | 9.50 |

The KL arm's p90 (0.2325) and max (0.2326) are the same number to four decimals: over 710 decisions on varied boards
the gate emits a near-CONSTANT, and that constant sits under tau, so greedy play is not rare but arithmetically
impossible. It is NOT a masking artifact -- the collapsed arms have ~4 affordable cards at 100% of decisions (they sit
on capped elixir) against the init's 1.11 at 59% (the init spends). Card diversity died with it: `engA_kl_m253` never
played 9 of its 10 cards in 16 matches; the control never played 6. Human reference (§5cs.41 D, different instrument,
quoted as scale not as a comparison): pro ghosts play **45.1 cards/match**.

**B. RETRACTION of §5cs.45's reading.** §5cs.45 reported the KL arm at 16.73/44.02 (v1) and 16.28/42.69 (v2), top-1
ABOVE the init, and read it as "moved toward pro placements, not pinned". The numbers are correct and reproduce; the
READING was wrong. `read_ckpt.py` measures top-1/top-5 agreement of the per-card cell map GIVEN a card and a board --
it is conditional on playing and never evaluates the gate. It therefore graded the aiming of a policy that does not
shoot, and it would have scored a permanently-waiting policy just as well. **The arm GAP (+5.5 top-1 / +11.1 top-5)
still stands as a statement about the cell heads;** "the KL arm improves on the BC init" does NOT stand as a statement
about play. Trap for the record, and it is the whole reason this was missed: **every conditional metric needs an
unconditional companion** -- agreement without a play-rate readout is not a policy grade.

**C. Cause (b, and it is the lead's design error).** `engine_ppo.py` §2.1 lists, deliberately, "NOT used
(doctrine/scaffold): explore floors 0.15/0.15, gate prior coef 2.0, spell target mask, drills, hazard, distill,
search". The gate prior is not doctrine: `train_sim_ppo.py:340-348, 1758-1772` is a Bernoulli cross-entropy pulling
the GATE HEAD ONLY toward the pro `P(play | elixir bucket, phase)` table that `tools/gate_prior.py` fit from the
crawled replays (`config/gate_prior.json`: schema 1, 519 replays, 23,620 plays; single-elixir p_play 0.063 at 3 elixir,
0.203 at 9; double 0.446 at 9), with play-masked rows excluded and card/cell heads untouched. bcA HAD it; the engine
driver dropped it. So the engine run changed TWO things at once -- the environment AND the removal of the gate scaffold
-- which breaks one-change-per-experiment, and the predicted failure is exactly what happened. Secondary reading (b):
with an unshaped reward and a losing baseline, the immediate return of playing (elixir spent, card dies, counterpush)
is locally negative while the terminal penalty is shared by waiting, so "wait" is a local optimum the entropy
coefficient 0.02 on gate+card cannot hold open.

**D. Kill (owner ruling, "stop and relaunch with the gate scaffold").** State at kill, both arms m=422:
control pl +0.0021 vl 0.4546 ent 0.107 cell_ent 3.524 kl_cell 1.2150 raw_p99 7.55, cum 23W/399L; KL pl +0.0013
vl 0.3790 ent 0.165 cell_ent 3.567 kl_cell 0.0182 kl_term +0.0055 raw_p99 10.39, cum 23W/399L. `taskkill /PID <p> /T /F`
on 51956, 32284 (shims) and their children 31628, 54320. Verified: python processes **7 -> 3**, the three guarded
survivors alive (crawler 29444 + 53824, owner's uvicorn 63608), qemu 54304 UP and reused, free RAM 2.4 -> **8.6 GB**.
Checkpoints kept as evidence: `engA_{ctrl_m250, kl_m253, *_m0, *_latest}.pt`.

**E. The relaunch (agent running).** Same design, ONE difference from the killed run: `--gate_prior_coef 2.0` in BOTH
arms, so `--kl_coef` (0 vs 0.3) remains the only between-arm variable. Same init (sha asserted, read-only), seed 41,
bcA_run.yaml values, warm-up 60, `--kl_in_warmup 0`, rollout 1024, 2,000 matches, direct ports 38031/38032. New
prefixes `engB_ctrl` / `engB_kl` and logs `engB_*_20260905.log` so the killed run's evidence is not overwritten.
New monitoring in the update line (NOT an experimental variable): `p_gate` mean/p90, `frac_gt_tau`, `gp_ce`,
`gp_target`. Deliberately NOT bundled: exploration floors, the critic-warm-up fix, any kl_coef retune, any reward
change -- each is a separate arm.

**Not established.** Whether the gate prior actually prevents the collapse on the ENGINE (that is what engB tests);
whether the collapse also happens with the prior at a lower coef; the greedy play rate of these checkpoints on ENGINE
boards (b -- the probe above is the sim, because the VM was running the experiment under test; the engine's own
sampled `p_play` was 0.028-0.058, which is a DIFFERENT instrument and must not be compared with the sim greedy rate);
how much of the cell-map agreement change in §5cs.45 survives once the policy plays at a pro-like rate.
