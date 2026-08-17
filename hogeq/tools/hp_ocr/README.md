# Tower-HP digit OCR

Trains the small digit CNN that reads each princess tower's printed HP, used by
[`clashrl.tower_hp`](../../src/clashrl/tower_hp.py) for the **chip-damage reward**
(reward partial HP loss even when a tower survives).

## Files

- `labeled_digits.npz` — 81 hand-labeled HP-number strips (white-masked + grayscale,
  20×56 each) with their string labels. The 2v2 base set (full 0-9 digit coverage,
  incl. low 3-digit values).
- `labeled_digits_1v1.npz` — 47 strips from a 1v1 match (level 14-15 towers), the
  current tower rendering. `train.py` upweights these (×3) so the CNN adapts to the
  1v1 digits while keeping the 2v2 set's digit coverage.
- `train.py` — loads both sets, slices each strip into digits, augments, trains a
  `DigitNet`, prints accuracy, and exports weights to
  `../../src/clashrl/hp_digits.npz` (what the package loads at runtime).

## Retrain

From the repo's `icebow/` folder:

```powershell
.venv\Scripts\python.exe tools\hp_ocr\train.py
```

Per-digit accuracy is ~92%. That's sufficient: `TowerHpTracker` only confirms a new
HP value after it reads identically on `env.hp_consensus` consecutive frames, so
transient misreads are filtered out (tower HP is piecewise-constant + monotonic).

## Adding data

If reads are poor at a new resolution, capture more strips: crop each princess
tower's HP-number box (see `env.enemy_tower_hp_boxes` / `env.my_tower_hp_boxes`),
build the white mask (HSV `V>180, S<95`) and grayscale-masked strip resized to
20×56, label the true number, and append to `labeled_digits.npz` (arrays `wmasks`,
`grays`, `labels`). Then re-run `train.py`.
