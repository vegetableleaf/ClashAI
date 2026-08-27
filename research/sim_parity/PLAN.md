# Sim Parity — Phase I completion: I4 → I5 → features (I6-I10)

## Context

Research is frozen (`research-frozen-2026-08-26`) and adjudicated (all 14 R2 decisions + rulings
1-10 in `research/sim_parity/decisions.md`). Done on branch `sim-parity` (worktree
`C:\Users\benpe\ClashBot-parity`): the 7 pulled-forward engine items (`50a15de`..`9f0e19d`), E1 by
measurement (`c460939`), I3 evolution restock — 1000/1000 decks field a real evo, 0 phantoms, 42/42
in rotation (`9a57aef`), I1 backport — `engine.py`/`cards.py` now **byte-identical** across decks
(`8ca6aa5`), I0 parity harness verified-to-fail (`be47ddd`). Suites: icebow **773 OK**, hogeq at its
exact 42-failure baseline. The live tree still runs the PPO untouched.

**Owner sequencing rule (this session):** the PPO is NOT restarted until implementation is 100%
complete. When the 40k run finishes on its own: final eval + Discord report, then training sits
idle. Merge `sim-parity` → `main` only at 100%; the merged restart is that experiment's ONE change.

**New owner rulings folded in:** Boss Bandit's Getaway Grenade becomes an opponent-AI decision
(the engine's HP auto-trigger models a rule the game removed); heroes are ALWAYS fielded when a
deck has a candidate; the WILD slot gets a chance of a second evo, a second hero, or neither
(distribution mine to choose — see I8); hogeq's 42-failure test debt is IN scope (I10).

Everything below happens in the worktree. Two-deck discipline enforced by `tools/parity_check.py`
at every gate. Never stage `*/data/`. One commit per coherent step, measured before/after in the
body. Discord report at each stage transition.

---

## I4 — Importer hardening (before ANY re-import; ~1 day)

File `src/clashrl/card_import.py` (byte-identical pair; keep it so). Exact hooks (explored):

* **CLI**: `cli.py:563` has NO arguments today; add `--dry-run` (default when interactive),
  `--write`, `--force-field key.field`. Fix the stale help string ("RoyaleAPI open data" → Fandom).
* **Dry-run/diff**: before the write at `card_import.py:524-533` — the importer never reads the
  existing file; load it (guarded `path.exists()`) and print a field-level diff; `--write` gates
  the overwrite. Extend the existing `:535-547` summary idiom.
* **Allowlist**: `config/import_allowlist.json` (byte-identical pair), generated from the frozen
  registry (42 evos + 16 live heroes + announced set with dates). Hook after the removed-cards
  subtraction at `:498` where the page set is last a plain list. Emitting a key outside it = hard
  error naming the key. Announced content (mega_knight/battle_healer heroes 7 Sep 2026; the
  API-forward-declared berserker/giant evos) present with `status: announced` so the error message
  can say *why*.
* **Hero scrape**: extend the walk with `/Hero` subpages (mirror the `_EVO` filter at `:348-349`
  and the uncategorized probe at `:469-485` — remember the Elite-Barbarians trap: live subpages
  can be UNCATEGORIZED, so probe `<base>/Hero` for every base). Emit `<base>_hero` rows (body
  deltas + whatever vardefines exist; ability numerics that only exist in prose stay null for
  I8 curation).
* **Pins**: `config/import_pins.json` (byte-identical pair) from the adjudicated ledger — the 5
  balance-lag pins + everything `verdict: pin` (66 rows) + owner-verified values (MM
  `ability_bomb_damage: 332`, spark 48 family...). Applied as a post-pass over `out` between
  `:517` and `:533`; refuses `--write` if a pinned field would regress or a `verified:true`-backed
  value changes without `--force-field`.
* **Provenance**: widen `_wikitext()` (`:356-357`) to `prop=wikitext|revid`; attach
  `_src: {revid, fetched}` per row AFTER the `:449` non-null filter. Two caveats from exploration:
  add `_src` to `CardDB.deck()`'s evo-overlay skip tuple (`cards.py:453-461`) so base provenance
  survives, and write the file ONCE + copy to the other deck (parity_check demands byte-identity —
  no per-deck regeneration of `fetched`).
* **E2 closed here**: declare `lifetime_s` properly in the mechanics import instead of the
  undeclared pass-through (`tools/import_mechanics.py`), so a blanket fix can't silently change
  tesla 30→25.
* **crown_damage_audit.py**: fix the regex (`of (?:the|its) full damage`), extend `CARDS` with the
  evolutions, and port the tool to hogeq (it is icebow-only). It must FAIL on the known-stale set
  before I5 and pass after — that's its negative control.
* **Offline fixtures**: follow the established idiom (`test_r2_engine_schema.py:373-394` reads
  `research/sim_parity/webcache/` with skipTest-on-missing — no new fixtures dir). Required
  negative control: an announced-but-unreleased Evolution page must NOT produce a row.

*Gate:* fixture suite green; live `--dry-run` diff reconciles with `stat_diffs.jsonl` verdicts
(any surprise = stop, investigate); crown audit red-then-green demonstrated; parity_check green.

## I5 — Data application from the adjudicated ledger (~1 day)

Apply script `research/sim_parity/scripts/i5_apply.py` consuming `ledger/stat_diffs.jsonl` +
`ledger/r2_buckets.json` + the decisions.md row rulings. NB bucket rows carry a REDUCED schema
(no `proposed`/`verdict`, renamed probe fields) — re-join to stat_diffs on `(key, field)`.

* The **101 `update` verdicts** + adjudicated buckets: KBGAP 110 (additions incl. three_musketeers
  damage — already partly landed by the engine batch; ram_rider slow duration landed; apply the
  rest), LAG 77, CROWN 15, PARENT 7, ROUNDING 10 (adopt wiki floor()), DUP 13 (merge's pick),
  NAMING 2. Route: guarded `cards-import --write` for import-owned fields; direct `cards.yaml`
  edits for curated/prose values using the house citation styles (dated comment + superseded value
  named + `verified: true`; shrink the `[verify]` marker set — that is the established idiom).
* **Row rulings** (decisions.md "#5/#9/#10/#12/#14" lists are the spec): tesla common +
  tesla_evo hp 1182; earthquake 81; bomber common; MM 332 (+ delete the false "not published"
  comment); firecracker_evo wiki values incl. spark 48 + split durations; giant_snowball_evo
  air+ground **with** the `rolls` derivation fix (E4 — flip `attacks` and the ground_only-derived
  roll together, tests proving roll_len stays 4.5); cannon_evo 281; mortar/mortar_evo 4.7s;
  phoenix 3.8s; royal_ghost 1.8s re-cloak; fisherman slow REMOVED; royal_delivery crown damage
  DISCARDED + 12% on spawn damage; goblin_cage sight→lifetime semantics; lumberjack_ghost 4.5s
  rage-pool lifetime + untargetable/damage-immune-but-knockbackable (engine flags exist);
  goblin_curse 35/s × 6s zone; UNPUB rows tagged `unsourced: true` (keep sim values).
* **Per-card `chain_tiles`**: new KB field + CardSpec plumb; `_CHAIN_TILES = 3.0` becomes the
  fallback; ED family = 4.0 per the three-page evidence (decision #6).
* **stat_sweep --all**: implement (iterate `env.db.cards`, not the pool union — `:101-108`);
  harden `page_for()` for full-DB coverage; sync `EXPECTED` (`:64-71`) to the pins file so pins
  are the single source of deliberate deviation; fix the `and ours_hp` truthiness skip that hides
  legitimate zeros. `cards.yaml` meta block bumped (updated/stats_source, both stale since 07-24).

*Gate:* `stat_sweep.py --all` green in BOTH decks (0 unexplained at 2%); crown audit green; real
null-hitpoint gaps = 0; suites at baseline; parity_check green.

## I6 — New evolutions (0.5 day)

R1a found zero missing evos beyond the KB's 42; the work is `elite_barbarians_evo` re-sourced from
its live (stub) page replacing the announcement-authored row — pull what exists, keep the rest
null+`[verify]`. Allowlist updated in the same commit. `tests/test_evo_wave4.py` per house style.

## I7 — Champion abilities, enemy-side, full fidelity (~2-3 days)

* **`ability_kind` dispatch**: CardSpec gains `ability_kind` + the ~10 generic params; engine
  registry `ABILITY_KINDS: {kind: handler}`; `champion_ability()` becomes the dispatcher. Today's
  truthiness dispatch (`ability_bomb_dmg > 0` at `:1502/:2428`, `ability_invis > 0` at `:2435`)
  migrates: mighty_miner → `bomb`, boss_bandit → `movement_flight`.
* **Ruling-5 fix (live bug)**: `champion_ability` (`engine.py:1501-1504`) picks the OLDEST body
  (`next()` over append-ordered `self.units`). Fix: select the NEWEST living champion body FIRST
  (deploy-sequence tag on Unit), then test cd/uses/elixir — a spent newest body must NOT fall back
  to an older one (that fallback is exactly what ruling 5 forbids). Test with two coexisting bodies.
* **Ruling-7**: elixir refund when the body dies between activation and effect resolution (during
  `ability_delay`) — currently absent.
* **Boss Bandit (new ruling)**: remove the engine HP auto-trigger; the ability becomes a normal
  button; `ScriptedBot._try_ability(eng)` decides — per-kind default heuristics (defensive kinds:
  body under threat / ≥3 enemies within 4t; escape kinds: HP low OR overextended past the river;
  offensive kinds: mid-push near a tower), KB-overridable via `ability_ai:`.
* **The 6 unmodeled champions** from frozen `abilities/*.yaml` at FULL fidelity: archer_queen
  `stealth` (+attack buff — resolve the three-way buff conflict by the level-table formula, the
  file documents all three), golden_knight `dash_chain` (THREE terminators incl. Crown-Tower stop;
  analog dash speed 500 marked untested), skeleton_king `soul_bank` (souls stop accruing post-use,
  ruling 8), little_prince `guardian` (Royal Rescue — Guardienne fully specified: 1600/217/1.2s,
  ground-only, permanent), monk `reflect` (real projectile reflection per the structured
  reflection_rules block; 25% crown rule + Barbarian Barrel exception), goblinstein `zone`
  (Lightning Link; stats flagged stale post-4/8/2026 — apply the I5-corrected numbers).
* No hand-lock (ruling 4). Head shapes pinned unchanged (icebow 10, hogeq 11) — enemy-side only.
* One bare-engine test per champion, wiki + ruling cited. Open geometry questions (Goblinstein
  link "2 tiles from what") get implemented from the recorded evidence with the choice documented
  in the test docstring, or land on the owner's in-game queue if genuinely undecidable.

*Gate:* all 8 champions work in enemy hands via `_try_ability`; hogeq's existing ability tests
green; checkpoints still load (head-shape assertion).

## I8 — Heroes, enemy-side, full fidelity (~4-6 days, the largest block)

* **KB rows**: `<base>_hero` via the I4 scrape + curation from the 16 frozen spec YAMLs (numbers
  with sources; prose-only params curated with citations; open_questions → `[verify]` markers).
* **Slot model (owner ruling, this session)**: dedicated Evolution slot = current I3 behavior
  (always one, uniform over candidates). Dedicated Hero slot = ALWAYS field one when the deck has
  a candidate (uniform). **Wild slot** = second evo / second hero / neither at **1/3 each**
  (renormalized over what remains available; wild-evo ≠ slot-evo, wild-hero ≠ slot-hero), drawn
  from the bot RNG per match; knobs `sim.wild_evo_prob`/`sim.wild_hero_prob` (documented as
  UNMEASURED choice, tunable when a source exists). Mirror the I3 wiring exactly:
  `meta_decks.py` gains `has_hero`/`hero_candidates` beside `has_evolution`/`evo_candidates`
  (`:67-90`), loader validate-don't-trust, `opponents.py` constructor + factory (`:418-419`).
* **Engine handlers by shape family**, ordered by candidate frequency, all full fidelity:
  summon ×5 (banner reinforcements, auto-turret, tombstone queen...), dash_chain ×3, buff_self ×3,
  zone ×2 (blizzard slow), taunt_shield ×2, movement_flight ×2 (fire tornadoes reuse the vortex
  machinery), stealth, throw_displace (throw-heaviest reuses hook/knock machinery),
  transform_levelup (pancakes), guardian/bomb/reflect/soul_bank shared with I7 kinds. Refund rule
  applies (Heroes page documents it; ruling 7 extends it).
* `_try_ability` covers hero kinds. `support:` (tower troop — measured per deck, currently INERT)
  gets consumed in the same pass: `opponents`/tower-roll wiring to field the deck's measured tower
  troop instead of the config-level random roll, since the machinery (`Tower.troop` variants)
  already exists.
* Detector taxonomy already lists all 16 heroes + abilities; detector RETRAINING stays out of
  scope (flagged).

*Gate:* every live hero implemented + tested (per-family tests + slot tests: always-one-hero,
wild distribution reproducible under seed, caps respected); evo_audit extended to hero slots;
suites at baseline.

## I9 — Cross-cutting gaps (~1-2 days)

Friendly-target spells: `_resolve_spell` own-team path — rage buff (now that its KB row is
honest), heal_spirit heal, clone per meta frequency (mirror only if the pool fields it — measure,
decide, record). `drill_env.py` evo cycling mirroring env.py's machinery. sim_view draws chain
arcs + ability projectiles (the debugger-invisibility that fed the original chain report).
perception.py hogeq TypeError (the DRIFT-list live bug: threat-gate memory fix silently inert).

## I10 — Closeout + hogeq debt + landing (~1 day)

* **hogeq test debt to ZERO** (owner: in scope): the 42 pre-existing failures are icebow-card
  lookups + inert `xbow_*`/`rocket_*`/`nado` reward terms (§6.9). Port/parameterize the tests,
  strip the dead terms. Both suites end green — hogeq's baseline stops being "42 knowns".
* Full gates: both suites, `stat_sweep --all` both decks, parity_check, evo_audit (+hero),
  crown audit, negative controls, head-shape assertions.
* Docs: EVOLUTIONS.md / SIM_FIDELITY.md status sections; HANDOFF gets the Phase-I ledger;
  decisions.md deferred items reviewed with the owner.
* **Landing (owner rule)**: merge `sim-parity` → `main` ONLY when everything above is done AND the
  40k PPO has finished on its own. No new PPO before the merge; the merged restart = the ONE
  training change. When the 40k waiter fires mid-implementation: final eval (bench + spell/rocket
  probes on a COPIED checkpoint), Discord report, leave training idle.

---

## Verification summary

| Proof | Mechanism | Stage |
|---|---|---|
| Importer cannot invent content | allowlist hard-error + announced-page fixture control | I4 |
| Curated values survive import | pins + refuse-on-regression + round-trip fixture | I4 |
| Crown audit actually detects | red on known-stale set, green after apply | I4→I5 |
| Stats correct everywhere | stat_sweep --all, pins = only deviations, both decks | I5 |
| Ability per wiki+ruling | bare-engine test per champion/hero, citations in docstring | I7/I8 |
| Newest-body + refund rules | two-body coexistence tests | I7 |
| Slot model honest | seeded-RNG distribution tests; caps respected | I8 |
| No checkpoint break | head-shape assertions (icebow 10 / hogeq 11) | I7/I8 |
| Two-deck parity | parity_check at every gate | all |
| No PPO contamination | all work in worktree; live tree `git status` clean | all |
| hogeq suite green | 42 → 0 pre-existing failures | I10 |

## Risks

Import regression reverting curated values (pins + dry-run default); hero ability scope (16 novel
mechanics — family handlers + frequency order; fidelity never cut, only order); wild-slot
distribution is an unmeasured choice (knobs + documented); Goblinstein/AQ intra-page conflicts
(implement from recorded evidence, document the choice, owner queue if undecidable); champion
two-body edge cases (dedicated tests); the 40k PPO finishing mid-work (handled: eval + idle).

## Sizing

I4 ~1d · I5 ~1d · I6 ~0.5d · I7 ~2-3d · I8 ~4-6d · I9 ~1-2d · I10 ~1d ≈ **10-14 working days**.
Deferred (unchanged): our-deck heroes/champions, waypoint pathing, detector retraining for hero
classes, hero drills, `import_mechanics.py` modernization beyond the E2 declaration fix.
