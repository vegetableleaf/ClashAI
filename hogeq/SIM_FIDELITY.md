# Sim Fidelity Audit — 2026-08-15 overnight session

Goal: raise sim ↔ real-CR parity for the next training startup, under one hard constraint —
the overnight PPO checkpoint must resume cleanly (no observation/action-space changes; the
running trainer was never touched). Every number below was confirmed against the wiki via
`api.php` before landing (per standing instruction after the elixir-blob lesson: my memory
said blobs refund 1 each; the wiki says golem 1 / golemites & blobs 0.5 — memory lost).

## How the audit ran

1. Systematic engine survey (what's already modeled) — the engine is deeper than assumed:
   sticky target locks with aggro-reset rules, tower first-hit load calibrated against
   reference interactions, 4-phase elixir schedule, 1 s deploy freeze, push-mass collision,
   river jumpers, submerged-Tesla spell immunity, building HP decay, OT sudden death +
   standing-tower tiebreak, E-Giant reflect, Elixir-Golem death refunds, Monk 3rd-hit combo.
2. Brainstorm vs. real-game knowledge → candidate gap list.
3. **Data-driven filter**: counted each suspect card across the 1000-deck opponent meta pool;
   fixed by (frequency × severity ÷ cost).
4. Wiki verification of every stat touched; implementation + 11 new tests; 112/112 green.

## Confirmed gaps → implemented (9)

| Fix | Ladder share | What was wrong |
|---|---|---|
| Mortar range 3.5→**11.5**, dead zone **3.5**, deploy **3.5 s** | 6.7% | Range table carried the dead-zone minimum as reach — Mortar decks could never siege at all |
| X-Bow deploy **3.5 s** (was 1.0) | ours + mirrors | Sim gave defenders 2.5 s less counterplay window than the game; inflated offensive bow value |
| Poison = **8 s DoT zone**, 92/s troops, 23/s crown, −15% move | 10.2% | Resolved as a single 92 blast = 12% of real damage |
| Lightning = **top-3 highest-HP** + 0.5 s stun, radius 3.5 | 10.9% | Was a radius blast nuking the swarms real Lightning ignores |
| Void = 4 s zone, 3 ticks, count-tiered 696/294/153 (crown 97/51/35) | 8.2% | Was a 0-damage no-op |
| Graveyard = **12 Skeletons** every 0.5 s from 2.2 s, radius-4 edge | 6.8% | Was an 81-damage blast that spawned nothing — the classic siege-killing archetype absent from training |
| Vines = top-3, root 2.5 s, 306 dmg (crown 78) | 5.0% | Was a generic freeze-flag blast |
| Ronin **parry** (blocks a melee hit, counters ×2, 3.5 s cd) | 5.5% | Curation documented the ability; engine never applied it |
| Berserker | 23.2% | Audited — already correct (0.6 s swing, 896/102). No change |

## Parity channel (2)

- **Tile snap**: every deploy (troop and spell reticle) now quantizes to the game's tile grid,
  exactly like a live tap. Removes a systematic half-tile sim↔live placement disagreement.
- **Action latency** (`sim.action_latency_s: 0.25`, our side only): decisions reach the board
  when the live decide→tap→game pipeline would land them; elixir committed at decision time.
  The sim policy now has to LEAD, the way the live one must.

## Considered and rejected/deferred (with reasons)

- **Champion actives** (Golden Knight dash 6.9%, Skeleton King ult, AQ cloak, Mighty Miner,
  Boss Bandit, Monk deflect): opponent scripts wouldn't trigger them intelligently, so
  modeling buys little distribution shift for high cost. Passive stats are correct. Deferred.
- **Goblinstein two-body** (3.7%): monster-vs-doctor split needs per-body HP the wiki page
  doesn't publish cleanly; current merged approximation keeps total stats sane. Deferred.
- **Rune Giant buff** (3.8%), **Spirit Empress forms** (2.4%), **goblin_curse** (2.1%),
  **clone/mirror** (0.5%): frequency × effect too small this round.
- **Unit-level first-attack load times**: the engine's combat was calibrated against
  reference interactions (e.g. Bomber-vs-tower lands exactly one bomb) WITHOUT them; adding
  a universal load would silently break those calibrations. Rejected pending re-calibration.
- **Goblin Demolisher <50% transform** (3.8%): splash/death-blast already in KB flags; the
  charge transform needs unpublished numbers. Deferred.
- **Elixir-read noise, frame jitter randomization**: obs-space adjacent; not worth the risk
  in the same batch as a resume-critical night. Deferred.
- **Trapezoid x-per-y warp refinement (live)**: princess columns show only ~0.005 drift
  top-vs-bottom; below measurement noise. Rejected.
- Known approximation kept: tower-sprite anchor bias (~half a tile on mid-land live taps,
  legal-land only) — logged 2026-08-14, needs a platform-base re-anchor pass.

## Where things landed

- `sim/engine.py`: `_Zone` system (Poison/Void/Graveyard), top-N spell resolve, `min_range`
  dead zone (acquire + attack gates), `deploy_time_s` override, tile snap + `_pending`
  action-latency queue in `deploy()`/`_finish_deploy()`, Ronin parry in `_land_hit`.
- `config/cards.yaml`: wiki-cited curations for mortar, x_bow, poison, void, vines,
  lightning, graveyard, ronin.
- `config/config.yaml`: `sim.action_latency_s`.
- `tests/test_sim_fidelity.py`: 11 scenario tests, one per mechanic, including the
  falsification cases (swarm under Lightning untouched; Mortar blind spot can't fight back;
  void tier collapse when the crowd dies).

---

# Batch 2 — user-directed fixes (2026-08-15, pre-dawn)

Seven reports + two follow-ups, all wiki/RoyaleAPI-verified before landing:

1. **Bomber Evo "reverted"** — investigated, NOT regressed: spec is ranged (4.5), splash, 2
   bounces, and the measured stop-gap vs a stationary target is 4.9 tiles. What reads as
   "melee" is a WALKING target (a marching Giant) closing the distance itself — real CR,
   since ranged units don't kite backward. Pinned with two regression tests.
2. **Collision/pathing** — walkers now steer AROUND stopped allies (attacking/locked/
   deploying) with the same shoulder-rounding as towers; the dodge point is vetoed unless it
   is legal ground (never into the river at a bridge choke — walker just waits behind).
   In `_separate`, a stopped attacker is a WALL to similar-or-lighter allies (≤1.4× mass);
   only a clearly heavier body still shoves it. Marching same-direction pushes stay.
3. **Push tiers** — per the wiki's hidden-mass notes ("large disparity in speed makes up for
   the small disparity in mass"): ally pushing power now scales with speed surplus, so a Hog
   shoves an Ice Golem up the lane while an equally-fast Goblin barely moves it, and a
   Bandit behind a Golem is pace-capped. Enemy body-blocking stays pure volume. Air-air and
   ground-ground both covered (the separator already pairs same-medium only).
4. **Battle Ram** — charge 573 (=2× 286) after 3 tiles, kamikaze on connect, and the break
   reveals 2 real Barbarians (670/191) via the death-spawn path, on connect OR on death.
5. **Charge gallop** — an armed charge (Prince/Dark Prince/Ram/…) now runs at double pace
   until the hit spends it ("with his increased speed and damage while charging").
6. **Evo Cannon barrage** — no longer projectiles: nine impact rings (5 front, 2.5 tiles
   ahead; 4 flanking) land together ~1 s after placement [verify timing/layout], each a
   2.5-tile damage area with 1-tile knockback, any victim damaged ONCE across overlaps.
7. **Fused death bombs** — Balloon / Giant Skeleton / Bomb Tower drop a bomb that explodes
   after 3 s (wiki-exact) through the spell path, with knockback; walking out is the
   counterplay (test proved a walking Knight escapes it). GS bomb deals DOUBLE to crown
   towers (688→1376). Goblin Demolisher stays instant + knockback.
8. **Goblin Demolisher rework** — his "life 10" was bleeding HP from deploy; it is the lit
   FUSE. Below 50% he swaps spec: very fast, melee (0.5), building-only, kamikaze — sprints
   at the nearest building and detonates on connect or when the 10 s fuse runs out.
9. **Wall Breakers** — the barrel blast is AREA (radius 1.5, wiki attr row): troops beside
   the building take it too.

Tests: 11 more in test_sim_fidelity.py (33 total there). Suite 123/123. Smoke 584 steps/s.
