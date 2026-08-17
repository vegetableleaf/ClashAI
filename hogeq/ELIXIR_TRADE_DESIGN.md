# Design: live `elixir_trade` as a two-sided resource potential (delayed settlement)

**Status: design only — not implemented.** This is repair item "fix `elixir_trade` credit
assignment" from `log.txt` 2026-08-12 / the README's planned list. Written 2026-08-12; implement
as its own gated change (nothing else in the same batch), after the current from-scratch sim run
has been judged on placement spread.

## 1. The problem, measured

The live `_trade_reward` (env.py) is still the OLD shape:

```
reward = clip(Δ enemy red-pixel mass) − elixir_spent / value_norm
```

Two independent failures, both measured:

* **The spend half is a flat tax on acting.** It does not telescope — it accumulates at
  −0.1/elixir forever. The sim measured the consequence before its rework: −10.17/match, **0 of
  40 matches positive**, play-steps scoring 52 up vs 1459 down, and a winrate that plateaued from
  match 3000 to 9500 while the policy sat at the balance point between the win signal and the
  spend tax. Live, over the 5-match diagnosis run, `elixir_trade` was the largest term at −22.6
  (76 pos / 140 neg fires). This is the same action-tax shape that collapsed three runs.
* **The mass half bills the agent for things it did not do.** It fires every step and credits or
  charges ambient enemy-mass change: towers killing troops, troops expiring, and — worst — the
  OPPONENT deploying, which reads as a penalty against *us*. Credit assignment is essentially
  random with respect to the agent's own play.

## 2. What the sim already became (mirror target)

The sim's `_trade_reward` was reworked (2026-08-12, sim/env.py) into a **true potential over both
sides' resources**:

```
Φ = [ V_board(mine) + E_bar(mine) − V_board(theirs) − E_bar(theirs) ] / value_norm
reward = w_elixir_trade × clip(Φ_t − Φ_{t−1}, ±trade_cap)
```

where `V_board` is each living unit's deck cost split across its bodies, scaled by remaining HP.
Properties that matter (all argued in the sim docstring):

* **A deploy is a transfer, not a loss** — elixir leaves the bar and becomes board value, so a
  play scores exactly zero at the moment it happens; only its *consequence* moves Φ. This is the
  "delayed settlement" the README asks for, expressed as a potential instead of per-play windows.
* **The opponent's deploys also net to zero** (their −bar +board cancels), so their push no longer
  reads as a penalty against us.
* **It telescopes** — Σ Δ Φ = Φ_end − Φ_start — so neither idling nor spamming can farm it.
* `train.n_step: 3` + γ already carry a settled consequence back to the causing action; no extra
  machinery is needed for credit transport.

The live rework = translate Φ to live perception. That is the whole design question.

## 3. Live Φ: what each piece maps to

| Sim quantity | Live source | Quality |
|---|---|---|
| `E_bar(mine)` | `Vision.read_elixir` (bar pips) | reliable, calibrated |
| `E_bar(theirs)` | `OpponentElixirEstimator` (mirrored spend accounting; already wired as obs slot `mem[5]`) | estimate; self-correcting on observed enemy plays, drifts when the detector misses deploys |
| `V_board(theirs)` | detector tracks tagged `enemy` (TeamTracker/PerceptionLoop) × KB elixir of the card | recall-limited; flickers on missed reads |
| `V_board(mine)` | own plays are **ground truth** (card + cost + time known exactly); detector tracks tagged `mine` confirm survival | good: spawn known; death read from track loss |
| per-unit HP fraction | **not observable live** (no per-troop bars readable) | approximated — see below |

Approximations, stated up front:

* **A unit counts at full value until its track dies.** The sim scales `V` by HP fraction; live
  cannot. So live Φ settles a kill *late* (at death) rather than smoothly — a step function per
  unit. Acceptable: the per-step clip (`trade_cap`) bounds each step, and the *sum* over the fight
  is the same elixir value.
* **A track's value = the card's full KB elixir** (not split per body). Live squad detections
  (skeletons, recruits) usually box as one unit or an unstable count, so per-body accounting would
  be noise. One track = one card's worth is the honest resolution the detector actually has.
* **`E_bar(theirs)` drift**: the estimator under-counts spends it never saw. Since Φ *subtracts*
  enemy elixir, a missed enemy deploy would wrongly hold their bar high — but the same miss also
  fails to add their board value, and the two errors **cancel in Φ** (that is the transfer
  property doing the work). The residual error is only their regen while the estimate is pinned
  at the 10-cap wrongly — small and bounded.

## 4. Perception-validity gate (the live-only rule)

The sim never has an unreadable frame; live does. The rule, consistent with the 2026-08-12 repair
(quiet-branch deletion + blind-frame spend waiver, both of which this design SUBSUMES):

* **Compute Δ Φ only between two frames with a healthy perception pass** (perception-loop
  snapshot fresh, or a successful synchronous detector pass). On a blind/stale frame, carry
  Φ forward unchanged (Δ = 0). This freezes *both* signs — a measurement-validity gate, not an
  asymmetric term — and preserves the telescope (the next valid frame settles the accumulated
  change, subject to the per-step clip; use a slightly larger clip for a settle-after-gap step,
  or spread it over k steps, to avoid one giant step).
* When this lands, today's interim `_perception_blind` spend waiver is **deleted** — there is no
  spend charge left to waive.

## 5. What this retires

* **The spell-impact sampler** (env.step's `eval_spell` branch): it exists to catch the mass
  change at a spell's predicted impact for the old immediate credit. Under Φ the consequence is
  settled from the ordinary frame stream (the dead enemy tracks disappear over the next 1–3
  frames), so the blocking wait — up to ~3.6 s per cast, the largest cadence outlier this deck
  has, measured under `spell` in the new `[cadence]` line — is deleted outright. (The rocket
  aim/lead assists stay: they are control, not reward.)
* **The interim blind-frame spend waiver** (see §4).
* `defeat_cap` / red-mass plumbing in the trade path (enemy_mass stays for the threat lane read).

## 6. What this does NOT do

* No engine deep-copy — `counterfactual` stays sim-only, per the standing "do not" list.
* No per-play attribution windows with lane/radius heuristics (the README's literal "judge a play
  by what followed it near it"). That shape re-introduces hand-written classifiers with tunable
  attribution knobs — the family that has failed three times. The potential form settles the same
  consequences with **one** mechanism and zero attribution parameters. Fall back to per-play
  windows only if Φ measures too noisy live (gate below), and then only with disappearances
  partitioned across open windows so two plays cannot both claim one kill.
* No weight retune in the same change: keep `elixir_trade: 1.0`, `trade_cap: 1.0`,
  `value_norm: 10` — the units are the sim's, so the sim-tuned weights transfer.

## 7. Implementation sketch

* `env.py`:
  * new `_trade_potential_live()` — sums `E_mine` (bar read), `E_theirs` (estimator), `V_mine` +
    `V_theirs` from the team-tagged track set (`self._ploop.snapshot()` / `self._team_tracker`),
    each track valued at its base card's KB elixir (`CardDB.elixir(base_key)`);
  * `_trade_reward` becomes `clip(Φ_t − Φ_prev, ±trade_cap) × w`, with the §4 validity gate and
    `Φ_prev` reset per match (`reset()`);
  * delete the `eval_spell` sampling branch + `spell_effect_reward` gating (config key marked
    INACTIVE), delete `_perception_blind`;
  * `rw_stats` name stays `elixir_trade` so the JSONL/policy-stats history stays comparable.
* `reward_stats` needs nothing.
* `play.py` unaffected (no rewards there).

## 8. Acceptance gates (all on the standing rules)

Sim side must be untouched (diff-check: no sim behaviour change). Live, over ≥5 measured matches:

1. `elixir_trade` fires **both signs** (pos > 0 — today's live term is the passivity gradient);
2. per-match `elixir_trade` total is no longer the most-negative term by default;
3. a no-play match segment scores ≈ 0 net on the term (telescope check: quiet board drift must
   cancel);
4. plays/match does not fall; mean elixir does not rise; win rate flat or better;
5. `[cadence]` shows the `spell` phase gone (sampler deleted) with no other phase regressing.

If (3) fails — Φ drifting on empty boards — the detector flicker is leaking through the validity
gate; tighten the gate (require N consecutive healthy frames) before touching weights. If (1)/(2)
still fail after that, only then consider the per-play window fallback (§6).
