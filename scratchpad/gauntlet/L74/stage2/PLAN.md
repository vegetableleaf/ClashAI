# Stage 2 build plan: realistic SIM opponents (final synthesis, 2026-10-17 ~23:00 EDT)

Grades: **(a)** measured, with the number; **(b)** plausible but untested, with the test that settles it; **(c)** contradicted, with the evidence.

## 0. Decision in one paragraph

We use Design 3's plan: try the cheapest options first and stop as soon as one passes. The pieces come from Design 1's zero-code configs. The core experiment is one paired test on Hog. Two Hog opponents are trained the same way, except one starts from E4 and the other from the imitation net `gen_v32_s0`. That pair answers "is imitation needed?" (2 of 3 judges picked Design 3; Judge 1's grafts turn Design 1 into the same ladder.)

The winning recipe is then trained once on all deck styles as **one deck-conditioned checkpoint**, which needs no routing code. It is gated on both trophy bands against live results. A sealed future block of live matches confirms the result. Only after that does it feed the icebow successor, as one change against its control.

No pipeline file changes are on the critical path. That matters because `rl_royale.py`, `search_s0.py`, `e1_eval.py` and `decision_options.py` all hold uncommitted in-flight work (Judge 3, (a)).

### What the gate must reproduce (corrected targets, (a))

There are **two separate gaps**, not one "overtime collapse":

1. **The SIM is too generous in regulation against non-Hog decks, in both bands.**
   - Live, non-Hog regulation win rate is 12/28 for CXXXVIII at 13k and 58/140 for CXXIV at 12k, so 70/168 = 41.7% pooled.
   - The SIM gives 57–78% (four tower-troop runs) and 72.4% (RT35 cue run).
   - Live regulation-loss rate is 31.7% (CXXIV at 12k) and 24.4% (CXXXVIII at 13k). The SIM with E4 gives 13.5%.
2. **Hog in overtime, at 13k only.**
   - Live: 1/13, Wilson range [1.4, 33.3]%.
   - SIM: 59–68% in every run.
   - Hog in regulation is not a gap: live 5/8, SIM 64–79%.
   - This cell was found after looking at the data, so it is a diagnostic, not a primary cell.

Corrections to the brief:
- **(c)** "Overtime 5/24 at 13k" is out of date. Pooled, it is 18/42 = 42.9%, and the two halves differ (p = 0.027).
- **(c)** The Hog gap between the two Marks is mostly a trophy-band effect. At the same band, CXXXVIII went 5/10 against Hog and CXXIV 13/23.
- **(b)** Whether the 13k overtime drop is Hog-specific holds on the pooled data but not over time. Non-Hog overtime was 8/18, then 9/11. Hog overtime was low in both halves (0/9, then 1/4).

## 1. Every judge objection, and what this plan does with it

| # | Objection (who) | Disposition |
|---|---|---|
| 1 | Rung 0 run on the Hog pool alone cannot see the regulation optimism against everything else (J1) | **Accepted.** Phase B runs on the full live eval pool. Every candidate reports the 4-way Hog/other × regulation/overtime split. |
| 2 | Test the rhythm idea with no retraining: `gen_v32_s0` at decide 10/20/40 (J1, J3) | **Accepted, low prior.** It is in Phase B (about 1 pod-h). J2 showed the predicted 4× tempo inflation is not seen: the SIM runs about 1.34× live (c-leaning). The D2 dataset rebuild runs only if decide 40 moves the gate cells. |
| 3 | Rung 1 must be a matched pair, E4 start vs imitation start (J1, J2, J3) | **Accepted.** That is Phase C. |
| 4 | Read the existing exploiter rows for the Hog/overtime cell before any RL (J1) | **Accepted.** Ticket S2-05, on the laptop, 0 pod-h. |
| 5 | Count every look; log every knob (J1, J2, J3) | **Accepted.** `stage2/ledger.jsonl`, one row per candidate × checkpoint × band, written before the result is read (S2-02). |
| 6 | Stopping-point knobs per band are circular (J2, J3, against D1's pass rule) | **Accepted. D1's pass rule is rejected.** One checkpoint must pass both bands. Only the level profile may differ between bands (D3's band rule). |
| 7 | R1d, the scripted punish layer, is fitted by construction, touches dirty `search_s0`, and needs an owner ruling (J2, J3) | **Rejected / deferred.** It is not built. If the owner wants it, it runs as a SIM-only probe outside the realism claim, after the in-flight `search_s0` work is committed. |
| 8 | D1 trained on the same deck pool it gates on (J3) | **Accepted.** Training uses a Hog subset of `mix/decks_live_train.json`; the gate uses `decks_hog_eval.json`. The overlap count is reported (S2-02). |
| 9 | Live levels and tower troops are swapped between seats in an exploiter run (J3, (a), `rl_royale.py:1628-1632`) | **Accepted.** Every opponent-training config sets `live_levels: false` and no `opp_tower_troops`. Both are on only in the gate. |
| 10 | Human tempo cannot be set on the learner seat (J3, (a), `OPP_TEMPO_KEYS`) | **Accepted.** The pair runs at default tempo, so init is the only difference. If a human interval is needed later, use `decide_every=20` + `opp_decide_every=10`. A reaction delay for the learner alone needs code, so it is out of scope. |
| 11 | Frozen CXXXVIII in training uses the rule-based Hero IW press and no posture head, and has no D3 rule stack (J1, J3, (a), `ocfg0`) | **Accepted and recorded.** The gate evaluates the real live stack (D3). A drop from training win rate to gate win rate is expected and is reported as the size of that gap. |
| 12 | Engine error is mixed into every comparison; fight parity is 0.941 (J1, D2 R2) | **Accepted.** S2-05 correlates the per-style SIM–live gap with per-card parity. It is weak at about 13 styles, and that is stated. |
| 13 | Low SIM regulation *wins* (17.8% vs 22.7% live for CXXIV) suggest the overtime excess is partly on both seats (J2) | **Accepted.** S2-04 splits the gap by seat. If both seats under-take towers, the cause leans to the engine, not the opponent. |
| 14 | Our own live play may cause the losses, not opponent skill (D1 step 0, D3 A2, J2 extension) | **Accepted.** S2-04 runs on the laptop tonight over the 13 Hog-overtime logs and the non-Hog regulation losses. |
| 15 | Add non-Hog regulation win as a cell; it is the largest well-sampled gap (J2) | **Accepted** as one primary cell pooled over both Marks (70/168). The false-fail rate of the larger gate is measured, not guessed (S2-02). |
| 16 | G1 compared a detected SIM number with an exact pro number (J2) | **Accepted.** G1 is not on the critical path. If it is used, SIM exact plays are compared with pro exact native-engine plays (same basis). |
| 17 | Cost per update: 2.4 min, not 1.8 or about 4.6 (J2); still unmeasured for this config (J3) | **Accepted.** Planned at 2.4 min/update (65 updates ≈ 2.6 h, 130 ≈ 5.2 h) (b). The smoke run times it. |
| 18 | Drop Inventory 1's 57-match pace figure; use `gate_fit`'s `classify` on both sides (J2) | **Accepted.** Pace comes from CXXXVIII's 117 graded matches in about 9 h. All style labels come from `gate_fit`/`live_eval.classify`. |
| 19 | `~/.ssh/id_ed25519` does not exist (D3, J1, J2, J3, (a): only `runpod_clashbot`, `clashbot_gcp`) | **Accepted.** Use `-i ~/.ssh/runpod_clashbot`. Whether the new pods accept it is (b); it is the first step of S2-01. |
| 20 | The 130/960 identical regulation-loss count looked like a copy error (J1) | **Resolved (a, J2).** It follows from `e4_gate.out`: 353−223 = 390−260 = 130. |
| 21 | The gap13k probe uses the ungrafted exploiter 5deeb40a, not the measured 862bfe92 (Inv 3) | **Accepted.** Phase B runs the grafted 862bfe92. It must be fetched from its pod first (S2-01). |
| 22 | Do not graft opponents (J3, `chain.sh:75`, `graft_generic` assumes r3c heads) | **Accepted.** |
| 23 | fv5 imitation as an RL init is untested (D1, D2, D3) | **Mostly resolved (a, J3).** league1/1b/1c used `gen_v1_s0` as init. The pre-ship smoke is still mandatory. |
| 24 | Live-log imitation would contaminate the gate: 406 of 437 ext logs are holdout (D2, (a)) | **Accepted.** Live data is used only for calibration and the gate. The 300–600-line live-log row builder is deferred. |
| 25 | Seed A/B: train the successor against one opponent seed, score it against another (D2, J2) | **Accepted** for Phase D and the successor. |
| 26 | One deck-conditioned opponent checkpoint avoids the list form of `league_exploiters` in dirty `rl_royale` (D2, J3) | **Accepted.** Per-style specialists are built only for a style that fails the gate. |
| 27 | Pros are not 13k trophy-road humans (all designs) | **Kept as (b).** S2-05 compares the 13k ext-log features with `gen_v32_s0` SIM features. A crawl of post-10-06 / 13k replays runs only if that distance is above 0.3 or the gate fails on style. |
| 28 | D2's full dataset rebuild and 3.5 VM-h drive put cost in front of anything shown to matter (J2, J3) | **Rejected for now.** It is re-opened only by objection 2 or 27. |
| 29 | Successor gains from exploiter leagues have been null 4 times (D1, D3) | **Kept as the prior (c-leaning).** S2-13 first re-scores the old arms against the gated opponent, which needs no training. |

## 2. Tickets

Pod-hours use 960 SIM games ≈ 18 min per pod (a) and 2.4 min per RL update (b). Every pod chain ends with a verified copy-back (normalise `sha256sum` output: the laptop prints `hash *path`) and `runpodctl` auto-stop. No laptop GPU. Never `python -`. Pods run a pinned commit (HEAD `656e790` unless the lead commits newer work), and its hash goes in the ledger.

### S2-01: Pod bring-up and fetches
- **Goal:** new pods P5 = `root@81.27.69.177 -p 23408` and P6 = `root@64.247.206.79 -p 10757` are usable with the right code, runtime and checkpoints.
- **Steps:**
  - `ssh -i ~/.ssh/runpod_clashbot`; record core count and GPU.
  - Sync code at the pinned commit, the fork36 runtime (0.1.36), CXXXVIII (`rlarm_gae_cue_u250/..._u0130_grafted.pt`, sha prefix 0fba110c), CXXIV, E4, `gen_v32_s0/gen_s0.pt`.
  - Fetch `rlarm_exploit_u0065.pt` (5deeb40a) and its grafted twin 862bfe92 from whichever pod holds them.
- **Acceptance:** sha256 of every synced checkpoint matches the laptop; a 2-match `gap.py` dry run completes on each pod.
- **Pod-h:** about 1 (b).
- **Depends on:** nothing. If `runpod_clashbot` is refused, stop and ask the owner for the right key.

### S2-02: Configs, pools, ledger, gate freeze (laptop, light CPU)
- **Goal:** everything Phase B/C needs, with no pipeline edits.
- **Files** (all new, `stage2/`):
  - `stage2/pools/decks_hog_train.json`: `mk_hog_pool.py` logic applied to `mix/decks_live_train.json`. Report its deck overlap with `decks_hog_eval.json`.
  - `stage2/mkcfg_stage2.py`: two arms copied from the `exploit` branch of `L74/rlarms/mkcfg_arms.py`.
    - `s2_hog_e4`: `init` = E4.
    - `s2_hog_il`: `init` = `icebow/data/pipeline/gen_v32_s0/gen_s0.pt`.
    - Shared settings:
      - `league_decks=stage2/pools/decks_hog_train.json`
      - `league_learner_icebow_share 0`
      - `league_frozen_opponent` = CXXXVIII grafted (sha check like `F1_U250_SHA`)
      - `league_pfsp off`, `league_external []`, `opp_style off`, `league_opp_policy live`
      - `live_levels false`, no `opp_tower_troops`
      - `save_every 5`, 65 updates, same training seed
      - env `ROYALE_HEROIW_FORM=hero`, runtime fork36
  - `stage2/ledger.jsonl`: knob ledger. One row per look: candidate, checkpoint, band, games, gate_fit sha, timestamp. Written **before** results are read.
  - `stage2/gate/FROZEN.txt`: sha256 of `gate_fit.py`, `live_targets.json`, the range table in section 3, and `gate_holdout.txt`.
  - `stage2/gate/merge_rows.py` (about 15 lines): swaps the Hog rows of an existing E4 run for a candidate's Hog rows, keeping live style proportions.
- **Acceptance:**
  - A diff of the two resolved configs shows only `init` (plus the derived config hash and feature version; E4 is fv6 and `gen_v32_s0` is fv5, which is part of "init").
  - `gate_fit.py --selftest` passes.
  - A parametric bootstrap gives the gate's false-fail rate with SIM drawn at the live rates (expected about 20–30% with 9 cells) (b), and it is written into FROZEN.txt.
- **Pod-h:** 0.
- **Depends on:** nothing.

### S2-03: 13k level profile (D3 R0)
- **Goal:** the only allowed difference between the two bands.
- **Files:** `stage2/levels/levels13k.py` → `levels13k.json`, built from opponent tower and card levels in the 13k-band ext logs. It uses levels only, never results, so it does not leak the gate outcome.
- **Route:** `LIVE_LEVELS` is a constant (`rl_royale.py:1546`). The zero-code route is a pod-local checkout copy with the 13k file in place, never synced back. (b) Confirm `search_s0`/`gap.py` read levels through that constant; if not, note it and gate both bands on the existing table.
- **Acceptance:** level-16 tower share in the file is about 70% (40/57) vs 48% in the current table; a 2-match dry run's `run.json` shows the new sha.
- **Pod-h:** 0.
- **Depends on:** S2-01.

### S2-04: Live-side fault audit (laptop, light CPU, tonight)
- **Goal:** separate "the opponents are stronger than the SIM's" from "our live pipeline misbehaves".
- **Method:**
  - Inputs: the 13 Hog-overtime logs at 13k vs CXXIV's 31; all non-Hog regulation losses (CXXXVIII 13k: 16; CXXIV: 82).
  - Measure in each: our stalls (> 10 s without a play before the losing push), our elixir when the push arrives, reader misses and freezes, decision latency, D3 rule fires, tower-loss time.
  - Compare with the same features in the SIM habit log.
  - Split the regulation gap by seat: our regulation wins vs our regulation losses, SIM vs live.
- **Files:** `stage2/audit/live_side.py`, `.out`.
- **Acceptance:** a table per cell: count of losses with a flagged own-side fault, with its share.
  - If own-side faults explain at least half of either gap, that gap leaves Stage 2 and becomes a live-path ticket.
- **Pod-h:** 0.
- **Depends on:** nothing.

### S2-05: Free diagnostics (laptop, light CPU)
- **(a)** Hog 2×2 and non-Hog regulation cell from the existing grafted-exploiter rows (`exploiter_gate.out`'s source).
- **(b)** Per-style SIM–live gap vs per-card fight parity (fork36 harness numbers), Spearman correlation over the styles. Stated as weak.
- **(c)** Classify SIM opponents by *played* cards as live does, if `matches.jsonl` carries plays. Otherwise note it as (b).
- **(d)** Population check: plays/min, elixir at play, lane split, quick-answer share from the 31 non-holdout ext logs plus the 13k holdout logs (features only, no results) vs `gen_v32_s0` SIM rows, all through the same detector.
- **Files:** `stage2/diag/*.py`, `.out`.
- **Acceptance:** each produces a number or an explicit "rows not on disk".
  - If (a) shows no existing opponent gets Hog overtime below 40% while leaving Hog regulation near even, raise S2-04's priority.
  - If (d) gives a distance above 0.3, open the crawl ticket.
- **Pod-h:** 0.
- **Depends on:** nothing.

### S2-06: Phase B, no-training screening
- **Goal:** find out whether an existing network plus one knob already passes.
- **Runs:** `chain.sh seeds_eval` → `gap.py --arms D3`, fork36, tower troops at live rates, live levels, `--census-file mix/decks_live_eval.json`, 960 games per Mark (CXXXVIII and CXXIV), **new job name per run** (seeds_eval skips directories with 480 rows).

| Candidate | Flags | Marks |
|---|---|---|
| B1 E4 T .3 | `--opp-T .3` | both |
| B2 gen d10 | `--opp-ckpt gen_v32_s0 --opp-T .1` | both |
| B3 gen d20 | B2 + `--opp-decide-every 20` | both |
| B4 gen d40 | B2 + `--opp-decide-every 40` (training stride) | both |
| B5 exploiter grafted 862bfe92 | `--opp-ckpt` | both |
| B6 E4 T .1 + 13k levels | S2-03 checkout | CXXXVIII only |

- E4 T .1 is the baseline and is **not re-run**: its fork36 promotion rows exist (`e4_gate.out`).
- **Acceptance:**
  - The gate (section 3) is scored for each candidate, with the 4-way split and regulation-loss rate.
  - A candidate within reach on every primary cell at 960 gets a confirming run at 1,920 per Mark.
  - **Stop rule:** a confirmed pass in both bands sends us to the sealed block and S2-14, skipping C/D.
  - Per D2's pre-registered null, a one-knob pass also means the gate cannot tell styles apart. The style distance then decides whether the candidate is realistic.
- **Prediction (b):** all fail the non-Hog regulation cell; none has gone above 23% regulation losses in 17 setups (a).
- **Pod-h:** 3.3, plus about 1.2 if a confirming run is needed.
- **Depends on:** S2-01, S2-02; S2-03 for B6 only.

### S2-07: Phase C, matched Hog pair (smoke + train)
- **Goal:** the one experiment that answers "is imitation needed?"
- **Runs:**
  - `rl_royale --smoke` for each arm (pre-ship rule; it also times the update).
  - Then 65 updates each, same seed, same runtime, same pod type.
  - Checkpoints u0005…u0065.
- **Acceptance:**
  - The smoke completes, and the resolved-config diff equals the S2-02 diff.
  - The training log shows the frozen seat using `ocfg0` (rule press).
  - Both runs reach u0065 with a verified copy-back.
- **Pod-h:** 0.7 (smokes) + 5.2 (b).
- **Depends on:** S2-01, S2-02.

### S2-08: Phase C Hog gate
- **Runs:**
  - Each arm × {u0025, u0045, u0065} on `stage2/mvp/decks_hog_eval.json`.
  - CXXIV with the 12k table and CXXXVIII with the 13k table, 960 games each.
  - That is 11,520 games.
  - Every look is ledgered.
- **Acceptance cells (Hog only):**
  - Hog win rate and Hog overtime share in both bands, with one checkpoint passing both.
  - Ranges at 480 SIM games (`hog_tol.py`; `gate_fit` recomputes them for the actual n):
    - 13k: Hog win 9.1–48.4%, overtime share 40.7–82.9%.
    - 12k: Hog win 45.5–72.9%, overtime share 43.5–71.2%.
  - Diagnostics: Hog regulation/overtime 2×2 (13k overtime win ≤ 33% is the hoped-for direction), style distance.
- **Readout of the pair:**
  - Only the imitation start passes → imitation is needed.
  - Both pass with style distance within 0.1 → imitation adds cost without realism; use the E4 recipe.
  - Neither passes → that is a finding. Diagnose before iterating: overtime share above range means it wins by stalling, like the old exploiter's 80.4%. The one-knob fix to try next is tower-damage shaping in the *opponent's* reward. It is ledgered and allowed for opponents.
- **Also:** `merge_rows.py` puts the winner's Hog rows into the existing E4 full-pool rows. That shows how much of the full gate a Hog-only fix closes (0 pod-h).
- **Pod-h:** 3.6.
- **Depends on:** S2-07, S2-03.

### S2-09: Phase D, one all-style opponent, seeds A and B
- **Goal:** realistic opponents for every style in one deck-conditioned checkpoint.
- **Runs:** the S2-08 winner recipe with `league_decks=mix/decks_live_train.json`, 130 updates, seeds A and B on separate pods, smoke first.
- **Acceptance:** both runs reach u0130 with verified copy-back.
  - Per-style specialists (and the list-form `league_exploiters`) are built only for a style that then fails S2-10, and only after the in-flight `rl_royale` work is committed.
- **Pod-h:** 0.4 + 10.4 (b).
- **Depends on:** S2-08 verdict. If neither arm passed, D waits for one diagnosed iteration of C.

### S2-10: Full two-band gate
- **Runs:** seed A at u0060, u0100, u0130, plus seed B at the checkpoint chosen for A.
  - Each is 1,920 games per Mark on seeds 741200/742000/743000/744000, using the promotion-eval conditions with only `--opp-ckpt` changed.
  - That is 3,840 games per checkpoint.
- **Acceptance:** section 3, all primary cells plus the chi-square fit plus style distance, in both bands, at one checkpoint. Seed B must also pass (reproducibility).
- **Pod-h:** about 4.8.
- **Depends on:** S2-09.

### S2-11: Leash measurements (answers the owner's question with data)
- **(a) Is the KL leash binding today?** Read `beta` (KL weight) and gate/card/cell KL across the gae_cue u250 → u0130 training log on its pod. In league1 the weight sat at its floor of 0.03 and KL stayed under target (0.016 → 0.076) (a, J2).
- **(b) How far has the learner drifted from pro play?** Run `eval_gen per_deck` agreement for CXXIV, u250 and CXXXVIII vs `gen_v32_s0` on v32 validation rows (icebow and Hog/MK/Golem decks). CPU, on a pod.
- **Acceptance:** two numbers per checkpoint (beta trajectory; card/cell agreement).
- **Pod-h:** 0.5.
- **Depends on:** S2-01.

### S2-12: Sealed live block
- **Goal:** the only test with real power.
- **Start condition:**
  - The live-logger fix (owner-approved tonight) has landed.
  - FROZEN.txt is written.
  - The start timestamp and live Mark are recorded.
- **Rules:**
  - The candidate opponent is frozen and hashed before the first look.
  - One look.
  - If the live Mark changes, the block restarts.
  - Nobody computes gate cells on these matches before the look. The loss-review loop may still read them, but any fix it ships changes the Mark and restarts the block.
- **Acceptance:** at least 150 graded 13k matches (expected about 39 Hog and 78 overtime; error bars about ±7.5 and ±5.6 pp). The gate is scored once on them.
- **Pod-h:** 1.2 for the matching SIM rows.
- **Live time:** at about 13 graded matches/h (117 in about 9 h), roughly 12 h of play if it stays at 13k (b).
- **Depends on:** the logger fix.

### S2-13: Re-score the old exploiter-league arms on the gated opponent (free test)
- **Runs:** gae_exu250, fact03 and their controls vs the S2-10 opponent (seed B), 960 games each.
- **Acceptance:** paired deltas with CIs.
  - If they are still null, the "training against realistic opponents helps" prior falls further before S2-14 is spent.
- **Pod-h:** 1.2.
- **Depends on:** S2-10 pass.

### S2-14: Successor arm (one change)
- **Arm:** successor base (CXXXVIII init, Hero IW form, learned ability press) + 65 updates. The only change is `league_exploiters = {ckpt: S2-10 seed A, decks: mix/decks_live_train.json, share: 0.3}`. Share 0.3 matches the earlier exploiter test.
- **Control:** `fresh_succ_ctl` (queued on 29286) if its config hash, seed and runtime match exactly. Otherwise train a twin.
  - The owner-approved weighting cut must be in **both** arm and control, so the opponent entry stays the only difference.
- **Evals:**
  1. Promotion eval (960 paired). It fails only if clearly worse (CI top < 0).
  2. The Stage-2 gate opponent **seed B**.
  3. The live A/B, which decides. It waits for the owner's go: CXXXVIII is an owner-chosen live trial.
- **Pod-h:** about 7.
- **Depends on:** S2-10 pass. S2-13 is recommended first.

**Deferred, not built:**
- R1d punish layer
- `train_gen --init/--decks-with` (`gen_v32_s0` already holds 4,126 Hog sides)
- the live-log imitation row builder
- the D2 drive and stride-20 dataset rebuild (re-opened by B4)
- the 13k replay crawl (re-opened by S2-05(d) or a style failure)
- list-form `league_exploiters`

## 3. Gate spec

**Bands.**
- **13k** = Mark CXXXVIII at ≥ 13,000 trophies (live 35/78), levels = `levels13k.json`.
- **12k** = Mark CXXIV, all 300 (12,000–12,999), levels = current `live_levels.json`.
- **Band rule:** the same opponent checkpoint and settings in both bands; only the level profile differs. Both bands must pass.

**SIM side.**
- Promotion-eval conditions: fork36, D3 live stack, tower troops at live rates, `decks_live_eval.json`, Hero IW form.
- 1,920 games per Mark (Hog alone needs about 870 at 13k; 12k needs about 2,000–2,700).
- Style labels come from `live_eval.classify` on both sides.

**Primary cells.** Each needs |z| < 1.96, where z = (SIM − live) / sqrt(var_SIM + var_live).

| Cell | Band | Live | Allowed SIM range (at about 9× live n) | E4 today |
|---|---|---|---|---|
| Hog win | 13k | 6/21 | 8–49% | 66.3% fail |
| Overtime win | 13k | 18/42 | 27–59% | 61.5% fail |
| Overall, re-weighted to live style mix | 13k | 35/78 | 33–57% | 63.4% fail |
| Overtime share | 13k | 42/78 | 43–65% | 60.3% pass |
| Hog win | 12k | 32/54 | 46–73% | 59.1% pass |
| Overtime win | 12k | 86/137 | 54–71% | 60.5% pass |
| Overall, re-weighted | 12k | 154/300 | 45–57% | 59.0% fail |
| Overtime share | 12k | 137/300 | 40–52% | 68.6% fail |
| **Non-Hog regulation win, both Marks pooled** | both | 70/168 = 41.7% | about 34–50% (computed at actual n) | 57–78% fail |

**Secondary (required).**
- Per band, the sum of z² over styles with ≥ 10 live matches (the rest pooled) is below the 95% chi-square cutoff. E4 at 12k: 31.0 on 15 df, fail.
- `L74/human/opp_behaviour.py` style distance ≤ 0.70. That is the best strong opponent so far; the noise floor is about 0.04–0.05. The threshold is a ledgered knob (b).

**Diagnostics (reported, never gated).**
- Hog × regulation/overtime 2×2 (13k Hog overtime live 1/13).
- Regulation-loss rate: live 31.7% / 24.4%, SIM 13.5%.
- Regulation win rate by seat.
- Training-to-gate win-rate drop (frozen-seat gap).

**Known weaknesses, stated plainly (a).**
- At current 13k n, the gate rejects only errors of about 20 pp (Hog), 15 pp (overtime) and 12 pp (overall).
- There is no multiple-testing correction, so a perfect opponent fails about 20–30% of the time. S2-02 measures the exact rate. This errs toward FAIL, which is the safe side.
- A tuning-set pass is **provisional**; only S2-12 counts.

**Held-out data.**
1. `stage2/gate/gate_holdout.txt` (431 logs of both Marks): excluded by filename from any training corpus. The current opponent recipes use pro data (inside `gen_v32_s0`) and SIM RL only, so they are clean.
2. Train vs gate deck pools: `decks_live_train.json` (and its Hog subset) for training; `decks_live_eval.json` / `decks_hog_eval.json` for the gate. Both were built 10-15 15:01, before CXXIV went live (a).
3. Opponent seed split: the successor trains against seed A and is scored against seed B.
4. Sealed block (S2-12): the current 117 + 300 matches are the tuning set; the next ≥ 150 graded 13k matches are the test set, with one look.
5. The 13k level table uses levels only, never results.

## 4. First 24 h schedule (EDT)

Pods:
- P5 = 81.27.69.177:23408 (new)
- P6 = 64.247.206.79:10757 (new)
- F1 = 81.27.69.177:23363
- F2 = 64.247.206.79:19400
- F3 = 216.81.245.71:34210
- F4 = 216.81.245.71:29286

F1–F4 are free from about 07:30–08:30. Before F4 is reused, `fresh_succ_ctl` and the gap13k probe on 29286 must be finished and copied back (S2-14's control).

| Time | Laptop (light CPU) | P5 | P6 | F1 | F2 | F3 | F4 |
|---|---|---|---|---|---|---|---|
| 23:00–00:00 | S2-02, S2-03; start S2-04 | S2-01 | S2-01 | (factorial) | (factorial) | (factorial) | (factorial) |
| 00:00–00:45 | S2-04, S2-05 | S2-07 smokes (both arms, about 40 min) | S2-06 B1–B4 | | | | |
| 00:45–03:25 | (idle; live runs) | S2-07 `s2_hog_il` 65 upd | S2-06 B1–B6 (to about 03:30) | | | | |
| 03:30–06:10 | | S2-08 for `s2_hog_il` (5,760 games, to about 05:15); then B confirm at 1,920 if any candidate is near | S2-07 `s2_hog_e4` 65 upd | | | | |
| 06:10–07:15 | | S2-08 for `s2_hog_e4` (half) | S2-08 for `s2_hog_e4` (half) | | | | |
| 07:30 | **Phase C verdict** → choose D recipe; `merge_rows` readout | S2-11 (b) drift (CPU) | auto-stop if nothing queued | free → S2-09 smoke | free → S2-09 smoke | free → S2-11 (a) read logs; idle → auto-stop | verify copy-back of `fresh_succ_ctl` |
| 08:30–13:45 | | | | S2-09 seed A 130 upd | S2-09 seed B 130 upd | S2-10 on seed A u0060 at about 11:00 | S2-10 on seed A u0100 at about 12:45 |
| 13:45–16:30 | | | | S2-10 seed A u0130 (split) | S2-10 seed B at chosen ckpt | S2-10 seed A u0130 (split) | auto-stop |
| ~16:30 | **First full two-band gate verdict** | | | | | | |
| 16:30–22:30 (only if pass) | freeze candidate hash into FROZEN.txt | | | S2-13 re-score (1.2 h) | S2-14 arm 65 upd | S2-14 control twin if hashes differ | |

Rules for this schedule:
- Any pod without a queued next job auto-stops (stop-idle-pods rule).
- No two GPU jobs on one pod.
- If Phase C gives "neither passes", F1/F2 run the one diagnosed iteration (for example opponent tower-damage shaping, ledgered) in place of S2-09, and the full gate slips about 6 h.
- The sealed block (S2-12) starts whenever the live-logger fix lands, independent of pods.

About 31 pod-h in the first 24 h, plus about 7 if S2-14 runs.

## 5. What the owner should expect, and when

| When (EDT) | What | Honest expectation |
|---|---|---|
| ~01:00 | Discord: pods up (or key refused), smokes pass/fail with timed s/update, S2-04 live-side audit | 50/50 (b) whether our own overtime and regulation play explains a large share. If it explains at least half, part of Stage 2 becomes a live-path fix. |
| ~03:30 | Phase B: 6 cheap options | All fail, mainly on non-Hog regulation (b, prediction). A pass would be good news and would also show the gate is weak. |
| ~07:30 | Phase C: is imitation needed for a realistic Hog opponent? | Most likely both arms beat CXXXVIII more often but win by stalling (overtime share too high), like the old exploiter (b). The imitation start should have a lower style distance (b). |
| ~16:30 | First full two-band gate verdict for one all-style opponent | Likely a fail on at least one cell the first time (b). Per the brief, "it cannot reproduce live" is itself a finding, and the diagnostics will say which gap (regulation vs Hog overtime) remains. |
| ~22:30 (only if pass) | Successor arm SIM results; re-score of the old exploiter arms | Prior is c-leaning: four exploiter-league tests were null. Live A/B only on your go. |
| Day 2–3 | Sealed block verdict (≥ 150 graded 13k matches after the logger fix, about 12 h of 13k play) | This is the only result that counts as confirmation. |

## 6. On loosening the leash

- **I agree with the direction. Two facts change the reasoning.**
  - **(a) There is no permanent pro-player leash today.** The KL is to each run's own starting checkpoint (`self.ref = copy.deepcopy(self.model)`, `rl_royale.py:3088`; `kl_target 0.10`, `rl_royale.yaml:122`). CXXXVIII is anchored to u250, u250 to u65, and so on. Every chained run re-anchors, so drift from pro play already accumulates without limit. The only pro anchor is the opt-in `kl_ref_gate` (F6), which CXXXVIII does not use.
  - **(b) The leash may not be binding at all.** In league1 the KL weight sat at its floor (0.03) and KL stayed under target (0.016 → 0.076). If that holds for the current runs, loosening `kl_target` would change nothing. S2-11 measures it before anyone plans loosening steps.
- **(c) Collapse is the wrong detector.**
  - The current SIM is already exploited with no visible collapse: the SIM says about 66% vs Hog, live is 29%, with the leash on.
  - Collapse can also come from the optimiser in a perfect SIM: entropy collapse, value error, self-play cycling.
  - The detector is the SIM-predicted vs live win-rate gap on a sealed block. A widening gap means the environment is exploitable: fix it, and do not loosen further.
- **Proposal.**
  - After the Stage-2 opponents pass a sealed block and fight parity reaches the 97.5% goal, step the learner's `kl_target` 0.10 → 0.2 → 0.4 → off.
  - One step per experiment, each vs a control twin.
  - Each step must show a SIM gain on the Stage-2 gate opponent **and** a live result inside the SIM's predicted interval.
  - S2-11's drift measurement tracks how far each step moves from pro play.
- **The opponents keep their leash.** Their imitation anchor is what keeps them human-like. An unleashed opponent becomes an exploiter, as the 80.4% overtime-share run showed.

## 7. Notes for the lead
- The owner's pod commands name `~/.ssh/id_ed25519`, which does not exist on the laptop (a). Use `runpod_clashbot`; whether the new pods accept it is untested (b).
- Design 1 reported an orphan `find.exe / -maxdepth 6 -name jni_bridge.cpp` (PID 39240, started 17:32) burning a core. It is not Stage 2's to kill; check it with `pgrep`-style verification and kill it in a separate command (pkill self-match trap).
- No commits were made and no pods were used in this phase. Only this file was written.
