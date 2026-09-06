# S0 step 2 — the shared observation contract (spec, 2026-09-06)

Owner rulings in force: hogeq inherits everything (one shared package, not two copies); live path may be
touched this gauntlet; one change per experiment. Audits this spec is written against:
`scratchpad/gauntlet/L63/obs_audit_engine.md` and `obs_audit_live.md` (file:line cites live there).

## 0. Where the code lives

New top-level package **`C:\Users\benpe\ClashBot\pipeline\`** (deck-agnostic; both decks import it).
`icebow/src/clashrl` and `hogeq/src/clashrl` are diverged copies (20 files differ) — nothing new goes
into either. Deck facts come from `pipeline/decks/<deck>.yaml` (8 card class names, crawl dir, data dir).

```
pipeline/__init__.py
pipeline/vocab.py          # unit/spell vocabulary + engine-name -> class rules
pipeline/obs_contract.py   # BoardState + from_engine + from_live + degrade + to_tokens
pipeline/decks/icebow.yaml, hogeq.yaml
pipeline/tests/test_obs_contract.py
```

## 1. Vocabulary (`vocab.py`)

- Canonical unit identity = the **detector's 230 class names** (`icebow/config/detect_classes.yaml`,
  byte-identical to the weights' `model.names`; order = class id). Live is the lower-information side, so
  its vocabulary is the contract's.
- Append engine-only names after id 229 (at least `MergeMaiden_Mounted`; the implementer lists every engine
  `name` that has no detector class, from the catalog + the `_ALIAS_INV` + CamelCase→snake rules in
  `scratchpad/gauntlet/L61/build_bc_v2.py:44-69`).
- Sub-spawn rule: engine names spawns by parent. Map `(name, max_hp)` → detector class for the six
  detector-only classes: golemite, lava_pups, elixir_golemite, elixir_blob, royal_recruit, mother_witch_hog.
  Measured: `Golem` max_hp {5120 parent, 1039 golemite}, `LavaHound` {3581, 215}. The implementer measures the
  other four from recorded engine frames if present; otherwise marks them `(b) untested` with a TODO and a
  threshold guess clearly labelled.
- Towers: check whether the detector vocab has king/princess tower classes. Towers are NOT units in the
  contract (they have their own slots, §2) — the vocab only needs them if the detector emits them.
- Export: `UNIT_VOCAB: list[str]`, `unit_id(name) -> int`, `engine_unit_id(name, max_hp) -> int | None`,
  `SPELL_CLASSES` (the 46 detector spell classes; 20 `_aoe`), and `is_spell(id)`.

## 2. `BoardState` (the contract)

All coordinates in ONE frame: the 18×32-tile board, normalised 0..1, **me at the bottom**, exactly the
convention `build_bc_v2.py` uses for engine side 0 (`x/18000`, `ny = 1 - y/32000`) and mirrors for side 1
(`18000-x, 32000-y` first). The implementer must state which y value is my king's row and assert it in a test
with the engine's known tower positions (side-0 king at (9000, 3000)).

```python
@dataclass(frozen=True)
class Unit:
    cls: int            # vocab id
    side: int           # 0 = mine, 1 = enemy, -1 = unknown (live only; engine never emits -1)
    x: float; y: float  # board frame above
    hp_frac: float | None   # engine: hp/max_hp; live: None
    deploying: bool | None  # engine: kind in (12, 14); live: None
    age_sec: float | None   # engine: (tick - first_seen_tick)/20 if the adapter is fed a history, else None
    conf: float             # engine 1.0; live detector conf

@dataclass(frozen=True)
class Tower:
    side: int; kind: str    # 'king' | 'princess'
    lane: str | None        # 'L' | 'R' for princess (in MY frame: L = x < 0.5), None for king
    hp_frac: float | None; alive: bool

@dataclass(frozen=True)
class BoardState:
    source: str             # 'engine' | 'live' | 'degraded'
    t_sec: float; t_source: str   # 'tick' | 'clock' | 'timer'
    double_elixir: bool; overtime: bool     # derived: t >= 120 ; t >= 180  (engine tick 3600 / 6000 at 20 Hz — confirm)
    my_elixir: float; my_elixir_exact: bool # engine exact (1e-4), live integer from the bar
    opp_elixir: float | None                # engine exact; live None (an estimator is S1's job, not the contract's)
    my_hand: tuple[int, int, int, int]      # vocab ids, deck-slot order as the game shows them; -1 = unknown slot
    my_next: int                            # vocab id or -1
    towers: tuple[Tower, ...]               # exactly 6, fixed order: my K, my L, my R, opp K, opp L, opp R
    units: tuple[Unit, ...]
    spells: tuple[Unit, ...]                # spell/effect instances (engine `effects` + detector `_aoe`/spell classes)
```

Card ids in `my_hand`/`my_next` use the same vocab (the card's troop/building/spell class name); the deck yaml
lists the 8 names.

## 3. Adapters

- `from_engine(obs, my_side, deck, *, history=None) -> BoardState` — accepts BOTH the raw `observe()` dict
  (`native_core/env.py:187-255`: tick, players, entities, projectiles, effects, episode) AND the list-encoded
  frame form on disk (`[side, x, y, name, hp, max_hp, kind]`, plus players' elixir). Mirror for side 1.
  Crown towers appear twice in the engine (entities with card_id −1 + `episode.crown_towers`) — use
  `episode.crown_towers` for the Tower slots and DROP the card_id −1 entities from `units`.
- `from_live(detections, reads, deck) -> BoardState` — `detections` are `replay_mine.Detection`
  (frame-fraction cx/cy/w/h, cls name, conf, team); `reads` is a small dataclass the implementer defines:
  `LiveReads(elixir_int, hand_names[4], next_name, tower_hp[6] (None allowed), t_sec, t_source)`. Frame→board
  goes through the existing `BoardWarp` (`icebow/src/clashrl/actions.py:55-155`) — IMPORT it, do not copy it;
  use `Detection.gy` (shadow-corrected y) for flyers. `team == "unknown"` → side −1 (kept, not dropped — the
  contract records it; the model decides).
- `degrade(bs, rng, *, recall=0.855, precision=0.886, elixir_to_int=True, drop_hp=True, drop_deploying=True,
  unknown_team_rate=None, pos_sigma_tiles=0.0) -> BoardState` — turns an engine state into a live-like one
  with the MEASURED detector numbers (HANDOFF.md:1080-1096: presence recall 0.855, precision 0.886 on the
  241-image / 820-box live gate). False positives: with rate (1−precision)/precision per kept unit, duplicate
  a random kept unit with jittered position and a random class from the same kind. `pos_sigma_tiles` and
  `unknown_team_rate` are UNMEASURED — defaults 0 / None and a docstring line saying so.
- `to_tokens(bs, max_units=64) -> (unit_tokens float32[max_units, F], unit_mask bool[max_units],
  scalars float32[S])` — F = [cls id (int stored as float, embedded by the model), side one-hot(3), x, y,
  hp_frac or 0, hp_known, deploying or 0, deploying_known, age/30 or 0, age_known, conf]; spells appended as
  tokens with a spell flag; S = [t/300, double, overtime, my_elixir/10, my_elixir_exact, opp_elixir/10 or 0,
  opp_known, hand 4×(deck-slot one-hot 8 + unknown), next (9), 6 tower hp_frac (or 0) + 6 hp_known + 6 alive].
  Document F and S as constants.

## 4. Tests (`pipeline/tests/test_obs_contract.py`, run with `python -m pytest pipeline/tests -q`)

1. **Synthetic pair**: build one engine `observe()`-shaped dict (5 units both sides incl. one flyer, one spell
   effect, towers with partial hp, elixir 6.37, hand of 4 deck cards) and the equivalent detection list +
   LiveReads (frame fractions produced by inverting `BoardWarp` on the same tiles — if BoardWarp has no
   inverse, place detections via its forward map on chosen frame points and compare in board space).
   Assert: same unit count, same cls, same side, |Δx| ≤ 0.5/18, |Δy| ≤ 0.5/32; towers equal on alive/kind/lane;
   my_elixir 6.37 vs 6; hand/next equal.
2. **Mirror**: same engine board given as side 1 (coordinates mirrored) → identical BoardState to side 0.
3. **Tower geometry**: engine side-0 king at (9000, 3000) lands in the bottom-centre of the frame; princess
   towers land at the documented lanes; assert numerically.
4. **Real engine frames**: load recorded list-encoded frames if any exist (the engine audit says only
   list-encoded frames are on disk — search `scratchpad/gauntlet/L62/` and `scratchpad/gauntlet/ext/` for
   `frames`); run `from_engine` on every frame of one file; assert 0 unmapped names (print the unmapped set
   if not) and no coordinate outside [0, 1].
5. **degrade** is deterministic under a seed and, over 2,000 draws on a 10-unit board, keeps units at
   0.855 ± 0.02 and adds false positives at (1−0.886)/0.886 ± 0.02 per kept unit.
6. **to_tokens** shapes and mask; a BoardState with 70 units truncates to 64 by conf (live) / keeps nearest
   to the bridge first (engine) — implementer picks ONE rule and documents it.

Run the tests from the icebow venv (whatever `icebow/run.py` uses; check `icebow/requirements.txt`). Do NOT
run the detector, the engine, or the game.

## 5. Out of scope for this step (recorded so they are not lost)

- The own-click contract test on the 3 icebow + 1 hogeq `record.py` sessions (S0 step 2b, next loop).
- Live logger must start writing player tag + battle timestamp per match so RoyaleAPI / CR-API battle logs can
  be matched afterwards (S4 prerequisite; the live audit found nothing logs them today).
- Two live-path gaps found by the audit and NOT in HANDOFF: play.py never installs the board warp on `Vision`
  (RGB planes are a whole-window resize while canvases are board-true); play.py ignores `train.rl_gate_tau`
  for the non-PPO deployed checkpoint (uses legacy `Q(wait) >= Q(play)`). Both are S4 items.
- Opponent-elixir estimator, unit-age tracker for live (tracker memory exists in play.py) — S1/S4.
