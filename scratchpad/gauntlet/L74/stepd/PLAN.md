# Step d plan: the imitation rebuild with cue fields, then RL, toward 14k and Ranked

Written 2026-10-18 ~09:45 EDT (planning + laptop data prep; nothing ran on a pod; nothing committed).
Grades: **(a)** measured, number and source given; **(b)** plausible but untested, with the test that settles it;
**(c)** contradicted, with the evidence.
Code built today: `scratchpad/gauntlet/L74/stepd/` (section 4). "CLIII" = ICEBOW Mark CLIII: LEVELS (live since 07:36).

---

## 0. The plan in one paragraph

Build the imitation dataset from the **same 3.52 M pro rows that trained `gen_v32_s0`**. The only change is that each
unit token also gets its 22 cue floats. Those cues come from a RoyaleSim re-drive of every replay, and they are attached
only where the SIM board still matches the recorded board. Train **IL-cue** with exactly the `gen_v32_s0` recipe, so
`gen_v32_s0` is its no-cue twin. Train one more no-cue seed to measure seed noise. Then run two RL arms on the same
**step-d environment** (fin13 engine, live Hero IW press, live levels, Hero IW form, the learned ability head if c3_ab
passes):
- **CTRL**: CLIII + 130 updates.
- **REB**: IL-cue + 130 updates, with a KL leash to CLIII that starts tight and is loosened in three stages.

A **LEAGUE** arm (CTRL + the Stage-2 opponents) follows on the first free pod. Live gets whichever arm beats CLIII with
the CI low above 0 on both the standard and the fresh seeds. The two doctrine habits are scored on every checkpoint.

### Four facts, measured today or this week, that shape the plan

1. **CLIII has cue inputs, but they do nothing** (a).
   - The cue-blind control of CXXXVIII scored -0.73 [-3.65, +2.08].
   - Zeroing the cues changed 1 of 538 decisions (HANDOFF 10-17 14:16).
   - So RL alone has not taught the model to use cues. Supervised imitation gives far more gradient per row, which is
     why the cues go into the imitation stage.
   - Tiny dry run: after ~100 tiny imitation steps (2 epochs on 16 replays) the cue layer's weight norm was already 0.139. CXXXVIII's is 0.18 after 130
     RL updates. This is a pipeline check, not a result.
2. **The pros already show the owner's two habits; our RL line does not** (a).
   - These are interim tables from the habits worker (`L74/habits/live_tables.out`, `pro_tables.out`,
     `push_elixir.out`, `first_cycle.out`). That worker is still running.
   - First bridge X-Bow:
     - Pros: median **58-63 s** into the match, 6th-7th play, after **5-6** opponent plays seen. 9-13% come in the
       first 2 plays.
     - CXXXVIII: 41.8 s, 4th play, after 3 opponent plays seen. 32% in the first 2 plays.
     - CLIII (n 17): 27.4 s, 2nd play. 41% in the first 2 plays.
   - Heavy pushes (>= 10 elixir of opponent troops played within 15 s):
     - Pros answer with a Rocket in **18-27%** of them.
     - CXXXVIII answers with a Rocket in **4.0-5.4%**.
     - When our own elixir is under 6, CXXXVIII answers with cheap cards only in 46% of them; pros do so in 24-29%.
   - **Consequence:** a fresh pro base is where these habits come from. A tight leash to CLIII pulls them back toward
     CLIII. That is why REB loosens the leash in stages and scores the habits at every stage (section f).
3. **A RoyaleSim re-drive does not reproduce whole pro matches** (a). Laptop, RoyaleSim 0.1.35, 18 driven replays:
   - Final crowns match the real match in **7/18** with RoyaleSim, against 14/18 for the native engine drive that built
     v32.
   - The board agreement score (body Dice; definition in section a) is >= 0.9 on 48-60% of frames.
   - Agreement starts near 0.95-1.0 and falls mid-match.
   - So cues can only be attached to rows whose boards still agree. That is **36-53% of rows** (play rows 30-44%).
   - This is the owner's divergence concern, now measured on pro data. The fin13 fork may diverge less (b); D1
     measures it on all 14,661 replays.
4. **The leash "to the previous best" has never bound** (a).
   - In every recent run beta (the leash weight) sits at its 0.03 floor from about update 10.
   - The KL (how far the policy has moved from its anchor) is 0.05-0.09 per head, below the 0.10 target. Sources:
     Stage 2 LEDGER s2_hog_il / s2_hog_e4, and the 10-07 diagnosis.
   - So for CTRL the leash is already "light", and loosening it changes nothing.
   - Staged loosening only matters in REB, where the start model differs from its anchor.

### Corrections to the brief

| Brief item | Status |
|---|---|
| "pipeline/gen_*.py" | (c) No such files. The imitation code is `dataset.py`, `dataset_gen.py`, `train_gen.py`, `model_gen.py`, `eval_gen.py`. |
| "opponent elixir + cycle tracking matter" | Already model inputs (a). `sc[5]` is the public elixir counter; `opp_cycle` holds the 8 seen cards with plays-since and age; `opp_past` holds the last 3 plays. Imitation, RL and live all compute them with the same `public_observation.PublicObserver`. Today's parity check shows the three agree (section 4). |
| "~2,700 live matches with frames" | (c) as stated. About 2,800 graded ladder matches exist (`habits/index.json`), but only ~640 logs carry frame events (since 10-15 17:02) and **295** carry decision-time cue blocks (since 10-17 13:29). |
| "icebow crawl 2,073 X-Bow replays" | Already inside v32: corpus_v6 icebow = 1,638 crawl2 + 603 HF = 2,241 replays. |
| Hero IW pro data | (a) Unusable for icebow imitation. Of the 164 Path-of-Legends battles, **157 contain Minion Giant**, which the catalog cannot map. Only **1** hero side is icebow-like and 5 contain an X-Bow. Its value stays the press-timing model that already exists. |
| HF corpus (252,238 replays) | Its icebow and pilot parts are already in v32. More foreign replays bought +0.11 pp exact cell against +0.7 predicted (09-07, §5cs.96), so they are not added in v1. |

---

## a. The imitation dataset

| Item | Choice | Why |
|---|---|---|
| Rows | `gen_dataset_v32_fv5.npz` unchanged: 3,517,863 rows (1,012,450 play / 2,505,413 wait), 14,661 replays from 6 corpora, sha256 `29ecefa9...` | The no-cue twin (`gen_v32_s0`, sha `61011b6c...`) is then exact. Its states come from the native drive, which matches real crowns 78% of the time against 39% for RoyaleSim (a). |
| Split | By match: crc32(tag) % 100 < 10, giving 1,459 val replays / 349,264 val rows / 0 overlap; plus v3val, 12,237 icebow rows (a, `dataset.py:107`) | Every metric's CI resamples whole matches. |
| Cue fields | The 22 floats of `model_gen.cue_vector`. State one-hot over 7 (idle / moving / engaged / deploying / jumping / tunnelling / casting), charging, Tesla hidden, has target, target is a tower, attack phase over 3 (idle / windup / hit), attack fraction, frozen / slowed / raged / invisible / shielded, slow fraction. Taunted and stunned stay out (S6: not trainable). | These are the same 22 floats CLIII already reads live (`live_unit_state.LiveCues`) and in RL (`e1_eval.sim_cue_rows`). |
| Where cues come from | `cue_drive.py` re-drives each replay's commands in RoyaleSim and records `sim_unit_state.extract` (hit window 100 ms, one buff memo per match) at **exactly** each row's tick. `cue_sidecar.py` then aligns the bodies to the row's tokens with `live_unit_state.align`, which is `sim_cue_rows`' matcher verbatim (side + nearest within 3 tiles). | The same matcher in all three places means imitation cannot drift from RL or live. |
| Command source | Crawl CSVs, which include hero and champion presses: the pilot crawl (17,853 battles), `crawl_hf_icebow` / `crawl_hf_hogeq`, and icebow / hogeq crawl2 (`plays_ext_i1.csv`, the positioned copy). These cover **13,927 / 14,661 (95.0%)** of v32's replays (a). The rest can only be driven from the native recordings. | Ability presses are missing from the native logs. |
| Fidelity gate | A row gets cues only if its **body Dice** (the share of bodies that pair up between the dataset's board and the SIM's board, matched by same side, within 1 tile, hp within 15%) is >= 0.9. Within an accepted row, a token with no such match also gets 0. Zeros mean "unknown", the same thing a degraded live frame feeds. | The token Dice agrees with the native-frame Dice: corr **0.91**, same side of the 0.9 bar on **95.2%** of 3,678 rows (a). So the pod needs only the dataset, not the 13 GB native corpus. |
| Expected size | 36-53% of rows with cues (play rows 30-44%), so ~0.3-0.45 M cue-bearing play rows (b, extrapolated from 21 replays). D1 measures it. | — |
| Cue distribution | Share of known tokens per field, pro drive vs live (30 logs / 9,197 decisions / 35,676 tokens): moving .54 / .43, engaged .27 / .37, deploying .13 / .12, has target .48 / .57, windup .24 / .32, slowed .05 / .08 (a). | The pro rows are somewhat quieter because the gate prefers agreeing, calmer boards. That is a selection bias, recorded in the risks. |
| Opponent elixir / cycle | Unchanged fv5 inputs (above). | — |
| Weights | **None in v1.** The ~3x unfavourable weighting stays in RL, where `decks_rl.json` already carries it. `row_weights.py` + `train_gen --row-weights` are built if the owner wants it in imitation too; that costs one more GPU run (a weighted no-cue twin). | Weighting in imitation would be a second change against `gen_v32_s0`. Its reach is small anyway: on 21 replays it boosted 1 of 4-5 X-Bow sides. |
| Live logs | Not used as imitation rows in v1. Own-side rows are the old model's decisions, which is the leash's job. Opponent-side rows lack the human's hand and elixir. Stage 2 uses them as its gate holdout (406 of 437). | They are used for the live cue check, the dry-run decision check, the habit metrics and the live A/B. |
| Not included | Hero IW crawl (above). PRO2 pages (1,064 replays, forms unobserved). More HF replays. | — |

---

## b. The model

- **Same `GenModel` as the RL nets** (`model_gen.py:115`): d 128, 4 layers, 4 heads, d_c 64, 1,519,656 params.
  - Heads: gate, card pointer over the hand, 2,304-cell placement, wait pointer, value.
  - Add the cue layer (`cue_in`: 22 -> 128, no bias, zero-initialised), trained from the first row.
  - Identical heads are what allow a KL to CLIII.
- **Init: random**, as `gen_v32_s0` was, so the cue effect is IL-cue minus `gen_v32_s0` and nothing else.
- **Rejected options:**
  - Warm-starting from `gen_v32_s0` would need its own no-cue fine-tune twin.
  - Fine-tuning CLIII on pro labels was (c): -6.56 and -5.00 pp on 10-10.
  - A larger model (FirstLight's 12.7 M) is a later, separate change.
- **Deployment as for every Mark:** RL trains the plain net, and `L74/weekend/graft_generic.py` copies the 42 live add-on
  tensors (cell_refine, tower_refine, projectile_target) at deploy time.

---

## c. Imitation training

- **Where:** the training pod GPU (L40), script `d2_il_pod.sh`, after `d1_data_pod.sh`.
- **Runs:** both use the `gen_v32_s0` command exactly (`L73/gen_v32/chain_b.sh`: 4 epochs, bf16, rocket-context weight
  4.0 with the v32 artifact):
  - **IL-cue s0** adds `--cue-data`.
  - **IL-nocue s1** is the same recipe, seed 1, to measure seed noise.
- **Time:** v32 took 3.1 h on the laptop RTX 5050 (49 min train per epoch). Planning figure **~1-2 h per run on an L40**
  (b). The first epoch's log revises it.
- **Gate:** `il_compare.py`, paired, CI from 2,000 bootstrap draws over val **matches**. Subsets: all val rows, val rows
  with cues attached, and v3val.

**Health (must pass):**
- IL-cue against `gen_v32_s0` on card top-1, cell-tile top-1 and gate balanced accuracy.
- On v3val and all val rows, it may be no worse than the seed noise |nocue1 - v32|. Not every metric may sit below it.
- `gen_v32_s0` reference values: val card .613, cell-tile .224, gate balanced accuracy .747; v3val .657 / .204 / .776 (a).

**Cue effect (pre-registered measurement, not a kill switch):**
- Measured on the cue-attached val rows: cell NLL (a measure of placement-prediction error, lower is better), card
  top-1, gate NLL, wait top-1.
- "Cues help in imitation" means a CI that excludes 0 on at least one of them, by more than the seed noise.
- If they do not help, that is reported as (c), "cues add nothing even in imitation". REB still runs on its second
  rationale, the pro habits, and the plan says so.

**Live check:**
- Run `L74/cues/live/dry_live.py` with IL-cue on 20 held-out cue logs.
- Count how many decisions change when the cues are zeroed (CXXXVIII: 1/538). A model that uses its cues must change
  many more.

**SIM, informational:**
- IL-cue against CLIII on the standard promotion seeds (960 games), with habit metrics.
- Expect it to be well below CLIII: the gen_v3.2 base won 56 of 192 where R1e won 105 (a, 10-07). This measures the gap
  REB must close.

---

## d. The RL phase

### Step-d environment (identical in every arm, so it never confounds an arm comparison)

| Setting | Value | Evidence |
|---|---|---|
| Engine | **fin13** = clashbot36 head a697d1f9 (bundle `parity1016/clashbot36_fin13.bundle`, wheel P3 `/workspace/rsfork_fin13`). Needs ticket R1. | 5 fork laws landed after the bc2bf9d-era fork36 runtime, each verified "land" (Tesla hold, ring stun, reflect held, uppercut count / stand, Tesla under-damage v2); upgraded parity 0.925 on FIN12 (a, HANDOFF 06:04-09:04) |
| Hero IW | `ROYALE_HEROIW_FORM=hero`, `hero_abilities: true`, **`heroiw_press: live`** | the generic rule pressed ~5.4 / match against ~1.9 live; every Hero-IW model before was trained mismatched (a, overpress NOTES) |
| Ability | **`ability_head: true` + `ability_features: freeze`** if c3_ab is "not clearly worse" than c3_ctl (owner bar). Otherwise the live rule press. | c3_ab / c3_ctl in flight from CLIII |
| Levels, cues | `live_levels: true` (CLIII's change, +4.43 pooled), `cue_inputs: true` | (a) |
| Rocket + Tornado | The rules stay **off in training**. They act only on the live decide path; the learner samples, and habits are learned. The **spell-value reward** (`spell_value_reward` + `spell_value_lone`, w 0.02) goes in **only if** combo_rew_c3 beats combo_ctl_c3. | owner 10-18: Tornado only when a lone Rocket is not enough |
| League | As succ_levels: PFSP hard, 5 external snapshots, `decks_rl.json` with the six unfavourable archetypes boosted. **Verify the boost on the pod:** `mk_hist_decks.py` reports ~4.95x natural share, but the owner said ~3x (b). | memory train-on-unfavorable-matchups |
| Length | **130 updates**, seed 74, lr 1e-5, PPO as succ_levels | longer runs were the only measured gains: u250 -> cue130 +5.21 cue-blind, +65 -> CLIII +4.43 (a) |

### Arms (one change each)

- **CTRL**, pod A: init CLIII raw (`rlarm_succ_levels_u0065.pt`, 05d42da7).
  - The KL anchor is the init, so it is already the previous best. Leash as succ_levels (beta0 .3, min .03, max 3,
    target .1, leash max).
- **REB**, pod B: init IL-cue s0, KL anchor = **CLIII on all heads** (ticket K1: opt-in `kl_ref`).
  - Leash loosened in 3 stages. Updates 0-29: target 0.05, beta0 1.0. This copies CLIII's play on the student's own
    games, a method known as "kickstarting". Updates 30-79: 0.15. Updates 80-130: 0.4, which in effect releases the leash.
  - Log the KL to CLIII each update, plus the habit metrics at u30, u65 and u130.
  - **Stop/go at u65:** standard eval (18 min). If REB is more than 5 pp below CLIII, stop it and give the pod to LEAGUE
    or a CTRL replicate.
  - **Why this is not the distillation that failed on 10-14/15** (-8.33 / -9.17 pp). That run cloned the D3 *rule stack*
    with one-hot labels on the teacher's own states, which left the cell NLL overconfident (3.10 -> 4.71) and its ~5 pp
    residual looked rule-driven.
  - Here the targets are soft: CLIII's own network distribution. They are computed on the student's rollouts, mixed with
    the RL objective, and the student sees everything CLIII sees plus cues, so there is no privileged teacher (b).
- **LEAGUE**, pod A after CTRL: CTRL + `league_exploiters: {ckpt: s2_all_il_sA u0130 (or the checkpoint S2-10
  selects), decks: L74/mix/decks_live_train.json, share: 0.3}`.
  - Run it only if S2-10 passes, or on the owner's say-so, since these opponents are "more human-like" but not
    validated.
  - Every arm is also scored against **s2_all_il_sB** (the held-out opponent seed) as a secondary SIM eval.

### Controls and noise

- CTRL is REB's control. CLIII is everyone's reference.
- c3_ctl and combo_ctl_c3 (spell weight 0) both start from CLIII on fork36 with seed 74 and otherwise equal keys. Their
  spread is a free **lower bound** on run-to-run noise (the async actors are not deterministic). It is not a full
  seed-noise estimate, because the seed is the same.

### Reward

- The terminal outcome with GAE, as succ_levels; no shaping. The spell-value term only as above.
- The factorial (16 runs) found no reward or league factor that beats CXXXVIII (a, 12/16 read).

---

## e. Gates for live (owner bar: a clear, significant gain over CLIII)

- **Promotion eval, paired, same pod and command for both models:**
  - Arm D3, live levels, `--card-levels Rocket=16 Log=15`, opponent tower troops at live rates, `decks_live_eval.json`,
    E4 opponent at T .1.
  - **Standard** seeds 741200 + 742000 (960 pairs); **fresh** seeds 743000 + 744000 (960 pairs).
  - Pass = **CI low > 0 on both.** The checkpoint is pre-registered as u130; u65 is scored on the standard seeds for
    monitoring only.
- **Engine of the eval (owner decision):**
  - The trainee runs fin13, so I propose scoring CLIII and every candidate on **fin13**, with fork36 reported alongside
    for continuity.
  - The engine moves effect sizes (+9.06 on fork + troops against +3.44 on 0.1.35, a), so CLIII must be re-scored on
    whatever engine is used. Its 642/960 on fork36 is not a fin13 baseline.
- **Power (b).** Each 960-pair set has SE about 1.8 pp (from CLIII's CI [+0.21, +7.19]). Chance of passing **both** sets:

| True gain | Chance of passing both |
|---|---|
| +3 pp | ~15% |
| +4 pp | ~38% |
| +5 pp | ~64% |
| +6 pp | ~85% |

  So the bar asks for about +5 pp. Smaller real gains will usually be rejected, which is the cost of a strict bar.
- **Then live** (owner's call; deploy via `deploy_ckpt.sh` by the lead):
  - Check the account first (towers 4424, icebow hand).
  - Revert rule as before: after ~100 graded matches, a live win rate below CLIII's means revert.
  - The habit report goes with it as information, not a gate.

---

## f. The two doctrine habits: learned, then measured

Neither habit gets a rule (owner 10-15: no hard-coded habits). Three levers act on both:
- the pro base,
- opponents that punish,
- a leash loose enough to let RL move.

The habits worker fixes the exact definitions. These are the metrics to put in the eval:

**H1. Bridge X-Bow only in a punish window.**
- **Inputs:** the public elixir estimate and the opponent cycle (above).
- **Metrics per checkpoint:**
  - first bridge X-Bow: time, play index, opponent plays seen before it;
  - share of bridge X-Bows inside a punish window, by the worker's P1-P4. In the SIM the TRUE opponent elixir is scored
    next to the public estimate;
  - P(heavy counter within 8 s);
  - X-Bow life and damage;
  - early bridge X-Bow share (`--habit-log`: CLIII 65.7% against CXXXVIII 58.3%, a).
- **Caveat (b, leaning c):** in pro data, punish-window X-Bows do not show higher win rates. P1 gives 49.1% against
  45.4% on crawl2 and 47.6% against 49.0% on HF. That is association, not cause, but the doctrine's *value* is not
  demonstrated by the data. Win rate stays the gate. Punish windows do cut the immediate heavy counter, e.g. P3 12-27%
  against 31-39% (a).

**H2. Heavy push answered with Rocket or Rocket + Tornado, not cheap-card spam.**
- **Levers:** the pro base (Rocket 18-27% against our 4-5%), the spell-value reward if combo_rew_c3 passes, and the
  loosened leash.
- **Metrics per heavy push**, both play-based (>= 10 elixir in 15 s) and body-based (>= 10 on our half):
  - response shares: Rocket / Rocket + Tornado / cheap-only / other;
  - cheap cards spent;
  - elixir spent against elixir removed (`spell_value.SpellTracker`);
  - tower hp lost in 20 s;
  - all of the above split by "Rocket in hand".
- **Implementation (ticket H1):** extend `search_s0 --habit-log` (that file is dirty, so after it is committed), or run
  the worker's `sim_habits.py` on the eval rows if it already covers this.

**The leash conflict (owner decision).**
- Anchoring REB to CLIII on the card head pulls the Rocket choice back toward CLIII's 4%.
- If REB's H2 metric falls back toward CLIII between u30 and u65, the alternative is to anchor the card head to
  IL-cue (the pros) and the gate and cell heads to CLIII. That is a separate arm, not a mid-run switch.

---

## g. Pods and schedule (budget 3-4 pods)

Parity pods **P1 216.81.151.5:15617** and **P3 64.247.206.76:19899** are untouched. Training pods are
**T1 64.247.206.76:13396** (s2_all_il_sA until ~17:00 EDT, plus its S2-10 gate jobs) and **T2 64.247.206.76:14009**
(cue_ab2, then c3_ab with 65 updates, plus evals). All times below are (b).

| EDT | T2 14009 | T1 13396 |
|---|---|---|
| now - ~15:00 | cue_ab2 -> c3_ab (in flight) | s2_all_il_sA (in flight) |
| ~15:00-16:00 | **R1** fin13 runtime + `rl_royale --smoke` on both configs | Stage 2 jobs |
| ~16:00-18:30 | **D1** drive (24 workers, ~2-2.5 h) + sidecar (~0.3 h) | Stage 2 jobs; ~18:00 **CTRL** starts (130 upd at ~3.9 min = ~8.5 h) |
| ~18:30-23:00 | **D2** IL-cue s0 + IL-nocue s1 + `il_compare` | CTRL |
| 10-19 ~00:00-09:00 | **REB** (needs K1 committed; ~9 h, stop/go at u65 ~04:30) | CTRL done ~02:30; evals CTRL + CLIII on fin13, std + fresh (~1.2 h) |
| 10-19 ~09:00-10:30 | REB evals | **LEAGUE** (if approved) ~04:00-12:30, else a CTRL seed-75 replicate |
| 10-19 midday | results to the owner; live A/B for a passer | LEAGUE evals ~14:00 |

- **Cost:** about 20 pod-hours on T1 + 19 on T2, ~39 in all over ~1.5 days.
- **3-pod version:** drop LEAGUE, and T1 is free from ~04:00 on 10-19.
- **Optional (owner/lead decision):** run D1 (~3 pod-hours, CPU only) on a temporary pod before it is released, e.g.
  10757 once c3_ctl ends. That takes ~3 h off REB's critical path.
- **Disk:** keep >= 8 GB free (P3 incident). D1 writes ~0.7 GB of cue files plus a 0.36 GB sidecar.

---

## Tickets (who builds what next)

| Ticket | What | Notes |
|---|---|---|
| **R1** runtime fin13 | `fork_build.sh fin13` from the bundle, a new venv (not venvf36), a `freeze_fork36.py` copy with `SIM_PIN=a697d1f9`, a new id in `royale_runtime.py` (L23-27, a branch like L44-47, versions L91) and in `royale_heroiw.ENABLED`, and `gap.py --runtime`. Then smoke both configs. | — |
| **K1** `kl_ref` | `rl_royale.py`: opt-in `kl_ref: <ckpt>` (all three heads; template `_load_gate_ref` L3440) + `kl_target_schedule: [[0, .05], [30, .15], [80, .4]]`. Absent = same config hash. When `kl_ref` is set, the update-0 assertion keeps only the ratio check. Refuse a ref whose `gen_row_keys` differ (CLIII and IL-cue are both fv5 + cue, so the keys match). Tests + a real smoke (memory trainer-edit-preship-check). | `rl_royale.py` holds uncommitted work right now (the `heroiw_press` key the c3 runs use): **commit that first.** |
| **H1** habit metrics | As section f. | — |
| **D1 / D2** | `d1_data_pod.sh`, `d2_il_pod.sh`. | Written, syntax-checked, not run. |
| **Ship list for D1 + D2** | The repo at the step-d commit; `gen_dataset_v32_fv5.npz` (466 MB); `gen_v32_s0/gen_s0.pt`; `.foreman/codex_autopilot/runs/public_context_v32_w4/`; the five crawl dirs (CSV only, ~130 MB; icebow/hogeq crawl2 **must include `plays_ext_i1.csv`**). | The native corpus is NOT needed. |

---

## 4. What was built today (no pod; light laptop CPU; composite 0.1.35 venv = test harness only)

**Files**, all under `scratchpad/gauntlet/L74/stepd/` unless a full path is given:
- `cue_drive.py`: the re-drive with cue bodies. Three modes: native (with fid), pod `--from-data`, `--crawl-only`.
- `cue_sidecar.py`: the per-token cue array, the token-level fidelity and gate, and status codes.
- `row_weights.py`: the unfavourable-matchup x3 row weights.
- `parity_rows.py`: imitation builder against RL builder on the same SIM states.
- `il_compare.py`: the paired imitation gate, CI by match.
- `test_stepd.py`: 6 tests.
- `d1_data_pod.sh`, `d2_il_pod.sh`.
- `pipeline/eval_gen.py` (`GenRows` carries an optional `cue` array) and `pipeline/train_gen.py` (`--cue-data`,
  `--row-weights`). Both are opt-in; absent means unchanged.
- `scratchpad/gauntlet/L74/pro2/build_rows.py`: an optional `on_frame` hook and `record_ticks`, plus a **bug fix**.

**Bugs found and fixed:**
- **PRO2's card catalog loaded event variants** (a). 20 slugs collide, and the last entry won: knight became
  SuperKnight, rocket became GoblinPartyRocket, barbarian-barrel became BarbLog. Any PRO2 SIM row build would have
  driven the wrong cards. The first entry now wins.
- **Pro icebow replays would have been driven with the Hero IW** (a). `royale_heroiw.deck_forms` forces the hero form on
  any exact-icebow deck. Every replay is now driven with the Ice Wizard form its own deck string names.
- crawl2's `plays_ext.csv` has no positions; the positioned copy is `plays_ext_i1.csv`, which is now preferred. A
  blocked crawl source falls back to the native log.

**Results (a):**
- **Builder parity**, imitation against RL, same RoyaleSim states, 3 replays:
  - unit tokens identical on **1,057 / 1,057** wait rows;
  - the 22 cue floats identical on **1,057 / 1,057**;
  - detected opponent plays identical, **201 / 201**. These define `opp_cycle` / `opp_past`.
  - The opponent-elixir estimate differs by a mean of 0.02-0.04 elixir (max 0.13). The cause: the imitation counter
    uses the real-engine regen constants, RL uses the SIM's 1/56, 1/28, 1/18.6, about 0.3% apart. Negligible.
- **Pod mode equals native mode:** on the 1,270 rows that both modes attach, the cue rows are identical **1,270 / 1,270**.
- **Laptop drive cost:** 4-21 s per replay, about 11 s typical. 3 of 21 sampled replays fail on a hero Barbarian Barrel
  that 0.1.35 cannot load (b: the fork may load it).
- **The full imitation loop runs on tiny slices:** drive, sidecar, weights, `train_gen` with cues and weights, then a
  checkpoint with `cue_in` that reloads.
- **Tests:** `test_stepd` 6 pass, PRO2 20 pass, `test_model_gen` / `test_cue_inputs` / `test_dataset_gen` 24 pass /
  3 skipped. pyflakes clean.

## 5. Risks and open owner decisions

1. **REB may not catch CLIII in 130 updates** (b). Every imitation base so far started far below the RL line. The u65
   stop/go limits the loss to ~4.5 pod-hours.
2. **Cue coverage is biased toward calm, agreeing boards** (a, the distribution table). If the cue effect is null, the
   v2 options are per-body gating, or re-seeding the SIM from the recorded board every few seconds the way the parity
   harness seeds fights.
3. **Pre-10-06 replays run under 16.402 laws in fin13** (HANDOFF gap). That is part of the divergence and can only be
   reduced, not removed.
3a. **RL's pro-agreement monitor reads v3val rows without cues**, so a cue model's pro agreement inside rl_royale is
   scored cue-blind. Either pass the sidecar to that monitor (part of K1) or read the guard with that in mind.
3b. **Pre-ship check owed before the lead commits** (memory trainer-edit-preship-check): `eval_gen.py` is imported by
   `rl_royale` (load_model / GenRows / evaluate). The edit is opt-in, absent means unchanged, the tests pass and
   pyflakes is clean, but a real `rl_royale --smoke` on a pod is still owed.
4. **Owner decisions:**
   - (i) the eval engine moves to fin13, with CLIII re-scored there;
   - (ii) LEAGUE with Stage-2 opponents that have not passed their gate;
   - (iii) ~3x weighting in imitation too, at +1 GPU run;
   - (iv) the leash anchor conflict in section f;
   - (v) whether D1 runs on a temporary pod before it is released.
