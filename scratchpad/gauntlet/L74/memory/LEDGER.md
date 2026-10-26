# Plan A ledger (owner: record every experiment with its results)

## Pods (rented 10-25; key ~/.ssh/runpod_clashbot; pod-to-pod key ~/.ssh/podlink on 33912)
| port | GPUs / vCPU quota | role |
|---|---|---|
| 33912 | 2x 4090 / 108.8 | hub (restored archive), pro memory dataset + imitation (S3), control arm x_s102 meanwhile |
| 33458 | 1x 4090 / 54.4 (quiet host) | S4 X-Bow lock measurement vs candidate opponents (q_xb: E4, I u40 cal, W18 R1 / R2 / R3 cal) |
| 33522 | 1x 4090 / 54.4 | CLXIII gate baseline (gate48 succ48_o_s91 75) |
| 33569 | 1x 4090 / 54.4 | control arm x_s101 (CLXIII + tower_crown + xbow cost, no memory) |
Restore: /workspace/restore/restore.sh (archive pod_backup_weekend/succ48_1025 + venv rebuilt with exact versions); tests 27 + 5 skip,
smoke PASS on 33912; replicated to the singles (9.2 GB each, env check OK).

## Stages
| stage | status |
|---|---|
| S0 infra | DONE 10-25 15:05Z |
| S1a memory builder | DONE 63a1ebb: pipeline/match_memory.py (45-float events x 128, 54-float summary), 14 tests (planted-bug check: 6 / 6 caught), incremental == offline on 1,756 live decisions, 1.56 ms / decision |
| S1b wiring (model zero-init, storage per match, pro builder, rollouts, live) | in progress (agent) |

## S4 X-Bow denial, measured (memory/xbow_arch.py; reach X-Bow lock = princess -5% in 600 ticks)
| source | matches | lock [95%] | per-match (>= 2 reach): 0 locks / < .5 / >= .5 |
|---|---|---|---|
| SIM CLXIII vs E4 | 960 | 0.585 [0.568, 0.603] | 3% / 25% / 75% |
| SIM vs I u40 cal | 960 | 0.626 | 4% / 22% / 78% |
| SIM vs W18 R1 cal | 960 | 0.589 | 7% / 27% / 73% |
| SIM vs W18 R3 cal | 960 | 0.563 | 7% / 30% / 70% |
| LIVE CLX | 234 | 0.565 [0.521, 0.613] | 9% / 30% / 70% (control: 0.417, 27% shut-outs) |
| LIVE CLXIII | 35 | 0.462 [0.343, 0.574] | 16% / 41% / 59% (bridge 0.222, control 0.318; small n) |
Reading (a): the SIM mean is right (R3 = live CLX), the TAILS are not: live shut-out matches 2-5x more common, live archetypes
swing more (owner's point). S4 target = the pool's shut-out share and per-archetype spread, not the mean: I u40 cal + R3 cal now,
plus a stronger denier (W18 R4, live-Ranked X-Bow starts) for the shut-out tail.

## S1b wiring -- DONE (committed with this entry)
- memory: v1 model flag (fv6 base; absent = identical config hash + byte-identical records, tested). Encoder: card / form embed +
  46-float events -> 2 transformer layers d 64 -> masked mean + query pool; summary (54 + answer card) MLP; ONE zero-init linear
  into the global vector. G-mem-0: CLXIII vs CLXIII + memory on 2,500 pro rows: max |diff| 0 (gate / card / cell / value).
- Storage: per-match event tables (pro ~105 MB on disk for the corpus; per-row would be ~83 GB); features_at() == MatchMemory.
- Pro builder: python -m pipeline.dataset_gen memory --dataset gen_dataset_v32_fv5.npz --out X.npz --workers N (0.2 s / replay).
- Rollouts: 0.94 ms / decision memory build; learner log-probs = actor's within 8e-7 with memory active.
- Live: live_gen own_events now carry x / y / form; 6 recorded CLXIII matches replayed through GenPilot: memory == offline at
  2,174 / 2,174 decisions; +1.0-1.6 ms median per decision (encoder forward extra, GPU not measured).
- X-Bow answer rule: first opponent play in the lane within 4 s and 12 tiles (5 live matches: 14 / 26 answered; old 6-tile rule 3).
- NOTE (a): the live supervisor restarted a BAIT-deck run (wk_bait u60) at 11:51:21 EDT 10-25 and imported the then-uncommitted
  S1b live_gen / e1_eval / model_gen; for a no-memory model the only active change = extra own-play fields; ~3 matches normal;
  owner stopped it 12:15 EDT. Icebow LIVE_OPTIONS / CKPT_OVERRIDE untouched.
- Pod tree for memory work: 33912 /workspace/cb_mem = cb_stepd hard links + laptop pipeline (HEAD + S1b). Tests 52 + 9 skip
  (ROYALE_RUNTIME=fin15-linux needed for test_memory_s1b); rl_royale --smoke PASS with memory (mem_x_s110) and without (x_s101).

## 10-25 evening (17:40Z on)
- D1 deny opponent cfg CHECKED: no hazard keys (only a comment mentions it); gate_decode defaults to 'threshold' in
  decision_options.py, so the opponents' live stack has no forced play. D1 s74 on 33458 (u5 at 17:40Z, ~4 min / update).
- D1 s75 (replication seed, only `seed` differs) launched on 33522 17:5xZ from /workspace/cb_mem (= cb_stepd + 33458's cb_mem
  pipeline + D1 inputs relayed via the laptop); rl_royale --smoke PASS first. 33522 had been idle since its CLXIII gate queue
  finished 16:20Z (rows in /workspace/pushcal/ev/g48_succ48_o_s91_u0075_{e4,cal}).
- S3 step-0 identity on GPU: memory-vs-base 5.72e-6 = base-vs-base 5.72e-6 at max |out| 39.7 (fp32 GPU rounding, 1-2 ulp).
  Check made relative (1e-6 x max |out|) and both numbers logged; the exact-0 identity stays the CPU test.
- Per-card X-Bow counters, pro tables (xbow_cards.py -> xbow_cards_pro.out): 8,874 resolved own reach X-Bows, lock 0.507;
  unanswered 0.606. Lowest lock when ANSWERED by (n >= 60): E-Giant 0.16, Goblinstein 0.23, Giant 0.24, PEKKA 0.26,
  Giant Skeleton 0.28, Ice Golem 0.33, Ice Spirit 0.35, Bowler 0.36 (tanking the X-Bow / counter-push). DECK view (opponent
  played the card at any time; not causal): Goblinstein 0.36, Zappies 0.37, Archers 0.38 ... Lava 0.74, Skeleton Dragons 0.69,
  Balloon 0.65 (air beatdown = X-Bow locks). Pro X-Bow players, not our bot: a prior, not the bot's own rates.
- OWNER APPROVED S1c (10-25 ~18:20Z): per-card counter priors, cycle / counter-ready, king-activated, damage margin + trend,
  lock-likelihood head (pro + live X-Bow outcomes, frozen input, logged live); S3 then on the extended inputs; S4 pool D1 +
  I u40 cal + W18 R3 with fast-cycle counter decks; Tornado / king-activation parity, then a redirect-credit RL arm of its own;
  gate metrics (attempts vs score, Rocket cycling vs OT margin, behind > 2,000 -> seeks a lock, king activation / redirect vs pros).
  Dispatched: worker A = memory v2 + lock head; worker B = Tornado / king parity; worker C = gate_metrics.py + pro rates.
- S3 smoke (100 steps, GPU 1 of 33912): PASS. 104 frozen tensors unchanged; val loss 5.429 -> 5.003, cell top-1 0.171 -> 0.199,
  card top-1 0.576 -> 0.573, gate bal-acc 0.707 -> 0.682 (100 steps, lr warm-up only: no verdict). 0.165 s / step.
- Target-leak check (leak_check.py, 200,000 pro play rows): 0 rows with a visible own play at tick >= the row tick; the newest
  visible own play is >= 1 tick old (median 86). The cell gain is not the target leaking.
- S3 v1 CONTROL launched 18:25Z (2 epochs, bf16, /workspace/s3/v1ctrl on 33912): the baseline the v2 (S1c) S3 is measured
  against (one change per experiment); not the S3 that feeds S5.
- Live per-card X-Bow view (xbow_arch.py --live CLX_PARITY --cards 15 -> xbow_cards_live.out): answered by Mega Knight 0.13
  (n 38), Knight 0.45, Valkyrie 0.47, Tesla 0.48; unanswered 0.74 (n 223). Deck view lowest: Barbarian Barrel 0.34 (n 89),
  Tombstone 0.35, Poison 0.35, Tornado 0.38, Bowler 0.38 (small n, whole-match reveal).
- Pool check (pool_counters.py): decks_live_train_beat3 has 112 / 895 fast (avg <= 3.2) decks with >= 1 X-Bow counter =
  9.9% of training weight (>= 2 counters: 7.0%), at live frequency by construction (weights = live sides).
- S1c DONE (70eac89). S3 v1 control FINAL: val loss 5.471 -> 4.720, card +3.1 pp, cell +3.1 pp, gate bal-acc +0.9 pp; probes
  toward pros (X-Bow after >= 2 fails 12.2 -> 9.4%, pro 8.6; Rocket 1.1 -> 5.7%, pro 8.6). Memory zeroed = worse than CLXIII
  (gate 64.1%): the adapter now relies on memory. RL proagree scores memory models with an EMPTY memory (TODO: pass tables).
- S3 v2 (S1c inputs) launched 19:2xZ on 33912 GPU 1 (/workspace/s3/v2).
- x_s101 / x_s102 (no-memory controls, tower_crown + xbow cost): BOTH drift-tripped (x101 at u50, x102 at u75): seconds at full
  13.5 -> 30.3 / 32.2 s, first play 12.7 -> 28.7 / 31.0 s, win -5.0 / -4.1 pp vs u0. Verdict (a): that recipe re-learns the
  leak; it is NOT used for the memory arms.
- S5 pair launched 19:30Z, CLXIII's own recipe (succ48_o_s91), seed 105, 100 updates, drift_test (CB override -> cb_mem):
  mem_o_s105 (33912, init = S3 v1 adapter mem_best, memory v1) vs ctrl_o_s105 (33569, init = CLXIII raw). ONE change: memory.
  Graft check: graft_generic keeps all 36 memory tensors; eval_gen loads it as memory v1.
- 19:31Z the pair crashed at start: CLXIII's cfg has shaping_critic_scale 2.2 < 2.6 (bound since LEAK_MATCH_CAP 1.0). Both cfgs ->
  2.6 (same for both arms), relaunched 19:55Z; mem arm init pro agreement (12,237 VAL rows) cell 0.162 card 0.609 gate 0.686.
- S3 v2 FINAL = tie with v1 (val loss 4.7204 vs 4.7201; card 0.5788 both; cell 0.1964 vs 0.1972; gate 0.7124 vs 0.7110; probes
  equal): the S1c inputs add nothing to imitation; whether they help RL is the v2 arm's question.
- OWNER 10-25 ~15:40 EDT: v1 candidate live if it passes, then v2 if it passes; I may stop / start live overnight.
  promote_mem.sh: drift PASS at u100 -> 3,840-game gate vs CLXIII rows on 33522 (pair_both.py; pooled CI low > 0) ->
  deploy_ckpt.sh (Mark CLXIV MEMORY / CLXV ADAPTIVE), revert to CLXIII on a deploy or guard failure. The CLX baseline rows
  were not archived, so the bar is CLXIII (live, = CLX in SIM: G3 +0.3 [-2.4, +2.9]). Live --check PASS on the v1 adapter ckpt.
- launch_v2.sh: mem2_o_s105 (memory v2) on 33458 after D1 s74, then its chain. launch_tc.sh: memtc_o_s105 (mem + tower_crown,
  scale 3.5) on 33522 after D1 s75 -- tests the Rocket-credit lever + which x-arm term leaked; report only.
- 10-25 ~20:20Z MEASURED: the S3-imitation memory model is broken in SIM. E4 at u0 (seeds 741200 + 742000, 960 paired games):
  mem v1 (S3 v1 control adapter, grafted) 272 / 960 = 28.3% vs CLXIII 710 / 960 = 74.0%. Rollouts at u0 agree: mem v1 113 / 256,
  mem v2 100-119 / 256, control 171-177 / 256. Both memory arms + the 3 laptop chains STOPPED (STOP_REASON_LEAD on the pods).
  Also: the drift_test u0000 eval crashed for absolute `init:` paths ($CB prefixed); any memory arm must use a repo-relative init.
- Diagnosis worker on the SIM memory path (H1 skew / feed bug vs H2 pro-imitation policy shift); build worker on S3-aux (encoder
  trained only by per-card prediction heads, coupling stays zero = CLXIII at u0; memory_encoder_frozen in RL). Owner 10-25 ~17:00
  EDT: per-card memory signals for every deck card, deploy-ready by the morning; 5 more double pods requested.
- Reward-term history for tonight's arms (tonight1020/RESULTS.md, older SIM + W7 opponent, vs CLX): rocket_tower -4.69 / -6.46 pp
  (CLEARLY WORSE), princess_redirect penalty -1.25 / -6.35, tornado_king -7.92 / -10.94, lead +0.31 / -1.46; W10: chip Rockets
  do not pay in the SIM. -> Rocket / redirect arms may fail the SIM gate even if they fix the live flaw; report flaw metrics.
- counter_x3.py -> memory/decks_live_train_beat3_cx3.json: 104 fast (avg <= 3.2) decks with a S1c counter card (28 cards,
  answer lift < -0.10) sides x3 = 25.9% of league weight (was 9.9%).
- D1 s74 X-Bow-denial check running on 33458 (CLXIII vs D1 u60 / u40 calibrated, 2 x 960): q_xbD1.
- OWNER 10-25 ~17:30 EDT: fix the memory bug on the PRO-REPLAY path (no SIM-game fallback); rocket cycling + king redirect terms
  must WIN the SIM gate; 3 single pods added (33184 / 33040 / 33015: 1x 4090, 72.25 vCPU quota, 251 GB RAM, 60 GB disk; key
  runpod_clashbot). Replicating /workspace from 33912 (podlink; first try failed on host-key verification, fixed accept-new).
- NEW reward terms (reward_terms.py, opt-in, tests test_cycle_redirect_1025.py 6 / 6; rocket_tower / play_cost suites pass):
  rocket_cycle = rocket_tower's credit ONLY for a FREE chip (decided at tick >= 2400, own elixir >= 7, no own princess HP lost in
  the 5 s before); king_redirect = +w per king tower of OUR king HP lost from a Tornado's cast to 5 s after it ends, for Tornados
  cast with both princesses up that pulled >= 1 tile toward our king (caps 0.1 / event, 0.2 / match); princess damage untaxed.
  CrownTracker(king=...) records own-king HP change points only when king_redirect is on (crown_track "rocket_dmg+king").
- test_reward_terms_1020::test_updates_identical FAILS in the working tree (no-crown config differs from the PRE module at
  ~1e-9 relative); not from these edits (they act only with crown terms on); being checked with the aux build worker.
- mkarms.sh: tonight's arms (mem_a / mem_e x2 seeds / mem_l) from CLXIII's recipe + memory v2 + memory_aux + frozen encoder;
  exploiter decks mix/decks_live_train_cx3.json (fast counter decks x3: 104 decks, 31.5% of the exploiter's weight).
- OWNER 10-25 ~17:45 EDT: run everything to u100 (gate at u100); rocket_cycle's "no damage" must EXCLUDE enemy spell damage.
  Done: CrownTracker(troop=True) keeps troop_lost = own princess HP lost NOT explained by an enemy spell aimed within 5 tiles of
  that tower at this or the previous stop; rocket_cycle's quiet check reads troop_lost (test: spell-only damage does not block,
  troop damage does). Tests 24 / 24 (cycle_redirect + rocket_tower).
- D1 deny check (CLXIII vs, calibrated decode, 960 games each): D1 u60 win 49.5%, lock 0.544, shut-outs 8%; D1 u40 46.6% /
  0.562 / 6%; W18 R3 52.2% / 0.563 / 7%; I u40 61.1% / 0.626 / 4%. Live CLX 0.565 / 9%, CLXIII 0.462 / 16%. D1 u60 = the
  hardest SIM opponent and the closest to live denial.
- league_exploiters LIST form (rl_royale; dict form unchanged, test_exploit_league + own_cfg pass; new test_exploiter_list_1025):
  tonight's pool D1 u60 0.15 + I u40 0.15 + W18 R3 0.10 (40% of games), cx3 decks, calibrated decode.
- MEMORY BUG FOUND (skew/, diagnosis worker, 10-25 ~22:40Z): H1 (SIM builds memory wrongly) CONTRADICTED -- own plays 7,917 /
  7,935 exact, opponent plays 95.6% detected (median lag 4 ticks), field distributions close to pro / live. CAUSE = S3 imitation:
  the adapter learned a CONSTANT offset (empty memory adds a length-18.2 vector) that lowers the gate on every state (SIM gate
  prob 0.218 vs base 0.338; share above 0.35: 0.17 vs 0.49); on pro rows memory content cancels it (+0.10) but not in SIM
  (+0.002). E4 120-match pairs: base 76.7%, mem 32.5%, mem + empty memory 35.0%, offset removed 63.3% (360 pairs 57.8 vs 76.1:
  -18.3 pp [-24.4, -12.2] = pro-imitation drift, H2). Fix: skew/fix/zero_empty.patch (empty memory adds exactly 0; test 4 / 4)
  -> being merged by the S3-aux worker. S3-imitation adapters are dead; the S3-aux design (coupling zero) avoids it.
- Night chain READY (waiting on the S3-aux checkpoint): arm_chain.sh (pod-side: drift test to u100 -> 3,840-game gate vs CLXIII
  on the same pod -> memory ablation real vs EMPTY memory, 2 x 480 paired; abl.sh = generalised skew/run_skew.sh) and
  night_decide.sh (laptop: best arm with drift PASS + gate pooled CI low > 0 + ablation real - empty > 0 -> Mark CLXIV
  ADAPTIVE via deploy_ckpt.sh, revert to CLXIII on failure; deadline 10:30Z). CLXIII gate rows (matches.jsonl only) copied to
  33912 / 33184 / 33040 / 33015; D1 u60 + W18 R3 opponents + cx3 decks in their cb_stepd. Pods: mem_e_s106 33912,
  mem_e_s107 33184, mem_a_s106 33040, mem_l_s106 33015.
- S3-aux DONE (agent): /workspace/s3/aux_v2/mem_best_ze.pt sha 3d75a25d8ebedd4e (2 epochs, 29 min, memory v2, zero_empty).
  Policy unchanged: 106 base tensors + coupling bit-identical; CPU outputs = CLXIII exactly (real and empty memory); arm smokes'
  init pro agreement = CLXIII's reference (cell 0.1459, card 0.6687, gate 0.7315). Per-head val (30k rows; empty-memory in
  brackets): opp card in hand AUC 0.985 (0.603), opp next card acc 0.337 (0.060; chance 0.062), opp elixir now R2 0.83, own
  card swing R2 0.45 (0.30), value / elixir 0.64 (0.32), plays-until-in-hand acc 0.874, our tower HP lost next 10 s R2 0.51,
  X-Bow lock AUC 0.71 (n 87), Rocket tower dmg R2 0.14 (n 73). Committed 57dcdc4.
- Training trees /workspace/cb_arm on 33912 / 33184 / 33040 / 33015 / 33458 / 33522 (= cb_stepd + 57dcdc4 pipeline + s1c
  artifacts + cx3 decks + D1 / R3 opponents + pro memory tables). Arms: mem_e_s106 33912, mem_e_s107 33184, mem_a_s106 33040,
  mem_l_s106 33015, mem_e_s108 33458, mem_e_s109 33522 (extra candidate seeds on the two freed gate pods).
- OWNER 10-25 ~18:20 EDT: finishing Rocket only if the tower is finishable AND nothing else damaged it in the past 1 s.
  Done: DecisionOptions.lethal_quiet (CLI --lethal-quiet SEC; 0 = off = unchanged): lethal_rocket_target(skip=lanes) drops a
  princess whose public HP fell within the last SEC s of decision snapshots (recently_hit on record_hp's history); applies to
  the Rocket AND the Log finisher. Live pilot (live_gen_v2) snapshots every decision when on. Tests test_lethal_quiet_1025 3 / 3,
  test_lethal_rocket + test_lethal_log 49 / 49. LIVE_OPTIONS += --lethal-quiet 1.0 (backup .bak_1025_prequiet); --check PASS;
  live restarted between matches 18:29 EDT; live_play_20261025_182957 start record shows lethal_quiet 1.0, CLXIII NOLEAK.
  NOT in the SIM path yet (e1_eval / decide_batch pass no history): tonight's gates stay on the old rule (pairing with the
  CLXIII rows); SIM support owed before the next training so SIM matches live.
- OWNER 10-25 ~18:35 EDT: port the Log's Goblin Barrel lane fix to the troop answers (Knight / IW / Skeletons / Tornado were
  sometimes placed on the wrong side). Done: DecisionOptions.barrel_lane (--barrel-lane on|off; off = unchanged): a Knight / Ice
  Wizard (any form) / Skeletons / Tornado the model places on MY half while an enemy Goblin Barrel lands (in flight: visible
  target, as log_barrel) or its goblins stand on my half, all in ONE lane, moves to the model's best cell within 6 tiles of the
  barrel / goblins in that lane; enemy-half placements, both-lane threats and right-lane choices unchanged. Shared code: SIM
  decide_batch (match_kwargs barrel_goblins) and live_gen_v2. Tests test_barrel_lane_1025 3 / 3; decision-option suites 132 + 1
  skip; finisher suites 55. LIVE_OPTIONS += --barrel-lane on (backup .bak_1025_prebarrel); --check PASS; live restarted 18:46
  EDT; live_play_20261025_184734 start record: barrel_lane on, lethal_quiet 1.0, CLXIII NOLEAK; no decision errors.
  Tonight's gates do NOT use it (pairing with the CLXIII rows); next training's live stack should include both.
- OWNER 10-25 ~18:55 EDT: overnight, shut down idle pods unless planned work. night_decide.sh v2: as each arm finishes it copies
  res + drift checks + u100 raw / grafted ckpts to pod_backup_weekend/night1025/ARM/ (sha-checked) and STOPS that pod
  (runpodctl from inside); the control ctrl_o_s105 (33569) too. S3-aux ckpt + D1 / R3 opponents backed up there first.
- RESTART 23:1xZ, MEASURED reason: ctrl_o_s105 (CLXIII recipe continued from CLXIII, no memory) u25 drift check FLAGGED the leak:
  time at full 13.5 -> 25.8 s [+7.2, +17.3], first play 12.7 -> 22.4 s, plays / min -0.26 (third recipe to re-learn the leak
  under continued training: x_s101 / x_s102 and CLXIII's own run 13.8 -> 20.3 s u75 -> u100). The memory arms share the recipe,
  so all were restarted from u0 with a stronger leak weight (was 0.03; r_s95's 0.06 from a leaky parent: 20.9 -> 16.0 s, win
  -3.3 pp; LEAK_MATCH_CAP 1.0 bounds the term, critic bound unchanged): 0.12 on mem_e_s106 / mem_e_s107 / mem_a_s106 /
  mem_l_s106 / ctrl_o_s105, 0.08 on mem_e_s108, 0.16 on mem_e_s109 (weight hedge). restart_arm.sh.
- 33040 + 33015 share one host (load ~95): their arms run ~2x slower (rollout 270-615 s vs 123 s on 33184).
- Memory use, mem_e_s106 (mem_use.py, 6,000 icebow PRO val rows, real vs EMPTY memory): u0 0 (coupling 0, exact);
  snap u10 coupling |W| 0.183 (0 at u5: critic warm-up); gate |p(real) - p(empty)| mean 0.0069, p90 0.0193, max 0.0485;
  play / wait flips at 0.35 on 1.3% of rows; all RL change vs CLXIII |dp| 0.026. Learning, small so far; re-probe at u25.
- Owner asked (bedtime 10-25): evaluate github.com/voonhous/crforge in depth + a couple of tests, recommend switch or not;
  worker on it (laptop only, report L74/crforge/EVAL.md); the night run has priority.
- u25 memory use (mem_use.py, 6,000 icebow pro rows): mem_e_s106 gate |p(real) - p(empty)| mean 0.0114 (u10 0.0069), p90 0.033,
  max 0.090, flips 1.6%; mem_e_s107 mean 0.0209, p90 0.055, max 0.197, flips 4.2%. Memory use is growing.
- 00:5xZ speed triage: 33522 + 33569 share a host (load ~81), 33040 + 33015 share one (load ~83; quota 54.4 vCPU, not 72);
  rates at 00:48Z: e_s106 u25, e_s107 u24, e_s108 u23, a_s106 u15, l_s106 u14, e_s109 u10, ctrl u16. STOPPED the two
  attribution-only runs to speed their hostmates: ctrl_o_s105 (33569, pod myqw8dmlf9yyg2) and mem_a_s106 (33040, pod
  5szib3vfllat54); drift dirs + train logs saved to pod_backup_weekend/night1025/. night_decide restarted on the 5 arms left,
  deadline 11:00Z (07:00 EDT).
- crforge evaluation (owner bedtime ask; worker, laptop only; L74/crforge/EVAL.md): commit ad8ef3a532ad, Java 17 / Gradle,
  Apache-2.0, 652 commits in 30 days (one author). Every checked real value exact (princess HP L11 / 15 / 16 3052 / 4424 / 4858,
  Rocket on tower L15 / 16 497 / 546, Log L15 51, X-Bow L11 61, Tornado on tower L16 40 vs RoyaleSim 0.1.35 41; Earthquake on a
  hidden Tesla works, RoyaleSim 0.1.35 did 0); king activation = first damage + 70 ticks. CI claims 10,000 / 10,000 real battles
  tick-exact on client 16.402.22 (10-19 patch) -- PRIVATE dataset, recording method undisclosed (b). NOT run on our 145-match
  parity harness. Speed: ~1.5 icebow matches / s / thread on the busy laptop (RoyaleSim 0.1.17 ~3.1); integration 15-30
  engineer-days (no tower troops / per-card levels / mid-match starts in its env layer). Verdict: NOT NOW for training; pilot =
  point fights.py at crforge and rescore the 145 matches + J1-J4 vs fin15 (4-7 days); usable now as a reference engine.
  C:\Users\benpe\crforge_eval (0.66 GB) kept for that pilot; drive C 25 GB free.
- u25 drift checks (E4 960 vs u0 = CLXIII): mem_e_s106 (leak .12) win 0.760 (+2.1 [-2.8, +7.0]), full +4.9 s FLAG, first play
  +7.6 s FLAG; mem_e_s107 (leak .12) win 0.728 (-1.1), full -3.9 s [-7.6, -0.2] (BETTER), first play +1.4 n.s., plays / min
  +0.52: CLEAN; mem_e_s108 (leak .08) win 0.720 (-2.0), full +8.0 FLAG, first play +5.2 FLAG, elixir at play +0.28 FLAG.
  Same weight .12, one seed leaks, one does not: the weight alone does not settle it. Pros (pro_first_play.py, 29,290 match
  sides): first own play median 11.1 s, mean 12.7, p75 13.6, > 20 s only 7% -> the arms' 18-20 s opening wait is NOT pro-like.
- Owner 10-25 ~21:40 EDT: prune stale backups. 48 items from 10-10..10-14 (old pod relays, MEMP memory runs, pod1013 / pod1014*
  arms, podA-E, results_weekend.tgz; referenced only by their own old relay scripts) MOVED (not deleted) to
  pod_backup_weekend/_STALE_to_delete (26.77 GB); the owner deletes it (my rules forbid permanent deletion). Kept: succ48_1025
  (pod restore source), night1025, codex1018 (HANDOFF staging), w14 / w18 (opponents), bait, parity1016, all >= 10-15.
- 02:55Z mem_e_s106 DRIFT FAIL u50 (2nd leak flag) -> night_decide copied + STOPPED pod 33912 (03:02Z, as designed; it cut
  across my plan to reuse that pod for a backup arm -- the decide list should have excluded it).
- Leak diagnosis (a): training rollouts barely leak (mem_e_s109 u35: 0.73 elixir wasted / match, leak r -0.11 / match) while
  the E4 eval shows ~29 s at full; the strongest weight (.16) has the WORST opening wait (34 s). Not the weight. (b) the arms
  learned to wait for the opponent's opening and answer it; training opponents always open, E4 apparently waits.
- Backup arm mem_e4_s107 on 33458 = mem_e_s107 (leak .12) + E4 (rdef_e4 u0020) in the exploiter pool (share .15, T .1), ONE
  change; mem_e_s108 (flagged +8.0 s, weakest weight) stopped for it (records in night1025/mem_e_s108). Smoke running.
  night_decide restarted on mem_e_s107 / mem_l_s106 / mem_e_s109 (deadline 11:00Z); the backup is decided separately.
- 03:52Z mem_l_s106 DRIFT FAIL u50 -> pod 33015 copied + stopped. mem_e4_s107 (backup) launched 03:20Z on 33458 (u1 OK).
- mem_e_s107 drift: u50 CLEAN (win 0.743 +0.3 [-4.7, +5.4], full 12.7 s vs 13.5, first play 12.2 s) but u75 FLAG (win 0.709
  -3.0, full 24.1 s +10.6 [+6.3, +14.9], first play 27.2 s, plays / min -0.37): the arms drift into the opening wait as
  training continues. mem_e_s109 u50: FAIL=0 (first play +5.4 s flagged, not a gate metric).
- MODEL SELECTION 04:5xZ: mem_e_s107 training stopped at u80; its CLEAN u50 checkpoint (grafted c5be96a6) is being gated
  (gate_only.sh: 3,840 games vs CLXIII + memory ablation) on 33184 -> res_mem_e_s107u50. night_decide restarted on
  mem_e_s107u50 + mem_e_s109 (fetch now takes the checkpoint the res names). Note: an own-command kill pattern
  ("ev/mem_e_s107_u0100") killed my ssh shell once (pkill self-match trap); no harm (chain + trainer were already down).
- 08:24Z FINAL: mem_e_s107u50 gate pooled +0.34 [-1.56, +2.24] FAIL (tie); ablation 0 pairs (abl.sh failed; owed); mem_e_s109
  DRIFT FAIL at u100 (clean u75); pods 33184 / 33522 copied + stopped. mem_e4_s107 (E4 in pool) u25 FLAG (full 29.3 s, first
  play 28.9 s): E4-opener hypothesis CONTRADICTED. Live unchanged. Morning summary in HANDOFF.
- 10-26 morning, owner: keep working until a memory successor exists; 3 new single pods 33411 / 32657 / 33920 (54.4 vCPU each);
  no more pod stops. Replicated from 33458 (new podlink key there).
- ROOT-CAUSE CANDIDATE for the leak drift (b, from the code): rollouts sample the gate as Bernoulli(sigmoid((z - logit tau) /
  T_gate)) with T_gate 0.3 (e1_eval.sample_decide_batch), deployment / eval use the hard threshold p > tau. A sub-threshold
  opening gate (p .25 at tau .35) still plays 17% of decisions in training (opens within ~2 s, no leak cost) but never under the
  threshold -> RL lowers the opening gate for free and the deployed policy waits. Fits: training leak 0.73 elixir / match vs eval
  24-29 s at full, and the leak swinging between checkpoints (e4 arm u25 29.3 s -> u50 9.8 s; s107 u25 9.6 / u50 12.7 / u75 24.1).
  stall forcing ruled out (stall_elixir null -> anti_stall False). Test running: the leaky e4 u25 ckpt evaluated with
  --gate-decode hazard (rate execution, close to the rollout gate), 480 E4 games.
- Branch arms prepared (from mem_e_s107 u50: the graded grafted ckpt minus the 37 graft-added tensors; 5 projectile tensors keep
  the graft's values = the version that was gated): brT10_s107 / brT10_s111 (T_gate 0.1), brT05_s107 (T_gate 0.05); smoke on
  32657 running.
- ROOT CAUSE CONFIRMED (a): the SAME leaky checkpoint (mem_e4_s107 u25, 480 E4 games, seed block 741200, vs its u0):
  hard-threshold decode (deployed): full 31.3 s (+16.9 [+9.9, +24.5]), first play 29.8 s; rate decode (--gate-decode hazard,
  close to the rollout's sampled gate): full 16.0 s (+1.6 n.s.), first play 11.9 s (-0.8 n.s.) but win 0.504 (-25 pp). The leak
  is the train / deploy GATE mismatch (sampled at T_gate .3 in rollouts vs hard threshold deployed), not a learned habit the
  leak weight could price. Fix = train closer to the deployed decode: T_gate 0.1 / 0.05.
- 11:12Z four branch arms from mem_e_s107 u50 (smoke PASS on 32657): brT10_s107 32657, brT10_s111 33920, brT05_s107 33411,
  brT10_s112 33458 (the e4 arm stopped at ~u85; records in night1025/mem_e4_s107). All pods KEEP; no stops.
- abl.sh 0-pairs cause: skew_worker imported cb_mem's gap.py (memory v1 only: "memory must be ... 'v1', got 'v2'"); fixed with
  SKEW_GAP=$CB/... ; retest running.
- 10-26 09:41 EDT LIVE = ICEBOW Mark CLXIV: MEMORY (mem_e_s107 u50 grafted, c5be96a6; registered, parent CLXIII) on the owner's
  signal; deploy_ckpt.sh guard OK (icebow deck). Earlier 09:23 deploy attempt's STOP file ended the owner's direct live_play
  session between matches (my error: did not check for a direct session); cancelled, STOP removed.
- Replays (owner): run_live.sh keeps --clip-every 1800 (Discord clip); discord_clip.py now removes the full overlaid render +
  raw segments after cutting the clip (direct live_play.py runs keep their replays). Test on dummy files OK.
- Live watch (live_watch.py + 45-min watch_loop.sh -> promote/watch_CLXIV_MEMORY.log + Discord; alert on leak > 20 s or no new
  match). CLXIII live baseline (301 matches): win 0.482, full 8.2 s / match, first play 7.2 s, plays / min 10.3, Rockets 0.31 /
  match (tower 0.20), combos 0.023, X-Bow lock 0.514, ADAPT next X-Bow <= 30 s after a FAILED one 0.302 vs after a LOCKED one
  0.225 (CLXIII repeats more after failures), X-Bows / min 1.65 -> 0.85 after the first failure.
- live_gen_v2 now logs xb_lock_p (the v2 path dropped it); live restarted between matches to pick it up (play unchanged).
- 10-26 ~10:00-10:30 EDT owner: CLXIV live never Rocket-cycles / barely Rockets on defence (measured 4 matches: 0.25 Rockets /
  match, 0 tower Rockets; CLXIII 301 matches 0.31 / 0.20); SIM training of the branches: rockets 0.26 / match, rocket_cycle
  reward 0.006 / match (dead). Rocket package (rocket_cycle_w 2-3 + spell_value) started 13:59Z, then a generic wincon
  multiplier (14:01Z) -- owner: the multiplier pays Rocketing a lone Giant / Golem -> PAUSED, reverted (98edb8e); the three pods
  back on T_gate-only seeds brT10_s121 (33920), brT10_s122 (33458), brT05_s123 (33411); brT10_s107 (32657) continues.
- T_gate fix WORKS on the leak (a): brT10_s107 u25 full 4.7 s vs 12.7 (u0), first play 8.6 vs 12.2; brT10_s111 u25 7.6 s / 9.0 s
  (flags: threat idle +3.9 pp, threat ignored +3.6 pp). Win -4.3 / -3.3 pp at u25 (n.s.).
- SIM Rocket use in eval rows (rocket_rows.py): CLXIII gate E4 0.344 / match (2x+OT 0.278); CLXIV-base u0 0.467; brT10_s107 u25
  0.552; pros ~1.6. Deploy-time Rocket bar wired into night_decide (ROCKET_BAR env), not a training reward.
- OWNER APPROVED the non-exploitable design: (1) counterfactual SIM-fork credit (ROCKET and SIEGE triggers; alt vs actual
  action, critic value difference as the alt's advantage) -- build agent running; (2) measure SIM vs live OT chip-race frequency
  + Mortar defence live / pro / SIM -- measurement agent running. Owner also: Mortar defence must be fixed; top-1,000 Ranked aim;
  competent successor by 10-27 morning; never stop at a failure.
- 10-26 10:20 EDT owner STOPPED live (CLXIV): "cannot watch this anymore". CLXIV live record (11 matches, live_watch.py): win 3 / 11
  = 0.273 [0, 0.545]; full 0.4 s / match (no leak live); first play 6.0 s; Rockets 0.36 / match (tower 0.27); X-Bow lock 0.514;
  ADAPT next X-Bow <= 30 s after a FAILED one 0.389 (7 / 18) vs after a LOCKED one 0.105 (2 / 19): it doubles down after failures
  (c: the memory does not adapt the right way). CKPT_OVERRIDE left on CLXIV (no auto-revert; offered).
  Next candidates must show the reverse adaptation (fork credit's alternatives) before any live start.

## 10-26 ~12:45 EDT -- owner: STOP all pod work, plan first. PLAN APPROVED (scratchpad/gauntlet/L74/plan1026/PLAN.md)
- Owner mandate: >99.9% engine (game files + replays + live logs), human-like per-deck opponents, a reward / training design
  built from the whole history; no pods / training / experiments / live until a plan exists. Plan approved after 4 owner
  revisions: (1) reward NOT win-only (R_win + fitted zero-sum R_exchange + fork credit); (2) barrel_lane kept for successors
  (reader issue); (3) NO KL leash on our model (drift handled by removing its causes + noise cuts + scenario starts + per-update
  step limit + detect / select / branch); (4) macro strategies (sneaky lock, Rocket cycling in 2x / OT ...) via a mined macro
  library used as fork alternatives; (5) NO-DISCARD rule: a failing core part is iterated, never dropped, unless the owner says.
- Arms ended: brT10_s121 (33920), brT10_s122 (33458), brT05_s123 (33411): "DRIFT FAIL" = training CRASHED at start (a):
  SystemExit "shaping_critic_scale 3.5 < 3.7000 = the return bound + habit_terms.bound" -- a config bug, not a drift verdict;
  they never trained. brT10_s107 (32657) halted by the owner order during its u75 drift eval: u50 drift PASS (win 0.734 vs
  0.743, -0.008 [-0.061, +0.043]; flags elixir at play +0.11, first play 14.2 vs 12.2 s, Tornado / min -0.056; full 13.6 vs
  12.7 s). Records: C:/Users/benpe/pod_backup_weekend/night1025/{brT10_s107,brT10_s121,brT10_s122,brT05_s123}/ (s107 u75
  grafted sha 132f878f8e2cbd7f).
- Fork-credit build agent stopped (owner order). Uncommitted edits left for review: pipeline/e1_eval.py, pipeline/search_s0.py,
  pipeline/cf_credit.py (state: plan1026/cf_credit_build_state.md; it was sorting 6 test failures, pre-existing vs its own).
- Pods: 33458 + 33411 STOPPED (runpodctl stop; plan decision 6 default); 32657 + 33920 kept, idle.
- Live: CKPT_OVERRIDE wired back to CLXIII NOLEAK (8d328a43bf09fb7e; deploy_ckpt.sh wire, offline --check PASS; not started;
  plan decision 2: CLXIII = the fixed live data config). Revert file CKPT_OVERRIDE.pre_20261026_1243 (-> CLXIV).
- 10-26 measurements written up: memory/measure1026/REPORT.md (OT chip-race conversion gap; Mortar live / pro / SIM; live_siege.py
  evolved-Mortar Goblin bug still open).

## 10-26 13:03-13:20 EDT -- owner decisions 4 / 5 / 7 approved; device checks DONE (plan1026/devcheck/REPORT.md)
- Owner: poll the battle log after every match; device checks now with the MODEL playing; TV Royale harvesting OK.
- One live CLXIII Ranked match (main account 4858, 1-0 OT win vs 902b; live_play_20261026_130453.jsonl), then STOP.
- G-R2 (a): battle-log replay recorded by the reader reproduces the live board exactly on 1,014 / 1,017 common ticks (0.9971);
  11,012 / 11,014 paired bodies identical in position and HP. The replay also gives both decks + forms, both hands, both
  deal orders from tick 0 and exact elixir.
- G-R3 (a): no replay file cached on disk (root find before / after: only cache / telemetry mtimes changed).
- Battle-log polling: crapi.py `own --tag TAG` built + tested (10 / 10). BLOCKED: the only API key is IP-locked to the
  crawler VM 34.148.91.90, which is stopped (ssh timeout); none on the laptop. Needs the owner: a key for the laptop IP or
  the VM restarted. Our player tag also needed.
