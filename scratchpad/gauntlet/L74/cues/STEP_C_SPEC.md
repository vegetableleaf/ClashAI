# Step c: visual-cue inputs for the icebow model (owner 10-16)

Goal: give the generalist (GenModel) the per-unit cues a human sees (what a unit is doing, whether it is slowed /
frozen / raged ...), in a way that is SAFE (absent = today, bit for bit) and MEASURABLE (one A/B: the same RL
continuation with and without the cues). Step d = run that A/B on a pod (`run_cues_pod.sh`).

## 1. Fields (one row of `CUE_N = 22` floats per unit token)

Source: `pipeline/sim_unit_state.extract(battle, memo, hit_window_ms=100)` (SIM), the same fields the merged live
reader provides. Encoding = `pipeline/model_gen.py cue_vector(u, target_is_tower)`:

| idx | field | encoding |
|---|---|---|
| 0 | `cue_known` | 1 on every row built from a cue record; 0 = unknown (pad, spell token, unmatched body, imitation row) |
| 1-7 | `state` | one-hot idle, moving, engaged, deploying, jumping, tunnelling, casting |
| 8 | `charging` | 1 = charged (Prince / Dark Prince / Battle Ram) |
| 9 | Tesla hidden | 1 iff `hide == 'hidden'` ('up' / 'rising' / not a hiding building = 0) |
| 10 | `attack.has_target` | `attack.target is not None` |
| 11 | `attack.target_is_tower` | the target is a princess / king tower |
| 12-14 | `attack.phase` | one-hot idle, windup, hit (hit = the hit landed within the last 100 ms, the live 2-tick sampling) |
| 15 | `attack.frac` | progress mod hit speed / hit speed, 0 when phase idle |
| 16-20 | `status` | frozen, slowed, raged, invisible, shielded (0/1) |
| 21 | `status.slow_frac` | remaining / total of the longest slow (per-match memo in the SIM; the reader has the total), 0 if none |

Dropped after S6 (`L74/parity/S6_CUES_1016.md`): `taunted` (the SIM never sets it), `stunned` (stun reads `frozen`),
Rage / Poison buff frac / ms (the live duration accumulates; only the booleans raged / slowed and the slow `slow_frac`
are used), projectile `effect`. Not in v1: projectiles and areas (`extract` has them; a later step adds them as tokens), `charge_frac`, buff names /
remaining ms, `progress_ms` / `load_ms`, hero-ability state beyond `casting`.

## 2. Row alignment (`pipeline/e1_eval.py sim_cue_rows`)

`b["cue"]` is `[MAX_U=64, 22]`, row i = token i of the SAME `tok` the model sees (`to_tokens` order). At each
decision (`Match.gen_row`, the prepared tick) the SIM battle's units (`env.core._battle`) are extracted (per-match memo
`match._cue_memo`), towers dropped (they are not unit tokens), and each UNIT token (mask, not a spell, side mine/enemy)
is matched to a same-side body by position in this side's board frame (`x/18, 1 - y/32`, mirrored for side 1, the
`obs_contract._engine_xy` frame): pairs nearest-first, one body per token, within `CUE_MATCH_TILES = 3.0` tiles (the view
is extrapolated 26 ticks under the live conditions). Unmatched tokens, spells and pads stay 0. No uid: tokens carry
none and the live reader will not either, so live alignment is the same rule (section 6).

## 3. Model (`pipeline/model_gen.py`)

`GenModel.add_cue_in()` attaches `cue_in = Linear(22 -> d, bias=False)`, ZERO-initialised. In `encode_gen`, when the
model has `cue_in` and the batch has `"cue"`, `cue_in(cue)` is added to each unit token's input embedding (a forward hook
on `unit_in` for the duration of that encode; the residual then also flows into the patch tokens as unit embeddings
do). Zero weight -> every output identical; no bias -> a zero row (cue_known 0) contributes exactly 0 even after
training, so imitation rows / unmatched tokens read "no cue" rather than a learned offset.

Loading: `GenModel.load_state_dict` builds `cue_in` when the state dict has `cue_in.weight` (every loader: load_model,
eval_gen, rl_royale actors, e1_eval.load_policy). A pre-cue checkpoint loaded into a model that HAS the layer gets that
ONE key zero-filled; every other missing / unexpected key still fails strict loading.

`e1_eval.gen_row_keys(model)` adds `"cue"` iff the model has `cue_in`, so rows follow the MODEL: a checkpoint with the
layer (zero or trained) is always fed cues (rollouts, screens, search_s0, gap / live-pool evals); one without is
byte-identical to before. A cue checkpoint on a runtime without RoyaleSim >= 0.1.35 fails with a clear
`RuntimeError` (`e1_eval.require_cue_runtime`), never with silent zeros.

## 4. Trainer (`pipeline/rl_royale.py`)

`cue_inputs: on` (yaml bool; override `cue_inputs=on`): the generalist init gets a zero `cue_in` (kept if the init
already has one) BEFORE the ref copy and the Adam, so it is trained by PPO like every other weight, rides to the actors
in the state dict and is saved in every checkpoint. Actors record `cue` per decision (`Match._record` /
`_traj_arrays`, also `branch_row`), `collate` carries it, the learner's forward (`policy_terms`, `trunk_g`, value)
takes it through `gen_row_keys`. Pro-agreement / imitation rows have no cues -> zeros (no dataset rebuild in v1).
Refusals: S1 init ("needs a generalist init"); runtime without the 0.1.35 card table. Absent / null / off = the
historical config hash and code path (tests: `pipeline/tests/test_cue_inputs.py`).

## 5. The A/B (`L74/rlarms/mkcfg_arms.py`, `L74/cues/run_cues_pod.sh`)

* `gae_cue_u250` = arm gae's recipe (5 critic warm-up + 60 policy updates = 65), a FRESH run with `init:` = F1 u250
  (fresh Adam, KL anchored to u250), `cue_inputs: on`. `gae_ctl_u250` = the identical config without the key. The
  yamls differ by that one line (the runner diffs them). Init = `rlarm_gae/rlarm_gae_u0250.pt` if present, else the
  live `rlarm_gae_u0250_grafted.pt` minus its grafted cell_refine / tower_refine (written next to the yaml; its
  projectile_target_* are the live heads, which the graft re-applies anyway).
* Both with `ROYALE_HEROIW_FORM=hero`, runtime `20261016-linux`, `/workspace/venv35/bin/python`.
* Graft source = the live u250_grafted file (its 42 head tensors equal rseries_r3c_u0030_..._w2.pt's, checked
  10-16); `graft_generic.py` keeps every other tensor, so `cue_in` is carried (it prints `cue_in carried: True`).
* Eval: `L74/mix/live_eval_pod.sh` D3 on the live-mirrored pool, seeds 741200 + 742000 (960 paired), both arms.
  Read: paired difference cue - ctl (`L74/mix/live_cmp.py`); a cue layer whose weight stays ~0 means the cues were not
  used (check `cue_in.weight` norm in the final checkpoint).

Pod command (27-CPU pod with the 0.1.35 venv and the data of POD_README + `rlarm_gae_u0250_grafted.pt`):

    cd /workspace/clashbot && nohup bash scratchpad/gauntlet/L74/cues/run_cues_pod.sh > /dev/null 2>&1 &
    # done when /workspace/results/CUES_ALL_DONE exists; log /workspace/results/CUES/run.log

## 6. Live mapping plan (NOT built here; the next ticket)

`pipeline/live_unit_state.py cues(frame)` -> the `extract` schema from the merged reader's blocks, exactly the
mapping already prototyped in `L74/parity/s6/live_cues.py live_cue` and `L74/parity/READER_STREAM_SPEC.md` section 5:
`behavior_state_raw` 4/11 deploying, 3/5 jumping, 6 tunnelling, 10 casting, 2 engaged, 1 moving, 0 idle; charging =
speed >= 1.6 x walk over two consecutive frames, ONLY on cards with a charge row in the card table; hide = raw 0
hidden / 2 up on hiding cards; attack target = the target generation id (tower or not from the tower list), DROPPED
(-> has_target 0, phase idle) when the centre distance to the target body is > max(sight range, attack range) + 1.5
tiles (a path / default target, not an acquired one; S6: target agreement 0.50 -> 0.96; reference
`L74/parity/s6/analyze.py` SIGHT / SIGHT_SLACK and `live_cues.py`); phase / frac from progress, the definition's
HitSpeed and the same 100 ms hit window; status from buff names with `sim_unit_state._statuses`' rules (stun -> frozen;
no stunned / taunted features); slow_frac = remaining / duration straight from a buff, but for AREA slows remaining /
the card table's duration (the live area buff's own duration is not the total); Rage / Poison ms / frac never used. Then per live decision: `cue_vector(u, target_is_tower)` for each reader body, aligned to the
live `tok` rows by the SAME rule as `sim_cue_rows` (side + nearest position in the board frame, <= 3 tiles,
nearest-first, one body per token), and passed as `row["cue"]` in `live_gen_v2` / `live_mem` only when the loaded
model has `cue_in` (a cue model with no cue source must refuse, as on the SIM). A degraded frame (`cues_degraded`)
-> all rows 0 (cue_known 0), never stale cues. Gate before any live use: offline replay of logged frames, the
model's rows with and without cue blocks identical for a non-cue model, and S6-style SIM/live field agreement.

## 7. Laptop runtime (how the smokes / SIM-cue tests ran on Windows)

The laptop's pinned runtimes are royalesim 0.1.13 / 0.1.17 (no 160402017 card table), so `cue_inputs` refuses there.
A composite venv gives 0.1.35 without touching the repo venv:

    S=<scratch>; py313 -m venv --without-pip $S/v35; SP=$S/v35/Lib/site-packages
    cp -r <unpacked royalesim-0.1.35 wheel>/{royalesim,royalesim-0.1.35.dist-info} $SP/
    git -C research/ext/Royale/RoyaleGym archive a7deb6e royalegym | tar -x -C $SP      # = the rt35 pin, 0.1.23
    echo 'C:\Users\benpe\ClashBot\research\ext\Royale\.venv\Lib\site-packages' > $SP/zz_base.pth   # torch, numpy, ...
    ROYALE_RUNTIME=unpinned-linux $S/v35/Scripts/python.exe -m pipeline.rl_royale --config <gae_cue_u250.yaml> \
        --run smoke_cue --smoke advantage=gae critic_warmup_updates=1 actor_device=cpu learner_device=cpu \
        league_decks=scratchpad/gauntlet/L74/mix/decks_live_train.json      # decks_rl.json is pod-only

(`unpinned-linux` = no byte check, the purelib of the running venv; a laptop-only test harness, never for results.)
