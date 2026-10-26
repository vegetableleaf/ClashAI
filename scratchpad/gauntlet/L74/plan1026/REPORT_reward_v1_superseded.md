# ClashBot rebuild: reward and training design

This is a plan only. I changed no files. It is based on the failure documents you listed, the committed HANDOFF, and the code paths in `rl_royale.py`, `e1_eval.py`, `decision_options.py`, `live_gen_v2.py`, `cf_credit.py`, `search_s0.fork_into`, `match_memory.py` and `livecal.py`.

## What the code shows (why failure #1 keeps coming back)

There are three separate decision stacks today, and they drift apart:
- **Training rollouts:** `e1_eval.sample_decide_batch`. Model-only sampling, no rules.
- **SIM eval:** `decision_options.decide_batch`, configured by a hand-copied subset of the live flags (`L74/livecal/livecal.py:29`). It is missing `barrel_lane`, `lethal_quiet`, `rocket_value`, `rocket_tornado`, `log_air` and the IW press head.
- **Live:** `live_gen_v2.decide`. It re-implements `decide_batch` line by line (its comments say "SIM decide_batch: the same ...").

Every train/deploy mismatch on your list (sampled gate vs hard threshold, `tau_phase`, IW press 5.4 vs 1.9, combo / lethal_quiet / barrel_lane only live) comes from this split. The fix is structural, not another flag.

---

## 1. Core principles

**P1. Deploy exactly what you train: one `decide()` used by rollouts, forks, SIM eval and live.** (Failures 1, 11)
- **Decision: deploy the sampler itself, not a threshold.**
  - The gate is `Bernoulli(sigmoid((z − logit tau_phase)/T_gate))` with `T_gate = 0.1`.
  - It is applied per unit of time: `p_step = 1 − (1 − p_b)^(dt/0.5 s)`. `dt` comes from `live_gen_v2.hazard_step_s` live (capped at 2 s) and is 0.5 s in the SIM, so the two are identical.
  - Card and cell are sampled at T = 0.1 too, if a pre-check passes (see 3a). Otherwise they are argmax everywhere.
- **Why not a hard threshold with T .1 training:**
  - A "free" band of about ±0.3 logits around tau still exists, where training plays 5–95% of the time and deployment plays 0 or 100%. The 10-26 leak was exactly this, only wider at T .3.
  - The rate-decode test (same checkpoint: 16 s leak but −25 pp win) shows that a checkpoint trained under one decoder is broken under any other. The only safe state is the same decoder.
  - The measured cost of a T .1 sampled gate vs greedy is −0.42 pp [−5.6, +5.0] (`L74/gap/FINDING.md`), so deploying it is free.
  - PPO ratios become exact, there is nothing to "lower for free", and the KL leash measures real behavioural change.
- **This removes the gate-temperature dilemma.** T is chosen for play quality only. Exploration comes from counterfactual forks (P3), not from action noise.
- **Rules:** only your finishers stay (lethal Rocket / Log, with `lethal_quiet`). They run inside `decide()` in every path, and rule-forced rows are marked as forced and left out of PPO. Every other live decision rule is removed. That includes rocket_tornado, rocket_value, tau_threatened, xbow_class class_sample, log_air, xbow_dead_lane, rocket_dead_target and spell_aim. You asked for barrel_lane on 10-25, so it is your call: keep it and it moves into `decide()`, or drop it.
- **One source of truth:** the SIM decision config is generated from the `LIVE_OPTIONS` file, and a SIM eval whose options differ from the deployed file is refused.
- **Perception and actuation are mirrored in the SIM as conditions:** extrapolate 24, afford-ticks, action delay, L16 levels, and the IW press head with the same decode.

**P2. The reward is the win, and nothing else.** (Failures 3, 4) No term pays a behaviour and no potential shaping is used; both are measured as farmed or null.

**P3. Exploration and long-horizon credit come from counterfactual SIM forks.** (Failures 1, 5, 12) A fork credit is a difference in the same win objective between two actions from the same state. In expectation it cannot pay something that does not raise P(win).

**P4. Audit the SIM's incentives; never patch them with reward.** (Failures 5, 13)
- Before a fork trigger is switched on, forks on scenario states measure how the SIM prices each doctrine action.
- If the SIM disagrees with pro and live evidence (for example, it says a Rocket on a Ram Rider loses), that trigger stays off and the case goes to the engine or opponent pillar as a fidelity bug.

**P5. Keep each run stationary.** (Failures 6, 7)
- The opponent pool is frozen and versioned for each run, with no learner snapshots in it (`league_mix` latest/older/init = 0).
- The KL anchor is fixed, and moves only after a promotion is verified live.
- Runs are capped at 100 updates.

**P6. Selecting a checkpoint and confirming it use different seeds.** (Failures 8, 9) Two or more seeds per arm. The checkpoint is chosen on a selection block and promoted only on sealed confirm blocks (a new seed registry, `SEEDS.md`; the old 741200–744000 blocks are spent). Gates use pooled CIs.

**P7. SIM-predicts-live is measured, not assumed.** (Failure 2)
- A sealed live calibration block of the parent gives per-metric SIM-to-live offsets and the win shrinkage slope (currently 0.38 [−0.30, 1.06]).
- SIM gains are split into archetypes where the SIM matches live and archetypes where it doesn't. Hog, golem and lava are currently 30–39 pp too easy in the SIM.
- If a live block lands outside its prediction interval, the lineage stops.

**P8. No imitation into policy heads.** (Failure 10) Pro data trains only auxiliary or representation heads, as the S3-aux encoder already does.

**P9. Memory must have information value before it can be rewarded.** (Failure 13) Run the adaptation-value audit, use persona opponents, and gate on a memory ablation.

**P10. Instruments read played behaviour, not pro agreement.** (Failure 8)
- Every metric runs on games played with the deployed `decide()`, through one code path for SIM, live and pro, with a planted-bug test.
- Pro agreement is demoted to a tripwire.

---

## 2. Reward

**What is rewarded:** R = +1 win, −1 loss, 0 draw at the end of the match, decided by the SIM's real rules, including `overtime_tiebreak`.
- No crown bonus: trophies do not count crowns, and a crown bonus pays 3-crown gambles (mistake 3).
- Tiebreak HP counts only through the win rule.
- Dropped from new recipes: habit_terms (leak, idle, trade, xbow cost), reward_terms (rocket_tower, rocket_cycle, king_redirect, lead_protect, redirect, tornado_king), spell_value, all shaping, the posture head, opt3's branch_gate, and `kl_ref_refresh_every`. The recipe validator refuses these keys. The code stays for old A/Bs.
- The leak is not given a term back. Its confirmed root cause is the decoder mismatch, which P1 removes. A fork trigger (T7 below) credits playing vs waiting at full elixir directly, and the drift bars catch a regression. If the leak survives identical decoding, the SIM does not punish it; that goes to the opponent pillar.

**Things that are not rewards:**
- The S3-aux memory heads (frozen encoder, zero_empty, learned coupling).
- A critic calibration audit: a reliability table of the critic's value by phase and HP margin against actual outcomes, run before forks are trusted.

**Counterfactual fork credit.** This extends `pipeline/cf_credit.py` and the existing hook into `e1_eval.run_selfplay_batch`.

Triggers (budget about 4 fork points per match; the probabilities are set by the pilot):

| ID | Fires when | Alternatives (the policy's own argmax cell within each allowed set) |
|---|---|---|
| T1 rocket_avail | Rocket affordable and not played | rocket_clump (≥ 2 elixir of value), rocket_princess (weakest princess), base |
| T2 rocket_played | the policy plays a Rocket | wait, the policy's second card |
| T3 defence_wincon | a building-targeting win condition (Ram Rider, Balloon, Royal Hogs, Hog, Giant, Golem, Lava ...) is on my half; Tesla's cycle position is logged as context | Rocket on it, Knight in front, Skeletons pull, wait |
| T4 siege | an enemy Mortar or X-Bow is in reach of, or locked on, one of my towers (as in the draft) | siege_<card>, front_<card> (pros answer ~7 tiles in front within ~2 s; Rocket only ~10%) |
| T5 xbow_after_fail | within 30 s of a failed reach X-Bow | wait, defensive X-Bow (own half), rocket_princess, base |
| T6 xbow | the policy plays a reach X-Bow | wait, defensive X-Bow, other lane (at 1-1: the other princess) |
| T7 idle_full | elixir ≥ 9.5 with the gate closed, or no play yet at t ≥ 8 s | play now (policy argmax) |

"wait" is always an alternative when the base plays, and "play now" when the base waits. At most 3 alternatives per fork.

**Estimator:**
- ΔQ(alt) = mean over k of V_end(alt) − mean over k of V_end(base), with K = 2 paired continuations per action using common random numbers.
- Base sample 1 is the real trajectory itself, read from the trajectory's row at root + H. This saves a continuation; the current Runner re-simulates it.
- V_end is the critic at the first learner decision at or after root + H, or the terminal outcome if the match ends first.
- Advantage for the alternative's row:
  `A_alt = cf_w · clip(ΔQ/sd_real, ±3) · ΔQ²/(ΔQ² + SE²)`
  with cf_w = 1 and sd_real = the standard deviation of the batch's real-row GAE advantages before normalisation (as in the draft). The last factor shrinks noisy alternatives toward zero.
- Rows enter PPO through the existing `cf_append` path, with behaviour log-probs at the deployed temperature. The PPO clip (×1.2 per pass) is the deliberate trust region.

**Horizon:**
- 600 ticks (30 s) by default; 400 for Rocket triggers in single and double elixir.
- **Terminal** (no critic) once ≤ 60 s of overtime remain. Close tiebreaks are where chip Rockets matter (live ~5% of matches end in a tiebreak within one Rocket; the SIM matches at 6%).

**Noise and bias control:**
- **Bias audit:** 10% of forks are extended to the terminal outcome. For each trigger, the slope of terminal ΔQ against critic-bootstrapped ΔQ must fall in [0.7, 1.3]; otherwise that trigger's horizon is lengthened.
- **Noise:** a trigger whose pilot median |ΔQ|/SE is below 0.5 is disabled, because it adds only noise.
- **Cost:** fork compute ≤ about 1× the main rollouts. Main matches per update drop from 64 to 48 (E 12 × G 4).

**Why it can't be farmed:** in expectation ΔQ = Q(s, alt) − Q(s, base) for the same objective. The only bias is critic error at the horizon, which is the same function on both branches and is audited. It can still exploit SIM bugs, as any win-maximiser can; P4 and P7 guard against that.

**How match memory is made to pay:**
- **(a) Adaptation-value audit, before any training (cheap):**
  - In the opponent pool, compare P(lock | our previous reach X-Bow failed) with P(lock | it locked), against the same split on live CLX/CLXIII.
  - Run a persona-oracle fork test: ΔQ(X-Bow again vs wait, after a failure), split by opponent persona.
  - If failures don't predict future failures, and ΔQ doesn't change sign between personas, memory has nothing to learn. Memory promotions are then blocked and the gap goes to the opponent pillar. This is why CLXIV doubled down: SIM denial is nearly uniform (lock 0.54–0.63, shut-outs 3–7%, vs live 9–16% and 0.13–0.74 by archetype).
- **(b) Opponents:** a persona latent drawn per match, fixed within the match and varied between matches and within a deck. At least these axes: X-Bow denial (holds the counter, then counter-pushes), bridge pressure, holding spells in reserve, lane preference, banking. Fitted to the live tails. Interim: `adaptive_opponents.opp_style` plus D1 u60 (the strongest denier) against I u40.
- **(c) Credit:** T5 and T6 give the "X-Bow again vs switch" signal. Its sign depends on the persona, and memory is the only input that reveals the persona, so the gradient has to flow through the memory coupling.
- **(d) Gate:** paired comparison of real memory vs memory shuffled from another match against the same deck, and vs empty memory.
  - A promotion as "ADAPTIVE" needs real − shuffled with CI low > 0.
  - Any promotion needs real − shuffled ≥ −1 pp.
  - abl.sh needs its fix first (it ran 0 pairs on 10-26).
- **(e) Mid-match adaptation metrics** (one code path for SIM, live and pro; extends `memory/xbow_arch.py` and `live_watch.py`):
  - **X-Bow persistence ratio** = P(reach X-Bow within 30 s | last one failed) / P(same | last one locked). CLXIII live 1.34, CLXIV 3.7; target ≤ 1.0.
  - **Conditional lock gain:** the lock rate of X-Bows placed after a failure should be at least the overall lock rate.
  - **Switch rate:** after two or more failures, how often it switches to a defensive X-Bow or a chip Rocket within 60 s. Pro reference: a chip Rocket within 30 s of a failed bridge X-Bow 18.4%.
  - **Memory-swap probe:** on 2,000 recorded live states, replace the memory with a synthetic "2 failed" vs "2 locked" history. ΔP(reach X-Bow) must be negative.

---

## 3. Training procedure

**a. Starting point (B0) and the decode check.**
- B0 = CLXIII raw plus the S3-aux memory v2 encoder (sha 3d75a25d) with zero coupling. It is identical to CLXIII at u0, which a CPU identity test checks.
- Round 0 is an eval only (one change: the decoder). 1,920 SIM pairs each:
  - B0 with the unified gate (T .1) and argmax card/cell
  - B0 with all three heads at T .1
  - B0 under today's SIM stack
- Rule: adopt all heads at T .1 if it is within −1 pp of argmax (CI low > −2.5 pp). Otherwise card and cell stay argmax and learn only from forks.

**b. Anchor.** KL to a frozen B0 for all three heads, measured on the deployed (T .1) distributions; `kl_target` 0.10, which you control. This extends the existing `kl_ref_gate` / `kl_ref_card` to a `kl_ref` that covers the cell head too.
- The anchor moves to a new checkpoint only after that checkpoint passes live (L6), never after a SIM-only win.
- This caps how far the lineage can drift; widening the cap is your decision.

**c. Environment.**
- A frozen, sha-registered pool per run, made of the opponent pillar's release or the interim pool (D1 u60, I u40 cal, W18 R3 cal, E4, plus opp_style personas, counter decks ×3).
- 20–25% of matches start from scenario states.

**d. Learner.** Critic warm-up of 5 updates; GAE γ_tick .99994, λ .95; lr 1e-5, clip .2, 2 epochs, minibatch 256.

**e. Seeds, length, drift checks, selection.**
- 2 seeds per arm, 100 updates at most, checkpoints at u25, u50, u75 and u100.
- Every 25 updates: a 960-game drift check vs u0 on the selection block (drift_check bars, plus first play and seconds at full elixir now as gating metrics), the probe-set KL by state cluster (opening, full elixir, under attack, OT), and the memory-swap probe.
- Stop at 2 consecutive flags.
- Selection: the best of 4 checkpoints × 2 seeds per arm on the selection block, then confirmation on sealed blocks.

**f. Compute on four 4090 pods.**
- About 4.5 min per update on a quiet pod with forks (an estimate; the pilot measures it). 100 updates is about 7.5 h, plus about 2.7 h of drift checks, so about 10 h per pod-run.
- Gate: about 4.5 h on 2 pods. One round is about 15 h of wall time.
- Rounds, one change each:
  - **R1:** unified decode without forks vs with forks.
  - **R2:** forks with the opponent pillar's personas vs the interim pool.
  - **R3:** unfreeze the memory encoder, or add an online lock-prediction aux head.
- Each round's winner becomes the next run's starting point. The anchor stays at B0.

---

## 4. Evaluation ladder

Anything that fails a rung stops there.

- **L0 Identity:** recorded rows replayed through the rollout, eval and live paths of `decide()` must give identical logits, log-probs and actions. `LIVE_OPTIONS` must equal the generated SIM config.
- **L1 Fork pilot** (200 matches): fork cost share, SNR per trigger, the bias-audit slope, and the baseline reproducing the real continuation (the existing test).
- **L1b Incentive audit:** fork ΔQ on the scenario suite, compared with doctrine and pro data. Expected signs:
  - Rocket on Ram Rider / Balloon / Royal Hogs with Tesla out of cycle: positive.
  - Rocket on a lone Golem: negative.
  - Troop in front of a locked Mortar: positive.
  - Chip Rocket in a close OT: positive.
  - X-Bow after failures against a denier: negative.
  - A mismatch disables the trigger and goes to the engine or opponent pillar.
- **L2 Drift:** as in 3e.
- **L3 SIM gate,** candidate vs parent on held-out personas and decks, 3,840 confirm pairs:
  - pooled win delta CI low > 0, with the matches-live archetype group ≥ −1 pp (non-inferior);
  - behaviour bars vs parent: idle, ignored, trade, full-elixir seconds, first play, plays/min;
  - habit metrics must not move the wrong way: Rockets per match, defensive-Rocket share on building win conditions with Tesla out of cycle, Rocket-on-lone-tank share, X-Bow persistence ratio, give-back rate after leading 1-0, damage concentrated on the weakest princess, king damage ≈ 0;
  - the memory ablation from section 2(d);
  - the probe-set KL within budget, and no state cluster with more than 30% argmax flips.
- **L4 Scenario forks from live states:**
  - **Built** from about 800 live CLX/CLXIII replays: clock, tower HP, elixir, both cycles rebuilt from public plays, and a forced replay of the last 10–20 s of plays.
  - **Accepted** only if the SIM board at the target tick matches live (units within 1.5 tiles, HP within 15%).
  - **Scenarios:** Mortar locked (pros lose 611 HP of the lane princess in 30 s and it falls 8.4% of the time; the SIM is currently 0.29 win vs Mortar decks against 0.67 vs other decks); Ram Rider / Balloon / Royal Hogs with Tesla out of cycle; lone Golem; close OT; after 2 failed X-Bows against a denier; up 1-0 in double elixir; 1-1.
  - **Pass:** 200 runs per model; no scenario more than 2 pp below the parent, and at least one target scenario better with CI low > 0.
- **L5 Calibration:**
  - A sealed live block of B0 under the unified stack, about 150 matches that you run and that are never used for tuning.
  - It gives per-metric offsets and updates the slope; every candidate gets predicted live metrics with intervals.
- **L6 Live** (you start it; pre-approved only if every rung above passed):
  - A 60-match first block. Alarms: behaviour outside the predicted interval, or win more than 15 pp below the parent (80% bound).
  - Then 300 matches for the calibration update and anchor re-basing.
  - Live has the power to catch a regression and check the predictions, not to confirm a 2–3 pp gain (3 pp needs about 4,361 matches per arm).

---

## 5. What I need from the other pillars, and how this behaves before they are perfect

**From (a), the engine:**
- deterministic fork `save_state` / `load_state` (exists);
- mid-match state injection (units, HP, elixir, cycles), or a robust forced-prefix replay;
- live levels and live latency conditions;
- throughput at least today's (forks add 1.5–2×);
- a parity report for each mechanic the scenarios use (Tornado vs the river, Rocket damage on towers, Mortar / X-Bow targeting, king activation, the tiebreak rule).

**From (b), the opponents:**
- a per-match persona latent API that also works inside forks;
- archetype calibration within tolerance: P(opponent takes a princess) within 10 pp of live (SIM −24 now), give-back after we lead 1-0 within 5 pp (live 14.5%), X-Bow lock rate and shut-out share, P(win) gap within 10 pp;
- held-out personas for the gates;
- versioned releases.

**Before they deliver:**
- The interim pool plus opp_style is used.
- Gates use the matches-live / doesn't-match-live archetype split.
- Triggers that fail the incentive audit stay off.
- The memory gate is advisory until the adaptation-value audit passes.
- No reward term compensates for a SIM gap. Gaps are reported to the pillar.

---

## 6. Files to build or modify

- **Modify:**
  - `pipeline/decision_options.py`: `decide_batch` gets a `gate_decode='sample'` mode (tempered draws from each match's RNG, log-probs, per-time hazard); finishers mark rows as forced.
  - `pipeline/e1_eval.py`: `sample_decide_batch` delegates to it; `selfplay_decide` uses one path for the learner in rollouts, forks and evals; `lethal_quiet` HP history added to the SIM path (owed per the memory ledger).
  - `pipeline/live_gen_v2.py`: `decide()` calls the shared function and stops duplicating it.
  - `scratchpad/gauntlet/L74/livecal/livecal.py`: `LIVE` is generated from the `LIVE_OPTIONS` file.
  - `scratchpad/gauntlet/L70/live/LIVE_OPTIONS`: stripped to finishers plus latency and perception flags.
  - `pipeline/cf_credit.py`: K paired continuations reusing the real trajectory, SE shrinkage, triggers T3 and T7, per-trigger horizon and terminal OT, bias-audit flag, per-trigger enable list.
  - `pipeline/rl_royale.py`: a `kl_ref` key for all heads, refuse `kl_ref_refresh_every` and the old term keys, no learner snapshots, a general scenario-start table (generalising `ot_start_share` / `xbow_start_share`).
- **New:**
  - `pipeline/tests/test_decide_identity.py`.
  - `scratchpad/gauntlet/L75/ladder/` containing `probe_kl.py`, `adapt_metrics.py`, `mem_swap.py`, `scenarios.py`, `incentive_audit.py`, `calibrate.py` (extends `opp_model/analyze.py` J11), `gate.sh` (generalises `arm_chain.sh` / `night_decide.sh`), and `SEEDS.md`.

---

## 7. Risks and timeline

**Risks:**
1. **The SIM simply doesn't pay the habits** (chip Rockets, defensive Rockets). Then nothing gets learned, which is the honest result. The audit shows it on day 4, not after a week of runs.
2. **Fork cost or noise.** The pilot sets K, H and the trigger set; low-SNR triggers are dropped.
3. **Critic bias.** Covered by the terminal audit and terminal-only credit in late OT.
4. **Live cadence differs from the SIM.** Covered by the per-time gate and checked on the calibration block.
5. **Personas are learnable SIM tells rather than human behaviour.** Covered by held-out personas and the live adaptation metrics.
6. **Live performance may dip at first when the live-only rules are removed.** The sealed block measures this before any candidate goes live.
7. **Low live power.** Promotions rely on behaviour predictions; trophies are a long-run measure.

**Timeline:**
- **Days 1–3:** unify `decide()`, add identity tests, generate the SIM config from `LIVE_OPTIONS`, build the ladder tools; run Round 0. You run the sealed B0 live block (about one day of play).
- **Days 3–5:** fork pilot, incentive audit, adaptation-value audit.
- **Days 5–6:** Round 1 (about 10 h of training) and the gate (about 5 h).
- **Day 7:** if a candidate passes every rung, a live block (pre-approved).
- **Days 8–14:** Round 2 and Round 3 as the pillars deliver.
- **Top 1,000 is a weeks-to-months goal.** History so far: the SIM gains +4 to +10 per promotion, but live gains only +1 to +5. The rate depends mostly on how fast the pillars close the SIM-to-live gap.

---

### Critical Files for Implementation
- C:\Users\benpe\ClashBot\pipeline\decision_options.py
- C:\Users\benpe\ClashBot\pipeline\e1_eval.py
- C:\Users\benpe\ClashBot\pipeline\cf_credit.py
- C:\Users\benpe\ClashBot\pipeline\rl_royale.py
- C:\Users\benpe\ClashBot\pipeline\live_gen_v2.py
