Adaptive opponents (explicitly invoked, default off)

PFSP: league_pfsp=hard replaces category mixing with a draw over init, all
retained learner snapshots, external exploiters, and S1 if league_mix.s1 > 0.
Each opponent starts at learner win-score p=.5. Completed matches update
p <- .95*p + .05*score, where win/draw/loss = 1/.5/0. Updates are sorted by
match tag and rollout index, independent of actor arrival order. Sampling
weight is (1-p)^league_pfsp_gamma + league_pfsp_floor, then normalized.
The floor must be positive. Ratings and external paths live in rl.league;
--resume restores them alongside the existing RNG and snapshot list.
league_snapshot_every and league_snapshot_keep reuse the existing mechanism.
External exploiters are not removed when learner snapshots age out.

Styles: opp_style=on draws aggression, lane preference, temperature multiplier,
spell delay and elixir bank from the commented ranges in pipeline/rl_royale.yaml.
A separate RNG seeded by (match seed, rollout index) draws one style per match.
Positive aggression lowers tau; positive lane preference favors the left in
the opponent's own frame. Temperature jitter affects sampling policies (the
live policy is greedy). Extra spell delay is in ticks. Banking waits below
the drawn own-elixir threshold unless a visible enemy body is on our half.
It never forces a play. No hidden opponent hand or elixir enters these rules.
The learner decoder, its temperature, and its PPO action probabilities are
unchanged. Each rollout logs an opponent_style event in train_log.jsonl.
Branch forks use a separate decoder; styles reject branch_gate=true.

Default-off compatibility: optional keys are absent from the YAML mapping
(documented as comments). Explicit off/on YAML booleans are accepted. Disabled
adaptive keys are removed from config_sha, and neither old RNG draws nor
checkpoint league fields change. Adaptive runs require opp_elixir=counter or
counter_all; the weekend driver uses counter for both sides.

Public history finding (no input-width change made):
- pipeline/dataset.py: OPP_PAST_K = PAST_K = 3.
- dataset_gen.opponent_past selects the last THREE accepted public plays,
  newest first, strictly before the observation tick, from the OTHER side.
  From a frozen opponent's point of view these are the learner's plays.
  Features: card, form, position in the observer's frame, and elapsed time.
- e1_eval.sim_v3_features uses this history for feature_version 3. For versions
  4+ it uses PublicObserver.features: causal visible-body/projectile sightings,
  not the engine's hidden hand/elixir or delivered-command truth.
- public_observation.opponent_cycle has EIGHT slots for DISTINCT observed
  cards, with form, subsequent sighting count and age. Repeats do not add slots;
  this is not a sequence of the last eight plays and does not assert readiness.
- model_gen.GenModel.global_features flattens opp_past into global_in, whose
  input width is constructed using PAST_K. Going from 3 to 8 requires a model
  schema/checkpoint migration, dataset/actor changes and compatible retraining.
  It is not a small default-off input change, so the history is documented
  rather than silently padding/changing existing checkpoints. Exploiters train
  the existing memory inputs; effective use of them needs later empirical eval.

Pod run:
  cd /workspace/wk_xl2
  nohup bash scratchpad/gauntlet/L74/weekend/adaptive/run_adaptive.sh > /workspace/adaptive-launch.log 2>&1 &

The worktree at that path must contain these changes and the existing pod data
links. This is a launch command only; nothing was started by this ticket.
The script waits for /workspace/results/wk/ICEBOW_DONE, then takes gpu.lock
before cpu.lock. Serial training/evaluation stages use 20 actors/workers,
leaving process headroom for the learner, orchestration, locks and tracker.

Three cycles: main resumes to updates 20/40/60; each fresh exploiter starts
from rseries_r3c_u0030_barrel.pt and trains 15 updates solely against its cycle's
immutable frozen main copy on the main's icebow deck. Main and exploiter use
terminal win/loss/draw reward with PPO match_loo, no shaping or branch workers.
The fv5 pro-agreement dataset is gen_dataset_v32_fv5.npz; existing training
guards remain active. An early guard stop fails the cycle rather than silently
using an undertrained checkpoint. Each completed exploiter's numbered file is
enrolled in the main checkpoint; cycles.json records frozen hashes and progress.
The third exploiter is enrolled after the final main segment, as specified;
it would first be played by main in a subsequent, separately requested cycle.

The main deck is icebow. Other decks use mk_weighted_decks.py and the weekend
archetype classifier, normalized to 60% unfavourable after removing icebow from
the census. S1's icebow-only bucket is disabled in this driver to preserve that
share. PFSP still includes every init/snapshot/exploiter in the active pool.

Final main gets the old live model's add-ons via graft_generic.py. The fixed
yardstick uses OLD and ADAPTIVE against calibrated set c (E4 add-ons) at T=.1,
unweighted evo and ladder census decks, and exactly the S2/CAL live flags.
Each candidate gets 480 evo games (30000:30480) + 480 ladder (30480:30960),
960 paired games / 1920 total. wk_compare supplies paired intervals and the
per-archetype table. Missing/skipped/duplicate rows or mismatched decks fail
the report. Positive lower CI = improvement shown; negative upper CI = worse;
otherwise improvement is not established. No deployment action exists.

Output: /workspace/results/wk/ADAPT/{SUMMARY.txt,DONE}, including caught failures
and INT/TERM. As with any shell trap, SIGKILL or host loss cannot write output.
On restart, an incomplete evaluation directory is preserved with a .partial_
timestamp before that evaluation is retried (search_s0 requires an empty dir).

Offline verification:
  python scratchpad/gauntlet/L74/weekend/adaptive/check_offline.py
Uses pytest and fake environments; does not import/run RoyaleSim. Windows
temporary test dirs inherit workspace ACLs. One pre-existing multiprocessing
exit test is deselected on Windows because sandbox named pipes are unavailable.
Git Bash and WSL startup were blocked by host permissions, so the shell wrapper
was reviewed statically; bash -n and actual pod execution remain unmeasured.
