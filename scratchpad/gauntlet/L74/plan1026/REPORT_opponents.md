# OPPONENT pillar: a plan for human-like, deck-conditioned opponents that are measured against humans

## 0. Decisions

1. **Stop building strength with win-only RL against icebow.** Every family so far has traded style for strength (O2b 0.65 style at CLX 83.8%; I u40 at CLX 48.8% but style 0.78). The audit names three causes, all fixable:
   - **The imitation data is bad.** O2 was trained on public-elixir inputs, sightings that are 24% late, invisible spells and a 4-play warm-up gap.
   - **The timing target is ill-posed.** `pipeline/dataset.py` samples wait rows every 40 ticks with a 20-tick play window. The gate learns a stride artefact, which is why it stayed flat at bal-acc 0.685 and why "decide 40" turned out to be the most human cadence.
   - **Every RL partner was icebow.**
2. **The data is the HF corpus re-run through the faithful engine.** That is 252k replays and 17.8M actions. My scan of 4 of the 52 parquet files: 86% Path of Legend, 88% of sides at level 16, 11% at level 11, evolutions in 23% of deck slots, heroes in 10%. So the data is current. Re-running gives exact own state (hand, elixir) for both seats, which removes every O1/O2 data defect. Live logs become the human-vs-our-bot fine-tune and the evaluation target, not the main corpus.
3. **One network, not per-deck models.** It is conditioned on the deck, the population (band), the mode and the match memory. It gets a proper timing head (a per-slot play probability plus the exact tick inside the slot) that replaces the gate, and an ability-press head. Per-deck fine-tunes are used only as an upper-bound yardstick.
4. **Calibrate strength in an order that costs no style first:**
   - (a) choose the band token;
   - (b) lower the card / cell temperature, leaving the timing head untouched;
   - (c) only then, RL with a **fixed** pull toward the imitation policy (KL penalty) and **frozen timing / ability heads**. Freezing timing blocks the measured "RL answers faster" drift: react 4.72 s vs human 5.98 s, plays per minute in double elixir 11.36 vs 8.33 (DIAG_12).
5. **"99.9% human-like" is a coverage number.** It is the share of the live opponents the bot meets that are modelled by a cell (a head deck, or else its archetype, per trophy band) that passes four levels of tests. "Pass" means *proven* equivalent to humans (an equivalence test), with margins set at the measured difference between two human populations (12k vs 13k humans = 0.10). A small sample therefore fails a cell; it cannot pass one. Section 4 explains why the literal reading cannot be checked.
6. **Attribution rule, set up front.** If levels A–C pass and D (outcome parity) fails, the remaining gap belongs to the engine or to the bot's live execution, not the opponent. The audit already shows this split matters: the bot's lost and slow live taps explain about half of the overtime gap (win | OT -5.2 of 10.3 pp, DIAG_12 §10). The live-tap handicap (`--tap-loss/--tap-slow`, decision G2) is on in every calibration and evaluation run.

## 1. Data: turning HF, pro and live logs into per-deck, per-skill state-action rows

### 1.1 Sources and their roles

| source | role | facts |
|---|---|---|
| HF IL_Replay (`L67/hf/replays`, 52 parquet files) | prior, deck coverage | Exact 20 Hz command ticks, positions, forms, per-card levels, ability events (3.4 per replay), final tower HP, crowns, elixir leaked and elixir by card type. No player tags, trophies or dates: `requested_player_tag` is empty in every row. |
| pro corpus (14,661) and PRO2 (1,069) | prior, deduplicated against HF | Today driven at level 11 on an old native build. Re-drive them at true levels. |
| live logs (about 3,100 matches; 51,285 opponent plays at >= 12k) | target population (humans vs our bot); trophy bands | Exact tower-fall timeline; 2-tick frames since 10-15; opponent hand inference 99.4% exact where it can be determined. |
| census (`L74/mix/LIVE_POOL.md`) | deck weights per band | 1,919 opponents. Only **829 (43%)** have a seen-card set that maps exactly to a deck in the HF library. The top deck is 1.7% of opponents. Most live mass is long tail, so archetype cells carry most of the 99.9% weight. |

### 1.2 Re-driving and validity (stage 1, the day the engine pillar's replay milestone lands)
- Extend `tools/hf_to_crawl.py` with an `--all-decks` mode that passes through levels, forms and final tower HP.
- Drive both command streams through the engine pillar's driver (`research/sandbox_tools/replay_drive.py`) at the replay's real card and tower levels.
- **Tier A (full match)** requires all of:
  - at least 99% of commands accepted;
  - the same crowns as recorded;
  - every final tower HP within 5% of its max;
  - each side's elixir leaked within 0.5.
- **Tier B (prefix only):** truncate at the first divergence (a rejected command, or tower HP off by more than 5%) and keep the prefix.
- Report the yield per archetype and per era. The era is inferred from card and hero availability, since there are no dates.

### 1.3 Live re-drive (gives the human-vs-bot data an exact opponent state)
- **Opponent commands:**
  - tick = first-sighting tick minus the detector lag, measured on our own seat (the SIM's detector: 95.6% of plays detected, median lag 4 ticks; LEDGER);
  - spells placed at the projectile target (the O1b relabel);
  - spells taken from the 2-tick frames.
- **Deck:** the seen cards, completed by P(deck | seen) from the 52,566-deck HF library.
- **Levels:** from tower max HP (4424 / 4858 = level 15 / 16).
- **Validity:** the re-drive must reproduce the logged tower timeline and the logged body positions.
- **Tags:** band (live L = 12.0–12.9k, M = 13k+, R = Ranked), our Mark, our tower level.
- **Splits are strictly by time.** Everything up to a fixed cutoff date is train; the next slice is the **calibration block**; every match after the freeze date is the **sealed block**, never used for training or tuning.

### 1.4 Rows (`pipeline/dataset_gen.py`)
- **Decision slots:** every 10 ticks per seat, the bot's own cadence.
- **Label per slot:** play or no play, the tick inside the slot (exact from the 20 Hz data), card, cell, ability press.
- **Volume:** keep every play slot and 1/8 of wait slots, weighted ×8, so the timing likelihood stays exact. That is about 504k sides × (~35 play + ~150 wait) ≈ **100M rows**. Build them from per-match traces, as `dataset_gen memory` already does for memory tables.
- **Context tokens:**
  - deck id, for decks with >= 50 training sides;
  - archetype (`clx_ranked/anatomy` win condition, grouped into the 10 cells of §4);
  - source / band: `hf_pol`, `hf_other`, `pro`, `live_L`, `live_M`, `live_R`;
  - mode;
  - era.
- **Splits:**
  - HF: random within each deck, 90/5/5, after deduplicating on the timeline key `hf_to_crawl` already uses;
  - live: by time, as above.
- **Self-check before any training**, with O1's pre-registered 99% bar: the same builder on OUR seat must reproduce the live decision inputs on at least 99% of fields.

## 2. Model: one deck- and band-conditioned GenModel (`pipeline/model_gen.py`)

**Inputs**
- Today's fv5/fv6 observation: exact for its own side, public-only for the other side (as `dataset_gen` already does).
- A **deck encoder**: a 2-layer set transformer over the 8 cards (card, form and level embeddings), plus a deck-id embedding with 20% id-dropout so unseen decks fall back to the card-set embedding.
- Band, mode and era tokens.
- **Match memory v2 from the start**, trained jointly with the rest. It is not a zero-initialised adapter, so the constant-offset bug that killed the S3 memory adapters cannot recur; keep `zero_empty` anyway.

**Heads**

| head | definition |
|---|---|
| **timing (replaces the gate)** | h_s = P(play in slot s) plus a categorical over the 10 ticks inside the slot. Trained as a discrete-time survival model, so its likelihood is exact. |
| card | the existing pointer over the hand, masked to cards affordable by the play tick |
| cell | the existing cell head plus CellRefine |
| ability | the same slot structure as timing, per controllable hero / champion (labels: HF `activate_ability`) |
| value | kept, to start the critic for the RL step in §3 |

**Decoding in the SIM**
- Decide every 10 ticks, draw Bernoulli(h_s), then sample the tick inside the slot.
- T = 1 on every head by default.
- The `decide_every`, `reaction_ticks` and `tau` knobs are retired for these opponents.
- The existing `gate_decode='hazard'` (`decision_options.gate_rate`) is a workaround that converts a stride-sampled gate into a rate. The new timing head replaces it.

**Not in v1: a per-player style latent z.** Conditioning on the opponent's own past plays and on memory gives a persona within each match. Add an 8-d, KL-bottlenecked z only if the between-match spread test B3 (§4) fails.

**Size:** compare d 128 / 4 layers with d 192 / 6 layers on level A. Take the smallest within 0.01 nats per action; SIM inference cost matters for the bot's RL throughput.

## 3. Training

1. **Pretrain on HF + pro + PRO2.**
   - Loss: timing + card + cell + ability.
   - `--deck-weighting sqrt` (already in train_gen) and source weights via `--row-weights`.
   - 2 seeds; early stop on held-out NLL per deck.
2. **Live fine-tune (how humans play against our bot).**
   - Validated live rows with band tokens, plus a 20% HF replay share to avoid forgetting.
   - lr 1e-5 to 3e-5; stop on the time-ordered holdout.
3. **Deck-specificity check, a yardstick only.**
   - Per-deck fine-tunes for the top 20 live decks and per-archetype fine-tunes for the 10 archetypes.
   - If the conditioned model is within 0.03 nats per action of each, ship one network.
   - Otherwise add 10 per-archetype LoRA adapters, never about 1,000 deck models.
4. **Strength calibration per band.** Stop at the first step that passes the level-D checks on the calibration block while A–C still pass:
   1. **Band token** (`live_L`, `live_M`, `live_R`, `hf_pol`). This costs no style.
   2. **Card / cell temperature** in {1, 0.7, 0.5}; the timing head stays at T = 1.
   3. **RL with a fixed pull toward the imitation policy** (the "piKL" method from the human-like-search literature):
      - `rl_royale` with the opponent-to-be as the learner;
      - a **fixed** λ in {0.3, 1, 3}, not an adaptive KL target (the W7/W14 leash never bound);
      - **timing and ability heads frozen**;
      - partners: 60% the bot pool over every deck the bot plays (icebow, hogeq, bait, …) with `league_opp_live`, and 40% the human model against itself on census-drawn deck pairs;
      - win-only reward;
      - stop at the first snapshot where D passes on the calibration block and B still passes.
      - If no λ reaches the band's strength with B passing, ship the human-like model and report the remaining strength gap. Do not ship a non-human opponent.
   4. **Not used:** OT-state starts, tank-deck ×3 practice, CLX-only mixes, decide-60/80. These patched a model that had no real timing.
5. **The bot always plays with its measured live handicap (G2)**, in calibration and evaluation, so the opponent is never tuned to absorb the bot's lost taps.

## 4. How "99.9% human-like" is measured

**Why not the literal reading.** Read literally, "a judge cannot tell bot from human more than 50.05% of the time" needs about (1.96 × 0.5 / 0.0005)² ≈ 3.8M matches per class to verify. That is not a usable target.

**The definition.**

**H = Σ_c w_c · pass_c**
- c = a cell: a head deck (at least 200 held-out HF sides and present in the live census), else its archetype, for each band.
- w_c = the cell's share of that band's live opponents (from the census).
- pass_c = the cell passes levels A, B and C, and D where the live sample is large enough.
- **Target: H >= 0.999**, i.e. effectively every cell the bot meets live passes. One failing Hog cell (about 18% of opponents) gives H ≈ 0.82.

Report H_ABC (checkable in simulation, with HF-sized samples) and H_D (checkable live, at archetype resolution) separately. Every pass is an equivalence test (TOST, 90% CI inside the margin), so a cell with too little data fails.

**Cells (10 archetypes):** Hog/cycle, Siege (X-Bow/Mortar), Log Bait, Heavy beatdown (Golem/Lava/E-Golem), Light beatdown (Giant/RG/E-Giant/Goblin Giant), PEKKA/MK bridge, Bridge spam (Royal Hogs/Ram/Bandit), Air (Balloon), Control (Graveyard/Miner/Drill), Other. Each is crossed with 3 bands. Head decks are added as their own cells.

| level | metric | threshold | reference today |
|---|---|---|---|
| **A: per decision**, held-out HF + live calibration block | card / cell top-1 agreement in matched states | at least the human-human ceiling, measured on matched states with `L67/agreement_ceiling.py`'s method | ceiling: 43.7% card, 27.5% exact cell (pro pairs at board distance < 0.25) |
| | NLL per action (card + cell + timing + ability) | at most per-deck / archetype fine-tune NLL + 0.03 nats | O2b: cell NLL 3.05, card 0.531 |
| | probability calibration (ECE) | card and top-cell <= 1.0 pp; timing per slot <= 0.5 pp | – |
| | timing, time-rescaling test | rescaled gaps between plays ~ Exp(1): KS D <= 0.02 per archetype (n >= 5k gaps) | gate bal-acc flat at 0.685 |
| | ability press timing | KS <= 0.05 per hero (n >= 2k) | – |
| | memory is actually used | late-match NLL (t > 120 s) with the real memory beats a memory taken from another match by more than the seed gap | – |
| **B: closed-loop behaviour** | B-HF: model vs model on HF deck pairs and levels (>= 2,000 games per archetype) against re-driven humans | every stat TOST \|d\| < 0.10 per archetype | – |
| | B-live: model vs the deployed Mark (G2 on) against live humans vs the same Mark, same detector on both sides | every stat \|d\| < 0.20 globally; RMS d over all stats <= 0.10 | RMS d: E4 0.93, gen_v32 0.77–0.79, O2b 0.65, I u40 0.78, B u20 0.53; human floor 0.05; 12k vs 13k humans 0.10 |
| | B3: between-match spread | per-match SD ratio (model / human) in [0.9, 1.1] for the tempo stats | – |
| **C: match-level discriminator** | fresh 2-layer transformer per evaluation over one side's event stream plus the other side's visible events, deck-conditioned; separate human matches from model matches, the same split as B-HF and B-live | held-out AUC upper CI <= 0.55 overall and <= 0.58 per archetype, and <= AUC(12k vs 13k humans) + 0.03 | – (n = 5,000 per class gives AUC SE ≈ 0.006) |
| **D: outcome parity**, sealed live block, n >= 1,500 matches at one Mark and one level config | D1, per-match prediction: before the block is played, P̂ = 64 SIM games per live match, with the deployed checkpoint, G2 on, live levels, and the opponent's completed deck and band | \|mean P̂ − live win rate\| inside ±4 pp (TOST); recalibration slope CI includes 1, point in [0.8, 1.25]; residual within ±8 pp for each archetype with live n >= 150; P̂ AUC at least that of a deck-only baseline | CLXIII: SIM 72.6% (E4) / 58.8% (cal) vs live 47.8%, residual +24.8 / +11.0 pp; Mortar 28.8% vs 66.8% |
| | D2: crown-state cells | all 12 items of the O4 gate v2 battery (11 cells + style, `w18/o4_gate.py`) | I u40 10/12 on recent-100 under G2; live 1-0-down 29.4% vs SIM 13.6–21.6% |
| | D3: does a SIM gain transfer live? (accumulates with each live A/B) | slope CI includes 1 and excludes 0 after 3 or more A/Bs | 0.38 [-0.30, +1.06] today |

**B stats (about 30):**
- tempo: plays per minute in 1x / 2x / OT, first play, gap between plays (p10 / p50 / p90), time to answer our play, share answered within 3 s, elixir at play, leak per minute, push elixir per 8 s (mean and max);
- placement: lane, split, bridge / own-half / our-half shares, pocket share after a princess falls, depth by card class;
- cards: per-card usage, spell share, play-to-play bigrams, P(answer card | incoming card class);
- adaptation: lane switch after losing a princess, same answer to a repeated threat, play rate at 0-2;
- abilities: press delay after deploy.

**Signature stats per archetype** (part of B; this is what "deck-specific playstyle" means in a measurable way):

| archetype | signature stats |
|---|---|
| Siege | placement row, defensive vs offensive X-Bow share, lock rate by crown state |
| Bait | barrel timing after our Log, punish within 6 s |
| Beatdown | elixir at tank drop, tank-at-back share, push size |
| Hog / cycle | cycle speed, Hog timing after a defence |
| Bridge spam | punish rate when we are low on elixir |
| Control | Graveyard / Miner targets and spell pairing |

**What the sample sizes can resolve.** Per-deck outcome parity cannot be tested live: about 2 matches per deck. D1's per-match P̂ pools decks while keeping them distinct. The 1,500-match sealed block resolves about ±2 pp overall and about ±8 pp per archetype; that resolution is stated, not hidden.

**Thresholds are pre-registered.** Write `THRESHOLDS.json` and log its sha before any model is trained. Discriminators are retrained fresh every time. The sealed block is never touched.

## 5. Files and modules (fewest new files)

**Edits**
- `C:\Users\benpe\ClashBot\tools\hf_to_crawl.py`: `--all-decks`; pass through levels, forms and final tower HP.
- `C:\Users\benpe\ClashBot\research\sandbox_tools\replay_drive.py` (or the engine pillar's driver): validity fields (crowns, final HP, leak, first divergence).
- `C:\Users\benpe\ClashBot\pipeline\dataset_gen.py`: `--slot 10 --wait-keep 0.125`, the context tokens, memory tables in the same pass.
- `C:\Users\benpe\ClashBot\pipeline\model_gen.py`: `TimingHead`, `DeckEncoder`, context embeddings, `AbilityTiming`. All load by checkpoint content, like the existing CellRefine / memory.
- `C:\Users\benpe\ClashBot\pipeline\train_gen.py`: timing / ability losses, validation metrics per deck and archetype.
- `C:\Users\benpe\ClashBot\pipeline\decision_options.py` and `C:\Users\benpe\ClashBot\pipeline\e1_eval.py`: `gate_decode='timing_head'` with tick sampling inside the slot.
- `C:\Users\benpe\ClashBot\pipeline\rl_royale.py`:
  - `league_exploiters` entries accept `band`;
  - new keys `kl_ref_fixed: λ` and `freeze_heads: [timing, ability]`;
  - absent keys = identical config hash (the same rule as the O6 / W7 keys).

**New**
- `C:\Users\benpe\ClashBot\pipeline\human_traces.py`: one entry point that turns hf / pro / pro2 / live sources into validated engine traces plus metadata. The live adapter is moved from `L74\opp_model\o1_records.py`.
- `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\opp_model\humanlike\scorecard.py`: levels A–D and H. It reuses `human\opp_behaviour.py` (FEATS extended), `w18\o4_gate.py` and `push_cal\push_cal.py`.
- `...\humanlike\disc.py`: the level-C discriminator.
- `...\humanlike\predict_live.py`: sealed-block P̂ per match, written and hashed before the block is played.
- Tests: `pipeline\tests\test_timing_head.py` (the likelihood is exact; T = 1 sampling reproduces the label rate on synthetic data) and `test_human_traces.py` (re-drive of a known replay reproduces its crowns and final HP; the observation of the other side is public-only).

## 6. Risks and timeline

**Risks**

| risk | detection / mitigation |
|---|---|
| Low re-drive yield (balance patches, missing levels, heroes) | Yield report per era; train on tier B prefixes. If tier A is below 30%, pretrain on prefixes only and lean harder on the live fine-tune. |
| HF players (top Path of Legend, human vs human) differ from our opponents (12–14k / Ranked, human vs bot) | Live fine-tune with band tokens; B-live and C-live catch it. |
| Imitation still too weak in closed loop (compounding errors) | Step 3 of the calibration order. Guard: frozen timing, fixed λ, stop rule. |
| RL drifts the style again | Abort the band at B fail. Report rather than ship. |
| Live sample size limits | Per-match calibration; resolution stated; blocks of at least 1,500 matches. |
| Confounds in D: one tower level was worth +15.8 pp live (O0); bot handicap; a Mark change mid-block | Block fixed to one Mark and one level config; G2 re-measured per Mark. |
| SIM throughput with a larger opponent network | Decide every 10 ticks; d <= 192 or distil. |
| Hidden-information leak in the SIM | Test that the opponent's observation of the bot is public-only. |
| Meta drift | Re-weight by the latest census each week; era tokens. |

**Timeline in working days.** Day 0 is the engine pillar's "human replays are faithful" milestone.

| when | work |
|---|---|
| −6 to −4 | Scorecard levels A, B, D on existing data; baseline E4, gen_v32_s0, O2b, I u40, D1 u60, B u20; pre-register thresholds. |
| −4 to −2 | `disc.py`, `predict_live.py`, sealed-block protocol. |
| −3 to 0 (parallel) | Timing head, deck encoder and tokens with tests; early signal by re-rowing the existing pro recordings (they have 10-tick frames) with slots and checking the timing metric; `hf_to_crawl --all-decks`; live command extractor. |
| 1–3 | Re-drive HF, pro, PRO2 and live; validity and yield report (about 0.5–1 pod-day of compute). |
| 3–5 | Rows, memory tables, splits, the 99% self-check. |
| 5–9 | Pretrain, 2 seeds on 2 GPUs; per-deck yardsticks; level A. |
| 9–10 | Live fine-tune; level A on the calibration block. |
| 10–12 | SIM decode wiring, league smoke; levels B and C. |
| 12–16 | 1–2 fix rounds (memory, z if B3 fails, capacity). |
| 16–23 | Strength calibration, 3 bands in parallel pods. |
| 23–24 | Freeze; publish sealed predictions; **hand the opponents to the bot pillar** (usable for training, flagged D-unverified). |
| 24–35 | Sealed live block (>= 1,500 matches at roughly 130–250 per day) and the D verdict. |

**Total:** about 30 days to usable calibrated opponents and about 41 days to an outcome-parity verdict. With a 30% buffer: **about 6 weeks to usable, about 8 weeks to verified.**

What I left out: per-deck models (one conditioned network unless the yardstick fails by more than 0.03 nats) and the style latent z (added only if B3 fails).

### Critical Files for Implementation
- C:\Users\benpe\ClashBot\pipeline\model_gen.py
- C:\Users\benpe\ClashBot\pipeline\dataset_gen.py (with C:\Users\benpe\ClashBot\pipeline\dataset.py's wait-stride row rule)
- C:\Users\benpe\ClashBot\tools\hf_to_crawl.py
- C:\Users\benpe\ClashBot\pipeline\rl_royale.py
- C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\human\opp_behaviour.py (the base of the new scorecard, with C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\opp_model\w18\o4_gate.py)
