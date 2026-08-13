# ClashAI observation format — `clashai-observation/1`


Produce one with:

```
run.py observe <frame.jpg> --out obs.json [--assume-match]
```

---

## Why the format looks like this


**1. Every position is given twice.** `xy` is normalized image space (0–1), `tile` is the arena
lattice. The tile lattice is what a simulator thinks in; the image coordinates are what lets you
redraw the box on the screenshot and check us. Emitting only tiles would force you to trust our
calibration blind.

**2. Flying units report their SHADOW, not their sprite.** A flyer is drawn above the tile it
occupies. `tile` is already corrected; `airborne` says the correction was applied, and
`sprite_xy` keeps the uncorrected centre. **Placing a Baby Dragon by its sprite centre puts it
~1.5 tiles too far forward.**

**3. Nothing is silently estimated.** Every block carries `method` (how it was read) and either a
confidence or an explicit `null`. Blocks that are known scaffolding rather than trusted numbers
say so.

**4. Fields are present even when unreadable, as `null`.** A missing key is ambiguous between
"this build doesn't produce it" and "it couldn't be read here". An explicit `null` beside a
`method` is not.

`schema` bumps **only when a field's meaning changes**. Added fields are not a bump — ignore keys
you don't know, but never ignore the version.

---

## The coordinate system

```
tile [0, 0]  = top-left, behind the OPPONENT's back line
tile [18, 32] = bottom-right, behind YOUR back line
```

18 × 32 is Clash Royale's real board. Values are **fractional** — a unit standing between tiles is
a real thing, and rounding would throw that away.

>  **The one calibration you must check.** Tiles are derived from `arena.box_norm`, which is
> calibrated for the client that captured the frame. A frame from a *different* client — other
> aspect ratio, cropped capture, YouTube recording — comes out **uniformly offset**. Uniform
> offsets look correct, which is what makes this dangerous.
>
> **Sanity check.** Use the tower entries — but read the next paragraph first, because their
> `tile` is **not** where the tower stands.
>
> A tower's `tile` is the centre of its **HP bar**, which floats above the tower. Measured over
> 120 validation frames it is stable to the second decimal:
>
> | | x | y |
> |---|---|---|
> | `E1` / `E2` (enemy) | 3.17 / 13.17 | **0.99** |
> | `M1` / `M2` (yours) | 4.02 / 13.62 | **22.27 / 22.50** |
>
> If your frames land near those, `box_norm` is right for your source. If they are all off by a
> constant, it is not, and every tile in the record carries that same shift.
>
> Two things this table admits rather than hides: the enemy and own pairs are **not** mirror
> images about x = 9, so the configured read windows are only roughly placed; and you cannot
> derive a tower footprint from these numbers. If your simulator needs the tower's ground
> position, treat that as missing data, not as something to compute from here.

---

## Blocks

### `screen`
```json
{"state": "IN_MATCH", "in_match": true, "detected_in_match": true,
 "assumed": false, "method": "template match ..."}
```
The state reader matches templates captured from **one specific client**. On a foreign frame it
returns `UNKNOWN` and every match-only block below suppresses itself to `null`.

`--assume-match` overrides it: `in_match` becomes true, `assumed` records that we overrode it, and
`detected_in_match` still reports what the reader actually thought. **Use it for dataset frames**
you know are matches.

### `hand` — the four card slots
| field | meaning |
|---|---|
| `card` | card key, or `null` if unreadable |
| `state` | `read` / `empty` / `unknown` |
| `affordable` | **not** the same as identified — a greyed card is correctly read *and* unplayable |
| `match_score` | template match strength |

**Reliability: deck-bound.** Only cards with a template in `templates/cards/` can be named. An
unknown deck reads as all-`null`. This is template matching, not the neural detector.

### `next_card`
Separate template set (the preview is smaller and blue-tinted). `error` is set when the deck has
no `templates/next/` — then it is simply unreadable, not absent.

### `elixir`
`value` 0–10, counted as filled pips by colour.

`multiplier` is **always `null` in a single-frame record** — the 1×/2×/3× phase is derived from
elapsed match time, which one frame cannot show. The live bot gets it from `clock.ElixirClock`.
Emitting `1` here would be a guess a simulator would integrate as fact.

### `towers` — six entries
`E1`,`E2` (enemy princess), `M1`,`M2` (yours), `K_enemy`, `K_mine` (kings).

| field | meaning |
|---|---|
| `hp` | the printed number, via a small digit CNN |
| `hp_conf` | how confident that read was |
| `fill` | bar fill fraction, measured by colour **independently of the digits** |
| `state` | `alive` / `destroyed` / `no_bar` / `no_match` |
| `snapped` | **quality flag** — non-zero means this frame's geometry didn't match the config and the read window had to be moved |

Two independent signals on purpose: `fill` still works when the digits are unreadable, and
disagreement between them is itself information.

> On foreign clients the digit CNN is unreliable (different font, position, resolution) — expect
> nonsense numbers with low `hp_conf` and non-zero `snapped`. `fill` degrades more gracefully.

### `units` — the neural detector
| field | meaning |
|---|---|
| `cls` | detector class, e.g. `hog_rider`, `tesla_evo` |
| `card` | base card with `_evo`/`_hero`/`_ability`/`_aoe` stripped |
| `conf` | detector confidence |
| `team` | `mine` / `enemy` / `unknown` |
| `tile` | **shadow-corrected** ground position |
| `sprite_xy` | uncorrected box centre |
| `airborne` | whether the shadow correction applied |
| `team_evidence` | `bar` and `body` votes that fed the team decision |
| `hp` | `{"frac": 0..1}` from the unit's health bar, or `null` — see `bars` |
| `id` | stable identity across records within one match, or `null` — see below |

**`id` is not a list position.** The detector reorders `units.list` every frame; `id` is the
same number for the same unit across records, which is what lets you tell two knights apart
instead of re-guessing from position each time. It is `null` on a single-frame read (`run.py
observe` on a file) — one frame has no history, and an id that changed every read would be
worse than none. The Live tab supplies one.

### `units.remembered` — units the detector lost, that are still there

Present only alongside `id`. Clash Royale units do not blink out of existence, but detections
do: a unit walking behind a tower, or swallowed by a neighbour's box in a crowded push, drops
out for a few frames and comes back.

| field | meaning |
|---|---|
| `id` | same id it had when last seen, and the same one it gets back on return |
| `xy` / `tile` | **frozen at the last real sighting** |
| `missing_s` | seconds since it was last actually detected |
| `missed_reads` | consecutive reads it has been absent for |

**The position is not extrapolated.** Carrying it along its last heading would produce a
confident position nobody measured — and a unit that *stopped* behind a tower would be reported
marching straight through it. Frozen-and-dated is what is actually known.

Entries drop out after `observation.team_forget_s` (4.5 s by default). A consumer that wants
only confirmed sightings can ignore this block entirely; one that wants object permanence has
it without inventing it.

`team` comes from evidence fusion over short tracks — own-play anchor, motion direction, HP-bar
colour, first-seen side, body art — **not** from colour alone. `unknown` is a real answer and
appears often for spells, which carry no team UI.

### `bars` — health bars, and where per-unit HP comes from

A **second, separate detector** (2 classes: `hp_bar`, `tower_hp_bar`). Bars are geometry, not
card art, so they are not part of the 225-class model. If those weights are absent the block
reports `available: false`, every unit's `hp` stays `null`, and nothing else changes.

| field | meaning |
|---|---|
| `kind` | `unit` / `tower` |
| `fill` | filled fraction 0–1, or `null` if unreadable |
| `team` | from the bar's colour — **unit bars only**, always `null` on tower bars |
| `unit_index` | index into `units.list`, or `null` |

**`unit_index: null` does not mean "no unit there."** It means no *single* owner could be
named. Matching a bar to its unit was measured against 11,735 hand-labelled bars:

| | |
|---|---|
| exactly one plausible owner | **79.4 %** |
| two or more (ambiguous) | 2.5 % |
| none | 18.1 % |

Ties are reported, not broken. Picking the nearest candidate would convert 2.5 % of "don't
know" into roughly 1.3 % of confident-and-wrong, which is worse in a training label.

**A bar with no owner is a signal.** It usually means the board detector missed a unit that is
plainly there, so the entry is kept rather than dropped.

**`team` is a unit-bar reader and is `null` on tower bars.** Own unit bars measure at median
hue 100 (blue) and enemy ones at 18 (red), which scores **91.0 %** against ground truth on
3,008 bars. Tower bars do *not* separate: measured over 2,005 of them, own towers sit at median
hue 27 and enemy at 52, overlapping almost entirely. Reporting a side there would be a confident
coin flip, so it is not reported — each tower's side is already in the `towers` block, where it
comes from a fixed position rather than a guess.

> **`hp.frac` is not verified against true HP.** There is no HP ground truth in any dataset we
> have to score it against. What is established is that the measurement is derived from the
> bar's own two brightness plateaus (the spent part of a CR bar is not dark, only duller — an
> absolute threshold reads two thirds of all bars as exactly full), that it is measured from the
> **right** because the left end of the bar carries the unit's level badge, and that the
> resulting distribution is continuous over 0.12–1.00 with a median of 0.81 and nothing piled at
> zero. Treat it as a good relative signal, not a calibrated number.

**No bar usually means full health** — Clash Royale draws none until a unit takes damage. It is
still reported as `null`, not as `1.0`, because "undamaged" and "occluded" look identical here.

### `motion`
`available: false` in a single-frame record. Pass a previous record as `prev` to get per-unit
`delta_tiles`. That matcher is deliberately naive (nearest same-class neighbour) and labelled as
such — real tracking lives in `perception.py` at ~10 Hz.

---

## What is NOT in here yet

Stated plainly so you don't plan around data that doesn't exist:

| missing | why |
|---|---|
| **Absolute troop HP** | `bars` gives a *fraction*. Multiplying by max HP needs the unit's LEVEL, which nothing reads. |
| **Unit levels** | The only dataset that labels the level badge has it in **86 frames**. That is not a training set, so there is no reader and no near-term path to one. |
| **Status effects** (rage, freeze, shield, invisible…) | Ground truth exists but is far too thin: of seven flags, three have **zero** positive examples, `shield` appears only on one card, and the rest total ~4,300 boxes across dozens of classes. |
| **Crown count** | no reader built |
| **Match clock (mm:ss)** | not OCR'd; the live bot tracks elapsed time instead |
| **Tower ground position** | only the HP bar's position is known — see the coordinate section |
| **Elixir multiplier** | needs match context, not one frame |

---

## Known accuracy, measured

The detector behind `units`, measured on a **401-image validation set** (its own held-out split,
never trained on):

| metric | value |
|---|---|
| mAP50 | **0.805** |
| mAP50-95 | **0.569** |
| precision | **0.843** |
| recall | **0.690** |
| presence (units found at conf 0.40) | **0.837** |
| whitelist identity recall | **0.848** |

`yolo11m` @ 960 px, 225 classes. Trained on **36,316 boxes across 8,731 frames**; the 401-frame
validation split above holds a further 1,452 boxes and is never trained on.

> **Read those numbers as "on frames like ours".** 75.9 % of the training frames come from an
> imported public dataset (a different client, different capture pipeline) while the validation
> split is **0 %** of it — all 401 frames come from our own client. That is the right way round:
> the score measures what we care about rather than flattering itself on the bigger source. But
> it does mean the table describes accuracy **on our capture setup**. Frames from a different
> client, resolution or recording chain are out-of-distribution for this measurement, and the
> honest expectation is lower, not equal. Measure it on your own frames before relying on it.

Per-class recall varies a lot — common units (`skeletons` n=167, `knight` n=91) sit at 0.78–0.80,
while classes with few validation instances are noisy by construction. **Treat any per-class
number with n < 20 as indicative only.**

---

## Example

```json
{
  "schema": "clashai-observation/1",
  "frame": {"width": 669, "height": 1182},
  "arena": {"tiles": [18, 32], "box_norm": [0.03, 0.1, 0.97, 0.86]},
  "screen": {"state": "IN_MATCH", "in_match": true, "assumed": false},
  "elixir": {"value": 3, "max": 10, "multiplier": null},
  "hand": {"slots": [{"slot": 0, "card": "knight", "state": "read", "affordable": true}]},
  "towers": {"list": [
    {"name": "M1", "kind": "princess", "side": "mine", "hp": 1920,
     "hp_conf": 0.91, "fill": 0.761, "state": "alive",
     "tile": [4.02, 28.4], "snapped": 0.0}
  ]},
  "units": {"list": [
    {"cls": "ice_wizard", "card": "ice_wizard", "conf": 0.817, "team": "enemy",
     "xy": [0.29, 0.49], "tile": [5.12, 15.96],
     "airborne": false, "sprite_xy": [0.29, 0.49],
     "team_evidence": {"bar": "enemy", "body": null},
     "hp": {"frac": 0.463, "method": "bar fill"}}
  ]},
  "bars": {"available": true, "list": [
    {"kind": "unit", "conf": 0.824, "fill": 0.463, "team": "mine",
     "xy": [0.3, 0.47], "tile": [7.946, 15.044], "unit_index": 0},
    {"kind": "unit", "conf": 0.828, "fill": 0.365, "team": "enemy",
     "xy": [0.28, 0.4], "tile": [4.492, 11.251], "unit_index": null}
  ]},
  "motion": {"available": false}
}
```

---

