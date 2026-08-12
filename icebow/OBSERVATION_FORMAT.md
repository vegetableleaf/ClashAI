# ClashAI observation format — `clashai-observation/1`

The hand-off contract between ClashAI's vision stack and a simulator. One screenshot in, one JSON
record out, containing everything the screen can be made to say.

Produce one with:

```
run.py observe <frame.jpg> --out obs.json [--assume-match]
```

---

## Why the format looks like this

Four rules, each answering a mistake that is easy to make when consuming this data.

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

> ⚠️ **The one calibration you must check.** Tiles are derived from `arena.box_norm`, which is
> calibrated for the client that captured the frame. A frame from a *different* client — other
> aspect ratio, cropped capture, YouTube recording — comes out **uniformly offset**. Uniform
> offsets look correct, which is what makes this dangerous.
>
> **Sanity check:** the princess towers should land near tile y ≈ **3.5** (enemy) and ≈ **28.5**
> (yours). If they don't, `arena.box_norm` needs recalibrating for that source and every tile in
> the record is shifted by the same amount.

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

`team` comes from evidence fusion over short tracks — own-play anchor, motion direction, HP-bar
colour, first-seen side, body art — **not** from colour alone. `unknown` is a real answer and
appears often for spells, which carry no team UI.

### `motion`
`available: false` in a single-frame record. Pass a previous record as `prev` to get per-unit
`delta_tiles`. That matcher is deliberately naive (nearest same-class neighbour) and labelled as
such — real tracking lives in `perception.py` at ~10 Hz.

---

## What is NOT in here yet

Stated plainly so you don't plan around data that doesn't exist:

| missing | why |
|---|---|
| **Troop HP** | `troop_hp.py` exists but is a **scaffold, not wired in**. A troop's bar only appears once damaged, is tiny, and overlaps in a crowded push. |
| **Crown count** | no reader built |
| **Match clock (mm:ss)** | not OCR'd; the live bot tracks elapsed time instead |
| **Unit levels** | no reader built |
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

`yolo11m` @ 960 px, 225 classes, trained on 38,265 boxes across 8,731 frames.

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
     "team_evidence": {"bar": "enemy", "body": null}}
  ]},
  "motion": {"available": false}
}
```

---

## Feedback wanted

This is a **proposal**, not a fixed contract. Specifically:

1. **Tile origin** — we put `[0,0]` behind the opponent. If the sim uses a different origin or
   axis direction, say so; it's a one-line change here rather than a conversion on your side.
2. **Fractional vs integer tiles** — we emit fractional. If the sim snaps to integers anyway,
   we can emit both.
3. **Per-frame vs stream** — currently one record per frame. If the sim wants a time series with
   stable unit IDs, that needs the real tracker from `perception.py` wired in, which is a bigger
   change worth agreeing on first.
4. **Which missing readers matter most?** Troop HP is the most-requested and the most work; if
   the sim can do without it, we'd rather spend that effort elsewhere.
