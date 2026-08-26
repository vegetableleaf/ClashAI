# Sim Parity — evolutions, heroes, champions, stat refresh (both decks)

## Context

The owner wants the simulator brought to parity with the current game. Today's three-audit sweep
plus live source probes established the ground truth this plan is built on:

- **Phantom evolutions are real and worse than reported.** `build_spec`
  (icebow [engine.py:501-518](icebow/src/clashrl/sim/engine.py#L501-L518)) fabricates a spec for
  ANY `<x>_evo` key — a missing evo row merges nothing and returns the base card wearing the evo
  name. `opponents.py:81-97`'s evo picker's guards never fire, so the opponent's "evolution" is
  always deck slot 0. Measured: **287/400 meta decks field a phantom** (arrows_evo ×80,
  berserker_evo ×56, giant_evo ×6). sim_view labels units by spec key — that is the debugger
  sighting.
- **Heroes are a wholly missing card class.** The 2026 game has hero variants of existing cards
  (`<Card>/Hero` wiki subpages, ≥18 candidates; champion-style elixir-costed abilities; occupy the
  champion/wild slots). The detector taxonomy already carries 16 `_hero` + 16 `_hero_ability`
  classes, but the KB, importer (`card_import.py:29-30` — no Hero category), and engine have zero
  hero support.
- **Champions are mostly cosmetic.** 8 in KB with stats; only mighty_miner has a player-triggered
  ability (hogeq only), boss_bandit an auto-trigger; the other 6 have nothing. icebow lacks the
  entire ability plumbing (`ability_identity`/`policy_identities`/engine path).
- **The importer is a footgun.** `cards-import` is a destructive, diffless full overwrite, and the
  wiki's vardefines lag its own balance history — a naive re-run reverts a month of curated fixes
  (Rocket 341, Lightning 264, Zap 48, Log 35, Poison 21…).
- **Source reliability, measured today:** the official CR API forward-declares unreleased evos
  (claims Berserker/Giant evos that don't exist) AND lags real ones (missing Elite Barbarians evo,
  which is live with a wiki page). The API is an existence oracle for base cards only. Fandom
  api.php works via urllib (page fetches 402; api.php doesn't).
- **hogeq is strictly ahead of icebow** (champion ability path, spell_build_dmg,
  zone_first_tick_now, recoil, superseded spark model, four cards.py fixes incl. the
  evo_cycles/0-cycle guard). A stale `1.1**(level-11)` scaler survives in `CardDB.deck()` in BOTH.
- **Electro Dragon chain verified working** (3 targets, stun carried) — but `_CHAIN_TILES = 3.0`
  is one global constant for all chain cards; the evo's KB comment says 3.5. Per-card chain range
  is a stat-parity item, and marginal arcs dying at 3.0 would look exactly like "the chain doesn't
  work" on real boards.

**Owner rulings (locked):** heroes/champions are **enemy-side only** (no action-space change, no
checkpoint break); stat conflicts against `verified:true`/curated rows are **flagged for batch
review**, never auto-overturned; all ~24 abilities get **full engine fidelity** — no simplified
approximations anywhere; meta-frequency sets build ORDER only. **Champions are no longer removed
from the hand while their body is alive** (owner-confirmed rework) — do NOT build a hand-lock;
current lifecycle semantics (multi-body? which body the ability drives? per-body uses? refunds)
are ANSWERED by the owner in-game (see `research/sim_parity/decisions.md` items 4-8): two
bodies coexist and the button drives the MOST RECENTLY PLAYED body; single use is PER BODY; the
elixir refund applies to champions; Skeleton King stops accruing souls after use. The Champion
Rework is dated **29/9/2025** (not 2026) — that is the staleness cutoff for lifecycle text; the
4/8/2026 single-use change sits on top of it.

**Timing:** Phase R (research) starts immediately on approval and changes no pipeline code.
Phase I (implementation) starts only after the long PPO run is launched, and happens in an
isolated git worktree — the live icebow tree re-reads config on worker respawn and must never be
touched mid-run. Discord reports at every stage transition and major discovery (standing rule).

## Pipeline interleave (unchanged directives, run alongside Phase R)

1. Stage B (`ARM_clipfix.pt`) finishes → paired eval vs `ARM_control4.pt` (n=30,
   `PYTHONHASHSEED=0`, pre-committed ≥2σ or NO MEASUREMENT).
2. Card upgrades in `icebow/config/cards.yaml`: tesla/evo 14→15, ice_wizard 12→13 (HANDOFF §4i).
3. Launch the long PPO with watcher armed. Phase I may then begin (worktree).
4. Sim-parity merge lands ONLY at a declared PPO restart point and counts as that experiment's one
   training change.

---

## Phase R — Research (multi-agent, now; writes only `research/sim_parity/`)

Run via Workflow fan-outs; web access = python urllib against api.php (the proven path), custom
UA, throttled; webcache under `research/sim_parity/webcache/`. Never write inside either deck tree.

**R0 — Ledger scaffold + snapshot (2-3 h).** `research/sim_parity/{ledger,abilities,api_samples,
webcache,scripts}/`, `conflicts.md`, `decisions.md`. Dump the **merged** loader output (what the
sim actually sees, via `cards.py:139-174` from the hogeq tree) → `ledger/current_db_snapshot.json`.
Seed `ledger/registry.json` (evo/hero/champion tables, all rows `status: unconfirmed`).
*Gate:* snapshot reconciles with cards_stats.json meta (164/8/42).

**R1 — Enumeration (3 parallel agents).**
- *R1a evolutions:* wiki category walk + Evolution master list + release docs. Negative probes:
  Berserker/Giant/Arrows `/Evolution` must come back absent; positive: Elite Barbarians. Output:
  per-evo `status: live|announced|absent`, cycles, URL+revid+date.
- *R1b heroes:* "Heroes" master page + every `<Card>/Hero` subpage (≥18 candidates vs taxonomy's
  16 — adjudicate the delta in `conflicts.md`). Per hero: `abilities/<base>_hero.yaml` — body
  deltas, ability name/cost/uses/cooldown, mechanic prose verbatim + citation, every extractable
  number, proposed `ability_kind`.
- *R1c champions:* verify the 8 vs `Category:Champion Cards` + 2026 additions. Per champion:
  ability spec file (6 unmodeled + re-verify mighty_miner/boss_bandit). **Lifecycle rules from
  current master pages + newest balance notes ONLY** — no hand-lock assumed; resolve multi-body
  semantics, ability-target selection, per-body uses, refund rule; queue in-game checks for the
  owner where prose is ambiguous.
*Gate:* all tables closed, every row sourced (URL+revid+date), deltas adjudicated.

**R2 — Stat diff sweep (2 days, deliberately slow; agents split by card family).** Compare merged
snapshot vs fresh wiki via THREE paths: level-11 vardefines, attr-table/infobox, balance-history
reconstruction (generalizing `tools/crown_damage_audit.py`). 2-of-3 agree → verdict; else
`conflicts.md`. Mandatory adversarial cross-checks from past incidents: crown/troop field mix-up
check (the spark_dps_small 60-vs-48 shape), building-vs-spawned-unit check, edit-war check
(re-fetch ≥48 h later, compare revids, quarantine changed pages). Priority: 5 real null-hitpoint
rows, evo hit_speed family, 45 `verified:false`, 17 `[verify]` markers, elite_barbarians_evo full
re-source, formal provenance for the 5 balance-lag pins. Output: `ledger/stat_diffs.jsonl`, one
claim per (card, field) with sources, cross-check results, verdict ∈ {match, update, pin, escalate}.
*Gate:* verdict-complete, zero unresolved escalations.

**R3 — Mechanic parameters.** Per-card chain ranges/target counts (replaces the `_CHAIN_TILES`
global), friendly-spell numbers (Rage/Heal Spirit/Clone/Mirror + meta-frequency), hero/champion
slot rules re-verified from current sources. Output: `ledger/mechanics.json`.

**R4 — Battlelog API probe (2-4 h).** Does `/players/{tag}/battlelog` / `currentDeck` expose
per-card `evolutionLevel` / hero indicators? (`deck_import.py:34` currently discards this.) If yes:
collect over the 120-player set → `ledger/meta_evo_slots.json` (real per-deck evo+hero slots). If
no: curated top-20 fallback, provenance-marked.

**R5 — Adjudication + freeze.** Consolidate `conflicts.md` (escalations, verified-row overturn
requests, in-game confirmation queue) → owner batch session → `decisions.md` → commit + tag
`research-frozen-<date>`. **Phase I consumes only the frozen ledger — no re-fetching.**

---

## Phase I — Implementation (worktree `ClashBot-parity`, after PPO launch)

Every change lands in BOTH decks in the same commit; `tools/parity_check.py` (new, I0) enforces
the byte-identical config quartet + a whitelisted src diff at every gate.

**I0 — Worktree + parity harness. DONE 2026-08-26.** `tools/parity_check.py`, byte-identical in
both decks and runnable from either. Baseline: config quartet byte-identical, `cards.yaml`
identical apart from its 783-byte `deck:` block (checked by stripping it, NOT by allow-listing the
file), `src/clashrl` 80 files -- 60 shared identical, 20 declared, **0 unexpected**. The allow-list
is split into DECK-SPECIFIC (11 entries, should differ forever) and DRIFT (8 entries, recorded not
blessed, meant to shrink). Verified to FAIL, not just to pass: four probes (shared engine edit,
config edit, `cards.yaml` edit outside the deck block, new unlisted file) each exit 1; clean exits
0. See conflicts.md "I0".

**I1 — hogeq->icebow backport. DONE 2026-08-26**: `sim/engine.py` and `cards.py` are now
BYTE-IDENTICAL between the decks and `config/cards.yaml` differs only in its `deck:` block. Also
fixed `evo_cycles` 6/42 -> 42/42 (two counts were missing from the imported rows and came from the
wiki ledger) and the `1.1**` scaler in `CardDB.deck()` (worst delta -0.93% icebow, -0.76% hogeq).
icebow's card head stays at 10: engine path only, no action-space slot. Original scope follows.

**I1 (as planned) — hogeq->icebow backport (1 day; prerequisite).** Engine: `spell_build_dmg`,
`zone_first_tick_now`, `champion_ability` + ability CardSpec/Unit fields, `recoil`,
`spark_end_dmg` (replacing icebow's superseded spark model). cards.py: `evo_cycles()` fix,
0-cycle guard, ability pricing, `policy_identities`. BOTH: kill the stale `1.1**` scaler in
`CardDB.deck()` → `levels.py`. Port `test_champion_ability.py` + `test_evo_cycle_and_sparks.py`;
reconcile diverged test lists. *Gate:* both suites green; scaling test added.

**I2 — Phantom-evo kill (2-4 h).** `build_spec` raises KeyError on unknown `_evo`; opponents' evo
picker checks row existence. New `tests/test_no_phantom_evos.py` (berserker/giant/arrows evo raise;
elite_barbarians_evo builds) + `tools/evo_audit.py`. *Gate:* phantoms 0/400 (was 287/400).

**I3 — meta_decks evo slots. DONE 2026-08-26, but NOT as written.** The premise failed: the
battlelog's `evolutionLevel` reports a player's OWNED evolution level, not the fielded slot (three
evolutions for 153/233 decks against a two-slot game; a level for `berserker`, which has no
evolution), so `meta_evo_slots.json` cannot say which card was slotted and its 233 `evo:`
declarations were stripped. RoyaleAPI / Deck Shop / StatsRoyale are all 403. **The stated gate --
"fielded-evo distribution matches the ledger" -- is therefore unmeasurable and was dropped.**

Shipped instead: a derived `evo_candidates:` per deck (the deck's cards that really have an
evolution, == the 42 wiki-verified rows in `ledger/r1a_evolutions.json`), with ScriptedBot drawing
ONE uniformly per match. `deck_import.py` stops tallying `evolutionLevel` entirely so a re-import
cannot recreate the bad slots. *Gate, met:* 0 phantoms, 0 candidates failing `build_spec`,
1000/1000 decks field a real evolution, all 42 reachable. See conflicts.md "I3 RESOLVED".

**I4 — Importer hardening (1 day; precedes any re-import).** Hero subpage scrape → `<base>_hero`
rows; allowlist (`config/import_allowlist.json`, generated from frozen registry) — emitting a key
outside it is a hard error; `--dry-run` default with field-level diff, `--write` to save;
`config/import_pins.json` (balance-corrected values) — refuses to regress a pin or change a
verified-backed field without `--force-field`; per-row `_src: {revid, fetched}`. Offline wikitext
fixtures in `tests/fixtures/wikitext/`; **negative control: an announced-but-unreleased Evolution
fixture must NOT produce a row.** *Gate:* fixture suite green; live `--dry-run` diff matches
`stat_diffs.jsonl` verdicts (any surprise = stop).

**I5 — Stat fixes from the ledger (1 day).** Apply `update` claims (guarded import or cards.yaml
with dated citations), `pin` claims → pins file, verified:false flips only on 2-of-3 agreement.
New `chain_tiles` KB+CardSpec field (`_CHAIN_TILES` becomes fallback). Implement
`stat_sweep.py --all` (advertised, never built); sync its EXPECTED dict to the pins file. *Gate:*
`stat_sweep --all` green both decks; real null-hitpoint gaps = 0.

**I6 — New evolutions (0.5-1 day each).** elite_barbarians_evo re-sourced from its live page +
anything R1a found, via the established CardSpec-field/generic-path/KB-row pattern.
`tests/test_evo_wave4.py`, wiki-cited docstrings. Allowlist updated in the same commit.

**I7 — Champion abilities, enemy-side (2-3 days).** `ability_kind` dispatch registry in the
engine (~10 generic param fields reusing the existing ability block); mighty_miner becomes
`ability_kind: "bomb"` (hogeq action slot unchanged — head shapes asserted against pre-change
checkpoints); boss_bandit folds in as an auto-cast kind. Implement the 6 missing champions at
full fidelity from frozen specs (incl. Monk's actual projectile reflection — no simplified
window). Champion lifecycle per R1c findings — **no hand-lock**; whatever multi-body/ability-
target semantics research confirmed. Opponent AI: `ScriptedBot._try_ability` with per-kind
default triggers, KB-overridable. One bare-engine test per champion. *Gate:* all 8 work in enemy
hands; hogeq's existing ability tests still green.

**I8 — Heroes, enemy-side (4-6 days; largest block).** KB rows + curation from frozen specs.
Engine handlers by shape family, ordered by meta frequency, all full-fidelity: buff, taunt+shield,
summon/spawn (banner/turret), zone (blizzard), movement/flight (+fire tornadoes via tornado
machinery), throw/displacement, transform/level-up, stealth. Slot + refund rules per R1b.
`hero:` slots go live in ScriptedBot. Taxonomy additions if R1b found live heroes missing from
`detect_classes.yaml` (detector retrain flagged as separate later work).
`tests/test_hero_abilities.py` per family + `test_hero_slots.py`. *Gate:* every `status: live`
hero implemented+tested or explicitly owner-deferred in `decisions.md`.

**I9 — Cross-cutting gaps (1-2 days).** Friendly-target spells (`_resolve_spell` own-team path:
Rage, Heal Spirit, Clone; Mirror per ledger scope); `drill_env.py` evo cycling mirroring env.py's
machinery; sim_view draws chain/ability projectiles so working mechanics are visible in the
debugger. *Gate:* suites green both decks.

**I10 — Closeout (0.5 day).** Full suites + `stat_sweep --all` + parity_check + evo_audit +
negative controls; EVOLUTIONS.md/SIM_FIDELITY.md updated; HANDOFF updated. **Landing:** merge at
the declared PPO restart only; owner stops run → merge → fresh PPO (= that experiment's one
change). Never touch the live icebow tree mid-run.

---

## Verification (proof per claim)

| Proof | Mechanism |
|---|---|
| Phantoms dead | build_spec raises; evo_audit 0/400 |
| Importer can't invent content | allowlist hard-error + announced-page negative control |
| Curated values survive import | pins + refuse-on-regression + round-trip fixture |
| Stats correct | stat_sweep --all, 2% tolerance, pins = only deviations |
| Abilities per wiki | bare-SimEngine test per champion/hero, wiki-cited docstring |
| No checkpoint break | head-shape assertion vs pre-change checkpoints |
| Two-deck parity | parity_check at every gate |
| No PPO contamination | worktree-only writes; live tree `git status` stays clean |

## Key risks

Import reverting curated fixes (pins+dry-run); wiki edit wars (revid + 48 h re-fetch + 2-of-3
vote); crown/troop + building/spawn mix-ups recurring (dedicated cross-checks); battlelog lacking
evo fields (curated fallback); ability scope explosion (shape families + frequency ordering +
owner-approved deferral list — depth is never cut, only order); champion lifecycle mis-modeled
from stale sources (current-sources-only rule + owner arbitration).

## Sizing

Phase R ~4-5 elapsed days (parallel; owner-latency on R5). Phase I ~2.5-3.5 weeks.
Deferred (owner-optional): our-deck heroes/champions (checkpoint break — next deck redesign);
waypoint pathing; detector retraining for hero classes; hero drills; `import_mechanics.py`
modernization (source dead since 2023).
