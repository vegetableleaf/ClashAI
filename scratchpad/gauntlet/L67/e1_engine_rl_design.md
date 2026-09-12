# E1 -- overnight S1 engine-RL design (L67, 2026-09-12)

Design only. Nothing started. Builds on `engine_rl_feasibility.md` (same dir) -- its facts are not repeated.
Labels: (a) verified in code/HANDOFF with file:line; (b) proposed / untested.

Owner-approved spec (2026-09-12): one overnight S1 engine-RL run; init `icebow/data/pipeline/s1_icebow_v6lat_s0.pt`;
terminal win/loss reward only; KL leash to frozen init; degrade()d obs; ghost opponents with a HELD-OUT ghost
set as validation (thousands of matches); pro agreement must not fall; 2 engine slots, ~15.9 s/match; runs only
when the owner says the box is free; smoke test first.

## 0. Four facts found while designing that change the plan (read these first)

1. (a) **The 72.3 +- 2.3 number is NOT the E1 init's number.** §5cs.66 (HANDOFF l.3868-3876) graded the v1 checkpoints
   `s1_icebow_s{0,1,2}.pt` (corpus v3, floor grid), clean compact obs, greedy, tau 0.5, on the first 100 entries of
   `random.Random(0).sample` over all 477 pool entries. `s1_icebow_v6lat_s0.pt` (args: data `s1_dataset_v6.npz`,
   grid lattice, epoch 15, 1,264,680 params -- read from the checkpoint) has no engine winrate of that kind in this
   design's sources (see §1.6). **E1 needs its own baseline, on the degraded pipeline, before any RL step.**
2. (a) **`degrade()` is not exactly what live feeds the model.** degrade() makes unit hp / king hp `None` (hp_known 0)
   (obs_contract.py:541-557), but the live student sends every unit at hp 1.0 (`from_live(..., unit_hp_default=1.0)`,
   student_live.py:62,141-142) and the king at 1.0 (`live_reads(fill_king_hp=True)`, student_live.py:488), because
   "supplying beats flagging" was measured (5cs.98 E: 18.78/52.11 -> 20.15/63.25). Live also resolves an unknown-team
   unit to ENEMY when my deck cannot produce its class (`mine_classes`, obs_contract.py:385-416, 459-461); degrade()
   does not. Plan: a `live_view()` = `degrade()` + those two live rules (section 3.1). (b) untested that it matters
   on the engine; it is a 10-line function with a unit test.
3. (a) **`v6lat_s0` was trained on CLEAN rows only.** On the degraded v3 VAL the v6lat seeds score 16.35 +- 0.56 exact
   cell / 49.27 +- 1.22 card vs 21.04 / 64.99 clean (HANDOFF l.3220 / l.3206-3214). So RL on degraded obs starts from
   a policy that is 4.7 pp / 15.7 pp worse on the view it will train on. Any early "gain" can be the policy adapting
   to degradation (which supervised v6aug already bought: +3.10 cell / +11.1 card degraded, HANDOFF l.3121-3127) --
   NOT winning. The pro-agreement guardrail must be read on BOTH the clean and the degraded VAL (section 3.6).
4. (a) **The ghost pool rows carry NO opponent identity.** `opponent_tag` is the empty string in 477/477 icebow and
   241/241 hogeq pool entries (measured this loop); `player_tag` is OUR side's pro (83 distinct icebow). The crawl's
   `battles.csv` has an `opponent_tags` column (header read this loop) -- join by `replay_tag` (section 2.2).

## 1. Existing pieces to reuse (all (a), file:line)

### 1.1 Engine client and match env
- `NativeRoyaleEnv(host, port, timeout)` -- `research/ext/cr-native-sandbox/native_core/env.py`; constructed at
  `scratchpad/gauntlet/L62/engine_env.py:124`. Ops used: `reset(replay, warmup_steps=0)`, `step(n)` -> `tick_after`,
  `episode`; `act(side, deck_index, x, y)` -> `accepted`, `result_code`, `placement_valid`, `placement_reason`;
  `observe()`; `last_episode`; `close()`.
- `EngineMatchEnv(*, port=38031, host, pool, decision_ticks=10, elixir_slack=40, tail_cap=7200, seed=0,
  replay_seed=424242, level=11, timeout=120.0, deal_cache=True, warmup_ticks=90, w_hp, w_crown, w_outcome)`
  engine_env.py:102-106. CAUTION: its constructor still calls `V2.init_worker()` and builds the OLD `SimMatchEnv`
  (l.107-121) even when only the raw path is used -- a RAM and import cost that `engine_play.RawEngineEnv` inherits.
- **Reset against a chosen ghost:** `env.reset(entry)` or `env.reset(index=i)` (l.295-363): `_resolve_decks(entry)`
  (l.217-256; deal inference `RD.infer_deals` + `RD.sp_order_for`, cached per tag in `L62/deal_cache.json`, 375
  entries cached now -- a miss costs one extra engine reset), `build_replay(template, deck0, deck1,
  seed=replay_seed)` -> `eng.reset`, asserts 6 crown towers (l.317), schedules the ghost's non-ability commands
  (l.325-328), advances to tick 90 (the engine refuses every deploy before 4.5 s, l.132-136).
- **Ghost driving:** `_advance_to(target)` (l.401-414) stops on every ghost tick; `_fire_ghosts_at` (l.366-393) retries
  a code-13/1050 elixir refusal each tick up to `elixir_slack` 40 ticks, counts refusals + reasons.
- **Outcome:** `engine_play._outcome(env, state)` (pipeline/engine_play.py:225-237) -> ("win"|"loss"|"draw", crowns)
  from `last_episode.winner`, falling back to crowns. **E1 reward = +1 / -1 / 0 from this, nothing else.**
  `EngineMatchEnv.step`'s dense reward (l.455-470: tower-HP delta + crowns + 3x terminal) is NOT used -- E1 drives
  `_advance_to` directly, as engine_play does.
- Match end: `env.terminated or env.tick >= env.tail_cap` (engine_play.py:319); tail_cap 7200 ticks = 360 s.

### 1.2 How S1 acts in the loop today (`pipeline/engine_play.py`)
- `RawEngineEnv(port, host, pool, decision_ticks, seed)` (l.138-154): EngineMatchEnv with `_render` returning the raw
  `observe()` dict and `_resolve_decks` keeping `final_decks`. `load_model(ckpt, device)` (l.160-178) -> (S1Model, info
  incl. `grid`; v6lat = "lattice").
- Per decision (l.263-319), every `decide_every`=10 ticks (0.5 s):
  `compact_raw(state)` (l.82-88; drops `kind`, effects, projectiles -> same row format as training, §5cs.61 leak fix)
  -> `from_engine(obs, side, deck, engine_deck=engine_deck_names(env.final_decks[side]), unmapped=set())`
  (obs_contract.py:220-329) -> `to_tokens(bs, 64)` (obs_contract.py:599-623) -> `_past(done_plays, tick)`
  (dataset.py:62-68; my last 3 ACCEPTED plays, ages from ticks) -> `decide(model, tok, mask, sc, past, tau, gate, rng,
  device, policy)` (l.181-219).
- `decide`: `enc = model.encode(tok, mask, sc, past)`; `heads = model.heads(enc, hand_mask_from_sc(sc))`
  (model_v3.py:131-137; card logits masked to hand with -1e4); gate = `sigmoid(heads["gate"])` -- ONE logit, trained
  with BCE (train_s1.py:82); play iff p > tau (threshold) / Bernoulli(p) (sample) / never (none); card = argmax of the
  8 hand-masked slot logits; cell = argmax of `model.cell_logits(enc, slot)` (model_v3.py:139-146, 2,304 cells,
  NO legality or affordability mask -- the engine refuses and the harness counts it: 85.5% accepted in §5cs.66).
- Play: `cell_to_engine(cell, mirror, grid)` (l.70-73, `cell_xy` lattice offset 0.0, model_v3.py:63-68) ->
  `env.eng.act(side=side, deck_index=deck_index_of_slot[slot], x, y)` (l.283); accepted -> `done_plays.append`.
- Live differs (student_live.py:135-236): card logits are also masked to AFFORDABLE + tray-readable slots before the
  argmax (l.163-191); tau 0.27 and anti-stall 9 elixir / 12 s in the owner's runs 8-9 (HANDOFF l.2747); cycle-rule
  `drop_cycle_repeats` on `past` (l.311-323).

### 1.3 `obs_contract.degrade` (obs_contract.py:486-558)
- Signature: `degrade(bs, rng: np.random.Generator, *, recall=0.855, precision=0.886, elixir_to_int=True, drop_hp=True,
  drop_deploying=True, unknown_team_rate=0.25, pos_sigma_tiles=0.45, wrong_team_rate=None -> {troop .15, building .15,
  spell .40}) -> BoardState` (source "degraded").
- Effects: each unit/spell kept w.p. recall; per kept unit a false positive w.p. (1-precision)/precision = 0.129 (random
  class of the same kind, jitter max(0.45, 1.0) tiles); Gaussian 0.45-tile position noise; side -> -1 w.p. 0.25, else
  flipped w.p. the kind's wrong-team rate; hp/deploying/age -> None; conf redrawn from the measured mixture
  (`_draw_conf`); elixir floored; opp_elixir None; alive king hp -> None. Only recall/precision/0.45/0.25 are measured;
  FP jitter is labelled UNMEASURED in the file (l.494), wrong-team troop/building 0.15 is (b) (l.498).
- RNG: fully determined by the passed Generator; draw count depends on unit count, so the SAME seed on a different
  board gives different noise. `build_degraded.py` uses one `np.random.default_rng(seed)` for all rows (L67/build_degraded.py:34).
- Engine obs carries no spells at all (compact_raw drops effects) so the spell path of degrade is inert in E1.

### 1.4 Old engine PPO trainer (`scratchpad/gauntlet/L62/engine_ppo.py`, 627 lines) -- what to copy / not copy
COPY (adapted to S1):
- Output-path guards (l.109-122): refuse to overwrite any `*_*.pt`, refuse an existing log, refuse `icebow/data/` except
  an allow-listed prefix.
- Frozen reference (l.148-152): deep copy of the init, `eval()`, `requires_grad_(False)`; reference log-probs computed
  ONCE per update, batched (l.412-421).
- KL leash (l.457-466): KL(pi_theta || pi_ref) over the renormalised masked support, PLAY rows only, cell head in the
  loss (`kl_coef * kl_cell`), card KL logged. How the coefficient was set: kl_coef 0.3 "from the smoke (|KL
  term|/|policy loss| 0.025 at update 1, 0.16 at update 2 at coef 0.1) -- a guess at about half the policy loss, not a
  tuned value" (HANDOFF l.1771-ish, §5cs.44 A). Result at 0.3: kl_cell held 0.06, top-1 flat 15.44 -> 15.64 over 609
  matches; at 0: kl_cell 1.54, rails 0.262, top-1 6.87 (§5cs.51 A-B).
- Gate prior (l.160-185 setup, l.249-272 target, l.481-490 loss): Bernoulli CE of the GATE HEAD toward
  `icebow/config/gate_prior.json` schema 1 (519 replays, 23,620 plays, dt 0.6) `p_play[single|double|triple][elixir
  bucket 0-10]`, phase flips at 120 s / 240 s, rows with nothing affordable excluded; coef 2.0 in engB. It stopped
  the collapse (engA 0.12 plays/match without it, §5cs.46 A; engB gate alive, p_gate 0.099 vs target 0.095 at kill,
  §5cs.51 B). Table values read this loop: single 0.063 @3 / 0.203 @9; double 0.103 @3 / 0.446 @9; triple 0.157 @3 / 0.459 @9.
- Sampling factorisation (l.306-316): log pi = lp_gate[g] + play * (lp_card[c] + lp_cell[cell]); entropy split.
- `save()` (l.214-231): step checkpoint + `_latest.tmp` -> `os.replace` -> `_latest.pt`. **Change: write `_latest`
  EVERY update** (trap: engB lost m500->m609 because `_latest` was only written at save_every, HANDOFF l.2217-2223).
- Crash path (l.572-584): log ABORT, save `crash<m>_<time>.pt`, close env in `finally`; non-finite guards (l.515-527).
- Log line fields (l.554-564) incl. `frac_gt_tau` -- "the readout whose absence hid engA's collapse" (l.58-60).
DO NOT COPY:
- The critic warm-up on the shared trunk (l.466-476): it moved both arms ~1.15 nats of cell KL from the init BEFORE any
  policy gradient (§5cs.44 B). E1 uses a fixed baseline, no learned critic on the trunk (section 3.2).
- GAE over dense per-step reward (l.396), PPONet/PolicyNet CNN, the 2-logit gate, `clamp_heads` (CNN-specific).
- One EngineMatchEnv per trainer process with rollout-then-update blocking (27-28 s rollout + 12 s update, §5cs.44 C):
  E1 separates actors from the learner (section 5.2).

### 1.5 Pro-agreement eval for S1
- Command: `python -m pipeline.eval_s1 icebow --data <npz> <ckpt> [<ckpt> ...]` (pipeline/eval_s1.py:22-44) ->
  `train_s1.evaluate(model, rows, grid)` (train_s1.py:96-152) on `split == 1` rows. Prints one JSON line; writes nothing.
- Metrics (PLAY rows, cell teacher-forced on the PRO's card): `cell_half_top1` (= "exact cell" on lattice), `card_top1`
  (hand-masked), `joint_top1`, `place_dist`, `cell_nll`; ALL rows: `gate_acc`, `gate_bal_acc`; `wait_top1`, `value_acc`.
- The fixed instrument is the v3 VAL: `icebow/data/pipeline/s1_dataset.npz`, 13,761 rows / 3,796 plays. v6lat_s0 on it
  (L67/s1_v6/eval_v3val_icebow_v6lat.out line 1): **exact cell 20.97, card 65.46, joint 14.09, dist 3.513, gate_acc
  .8258, gate_bal_acc .766**. 3-seed band: cell 21.04 +- 0.22, card 64.99 +- 0.57 (HANDOFF l.3206-3214).
- Degraded twin: `--data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz` (same rows through degrade seed 0).
  v6lat_s0 (eval_v3degraded_icebow_v6lat.out line 1): **cell 16.10, card 48.18, dist 4.603, gate_acc .7511,
  gate_bal_acc .743**; 3-seed band 16.35 +- 0.56 / 49.27 +- 1.22 (HANDOFF l.3220).
- Selection split (v6 val, 55,461 rows / 15,065 plays, stored in the checkpoint's `val`): cell 21.16, card 63.36.
- Trap to carry: this metric is CONDITIONAL on playing and teacher-forces the card; it "would have scored a
  permanently-waiting policy just as well" (§5cs.46 B, HANDOFF l.1869-1874). Every read needs the unconditional
  companions: `gate_bal_acc` here plus plays/min and card mix from the engine.
- Cost (b): v3 VAL 13,761 rows through a 1.26 M-param model on CPU -- the file is 5.5 MB; the eval is seconds-to-a-minute.
  Run it in the learner process on its own checkpoints (no engine needed).

### 1.6 The S1-vs-ghost winrate harness (72.3 +- 2.3)
- Runs (§5cs.65 B / §5cs.66 A, HANDOFF l.3868-3876, 3897-3903): `python -m pipeline.engine_play icebow --ckpt
  icebow/data/pipeline/s1_icebow_s{0,1,2}.pt --port 3703x --matches 100 --seed 0 --tau 0.5 --gate threshold --out
  scratchpad/gauntlet/L64/engine_ctrl/thr_{s0,ck1,ck2}`; control `--gate none` -> `none_s0`; random `--policy random
  --p-random 0.13` -> `rnd13_s0`. Scorer `scratchpad/gauntlet/L64/engine_score.py <control_summary> <run_summary>...`
  pairs by match index, asserts identical tags, reports W/D/L, survival delta +- SE, crowns, plays/min, accepted frac.
- Pool order: `random.Random(seed).sample(range(477), 477)`, first 100 (engine_play.py:373); 10 of those 100 are
  hero-knight entries (measured this loop); `--own-forms` exists to exclude them (l.374-382).
- Measured wall per match over the 100-match runs (summaries re-read this loop): threshold s0/s1/s2 **21.9 / 20.3 /
  21.1 s mean** (median 18.8-20.3, p90 27-30), 204 s of game time; sampled gate 22.1 s; no-plays control 8.7 s.
  **Use ~21 s/match, not 15.9** (15.9 was the 2-match smoke, §5cs.63 B).
- Instrument ruling already recorded: at n=100 the three seeds are indistinguishable (75/71/71); threshold vs sample
  (75 vs 68) is "inside the binomial noise (+/- 9 pp)" (HANDOFF l.3901).

## 2. Ghosts: where they live, the split, the eval protocol

### 2.1 What exists (a, measured this loop unless cited)
- **Pool v0** `icebow/data/ghost_pool/pool_env_v0.jsonl`: 477 entries (hogeq: 241), built 2026-09-05 by
  `L62/build_ghost_pool.py` from a crawl2 snapshot of 1,228 battle rows; refused 504 "play_not_positioned", 225
  "no_native_evolution_form", 15 no plays, 3 not-one-side, 3 no consistent deal, 1 ghost unpositioned
  (`pool_env_v0_build.json`). Our-side forms: 433 evo knight + evo tesla, 40 hero knight + evo skeletons + evo tesla,
  4 base. 335 real wins / 142 losses for our pro; 83 distinct pros; ghost plays median 44; 1 entry with <= 3 distinct
  ghost cards.
- The "120 of 619" refusal figure is the corpus-v3-era drive (§5cs.59, 619 fully positioned tags, HANDOFF l.2450 /
  l.2480-2485; hogeq 52 of 296 = evo Elite Barbarians). Pool v0 already excludes those classes of failure.
- **Corpus v6** `scratchpad/gauntlet/ext/corpus_v6/icebow/replay_<tag>.json`: 2,241 replays (740 MB), every one
  ALREADY DRIVEN IN THIS ENGINE (`log` = both sides' driven plays with tick/side/card/x/y/cost/accepted/delay_ticks;
  `final_decks` = the dealt engine order; `opening_state_hash`; `final.state_hash`/outcome/crowns; `grade`). Sample of
  40: accepted 98.5%, crowns match the real game 28/40 (cf. 76.9% on the v3 drive, §5cs.59).
- **Every pool v0 tag is an S1 training replay**: 477/477 are in `s1_dataset_v6.npz` (395 S1-train split, 82 S1-val);
  hogeq 241/241 (197 / 44). So 83% of the ghosts behind "72.3" were matches whose pro side S1 imitated.
- Opponent identity: pool rows have `opponent_tag = ''` (477/477). Join on `replay_tag` with
  `icebow/data/royaleapi/crawl2/battles.csv` `opponent_tags`: 477/477 found, 465 distinct opponents, 12 with 2 matches.
  Corpus v6: 1,638 of 2,241 tags have an opponent tag (the 603 HF-converted replays carry none --
  `L67/hf_to_crawl.py:120` writes `opponent_tags ""`); 1,566 distinct, 60 opponents with > 1 match (132 matches, max 9).

### 2.2 Proposed split (b, counts measured this loop)
Recommendation: **build pool v1 from corpus v6** (section 7); fall back to v0 only if the v1 parity check fails.
Deterministic rule, no RNG:
1. Candidates = corpus v6 replays with exactly one icebow side (3 mirror/none removed) AND our side's forms =
   {Knight evolution, Tesla evolution, rest base} -- the live deck (428 other-form replays removed, mostly hero knight).
   -> **1,810**.
2. `s1_val(tag) = crc32(tag) % 100 < 15` -- the SAME rule as `dataset._tag_split` (dataset.py:86-87, val_pct 15), so a
   held-out ghost is also a match S1 never imitated.
3. Opponent group key = `opponent_tags` if non-empty, else `"tag:" + tag` (no identity -> own group; the 603 HF rows
   cannot be grouped -- leak there is unmeasurable, recorded, not hidden).
4. A group containing ANY s1_val member is a held-out group: its s1_val members -> HELD-OUT; its S1-train members ->
   DROPPED (not moved to held-out, since S1 trained on them). All other groups -> RL-TRAIN.
5. Result: **held-out 293** (190 with an opponent tag), **RL-train 1,505**, **dropped 12**.
   Held-out ghost plays median 41, min 1; 13 of 1,798 entries have <= 5 ghost plays (tagged, kept, monitored).
- Not grouped by OUR pro (`player_tag`): the ghost is the opponent; the pro only fixes deck order/deal. S1 already
  split by tag, not player, so no new leak is introduced.
- Fallback v0 with the same rule: held-out = the 82 S1-val entries, 73 with the live deck's forms. Unpaired binomial SE
  at 72% is 5.3 pp at n=73 -- too weak for the verdict; v0 fallback downgrades E1's winrate read to a screen.
- Freeze the split into `icebow/data/ghost_pool/pool_env_v1_split.json` (tag -> train/heldout/dropped + group key +
  sha256 of the pool file) BEFORE the first RL step; the learner refuses a held-out tag in a train task (assert).

### 2.3 Eval protocol (b)
- **Rule under test = the live rule**, not §5cs.66's: greedy; card = argmax over hand AND affordable slots
  (student_live.py:169-179 semantics, cost <= floored elixir); cell = argmax; gate tau **0.27**; anti-stall 9 elixir /
  12 s of engine time since last accepted play or match start (student_live.py:126-133, L67r F2); obs = `live_view`
  (3.1). One rule, used for baseline, screens and final. (§5cs.66's tau 0.5 / no mask / clean obs is reported once in
  window A on the same 100 entries for continuity only.)
- **Randomness in an eval match** is ONLY the degrade/live_view RNG (engine deterministic 211/211, §5cs.59; greedy
  policy). Seed per match = `crc32(f"{tag}:eval:{k}")` for k = 0, 1, 2. Same seeds for init and candidate -> PAIRED.
- **Effective n is the number of ENTRIES, not matches.** 293 entries x 3 seeds = 879 matches, but outcomes of one entry
  across degrade seeds are correlated; report both, and compute CIs by an entry-clustered bootstrap (resample entries,
  10,000 draws). "Thousands of held-out matches" on a finite deterministic pool buys within-entry noise reduction, not
  thousands of independent draws. Unpaired SE at 72%: 2.6 pp at n=293.
- **Paired test**: per entry, mean win over seeds for candidate minus init; McNemar on (entry, seed) pairs as a second
  read. Arithmetic MDE (b): with ~20% discordant pairs (UNMEASURED -- window A measures it), 879 pairs give 80% power
  at alpha 0.05 for ~4.2 pp; clustering by entry pushes the honest MDE to ~5-6 pp.
- **Both slots**: tasks are (entry, seed) sharded round-robin over slots 0/1; the report includes a per-slot winrate so
  a sick slot shows up (`L67/eval_by_slot.py` exists as a pattern).
- **Guardrails already on the ledger**: one seed / one run is a SCREEN (§5cs.44 "one value, one seed -- a screen");
  winrate needs large n (§5cs.65 B: +/- 9 pp at n=100). Controls re-used: no-plays control and rate-matched random on
  the held-out set once (window A), so "any plays win against a replay" stays falsified on THIS set.
- **Pre-registered verdict (b)**: E1 PASSES only if (i) paired held-out winrate delta >= +5 pp with the clustered 95% CI
  excluding 0; (ii) pro agreement not below the band of 3.6; (iii) plays/min within +-20% of the init's on held-out;
  (iv) the exploit indicators of section 4 not above their init values by the stated margins. "No change" is an
  allowed, expected-likely outcome (engB leashed arm was flat over 609 matches with a denser reward, §5cs.51 A).

## 3. Algorithm (b unless cited)

### 3.1 Observation: `live_view(bs, rng, deck)`
`degrade(bs, rng)` with its defaults, then the three live rules degrade lacks: unit `hp_frac = 1.0` (live
`unit_hp_default=1.0`, student_live.py:62,141); alive king `hp_frac = 1.0` (`fill_king_hp`, student_live.py:488);
side -1 -> 1 for classes outside `mine_classes(deck)` (obs_contract.py:459-461). `opp_elixir` stays None (live default
`play.student_opp_elixir: false`, play.py:164, 841-853). Keep `compact_raw` (no spell tokens, no `kind`) -- parity with
the training rows; the missing-spell gap is recorded, not fixed (one change). The SAME tokens the actor fed the model
are stored and re-fed by the learner, so noise never differs between rollout and update.
Residual live-only gaps not modelled: tray-read failures / HandMemory, wall-clock `past` ages, the cycle-rule repair,
spell tokens, evo-class folding, detector timing. Named so no one reads E1 as "the live path, simulated".

### 3.2 Policy-gradient form: PPO-clip with a group (leave-one-out) baseline, terminal reward
- Reward: R = +1 win, -1 loss, 0 draw from `_outcome` (engine_play.py:225-237). No shaping, no discount, no critic.
- Why not a learned critic: the value head shares the trunk, and a critic warm-up alone moved the old policy 1.15 nats
  (§5cs.44 B). Why not plain REINFORCE with a running mean: entry difficulty dominates variance (no-plays control loses
  in 61-91 s on some ghosts, §5cs.64 C / §5cs.65 B). Why PPO-clip over REINFORCE: 2 epochs per batch and a clip keep
  the step bounded when the batch is noisy; the ratio is exactly 1 at epoch 0, so it costs nothing on-policy.
- **Group baseline**: each batch = 8 RL-train entries x G = 4 rollouts (different sampling/degrade seeds, split 2+2
  over the slots) = 32 matches. A_i = R_i - mean_{j != i} R_j. A group with one outcome gives A = 0 (no gradient).
  No std normalisation (it would blow up near-concordant batches); scale fixed at |A| <= 2.
- Each RL-train entry is used ONCE (1,505 entries, ~48 updates x 8 = 384 entries/night): no per-ghost memorisation
  pressure from revisits. Entry order = sorted by crc32(tag + "e1order"), deterministic.
- Loss per decision d of match i: `L_pg = -min(r_d A_i, clip(r_d, 0.8, 1.2) A_i)`, averaged per match then over the
  batch (so a 300-s match does not outweigh a 60-s one 5x).

### 3.3 Behaviour distribution and log-probs (the three heads)
The deploy rule is deterministic, the gradient needs a stochastic policy. Behaviour = a tempered version of the
deploy rule, fixed constants, so log-probs are exact:
- gate: `p = sigmoid((z_gate - logit(0.27)) / T)`; as T -> 0 this IS the live threshold rule. Masked (log-prob 0,
  excluded) when no card is affordable or when anti-stall forces the play (the environment, not the policy, decided).
- card: `softmax(z_card / T)` over hand AND affordable slots (8 slots, model_v3.py:131-137 + affordability).
- cell: `softmax(z_cell(enc, sampled card) / T)` over all 2,304 cells (S1 has no deployable mask; refusals are part of
  the environment, as in §5cs.66).
- `log pi(a_d) = log p_gate[g] + g * (log p_card[c] + log p_cell[x])` -- the old factorisation (engine_ppo.py:306-316).
- **T is calibrated in window A, not guessed**: T in {0.25, 0.5} on 40 RL-train entries each; pick the largest T whose
  sampled plays/min is within +-15% of the greedy live rule's and whose winrate is within 10 pp (a screen). Reason, (a):
  UNtempered sampling of the S1 gate over-plays (18.7 vs 11.2 plays/min, 40% refused, §5cs.65 B), because the gate
  was trained on one WAIT row per 2 s (dataset.py `wait_stride` 40 ticks) -- its p is not a per-0.5-s play probability.
- **Dropout trap**: S1Model has dropout 0.1 (model_v3.py:80,91). Both rollout AND update forwards run in `eval()`
  mode (gradients still flow). Smoke asserts ratio == 1 +- 1e-5 on epoch 0, minibatch 0.
- Stored per decision: tok[64,14], mask[64], sc[70], past[3,4], afford mask[8], anti-stall flag, (g, c, x), behaviour
  log-prob components, p_gate, T, policy version, degrade seed. ~4 KB/decision raw, ~408 decisions/match.

### 3.4 KL leash to the frozen init
- Frozen `pi_ref` = the init loaded once, `eval()`, no grad (engine_ppo.py:148-152 pattern); ref log-probs computed
  in the learner, batched, once per update (l.412-421 pattern).
- Per decision, on the SAME tempered distributions: `KL_gate` = Bernoulli KL (every decision where play was possible);
  `KL_card` over hand AND affordable (play decisions); `KL_cell` over 2,304 given the sampled card (play decisions).
  `L_kl = beta * (mean KL_gate + mean KL_card + mean KL_cell)`.
- Coefficient: **adaptive, start beta = 0.3** (the old value, chosen as ~half the policy loss, §5cs.44 A), target
  `KL_cell` kappa = 0.10 nats: after each update beta x2 if KL_cell > 1.5 kappa, /2 if < kappa / 1.5, clamp [0.03, 3].
  Reference points (a): the leashed engB arm sat at kl_cell 0.02-0.06 and neither learned nor forgot; the unleashed arm
  degenerated at kl_cell 1.2-1.5 (§5cs.46 D, §5cs.51 B). kappa 0.10 gives a little more room than the flat arm, an order
  of magnitude less than the failed one.
- The **table gate prior is NOT copied**: its p_play is fitted at dt 0.6 s on a per-decision basis (gate_prior.json
  `dt` 0.6) while the S1 gate means something else (trained on 2-s WAIT sampling); pulling S1's gate toward it would
  distort a pro-trained head. The per-board KL on the S1 gate is the stronger prior (it is the pro-imitation gate
  itself). engA's collapse happened with NO gate term at all (engine_ppo.py §2.1, §5cs.46 C). Collapse is watched by
  the plays/min stop rule (3.6), not assumed away.
- Entropy bonus: 0 (the KL to a non-degenerate init already holds entropy); logged per head; stop rule if a head's
  entropy falls below 50% of the init's.

### 3.5 Optimiser and schedule
Adam, lr 1e-5 (supervised S1 used 3e-4 OneCycle, train_s1.py:238-240; RL fine-tune 30x lower), grad-norm clip 0.5
(engine_ppo default), 2 epochs per batch, minibatch 256 decisions (S1 trains at bs 256 on this 8 GB GPU,
train_s1.py:185), ~13,000 decisions per batch. All S1 parameters trainable; wait/value heads receive no loss.
Update cost estimate: ~150 fwd/bwd passes at ~4 batches/s (S1 ran ~71 s/epoch over ~305 batches, §5cs.61 C) ~ 40 s.

### 3.6 Monitors (every update = every 32 matches) and checkpoints
Per update line (JSONL `scratchpad/gauntlet/L67/e1/train_log.jsonl` + human log):
- plays/match, plays/min, accepted fraction + refusal reasons, anti-stall fires/match;
- card mix (8 slots, share), elixir at play (mean, share at 10), seconds at 10 elixir per match;
- gate: p_gate mean / p90 / frac > 0.27 (the engA-collapse readout), sampled play rate, share of decisions with
  0.05 < p < 0.95 (how many decisions are actually stochastic);
- KL gate / card / cell (mean, p95), beta, entropy per head vs init, PPO clip fraction, ratio mean;
- batch: W/L/D, share of groups with mixed outcomes (the gradient's real sample size), mean |A|;
- train winrate (behaviour policy, EMA over 5 updates) -- descriptive only, never a verdict;
- ghost: delivered / refused / undelivered per match, wins by ghost-delivered <= 10, wins by <= 3 distinct ghost cards,
  wins whose terminal tick > ghost's last command tick + 200 ("outlived the script", section 4);
- wall: s/match per slot, update seconds, RSS per process, GPU memory, slot restarts.
Every 5 updates: `python -m pipeline.eval_s1`-equivalent in the learner on the checkpoint -- v3 VAL clean AND
degraded (1.5); logged beside the init's 20.97/65.46/.766 and 16.10/48.18/.743.
Every 16 updates (~510 train matches): held-out SCREEN = 60 fixed held-out entries (lowest crc32), eval seed k=0,
paired with the init's same 60 from window A. ~10.5 min on 2 slots.
Checkpoints: `e1_u{NNNN}.pt` every 5 updates (never overwritten, assert), `e1_latest.pt` EVERY update via
`.tmp` + `os.replace` (engB trap), `e1_crash_<u>_<unix>.pt` on exception. Format = `train_s1` layout
(`{"model", "args", "deck", "epoch", "val", "n_params"}`) + an `e1` dict (update, matches, beta, pool sha, split sha),
so `eval_s1`, `engine_play --ckpt` and `student_live` load it unchanged. No "best on held-out" selection.

Stop rules (learner saves and halts; each needs 2 consecutive updates unless marked):
1. plays/min (behaviour) < 0.6x or > 1.6x the window-A behaviour baseline (gate collapse / over-play).
2. KL_cell > 0.5 nats or KL_gate > 0.1 with beta at its 3.0 clamp.
3. Pro agreement (clean v3 VAL): exact cell < init - 0.5 pp (20.47) or card < init - 1.2 pp (64.26) or gate_bal_acc
   < init - 0.03 -- ~2x the 3-seed sd (0.22 / 0.57, HANDOFF l.3212). Degraded VAL is reported, not a stop (it may rise
   by adaptation, which is not the goal but not harm).
4. Held-out screen: paired winrate on the 60 falls >= 10 pp below init (single occurrence -> stop).
5. Section 4 exploit rules.
6. Any non-finite loss/parameter (single occurrence, crash save, engine_ppo.py:515-527 pattern).

## 4. Exploit guards specific to ghosts

### 4.1 Measured this loop on the §5cs.66 runs (a) -- the baseline the guards compare against
Joined `L64/engine_ctrl/<run>/summary_icebow_s0.json` with pool v0's last ghost command tick:
| run | wins | wins that ran > 10 s past the ghost's LAST scripted command | wins with ghost delivered <= 10 plays | wins where the real pro LOST |
|---|---|---|---|---|
| thr s0 (tau 0.5) | 75 | **25** | 5 | 25 of 33 |
| thr ck1 | 71 | **27** | 4 | 24 of 33 |
| thr ck2 | 71 | **20** | 3 | 21 of 33 |
| sampled gate s0 | 68 | **29** | 5 | 24 of 33 |
| random p 0.13 | 3 | 3 | 2 | 2 of 33 |
**27-38% of S1's wins already end with a SILENT opponent** -- the ghost's script ran out (its real match ended) and the
engine kept playing. This is the ghost-specific exploit channel, and it exists BEFORE any RL: a policy rewarded only
for winning can learn to survive longer rather than play better. (b) plausible, untested whether RL moves it.

### 4.2 Guards (b)
1. **Outlived-the-script share**: per update and per held-out eval, share of wins with terminal tick > last ghost
   command tick + 200. Window A measures the init's value on the live rule. STOP if the train-batch EMA exceeds the
   init's by 15 pp; the held-out verdict reports winrate BOTH over all matches and over matches decided before the
   script ended (PASS requires the gain in the second as well). No reward change (owner: win/loss only) -- the
   censoring option (outcome after script end -> reward 0) is parked, not used.
2. **Passive-opponent wins (FirstLight_CR trap, §5cs.95 B: 296 of 306 wins vs <= 3-card opponents)**: wins bucketed by
   ghost plays DELIVERED (<= 10 / 11-30 / > 30) and by distinct ghost cards delivered (<= 3 / 4-6 / > 6). STOP if the
   <= 10-delivered bucket's share of wins rises > 10 pp over the init's.
3. **Ghost refusal drift**: ghost refused + undelivered per match (engine_env.py:387-392 counters). A policy that makes
   the ghost's recorded plays illegal (e.g. occupying its placement tiles) is exploiting the replay, not the game. STOP
   if the per-match ghost refusal rate doubles vs the init's.
4. **Match-length drift**: mean seconds of WON matches vs init (204 s at tau 0.5, §5cs.66) -- flag at +20 s.
5. **Per-ghost flips on held-out**: every screen/final lists entries init-win -> candidate-loss and the reverse; a
   gain carried by a handful of entries (e.g. > 50% of net flips from ghosts with <= 10 delivered plays) is reported as
   exploit-shaped. Train entries are visited once, so per-ghost drift is only observable on the held-out screens --
   that is intended.
6. **Train vs held-out divergence**: train EMA winrate up >= 10 pp while the held-out screen is flat -> not a stop,
   written into the report as the first sign of pool-fitting.

## 5. Resources on this box

### 5.1 Box (a, read this loop)
31.4 GB RAM, 16 logical CPUs, RTX 5050 Laptop 8 GB, torch 2.11.0+cu128 with CUDA, C: 407 GB free. AVD
`royale_worker_api31` 4 vCPU / 4 GB (feasibility Q1); qemu "still 4.1 GB" with the VM up (HANDOFF l.2714). Two engine
slots only: direct doors 38031/38032 (ports 37031/37032 are the adb doors to the SAME engines, §5cs.66 C).

### 5.2 Process layout (b)
- `supervisor` (PowerShell, `scratchpad/gauntlet/L67/e1/run_e1.ps1`): preflight, launches 3 python processes with
  `Start-Process` recording PIDs to `e1_pids.json`, watches `slot<k>_down.json`, restarts services and actors.
- `actor0` -> 38031, `actor1` -> 38032: CPU torch (`torch.set_num_threads(2)`), a `RawEngineEnv` (pool v1 subclass),
  the current policy; loop: claim a task file (atomic rename) -> play -> write shard `.npz` -> next. Estimated RSS
  1.5-2.5 GB each ((b): the old CNN trainers were ~2 GB WS / ~3 GB private incl. the SimMatchEnv that EngineMatchEnv
  still builds, §5cs.44 C) -- measured in the smoke.
- `learner`: GPU; writes task files for version v, waits for 32 shards, updates, writes `e1_latest.pt` (version v+1),
  runs pro-agreement evals and screens (as eval tasks for the actors). Estimated 2-3 GB host, 1-3 GB VRAM at bs 256.
- Budget: ~4 GB VM + 2 x 2.5 + 3 ~= 12 GB of 31.4. The owner's live bot/detector must NOT run (the CUDA error "under
  two trainers + the detector on one 8 GB GPU", HANDOFF l.3129; and engine RL "cannot share the box with live play",
  feasibility Q7).
- Synchronous batches (on-policy, ratio 1 at epoch 0). Slots idle during the ~40 s update: ~11% throughput loss,
  accepted for exactness.

### 5.3 Expected matches (b, from the measured 21 s/match per slot, section 1.6)
One batch = 32 x 21 / 2 = 336 s + ~40 s update ~= 376 s. Night plan (window B, 8 h):
| block | matches | time |
|---|---|---|
| preflight (boot, liveness via the caller's own path, sha asserts) | -- | 10 min |
| training, ~45 updates | ~1,440 | ~4 h 42 min |
| 3 held-out screens (60 entries each, paired with window A) | 180 | ~32 min |
| final held-out, final checkpoint, 293 entries x seed k=0 | 293 | ~51 min |
| final held-out seed k=1 for final AND init (paired, 2nd seed) | 586 | ~1 h 43 min |
| margin (restarts, the ~73 s service reboots) | -- | ~0 -- tight |
Window A (before the night, ~1.5-2 h of free box): smoke (6) ~20 min; T calibration 2 x 40 entries ~15 min; init
held-out 293 x seed k=0 on the live rule ~51 min; no-plays control + rate-matched random on the 60-entry screen
subset ~10 min. If window B loses time, the seed k=1 block is dropped first (then the verdict rests on one seed and is
labelled a screen). Totals: ~1,440 RL matches + ~1,650 eval matches across A+B.
Disk: shards ~300-500 KB compressed per match -> ~0.7 GB for the night, kept under `icebow/data/bench/e1_20260912/shards/`.

### 5.4 Paths and backups (b; git-ignore status (a))
- Everything heavy under **`icebow/data/bench/e1_20260912/`** (new directory; `icebow/.gitignore:4` ignores `data/`, so
  none of it can be staged -- same place engA/engB wrote, 14 files there now): `init_s1_icebow_v6lat_s0.pt` (copy),
  `e1_u0000.pt` ..., `e1_latest.pt`, `e1_crash_*.pt`, `shards/`, `tasks/`, `ref_eval/`.
- Logs/reports (small, committable, no secrets) under **`scratchpad/gauntlet/L67/e1/`** (tracked -- not ignored).
- Guards copied from engine_ppo.py:109-122: the learner asserts the output dir did not exist or is empty, refuses any
  output path under `icebow/data/pipeline/` and any path equal to the init, refuses an existing log.
- Backup before launch: sha256 of `icebow/data/pipeline/s1_icebow_v6lat_s0.pt` recorded in the config header; copy to
  the run dir; the learner loads the COPY and asserts its sha equals the original's; the original is never opened for
  write. Record the pool v1 + split sha256. Snapshot `L62/deal_cache.json` (v0 fallback only -- two actors closing
  `EngineMatchEnv` both rewrite that one file, engine_env.py:261-263; v1 does not use it: `deal_cache=False`).

### 5.5 Engine failures, restarts, kills (a traps -> (b) policy)
- **Services are booted ONLY by the supervisor, BEFORE the python processes**, with the existing
  `scratchpad/gauntlet/L63/s0/_boot.ps1` (dot-sources `runtime.env.ps1` -- names only, never print it -- then up to 6
  attempts of `native_core.worker start --workers 2 --base-port 37031`). E1 python never calls `worker start`.
  Reason: the DataTables pump segfaults ~1 in 10 boots (HANDOFF l.1261) -> the retry loop; tree-killing a trainer
  "takes the engine service down" (HANDOFF l.1956-1960) -> services must not be in any trainer's process tree.
- Liveness = the caller's own path: `RawEngineEnv(port).reset(entry0)` on 38031 and 38032 (trap: a probe that calls
  `observe()` with no battle reported a false death, HANDOFF l.1966-1969). Services dead after idle need the ~73 s
  reboot (HANDOFF l.2335).
- Mid-run failure: `NativeHostError` / socket error / 120 s timeout in an actor -> the actor writes
  `slot<k>_down.json` (task id, exception text) and exits 3. Supervisor: `native_core.worker status --workers 2`; if
  that slot's service is false -> `_boot.ps1`; relaunch the actor; the task is re-queued (reward is terminal, so a
  half-played match is simply discarded, never counted). Cap: 6 restarts per slot per night; beyond it the slot is
  retired and the learner continues on one slot (batches take twice as long); both retired -> learner saves, stops.
- Hangs: only the direct doors are used; nothing else may connect to 37031/37032 during the run ("a client on 38031
  while 37031 is busy hangs 120 s", §5cs.66 C) -- no viewer, no `engine_play`, no probe.
- Artifacts: "the worker pool redeploys artifacts by hash on service start" (HANDOFF l.1859-1860) -- nothing under
  `research/ext/cr-native-sandbox/artifacts/` may change during E1.
- **Stopping**: write `icebow/data/bench/e1_20260912/STOP`; the learner saves `e1_latest` + `e1_u<NNNN>`, stops issuing
  tasks; actors exit after their current match. Hard stop only by exact PID from `e1_pids.json`, `taskkill /PID <pid> /F`
  WITHOUT `/T` (actors and learner have no child processes); never `/T` on the supervisor while a `_boot.ps1` child may
  be running. Never launch through a bash wrapper (`TaskStop` on a background bash killed only the wrapper; the python
  child survived and advanced, HANDOFF l.3970) and never rely on a tool timeout to end a child ("A BASH-TOOL TIMEOUT
  DOES NOT KILL THE CHILD", HANDOFF l.1263). After any kill: verify python process count and `worker status`
  `services [true, true]`. End of night: `worker stop --workers 2 --stop-vm` ("stop KEEPS the VM by default", l.2714).

## 6. Smoke test (window A, ~20 min of box; offline part first)

### 6.1 Offline, no engine (`python -m unittest pipeline.tests.test_e1`)
1. `live_view`: on a fixed engine BoardState, unit tokens have hp_known = 1 with hp 1.0, alive king hp 1.0, opp_known 0,
   no side -1 on a class outside `mine_classes(icebow)`; same seed -> identical tokens; different seed -> different.
2. Log-prob parity: actor-side behaviour log-prob == learner recompute from the stored tensors, |d| < 1e-4, over 200
   stored decisions; with `eval()` mode ratio == 1 +- 1e-5.
3. KL(pi || pi_ref) == 0 (< 1e-7) for every head at update 0; one synthetic update with lr 1e-5 gives 0 < KL < 1e-2.
4. Checkpoint round trip: save `e1_u0000.pt` -> reload in a fresh model -> identical logits on 100 decisions;
   `eval_s1` on `e1_u0000.pt` reproduces the init exactly (v3 VAL 20.97 / 65.46 / .766; degraded 16.10 / 48.18).
5. Output guards: refusing to write into `icebow/data/pipeline/`, into an existing run dir, or over an existing `.pt`.
6. Split: held-out 293 / train 1,505 / dropped 12 reproduced from the frozen split file; no held-out tag in any task.
7. Anti-stall and affordability mask match `student_live` on constructed states (same inputs -> same action).

### 6.2 Pool v1 parity (engine, ~5 min)
20 held-out entries: drive the corpus's OWN our-side commands through the v1 env as if they were the policy; require
`final.state_hash` equal to the corpus record in >= 19/20 (determinism 211/211, §5cs.59). Fail -> fall back to v0.

### 6.3 Engine smoke (both slots, ~15 min)
- 20 matches per slot = 40 matches = 10 RL-train entries x G 4: the first 32 feed one update (version 0), the last 8
  must be played by version 1 (checks the reload), at the chosen T.
- Assert every decision's `BoardState.source == "degraded"` (count logged == decisions) and live_view rules applied.
- All log-probs and p_gate finite; KL == 0 before the first update, 0 < KL_cell < 0.05 after it; beta moves as specified.
- One full update runs on GPU; peak VRAM and update seconds logged; `e1_latest.pt` written; actors pick up version 1
  for the next task (policy version recorded in the shard).
- Crash path: `taskkill /PID <actor1> /F` (no /T) mid-match -> supervisor relaunches, task re-queued, `worker status`
  still `[true, true]`, no duplicate shard. STOP file -> clean exit of all three within one match.
- Held-out eval on 10 entries across both slots, greedy live rule, seed k=0; the paired scorer runs on it.
- Readouts to record for window B: s/match per slot with learner present, RSS per process, share of mixed-outcome
  groups, discordance between two degrade seeds on the same 10 entries, plays/min sampled vs greedy.
PASS = all asserts hold and s/match <= 25 s per slot; otherwise fix before any night.

## 7. Files to create / modify, build time, open questions

### 7.1 Files (b)
New (none modify an existing live-path file):
- `pipeline/e1_view.py` -- `live_view(bs, rng, deck)`.
- `pipeline/e1_policy.py` -- tempered behaviour distributions, masks, log-prob, KL, entropy (ONE implementation
  imported by actor, learner and tests).
- `pipeline/e1_pool.py` -- corpus v6 -> `icebow/data/ghost_pool/pool_env_v1.jsonl` + `pool_env_v1_split.json`
  (split rule 2.2, last ghost tick, ghost delivered counts, opponent group, s1 split), and `PoolV1Env(RawEngineEnv)`
  whose `_resolve_decks` returns the corpus `final_decks` order (no probe reset, `deal_cache=False`).
- `pipeline/e1_actor.py` -- slot loop reusing `engine_play.compact_raw / from_engine / to_tokens / _past /
  cell_to_engine / _outcome`; train tasks (behaviour sampling) and eval tasks (greedy live rule).
- `pipeline/e1_learner.py` -- task scheduler, PPO + KL update, adaptive beta, monitors, stop rules, checkpoints,
  pro-agreement hook (calls `train_s1.evaluate`).
- `pipeline/e1_score.py` -- paired held-out scorer: entry-clustered bootstrap, McNemar, per-slot split, exploit
  buckets (4.2), pre-registered verdict (2.3).
- `pipeline/tests/test_e1.py` -- 6.1.
- `scratchpad/gauntlet/L67/e1/run_e1.ps1` (supervisor), `e1_preflight.py`, `window_a.ps1`, `README` section in this doc.
Modified: none required. (`engine_env.py` stays frozen; the v0 fallback needs only `deal_cache=False` per actor
plus a pre-warmed cache via the existing `L62/prewarm_deal_cache.py`.)
HANDOFF/memory updates at commit time per the standing rule (not part of this read-only design).

### 7.2 Build estimate (b)
pool v1 + split + parity harness 2.5 h; view + policy math + tests 2 h; actor 2 h; learner (update, beta, monitors,
stops, checkpoints) 3.5 h; scorer 1.5 h; supervisor / preflight / stop 1.5 h; smoke + fixes 2 h -> **~15 h of agent
work (two sessions)**, then window A (~1.5-2 h box), then window B (8 h box).

### 7.3 Decisions taken on the owner's behalf -- flagged, none blocking (b)
1. Obs = `live_view` (degrade + live's fill + mine_classes rule), not bare `degrade()` -- because the stated intent is
   "trains on what LIVE sees", and live fills (section 0.2). Bare degrade is a one-flag switch if the owner prefers.
2. Eval rule = the live rule (tau 0.27, anti-stall, affordability mask), not §5cs.66's tau 0.5.
3. Pool v1 (293 held-out) instead of v0 (73 usable held-out), conditional on the 19/20 state-hash parity.
4. No table gate prior (3.4); per-board KL on all three heads + a plays/min stop rule instead.
5. Ghost-exhaustion wins monitored + stop rule, no reward censoring (4.2.1).

### 7.4 What to expect, stated before the run
- (a) The closest prior experiment -- engB, leashed, 609 matches, reward DENSER than win/loss -- moved pro agreement
  nowhere and did not measurably win more (§5cs.51 A). E1 changes the model (S1, never RL'd), the obs (live_view),
  the baseline (group) and the leash (all heads, adaptive); its reward is sparser. (b) The most likely single outcome at
  ~1,440 RL matches (~45 updates, of which only mixed-outcome groups carry gradient) is a null within the ~5-6 pp MDE.
  A null is a result; the pre-registered verdict (2.3) keeps it from being read as either a win or a failure of RL.
- (b) If the degraded-VAL agreement rises while the held-out winrate does not, the RL bought what supervised v6aug
  already bought (+3.10 cell / +11.1 card degraded, HANDOFF l.3121-3127) -- report it as that, not as RL learning to win.

STATUS: complete

