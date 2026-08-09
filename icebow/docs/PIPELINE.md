# Getting a recording to produce data

Every command that reads a recording depends on one thing first: `detect_state` has to
recognise a frame as `IN_MATCH`. If it does not, `label` finds no plays, `outcomes` finds
no matches, `deck-detect` finds no cards, and `play` never acts. Nothing errors, they all
just return nothing, which is the confusing part.

## Why it fails

`templates/in_match*.png` are crops of one specific client: one window size, one interface
language. Template matching compares pixels, so a client that says `Restzeit` where the
crop says `Time left`, or a window with a different aspect ratio, scores far below the
0.80 threshold.

Measured on a 756x1334 recording from a German client: best score 0.544, threshold 0.80,
0 of 40 in-match frames recognised.

## Checking it

`run.py ui` → tab **Live** shows the current frame, the recognised state and the best
score of every screen template. `run.py diag` prints the same for the current screen.

## Fixing it

```powershell
.\.venv\Scripts\python.exe run.py calibrate --dry-run   # report only
.\.venv\Scripts\python.exe run.py calibrate             # cut and write
```

`calibrate` needs a recording that contains your clicks, because that is what makes the
labelling possible without asking you anything:

* frames around a logged click are **in a match** (you only play cards while playing),
* frames before your first click are **not** (menu, before you pressed Battle),
* pauses in the middle of a match are ignored: nobody plays a card every four seconds.

It then searches for the region that stays still during play and differs most from the
menu frames, measures how well every candidate separates the two groups, and keeps the
one whose worst in-match hit is highest. The crop is saved as
`templates/in_match_local.png` and entered in `config.yaml` with a threshold placed
between the two groups. Nothing is written when the groups are not clearly separable.

On the recording above it selected a 96x22 region, threshold 0.75, hitting 37 of 40
in-match frames and 0 of 26 menu frames.

Best input: start recording in the menu, play one full match, keep recording a few
seconds past the result screen.

## Then the deck

```powershell
.\.venv\Scripts\python.exe run.py cards-art                       # once: reference pictures
.\.venv\Scripts\python.exe run.py deck-detect --write-templates   # identify + name the crops
```

`deck-detect` samples the tray, groups the crops into distinct card faces and identifies
each against the reference pictures. With `--write-templates` a confidently identified
face is saved directly as `templates/cards/<card>.png`, which is the step that previously
meant renaming `_cand_*.png` by hand. Only confident faces are written: a wrong name
there would quietly break hand recognition for every later run.

Accuracy, measured against the 190 hand-labelled crops in `templates/cards/` with all 181
reference pictures competing: 83 % correct from a single crop, 12 of 12 cards correct when
6 crops of a face are averaged, which is what the command does.

Card levels are not visible in the tray. With `--player-tag "#YOURTAG"` and an API token
in `CLASHRL_CR_API_TOKEN` they are read from your account; otherwise the levels already in
`cards.yaml` are kept and reported as unchanged.

## Order of operations

1. `record` — menu, one match, a few seconds after the result screen
2. `calibrate` — only needed once per client/window setup
3. `deck-detect --write-templates` — deck and hand templates
4. `label --all`, `outcomes --all` — now they find data
5. `train-bc`, then `train-rl` or `play`

The simulator (`train-sim`, `sim-bench`, `policy-stats`) needs none of this: it runs
without the game.

## The other pipeline: training the vision AI

Separate network, separate data, four steps in a fixed order. Nothing above feeds it
except the recordings the frames come from.

1. `detect-frames` — pull in-match frames out of a recording into the labelling queue.
   Sampled around your own plays, so every frame is guaranteed to show a real board.
2. **Labelling tab** — draw the boxes. The model pre-fills what it already recognises at
   a low confidence floor, so this is correcting rather than drawing. This is the only
   place boxes are made; there is no second labelling path.
3. `sprites` — cut every box out of its background (GrabCut) into a per-class sprite
   bank, then `--synth N` pastes those onto other frames to generate extra labelled
   images. This is also what stops the detector learning the ARENA instead of the unit.
   It multiplies classes you have already labelled and invents nothing.
4. `detect-train` — writes `runs/detect/vision/weights/best.pt`, replacing the previous
   model, and a `model_card.json` with the measured mAP / precision / recall.

Measured on this repo, 63 hand-drawn boxes multiplied to 371 training images:

    mAP50       58.3 %   (best epoch 68.8 %)
    precision   66.5 %
    recall      55.6 %

Two things dominate that number, in this order: whether the class indices are consistent
(see the class-list note in the README — a mismatch there trained a Mini P.E.K.K.A as a
Minion), and how many boxes exist. More epochs is not the lever.
