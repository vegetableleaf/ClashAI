I've read every source and found nothing blocking. The working-copy ledgers match HEAD, except `L74/combo/RL_COMBO_REWARD.md`, which I read at HEAD.

**How to read the citations**
- `H:L<n>` is a line in `git -C C:\Users\benpe\ClashBot show HEAD:HANDOFF.md` (15,474 lines; newest first). The 10-04..10-12 entries are a `>` blockquote at L7785-10336 plus L15372-15474. The Aug-Sep "old HANDOFF" is L10336-15137.
- `EXP` = `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\succ48\EXPERIMENTS.md`
- `LED` = `...\L74\memory\LEDGER.md`
- `PA` = `...\L74\memory\PLAN_A.md`
- `RA` = `...\L74\reward\REWARD_ARCHITECTURE.md` (the 10-14 architecture draft; worth reading in full)
- `RP` = `...\L69\reward_plan.md`
- `EXPL` = `...\L74\exploit\EXPLOIT.md`
- `OPP` = `...\L74\opp_model\OPP_MODEL.md`
- `AN` = `...\L74\opp_model\analyze.out`
- `ROC` = `...\L74\rocket\ROCKET.md`
- `GAP` = `...\L74\gap\FINDING.md`
- `REG` = `...\L74\models\REGISTRY.md`
- `M1026` = `...\L74\memory\measure1026\` (10-26 measurements, no write-up yet)
- `mem:<name>` = `C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\<name>.md`

**Two name collisions to watch:**
- "R1" (rseries GAE, 10-02, Mark XLIII) is a different model from "r1" (NEWSIM re-attempt, 10-13..15, Mark CXII).
- "E1" / "E2" each name several unrelated things: defence-RL arms (10-09), the bait arm (10-21), the drift_tg run (10-22), and the succ48 E-rows (10-22/23).

---

## 1. Chronological catalog

### Era 0: Aug, own sim, hand-shaped rewards (REG Marks I-XXIII; RP §0)
- **08-07 DDQN, 08-23 wincon_reach drill PPO, 08-26 long run with reward fixes (Marks I-III).** About 11% win over 150 matches, 34% "ladder" eval.
- **`threat_miss_idle` free-standing penalty.** The elixir bar sat at 0-2 for 91% of steps; hold-to-6 scored 8.5x worse than spend-now. Cause: it charged every tick, with no "already answered" check and no rate limit (H:L10587).
- **bank_hold / restraint arms (V-VII).** 0-6% win; bank_hold harmful (sign test ~0.5%).
- **Placement collapse under PPO.** Row 13 went 41% → 84.5% of plays, using 28/432 cells (H:L10629).
- **Graded radius reward, arm G (XXII).** Knight collapsed to one cell on 3/3 seeds; there was no control (RP row 4).
- **Gate-prior KL arms (XIV-XVIII).** Failed or tied their bars.
- **Friend's RoyaleLearn elixir potential.** As loud as the win reward → Hog 95% of plays, Log 1% (RP row 7).
- **Verdict:** 10 days flat at 25-39% SIM win. Pro play itself LOST in that sim (26.1% vs 77.7% crowns-match on 211 timelines). Owner pivoted to imitation on 09-05 (mem:il-pivot-2026-09-05).

### Era 1: 09-05..09-24, imitation pivot and real-engine PPO
- **BC cell head (XXIV).** 15.44 / 46.61 top-1/top-5 pro agreement; the best policy for weeks (H:L10336).
- **Engine PPO (XXVI-XXVII).**
  - KL arm: gate collapsed to 0.12 plays/match; the pro-agreement metric could not see it (H:L12267).
  - With the gate prior: 500 matches moved the leashed arm nowhere (15.44 → 15.64) and wrecked the unleashed one (→ 6.87) (H:L12593).
- **S1 transformer imitation.** +1.5 pp exact-cell per corpus doubling (H 5cs.77/78). Degraded-row training: 74% vs 52% held-out under the live rule (REG XXXIII).
- **Search-teacher S3.** Five hypotheses, five nulls → closed (H:L14394).
- **Search distillation and value reranker.** Teacher agreement rose but SIM play fell (-0.54 / -0.39 tower); pro card agreement -14.5 pp. Reranker lost closed-loop (-1.26 / -1.03). Closed 09-10 (mem:distillation-required-for-long-run).
- **rl30b / rl30c (XXXV-XXXVI).** -2.3 pp held-out; at lr 3e-5, -11.5 pp at u89 (tripwire).

### Era 2: 09-25..10-06, RoyaleSim RL, generalist, R-series
- **league1 self-play (XXXVIII).** Null (+1.7 n.s.). league1b null. **league1c** (learner always icebow): +3.7 [+0.7, +6.7], the first RL gain (REG XLI).
- **R1 = per-decision credit** (GAE + per-tick discount + critic warm-up, 3 changes at once). +5.0 / +4.7 vs R0' (H:L10219; REG XLIII). Live 51.2%, n 303 (H:L8027).
- **R2 = R1 + tower_crown potential (w 0.3/0.3).** R2 - R1 -0.7 [-4.0, +2.7]; gate balanced accuracy .767 → .712; hard pro-agreement stop at u59 (H:L10219).
- **gen_v3.x imitation variants.** Projectile inputs -3.3, Rocket-context weighting -2.8 (REG XLIX-L). R1e (from gen_v3.1c) live 50.6% (n 231) (REG LII).
- **Codex autopilot 10-04..06** (`L72/improvement_loop/*/PLAN.md`). Rocket-aim, tower-slot, phase, spatial, defence-exposure and curriculum trials: all REJECTED. LXVI TOWERS went 6-11 live (REG LXVI).

### Era 3: 10-07..10-13
- **10-07 owner reintroduces shaping** ("most potential, hard to make non-exploitable"). The rules from then on: potential-based on state only, never pay for a behaviour (H:L8037).
- **RL diagnosis** (H:L8058):
  - Training decoded the play gate at sampling temperature 0.5 with threshold 0.27; deploy was greedy at 0.35. Training win rate was +21 pp vs greedy's +4-8.
  - Deck mix: icebow mirror 34% of training vs 4.5% live.
  - Signal-to-noise ~0.2; the KL leash never bound.
- **R1f.** Reactive +10/96 but ghost -3.0; RL made overspending worse; later updates lost the gain (H:L8046).
- **R2l (train-as-deployed + ladder decks).** +4/192 vs the +6 bar → fail; owner: "R2 is a failure" (H:L8404, L8460).
- **Training anti-stall found** (in since 09-12) and removed permanently. R1e had learned to rely on it: 151 vs 105 of 192 (H:L8460, L8482).
- **value_phi** (frozen value head as the potential, AUC .70, smoothed) (H:L8187) **+ Option-3 counterfactual gate branching (R3/R4):**
  - old R3 u0050: 120 vs 105/192 (sign p .13);
  - R3n: ghost -4.3, out (H:L9816);
  - R4c u0040: +10/+18 vs R1e but level with R3c (H:L9795);
  - the "significant" v2 wins were an artefact of the S1 opponent idling into draws (H:L9736).
- **Add-on heads (CellRefine, TowerRefine, barrel2k) on R3c u0030, live 10-08** (XCI/XCVIII). SIM +31/+30 of 192 vs R1e-as-live; realistic edge ~+6 n.s. (H:L9821, L9736). OT tower Rockets 0.10 → 0.52/match.
- **Hazard decode "hbt9"** (below threshold at ≥ 9 elixir, play at the gate's learned rate). SIM n.s. (609 vs 619); time at ≥ 9.5 elixir .175 → .075 (H:L8626). Live until 10-23.
- **Defence RL E1-E4** (branching when threatened; dense terms broke/dealt/lost/mat):
  - E2 -4.0 pp (p .047; "defends more, wins less");
  - E3 null;
  - E4 u20 +1.7, replication 611.5 vs 613 = noise (H:L9284-9300, L9445).
  - E4 live: 38.5% (n 52) vs OLD 54.4%, while SIM ranked it ABOVE OLD (+3.8..+5.9) (H:L9505).
- **Fast-plays RL** -9.5; own-cycle RL -6.8 (H:L9445, L9295).
- **Drills** (forked forced-mechanic labels). No label except D2/D3, which lost -3.3. Placebo: forced tower Rocket -16.5 → closed 10-12 (mem:drills-closed; H:L9466).
- **ADAPT / ADAPT2** (PFSP skill-matched league + play styles + exploiter cycles). SIM +1.56 / +2.29 n.s.; live 45% (40) and 48.7% (201) vs OLD 54.5% (H:L15404-15474).
- **Tornado second-card fine-tune on pro rows.** Pending loss unchanged: the habit lives in the bot's own states → method exhausted (H:L15408-15430).
- **MEMP match memory v0.** Memory vs zeroed memory -0.21 n.s. (H §10-12, memory seed A).
- **LIVEPHI** (potential learned from live). Failed the no-banking gate: P(win) .39 → .60 with own elixir → rejected (H:L15455).
- **LIVECAL.** Only pool P1 (E4, T .1) reproduced the live orderings; the adaptive league was the worst predictor (E4 ordering wrong by -8.33) (H §10-12).
- **NEWSIM (0.1.33).** v1 -0.52, v2 -3.33. The SIM's Hero IW ability alone costs ~17 pp (normal IW 51.5% vs hero 35.4%) → CXII trained with the normal IW (H §10-12). IW never-press: SIM +3.33 (H:L3509).

### Era 4: 10-14..10-16, reward architecture v1 (RA)
- **Economy.** Elixir spent on the push approach: pros 0.57, SIM 1.49, live 2.43. Two thirds is the model, one third live-only. The SIM punishes low elixir about 2/3 as hard as live (+17 vs +27 pp) (H:L3532, L3493).
- **Option 1.** The imitation gate is calibrated. RL eagerness grows down the lineage (+2.2 → +7.2 → +11.8 pp) because each run's KL anchor is its own already-drifted init (H:L3479). F6 (KL to the imitation gate) would have hit its cap by ~update 4 and was never run; the F6' variant scored -4.38 → closed (H:L3322, L2850).
- **Distilling the deployed player into the model.** -8.33; DAgger -9.17 → parked (H:L3433, L3312).
- **F1 per-decision credit (GAE): the only robust RL gain.**
  - +6.77 / +9.58 / +9.69 vs r1 over 3 seeds; fresh seeds +8.65 (H:L3346, L3223, L3086).
  - F3 (decisive opponents) null; F4 (gate temperature 0.1) -2.50 n.s. (H:L3274).
- **Step 3 potentials** (A1 score-aware tower, A1b tiebreak, A2 solvency). Null over F1 (+2.5 / +2.8 = seed spread) (H:L3170). The beatdown hint did not replicate (H:L3120).
- **A3 trade potential FAILED its scripted audit.** hold-to-10 and never-spells out-credited the imitation policy; stopped at u18. Fitted exchange rate: 22-25 elixir per princess tower (H:L3189, L3156).
- **Longer F1 training.** +5.0 / +1.0 / -0.8 by seed; plateau (H:L3134, L3128).
- **Matchup-fair critic (C2/F2).** Premise contradicted: critic AUC is equal on beatdown (H:L3052). Lambda .98 null (H:L2794).
- **gae_live (live-mirrored deck pool).** +4.79 / -2.60 / +2.71; at 250 updates -1.98 (H:L2811, L2750).
- **C1 posture head** (defend / balanced / pressure threshold offsets). Mean vs twins -0.38 on the live pool; "pressure" chosen 0% (H:L2750).
- **Defensive thresholds .45/.55/.65 on u250.** -7.40: decode thresholds are checkpoint-specific (H:L2794).
- **X-Bow lane-focus probe** (SIM-only rule) -3.65. Human-tempo bots are far too weak: F1 wins 78% vs them (H:L2826).
- **Learned ability head (B6).** -3.23; learned vs rule press -1.15 (H:L2207, L2065).
- **Exploiter league, 3 seeds.** +1.56 / +2.29 / -1.25 vs twins; on u250 -2.50 → closed (H:L1943, L1935).
- **T1, 500 updates.** u150 -3.75, u250 -3.85, u350 +0.31, u500 -0.94 vs u250 = plateau (H:L1787).

### Era 5: 10-17..10-19
- **Cue inputs (CXXXVIII cue130).** +5.94 vs u250, but the cue-blind control gave -0.73: the gain was the training run, the cue layer is inert (H:L1513, L1668).
- **Tower troops / fork engine arms.** Null. Found: SIM towers at level 11 vs live 15 (H:L1486).
- **Fast plays** -6.8 in SIM. The combo is a live-only rule (H:L1257).
- **16-run factorial** (cues, exploiters, troops, live levels, tower_score). Best = +0.83 vs CXXXVIII. The tower_score factor did not move Rockets (0.44 vs 0.49) (`L74/doctrine/factorial_analyze.out`; ROC §1.3).
- **succ_levels → CLIII LEVELS promoted** (642 vs 607 of 960) (REG CLIII); "+4.4 SIM, ~0 live" (H:L699).
- **IW press train/deploy mismatch.**
  - cue_ab (learned press) -5.00 CLEARLY WORSE; the head alone costs -7.60 (H:L1138, L1126).
  - Root cause: training pressed with a generic rule at 5.4/match vs 1.9 live (H:L1101).
- **Combo.**
  - Rule changes deployed: +0.21 n.s. (H:L1163).
  - spell_value v1 paid a lone Witch at a princess +0.16, more than a 12-elixir combo; fixed.
  - Reward vs control +1.35 [-2.08, +4.69] → left OFF (RL_COMBO_REWARD.md "Review fixes"; H:L699).
- **Stage-2 deck-conditioned opponents.** They turned into stalling exploiters. CTRL (with them) minus nos2 (without): -4.38 / -6.15 (overnight1018/LOG.md:41; OPP §4).
- **Step d, re-base on pro imitation (REB).**
  - The imitation init starts -26 pp; REB ends at -7.08, CLEARLY WORSE.
  - CLIII card-anchored twin: 0.00. CTRL: +0.36.
  - **nos2: +5.62 → CLX PARITY.** Its seeds: s75 -0.36 (-5.99 vs CLX), s76 +5.68 (`L74/overnight1018/LOG.md:9-46`).
- **Doctrine measured.**
  - Overtime starting 1-1: pros -22.9 pp, SIM only -8.1 n.s.
  - The bot gives back 1-0 leads 15-20% of the time (pros ≤ 5%).
  - Tower Rockets 0.39-0.58 vs 1.60/match (H:L660).
- **Habit diagnosis.**
  - Bridge X-Bow in the first 2 plays 31-41% vs pros 8-13%.
  - Rocket on heavy pushes 3-4% vs 22-23%.
  - SIM opponents convert mistakes 0.7% vs 6-7% live (H:L829).

### Era 6: 10-19..10-22
- **Level 16 everywhere.** L16 seeds of the CLX recipe: 0/4 pass (`L74/l16/RESULTS.md:3-8`).
- **W6 reward arms (old SIM):** none passed (`l16/RESULTS.md:11-24`).
  - lead_protect -0.10 / +2.50.
  - princess_redirect -0.31 / +2.40.
  - tornado_king at w .01 did not reduce pulls (1.04 vs 0.90 tiles).
  - The penalties barely fire: give-backs are 2% in SIM vs 15-20% live.
- **fin15 arms vs the W7 opponent** (`L74/tonight1020/RESULTS.md:6-11`; H:L574):
  - rocket_tower -4.69 / -6.46 CLEARLY WORSE;
  - tornado_king at w .1 -7.92 / -10.94 CLEARLY WORSE;
  - redirect -1.25 / -6.35; lead +0.31 / -1.46;
  - more tower Rockets (0.50 vs 0.35) did not turn into wins.
- **W10 Rocket study.**
  - Chip Rockets do not pay in the SIM: 0 chips 0.696 win vs 1 chip 0.582. Pros: 0.392 → 0.564.
  - A potential-form tower credit does not move Rocket use (ROC §1.2-1.3).
- **Seed variance.** Base recipe over 6 seeds: mean -0.29 vs CLX, SD 2.40 (H:L541).
- **9 arms.** OT starts -2.7, W14 opponent -1.3, bait decks 2.5x +2.0 n.s. Bait exposure did not change Log hold (0.558 vs 0.557) (`L74/tonight1021/RESULTS.md:110-119`).
- **Log study.** Log rate is pro-level; timing and target are wrong; the bait card is visible but ignored (+1.7%) (`L74/log_use/LOG_USE.md:9-23`).
- **Long run** (moving KL anchor every 50, 500 updates). u100 +1.15 → u150 -1.72 → u175 -7.86; tripwire at u219 (H:L415, L397). Its u100 = CLXII, 11-19 live (H:L425).
- **tower_crown branches from long u100.** -1.04 / -1.88 in SIM; the br74 live trial was ended at 2-4 (H:L375).

### Era 7: 10-22..10-25, "exploit" diagnosis and succ48
- **Exploit = decoder mismatch** (train T .5 / threshold .27 vs the deploy stack). u175 is +7-9 under the training decoder and the worst checkpoint under the deploy decoder; hoarding grows (EXPL §0, §2).
- **SIMCHECK.** The old "SIM looks the same" verdict had no board rows behind it (0/164 files) (EXPL §1b).
- **drift_tg** (gate temperature 0.1, threshold .35). Hoarding fixed 3/3 seeds, but each seed failed a different habit (EXP:L11-13; H:L265).
- **Push calibration.**
  - The "1.75x" SIM push gap was a scorer bug.
  - E4 is soft, I u40 hard.
  - Calibrated I u40 (decide every 20 ticks + threshold .2) fails 1/42 push cells (H:L296, L227).
- **Exploiter share 0.7 (x70 / x70cal).** Over-defending: trade -0.40 / -0.45 (EXP:L18-22).
- **Habit terms** (idle penalty, penalty-only trade). habc u75 trade FAIL -0.307 (EXP:L26).
- **tau_phase rollouts** (per-phase thresholds as deployed) shipped (H:L129).
- **Hazard play stripped 10-23.**
  - E10: drift init win 0.700 → 0.615; full-elixir 18 → 62 s.
  - E11: CLX without the hazard play wins the same (0.706) but leaks 52.6 vs 12.5 s, so E4 never punishes the leak (EXP:L28-29; H:L148).
- **succ48 leak penalty, drift-init lineage.**
  - Leak fixed (11.1 s), but the lineage starts ~9 pp below CLX (G1 -3.18 / -3.96) (EXP:L69-81).
  - trade weight > leak weight made wasting elixir cheaper than over-paying (EXP:L54-57).
  - The leak oscillates (EXP:L64).
- **CLX-start lineage and gate temperature.**
  - At 0.1 the leak cannot move: opening play probability ~1e-7, so no gradient (EXP:L104-105).
  - At 0.3 it unlocks (S17 u50: 21.7 s, +0.020); at 0.5 the opening is not fixed (EXP:L112-113).
- **G2/G3 → CLXIII NOLEAK.** S19 u75: +0.26 / 0.00 vs CLX-with-hazard (a tie), better trades (EXP:L142-151).
- **Seed dependence.** At leak .06 S23 improves and S24 regresses. S17 u150 reverts to 50.5 s: "long runs do not converge; pick by gate" (EXP:L135-139).
- **CLXIII observed live.** Owner: better defence, weak Rocket, no combos, keeps forcing failed X-Bows. SIM Rockets ~30% fewer than CLX; combos are rule-only (EXP:L155-185). habit_xbow_w built (EXP:L180).

### Era 8: 10-25..10-26, Plan A match memory
- **S4 X-Bow denial.** SIM mean lock rate matches live, but zero-lock matches are 3-7% in SIM vs 9-16% live (LED:L20-31).
- **S3 imitation memory adapter: broken.** It learned a constant offset that lowers the gate (0.218 vs 0.338) → E4 28.3% vs 74.0% (LED:L98-101, L132-138).
- **S3-aux encoder** (per-card prediction heads, coupling zero = CLXIII at u0). Opponent card-in-hand AUC 0.985; next card 0.337 vs 0.062 chance (LED:L145-150).
- **Leak relearned under continued RL.** x_s101/x_s102 (tower_crown + X-Bow cost) drift-tripped at u50/u75 (LED:L82-84). The no-memory control re-learned it by u25 (LED:L174-179).
- **New terms** rocket_cycle (free-chip credit) and king_redirect (LED:L114-126).
- **Leak-weight hedge .08 / .12 / .16.** Inconsistent across seeds; the strongest weight had the worst opening wait (34 s) (LED:L202-215). The "E4 waits for us" hypothesis was contradicted (LED:L228).
- **Root cause.** Rollouts sample the gate (temperature 0.3); deploy uses the hard threshold. The same checkpoint shows 31.3 s at full elixir under the threshold vs 16.0 s under the rate decode, but the rate decode wins -25 pp (LED:L232-246).
- **CLXIV.** mem_e_s107 u50 tied in SIM (+0.34 [-1.56, +2.24]). Live 3/11. After a FAILED X-Bow it plays another within 30 s 0.389 of the time, vs 0.105 after a locked one: it doubles down (LED:L227, L274-278).
- **Gate temperature 0.1 / 0.05 branches.** Leak 4.7 / 7.6 s at u25, win -4.3 / -3.3 n.s., threat-idle +3.9 pp (LED:L266-267).
- **Rocket package** (rocket_cycle_w + spell_value + a generic win-condition multiplier). REJECTED by the owner: the multiplier pays Rockets on a lone Giant or Golem. The rocket_cycle reward fired 0.006/match = dead (LED:L261-265).
- **Approved design:** counterfactual SIM-fork credit with ROCKET and SIEGE triggers (LED:L270; mem:owner-1026-successor-mandate).
- **Mortar.** SIM win vs Mortar decks 0.25-0.32 (-34..-44 pp vs other decks); Mortar decks are 2.9-3.2% of training sides (`M1026/sim_mortar.out`).
- **OT chip race.** Ahead 1-0 when play stopped deciding: SIM 0.48 vs live 0.32; OT win 0.68 vs 0.48; tiebreak win 0.56 vs 0.41 (`M1026/q1_ot.out`).
- **Live-only decode rules added 10-25** (not yet in the SIM): lethal_quiet and barrel_lane (LED:L154-170).

---

## 2. Recurring failure patterns

1. **Train/deploy mismatch: the most common root cause.**
   - Anti-stall in training only (R1e 151 vs 105/192, H:L8482).
   - Sampled gate vs greedy (-20 to -25 pp, GAP; H:L8058).
   - Rollout threshold .35 in every phase vs deploy .35/.45/.55 → hazard drift (H:L148).
   - Exploiter took the learner's threshold (H:L227).
   - Generic IW press 5.4 vs live 1.9 (H:L1101).
   - Level 11 vs 15/16 (H:L1486); hero vs normal IW (mem:icebow-trains-with-hero-iw).
   - Combo and hazard rules only in deploy (EXP:L161; H:L165).
   - Temperature 0.3 vs hard threshold → opening wait (LED:L232-246).
   - Grafted heads fitted on another trunk (H:L9466).
   - Gate calibrated to 2 s rows but asked every 0.77 s live (H:L12896).
   - Grid warp (H old §4.2).
   - **The gate-temperature loop is unresolved:** 0.1 removes the exploration the leak term needs (EXP:L105); 0.3 lets RL push sub-threshold probabilities down for free (LED:L232).
2. **SIM gains don't transfer, and over-prediction grows each promotion.** Calibration slope 0.38 [-0.30, +1.06] (AN:L110-117). Details in section 4.
3. **Terms that pay a behaviour get farmed or warp play.** threat_miss_idle, bank_hold, A3 trade, spell_value v1, rocket_tower (-4.7/-6.5), tornado_king w .1 (-7.9/-10.9), the generic multiplier, trade > leak (S5), idle .1 / exploiter .7 over-defending (EXP:L18-26), habit terms firing the defence-trade gate (EXP:L38-45).
4. **Potential shaping is null.** R2 tower_crown (-0.7), factorial E, A1/A1b, A2, value_phi, tower_crown branches (-1/-1.9). This is expected: it cannot change the optimum, so it cannot create an incentive the SIM lacks (RA §0, §11; ROC §1.3).
5. **The SIM win signal does not pay the habits the owner wants**, so the terms fight the win reward and fail the gate:
   - chip Rockets lose in SIM (ROC §1.2);
   - sneaky lock forced -9.8 (H:L456);
   - X-Bow lane focus -3.65; drills and placebo (H:L9466);
   - 1-1 barely punished (-8.1 vs -22.9);
   - give-backs 2% vs 15-20%;
   - low-elixir punishment 2/3 of live;
   - no X-Bow shut-out tails;
   - Mortar 3% of training;
   - IW press net-negative in SIM while the owner values it.
6. **Drift under continued RL; long runs don't converge.** Long run u100 → u175 -7.86; T1 plateau; R1f lost its gains; rl30c -11.5; S17 u150 reverted; memory arms drifted into an opening wait; habits random-walk without a leash (H:L265); the KL anchor itself drifts down the lineage (H:L3479).
7. **Opponent wrong in a different way each round.** E4 soft; S1 idles into inflated draws (H:L9736); I u40 over-rewards banking (~1.9x); bots answer too fast and play too much in double elixir (OPP §0.4); human tempo too weak (78%); Stage-2 stalling exploiters (-4.4/-6.2); training mix far from live (Mega Knight 1.8% vs 16.2%; H:L2993); SIM games tower-starved (OPP §0.3).
8. **Instruments blind or gamed.** Pro agreement blind to gate collapse (H:L12267); ghost screen saturated at 98% (H:L8058); scorer bug (H:L296); no board rows (EXPL §1b); monitor missed wins (H:L1215); 9 drift metrics → ~1/3 false-FAIL rate (H:L284); best seed picked on the same 960 pairs (H:L3144).
9. **Seed noise ≈ effect size; gates underpowered.** SD 2.4 pp; CLX replicate -5.99; exploiter "+4.48" was seed spread (H:L2021); 960 pairs ≈ ±3.7 pp (mem:gate-pooled-and-opponent-first); 5 pp live needs 1,570 matches/arm (AN power line).
10. **Imitation re-bases cost more than RL recovers.** REB -26 → -7; S3 memory offset; Stage-2 imitation init; distillation -8/-9.
11. **Decode rules on top don't generalise.** Thresholds are checkpoint-specific (-7.40); the SIM can't credit rules built for live-only failures (GAP "Reading"); owner bans habit rules.
12. **Long-horizon credit too thin.** Chip value only at the tiebreak; Log hold value lands seconds later (LOG_USE §verdict); GAE λ .95 covers ~20 decisions (H:L3052); λ .98 null; posture head added no information (H:L2750).
13. **Adaptation can't pay without varied, punishing opponents** (PA §1 "why RL has not fixed them"). CLXIV doubled down after failures (LED:L276).

---

## 3. What worked, and live history by Mark

**Measured gains that held up:**
- **Per-decision credit (GAE + critic warm-up).** R1 +5.0/+4.7; F1 +6.8/+9.6/+9.7, fresh +8.65. Live F1 vs r1 +2.7 n.s. (H:L3086).
- **league1c** (learner always icebow): +3.7.
- **Imitation base and data scaling.**
- **The owner's tower level-up** (4424 → 4858 HP): +15.8 pp live, for the same model (OPP §0.1).
- **Leak penalty + gate temperature 0.3.** Removed the need for the forced play; CLXIII tied CLX and kept it live (EXP:L142-151).
- **Gate temperature 0.1 branches** fix the opening wait (LED:L266).
- **Add-on heads.** OT tower Rockets up 5x at neutral wins (H:L9736).
- **IO fixes.** Taps: 1.47 → 0.34 lost/match (H:L446). Legal-cell guard, grid fix.
- **Calibrated I u40 opponent** (1/42 cells).
- **Parity work.** 0.892 → 0.941 on 145 matches; 0.926 on 403 (H:L722); 0.920 at FIN15.

**Live record by Mark** (dates from REG and HANDOFF):

| Mark | period | live record | trophies / note |
|---|---|---|---|
| XLIII R1 | 10-03..04 | 51.2% (n 303) | (H:L8027) |
| LII R1e | 10-04..08 | 50.6% (n 231); 48.9% (n 305) | ~11,000-11,378 (mem:overnight-2026-10-08-12k) |
| XCVIII "OLD" add-ons | 10-08..14 | 54.4% (n 379) | ~12,100 |
| XCIX E4 | 10-10 | 38.5% (n 52) | |
| CII/CVI ADAPT, ADAPT2 | 10-12..13 | 45% / 48.7% (n 201) | |
| CXII r1 | 10-13..15 | A/B1 76-74 vs OLD | |
| CXVII F1 u65 | 10-14..15 | 51.4% (n 148) | |
| **CXXIV** | 10-15..17 | 51.2% (n 248) | 12,000 → 12,530 (mem:trophy-goal-14k-then-ranked) |
| **CXXXVIII** | 10-17..18 | 53.4% of 103 graded; 48.1% overall | 12,530 → 13,063, then plateau at 13k |
| **CLIII** | 10-18 | 47.8% (n 46) | stuck at 13k (mem:session-end-2026-10-18) |
| CLIX | 10-18 | 47.6% (n 103) | net 0 trophies |
| **CLX** | 10-19..23 | 46.5% (n 114) at own tower 4424 → 62.3% (n 138) at 4858; Ranked 48.1% (112-121) | 13,060 → 14,030 (OPP §0.1; mem:ranked-gap-1021) |
| CLXI | 10-21 | no record found | interim Ranked |
| **CLXII** | 10-22 | 11-19 (36.7%) | Ranked |
| br74 | 10-22 | 2-4 | trial ended |
| **CLXIII** | 10-25..26 | 48.2% (n 301) | Ranked |
| **CLXIV** | 10-26 | 3/11 (27%) | stopped by the owner |

Live tally on 10-23: W2317 / L2182, 14,060 trophies (H:L148).

---

## 4. SIM-vs-live gap history

**SIM win minus live win of the same Mark** (AN:L123-128):
- rt35 context: CXII -4.0, CXVII +1.4, CXXIV +9.5, CXXXVIII +18.9.
- f36 context: CXXIV +7.9, CXXXVIII +13.5, CLIII +18.4, CLIX +22.3.
- fin13 context: CLIII +17.6, CLX +24.3 (at all-16: +9.6).

**Per promotion, SIM-predicted vs live gain** (AN:L110-117):

| link | SIM | live |
|---|---|---|
| CXVII - CXII | +10.2 | +4.8 |
| CXXIV - CXVII | +7.1 | +1.0 |
| CLIII - CXXXVIII | +4.4 | +2.8 |
| CLIX - CLIII | +3.4 | +0.8 |
| CLX - CLIII | +5.6 | +1.0 |

**Other cases:**
- F1: SIM +8.7, live +2.7 (H:L3086).
- E4: SIM above OLD by +3.8..+5.9; live -16 pp (H:L9505).
- ADAPT2: SIM +2.29; live 48.7% vs 54.5%.
- CLX: SIM 64-72% vs Ranked 48.1% (mem:ranked-gap-1021).
- CLXII: SIM +1.15 / +6.82; live 36.7%.
- CLXIII: SIM 72.6% / 58.8% vs live 47.8% (M1026/q1_ot.out).
- CLXIV: SIM tie, live 27%.

**Explanations found:**
- Own-tower level confound (OPP §0.1).
- SIM games tower-starved (both sides take a princess in 7.0% vs 18.0% of matches); OT 8-12 pp too common; Hog cell 76% vs 53% (OPP §0.3).
- SIM opponents answer too fast and play too much in double elixir (OPP §0.4).
- SIM rarely converts our mistakes (0.7% vs 6-7%) (H:L829).
- Ranked gap: OT chip races and tank decks (25.3% live vs 57.5% SIM) (mem:ranked-gap-1021).
- Matchup mix (H:L2993); a live re-weight at archetype-class level does NOT explain it (H:L2983).
- A live-only third of the economy gap (latency, taps, perception) (H:L3532).
- SIM Hero IW ability effect wrong (H §10-12 IWDIAG).
- Parity 0.92, not 0.975.
- Best seed selected on the same eval set (H:L3144).
- Shut-out tails missing (LED:L29).
- Being ahead 1-0 is much more common in SIM (M1026).

---

## 5. Owner requirements and doctrine the new design must respect

**Game doctrine:**
- **Tower targeting.** Ahead 1-0: defend out the match. At 1-1: take the other princess. Never target the king (the OT lethal Rocket on a princess is the one rule) (mem:tower-targeting-doctrine).
- **Keep both princesses.** Defence-first, positive trades, the most effective play rather than the cheapest, chip via X-Bow locks + Rocket cycling (mem:icebow-keep-both-towers-doctrine).
- **Defence chain.** Recognise → classify → counter; fallback mitigation is legitimate; preserve the synergies (mem:icebow-defense-doctrine). Fundamentals: triage, minimise rather than prevent damage (mem:defense-fundamentals-tier).
- **3.5-cycle deck.** Banking is correct but must be situational, not constant (mem:icebow-deck-is-3-5-cycle; mem:no-clx-leash-fix-exploit-first 10-23).
- **Matchup adaptation.** No offensive X-Bows into hard counters; switch to defensive X-Bows + Rocket cycling; bridge X-Bow only in a punish window (mem:investment-cards-matchup-adaptation, mem:stepd-started-exception, mem:late-game-rocket-cycle-concern).
- **Rocket.**
  - Must be used live: ≥ 1.0/match is a deploy check, not a reward.
  - Defensive Rockets vs Ram Rider / Balloon / Royal Hogs are wanted.
  - No direct Rocket reward terms and no generic multipliers; counterfactual fork credit is the approved route.
  - Rocket cycling only pays with a small OT damage gap (mem:owner-1026-successor-mandate; PA owner point 2).
- **Combo.** Tornado only when a lone Rocket is not enough; Tornado credit = (V_combo - V_lone) - 3 (mem:owner-decisions-1017-night).
- **Tornado redirect.** Reward redirects to our king while both princesses stand; penalise any pull toward the king once a princess is down (mem:reward-redirect-to-king).
- **Spells.** Never reward the Tornado or the sneaky lock directly. Measure Rocket / Tornado / Log on every candidate, including the Log bait-hold rate (mem:spell-use-measurement-requirement, mem:log-overuse-successor-requirement).
- **Mortar and Hero Bowler** defence must be learned (mem:hero-bowler-siege-counter).
- **Adapt within a match across ALL cards and abilities** (PA §3.4).

**Process rules:**
- **No hard-coded habit rules.** Decode rules only as approved SIM probes. The finishing Rocket/Log stays a rule; the other live spell rules should eventually be retired (mem:no-hardcoded-habit-rules).
- **No forced play or anti-stall anywhere.** No SIM-only rules; when live changes, training and every eval change in the same batch (mem:anti-stall-removed-permanently).
- **Shaping allowed** if potential-based on state only, never paying for behaviours, run as its own arm, and passing a scripted audit first. Geometry credit is a soft AND of placement and timing (mem:il-pivot-2026-09-05, mem:radius-reward-overnight-autonomy; RA §9).
- **One change per experiment** (a designed factorial is the exception); iterate rather than abandon; record every experiment (mem:one-change-per-experiment, mem:iterate-dont-abandon, mem:succ48-mandate-1023).
- **Leash.** No leash to CLX. At most a light leash, preferably to the previous best model, never a tight pro leash. Pro-agreement tripwire 5 pp. A drift test is required before any long run (mem:no-clx-leash-fix-exploit-first, mem:owner-decisions-1017-night).
- **Gates.**
  - Pooled-CI gate, opponent checked first, a stated expected effect before spending pods (mem:gate-pooled-and-opponent-first).
  - The 10-26 bar (mem:owner-1026-successor-mandate):
    - drift test;
    - pooled gate vs CLXIII with CI low > 0;
    - memory ablation;
    - Rocket ≥ 1.0/match;
    - Mortar-deck win ≥ 45%;
    - SIM adaptation;
    - scenario forks.
  - The owner starts live.
- **Training conditions.** About 3x weight on unfavourable matchups; all levels at 16; Hero IW with the live press rule; never deploy "IW never pressed" (mem:train-on-unfavorable-matchups, mem:icebow-cards-max-level-16, mem:iw-press-train-mismatch).
- **Live.** Never revert an owner-chosen live model; observe after a promotion (mem:never-revert-owner-live-choice, mem:observe-after-promotion).
- **Goal.** Top-1,000 Ranked; diagnose every failure the same turn (mem:owner-1026-successor-mandate).
