# Label Studio guide -- adding the Ice Wizard HERO to the board detector (L67)

Written 2026-09-12. Goal: fine-tune `icebow/runs/detect/board-24-5/weights/best.pt` so the new hero
Ice Wizard is boxed as the EXISTING class `ice_wizard` (owner ruling: no new class, no head change),
and remove the two known false positives (deploy snow circle -> `rage`, ability button -> `earthquake`).

Evidence tags: **(a)** measured / verified by reading code or files; **(b)** plausible, untested.

Sections: 1 previous workflow, 2 raw frames, 3 step-by-step guide (Step 0 + a-g), 4 traps (T1-T12).
Nothing was installed, started, trained or committed while writing this; no secrets were read or printed.

---

## 1. The previous Label Studio workflow (recovered)

**Where it is written down.** HANDOFF.md and HANDOFF_ARCHIVE.md never mention Label Studio (grep for
"studio" in both: 0 hits). The workflow lives in the code (`icebow/src/clashrl/preannotate.py`,
`detect.py`), `icebow/Instructions.txt:409-421,643`, `icebow/README.md:274-276`, `log.txt:381-406,1195-1210`,
and in Label Studio's own database (read read-only, storage paths and project titles only).

| fact | evidence |
|---|---|
| Label Studio **1.23.0**, system Python 3.13; data dir `C:\Users\benpe\AppData\Local\label-studio\label-studio` (sqlite db, `export\` holds 44 export files, `media\upload\1..3`) | (a) package metadata + listing |
| Projects: **1 "ClashAI"** (4,113 tasks, 1,902 annotations) and **3 "autolabeler"** | (a) sqlite |
| Project 1 had **three Local Files import storages**: `Train` = `...\icebow\data\detect\images\train`, `Val` = `...\images\val`, `To Label` = `...\images\to_label` (last sync 2026-08-08, 540 tasks); project 3 `autolabel` = `...\images\to_label` with regex `.*\.jpg`. All had "treat every object as a source file" on (`use_blob_urls` 1) | (a) sqlite |
| Task image references look like `/data/local-files/?d=to_label\trl_....jpg` (2,133 in `batch_all.json`), plus `/data/upload/1/...` (420, files uploaded through the browser) and `?d=Users\benpe\...` (242) | (a) parsed `data/detect/batch*.json` |
| `?d=` is the file path RELATIVE TO the document root. So `?d=to_label\...` means the root was **`C:\Users\benpe\ClashBot\icebow\data\detect\images`**; the 242 `?d=Users\...` refs mean that at another time the root was **unset**, which in 1.23 defaults to the drive root `C:\` | (a) `label_studio/core/settings/base.py:560-561` (`LOCAL_FILES_DOCUMENT_ROOT` default `os.path.abspath(os.sep)`) + the refs; preannotate.py:10-16 says the same |
| Env var NAMES: `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED` and `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` (LS 1.23 reads `LABEL_STUDIO_<name>` first, then `HEARTEX_<name>`, then the bare name) | (a) `label_studio/core/utils/params.py:114-115`, `base.py:560-561` |
| How they were set before is **not recoverable**: neither is a persistent User/Machine env var today, and the PowerShell history (2,504 lines) names neither -- it only shows `pip install -U label-studio` and two `label-studio-converter import yolo -i data/detect/preannot ...` lines (the older pre-annotation route, replaced by `run.py pre-annotate`) | (a) env + history, counted, values not printed |
| Labelling config: the XML that `detect.py:_write_label_studio_helpers` (lines 165-178) writes to `icebow/data/detect/label_studio_config.xml` -- `<Image name="image" value="$image" zoom="true" zoomControl="true"/>` + `<RectangleLabels name="label" toName="image">` with one `<Label>` per class. `from_name "label"` / `to_name "image"` are what `pre-annotate` emits (preannotate.py:170), so the names must stay exactly these | (a) |
| **Project 1's stored config has 225 labels; today's XML has 230.** Reusing project 1's config would be missing 5 classes -- paste the current file | (a) sqlite count vs file |
| Exports: LS **JSON** exports saved as `icebow/data/detect/batch1.json ... batch7.json` (batch7 = 1,701 Roboflow tasks), fused by `run.py detect-merge` into `data/detect/batch_all.json` (15,198 tasks), imported with `run.py detect-import --export data/detect/batch_all.json` | (a) files + README.md:274-276 + detect.py:821-910 |
| **`batch_all.json` is the complete source of truth of the current split**: all 15,167 stems in `images/train` + `images/val` are in it (0 missing) | (a) measured |
| JSON, not YOLO export, on Windows: the YOLO export crashes because label filenames derived from `?d=...\...` contain `? = \` | (a) detect.py:1063-1064 |
| Label queue: `detect.label_queue_subdir: to_label` -> `data/detect/images/to_label` (6,312 frames: 2,417 already imported, 2,094 in the `preannot_offered.txt` ledger, **2,599 never offered**) | (a) config.yaml:1467 + measured |
| `pre-annotate` instructions (printed by the tool): NEW project, paste the config, add a Local Storage but **do NOT Sync** (a sync creates a second, prediction-less task per frame), then Import the tasks JSON | (a) preannotate.py:212-219 |

---

## 2. Raw (box-free) frames -- what exists

**The overlay clips cannot be used.** `OverlayReplayRecorder._run` always draws: `out = draw_detections(frame, dets)`
(`icebow/src/clashrl/detect.py:526`), and no config key turns that off (the `overlay_replay` block,
`icebow/config/config.yaml:1367-1391`, has only enabled / seconds / keep_clips / max_clips / fps / scale / out_dir). (a)

**`play` has no raw-frame option.** The only other frame savers are `TrainFrameCollector` (detect.py:1331),
wired into `train_rl.py:321` and `record.py:90` but **not** into `play.py`; and `detect.capture_during_train`
is `false` anyway (config.yaml:1475). (a)

**What a "session" is.** `run.py record` (cli.py:584, `record.py`) writes
`icebow/data/sessions/<YYYYMMDD_HHMMSS>/` holding `video.mp4` (the RAW capture region, 12 fps, mp4v, **no
boxes**), `events.jsonl` (mouse clicks), and `meta.json` with `start_time` (Unix epoch seconds) and
`frame_times` (seconds since start, one per frame). `detect-frames`, `autolabel` and `detect-preview` all
read these sessions (detect.py:1187-1244). Four exist; the newest, `20260912_140221`, is 191 s long, and the
region is [734, 18, 657, 1198] -- the same `window` config the overlay recorder captures with
(record.py:46-49 vs detect.py:480). (a)

**So a raw recording path exists with no code change: run `record` in a second terminal while `play`
runs.** `meta.json` gives an exact epoch time for every frame, and `play` prints
`[student] PLAY ice_wizard ... wall=HH:MM:SS.mmm` on stdout (play.py:173-174, 894-896). Together they give
frame-exact alignment. Caveats:
- (b) `record`'s mouse listener will probably also log the bot's synthetic clicks. That is harmless, because we
  align on the play log, not on clicks.
- (b) A second 12 fps screen grab costs about 18% of a core (grab measured at 14.9 ms/frame, config.yaml:1380).
- (a) The `PLAY` lines go to **stdout only**. `data/play_*.log` contains none of them (0 `wall=` lines in
  `play_20260912_142958.log`), so stdout must be saved (`Tee-Object`).
- (a) `detect-frames --session` is **not** suitable here. It samples around *every* click-detected play
  (any card, t-2 s .. t+6 s; detect.py:1235) and writes into `to_label`, mixing the frames with 2,599 unrelated
  pending frames.

**Smallest code change if raw overlay-style clips are wanted instead (NOT made):**
1. `detect.py` `OverlayReplayRecorder.__init__` (after line 400):
   `self.draw = bool(cfg.get("overlay_replay", "draw_boxes", default=True))`
2. `detect.py:526`: `out = draw_detections(frame, dets) if self.draw else frame`
3. `config.yaml` `overlay_replay:` add `draw_boxes: true`. For a raw run set `draw_boxes: false` **and**
   `out_dir: data/raw_replays`. The folder pruner (detect.py:419) globs `match_*` in `out_dir` and keeps only 10,
   so a separate folder stops raw and overlay clips pruning each other.

Costs of that route:
- (a) While the flag is off you lose the overlay diagnostic clips.
- (a) The clips are wall-clock paced at 50 fps with DUPLICATED frames (detect.py:543-546), so extraction has to
  dedupe.
- (b) Clip time is only good to about 1 s, because the name stamp has 1 s resolution
  (`match_<HHMMSS>`, detect.py:469) and HANDOFF uses "frame = seconds x 50".

A parallel raw writer (keep the overlay and also write `raw_<stamp>.mp4` from `frame` before drawing) is about
6 more lines and doubles encode time and disk use (~169 MB/clip, config.yaml:1373). **Recommendation: use `record` in
parallel. It needs no code change and its timing is exact.**

---

## 3. Step-by-step guide (PowerShell; every command runs from `C:\Users\benpe\ClashBot\icebow`)

### Step 0 -- back up the dataset first
`detect-import` **deletes `images/train`, `images/val`, `labels/train`, `labels/val` and rebuilds them from
the export(s) you pass** (detect.py:1138-1143). (a) Import the hero export alone and the 15,167-image
split becomes about 250 images. Some of those images may exist only inside `images/train`; for example, the
420 `/data/upload/1` tasks were uploaded through the browser (b). So copy first (~500 GB free, `data/detect`
is ~10 GB; HANDOFF §9):
```powershell
robocopy data\detect\images\train data\detect_backup_pre_hero\images\train /E /NFL /NDL
robocopy data\detect\images\val   data\detect_backup_pre_hero\images\val   /E /NFL /NDL
robocopy data\detect\labels       data\detect_backup_pre_hero\labels       /E /NFL /NDL
Copy-Item data\detect\split.json, data\detect\data.yaml data\detect_backup_pre_hero\
```

### Step (a) -- record ~5 hero matches RAW
The deck's Ice Wizard slot must be the hero form, as in run17. Terminal 1 (the recorder, raw screen + clicks):
```powershell
.\.venv\Scripts\python.exe run.py record
```
Terminal 2 (the bot, with stdout saved; the play command is whatever you normally run -- run17 used the student path):
```powershell
.\.venv\Scripts\python.exe run.py play --student <your usual checkpoint> | Tee-Object -FilePath C:\Users\benpe\ClashBot\scratchpad\gauntlet\L67\hero_play_1.log
```
Play ~5 matches, stop `play` (Ctrl+C), then stop `record` (Ctrl+C). It prints
`[record] saved N frames ... to data\sessions\<stamp>`. **Start `record` BEFORE `play`** so every play falls
inside the video. (b) If a session gets long, stop both after each 2-3 matches and start a new pair. The
`record` video of a 15-minute session was 428 MB (`20260815_222309`). (a)

Also playing by hand? `record` alone is enough, but then there are no `PLAY` log lines. Use `detect-frames`
(it samples around your clicks, all cards) with `--count`, then **move** the new `<stamp>_g*.jpg` files out of
`to_label` into the hero folder below.

### Step (b) -- extract frames where the hero is on the board
Target **~200-300 frames**. 5 matches x ~5 hero plays (run17: 15 plays in 3 matches) x 9 offsets is about 225.
Offsets after each `PLAY ice_wizard`: **0.5 and 1.0 s** (the snowy deploy circle that was boxed `rage`),
**2, 3, 4.5, 6, 8, 10 and 12 s** (the hero walking, fighting, the ability button at frame (0.909, 0.765)
that was boxed `earthquake`, and the snowman after a press). (a) The regex below parsed all 15 hero plays out
of run17's stdout log. The rest of the script is (b): written for this guide and **not run**.

Save as `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L67\hero_frames.py` and run it once per session:
```python
# usage (from icebow/):  .\.venv\Scripts\python.exe ..\scratchpad\gauntlet\L67\hero_frames.py data\sessions\<stamp> ..\scratchpad\gauntlet\L67\hero_play_1.log
import sys, re, json, datetime as dt
from pathlib import Path
import cv2
sys.path.insert(0, "src")
from clashrl.detect import _read_at           # nearest recorded frame to a capture time (detect.py:71)

session, play_log = Path(sys.argv[1]), Path(sys.argv[2])
out = Path("data/detect/images/to_label_hero"); out.mkdir(parents=True, exist_ok=True)
OFFSETS = [0.5, 1.0, 2.0, 3.0, 4.5, 6.0, 8.0, 10.0, 12.0]

raw = play_log.read_bytes()                   # Tee-Object / '>' in PS 5.1 writes UTF-16 (run17's log starts FF FE)
text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
day = dt.datetime.strptime(session.name[:8], "%Y%m%d").date()
cap = cv2.VideoCapture(str(session / "video.mp4"))
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
seen, n, plays = set(), 0, 0
for m in re.finditer(r"\] (?:STALL-)?PLAY ice_wizard .*?wall=(\d\d):(\d\d):(\d\d)\.(\d{3})", text):
    plays += 1
    h, mi, s, ms = map(int, m.groups())
    t_play = dt.datetime.combine(day, dt.time(h, mi, s, ms * 1000)).timestamp()   # local wall -> epoch
    for off in OFFSETS:
        t = t_play + off - meta["start_time"]                                     # seconds into the video
        if t < 0 or t > meta["frame_times"][-1]:
            continue
        frame, fi = _read_at(cap, meta["frame_times"], t, total)
        if frame is None or fi in seen:
            continue
        seen.add(fi)
        cv2.imwrite(str(out / f"hero_{session.name}_f{fi:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        n += 1
print(f"{plays} hero plays, {n} frames -> {out}")
```
- Sanity check before labelling: open 5 of the frames and confirm there are **no drawn boxes** and the hero
  is visible about 1-12 s after deploy. A `PLAY` line is the bot's decision, not proof of a deploy; HANDOFF
  measured 18.4% of taps with no elixir drop. Frames without the hero are still fine as long as they are
  fully labelled.
- (b) Optional: add ~20-30 frames at random non-hero moments of the same sessions, so the new data is not all
  one board state.

**Why every frame must be FULLY labelled.** YOLO treats every part of the image without a box as
*background*. Suppose a hero frame boxes only the hero and leaves a Knight, a Hog Rider and a Tesla unboxed.
Fine-tuning then pushes the model to say "nothing here" for those three, which erodes recall on classes that
already worked. "Fully" means every visible instance of any class in `config/detect_classes.yaml`, on both
sides:
- troops and buildings
- spells and their `_aoe` effects
- `_evo` / `_hero` variants, and champion `_ability` effects

Arena towers are not classes; the only "tower" classes are `bomb_tower` and `inferno_tower` (a). **This is why
pre-annotation matters.** board-24-5 finds 0.855 of units on the frozen 241-image live subset (a, HANDOFF
§3 / board-26 gate table). At the recall-first 0.20 threshold most boxes arrive pre-drawn, so the job is
mostly deleting and fixing, with only ~15% of units drawn by hand (b).

### Step (c) -- pre-annotate the hero folder ONLY
```powershell
.\.venv\Scripts\python.exe run.py pre-annotate --subdir to_label_hero --out data\detect\preannot_hero.json
```
- `--subdir to_label_hero` is essential. Without it the tool would also emit tasks for the **2,599** unrelated
  never-offered frames in `to_label` (a, measured). The task refs become
  `/data/local-files/?d=to_label_hero\hero_...jpg` (preannotate.py:42-45).
- Weights default to the pinned `board-24-5`, conf 0.20, `model_version` "board-24-5" (a, detect.py:1373-1394,
  preannotate.py:133). Add `--device cpu` if the GPU is busy.
- The frames go into `preannot_offered.txt`, so a re-run offers only new frames. If you delete the LS project
  and start again, re-run with `--reoffer` (a, preannotate.py:108-114).

### Step (d) -- start Label Studio and create the project
PowerShell (the variables live only in this window):
```powershell
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT  = "C:\Users\benpe\ClashBot\icebow\data\detect\images"
& "C:\Users\benpe\AppData\Local\Programs\Python\Python313\Scripts\label-studio.exe" start
```
Git Bash equivalent:
```bash
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT='C:\Users\benpe\ClashBot\icebow\data\detect\images'
/c/Users/benpe/AppData/Local/Programs/Python/Python313/Scripts/label-studio.exe start
```
It uses the existing data dir (`%LOCALAPPDATA%\label-studio\label-studio`) and your existing login. The
browser opens at http://localhost:8080 (b, LS default port; `-p` changes it). In the browser:
1. **Create Project** -> name `ClashAI-hero`. Under **Labeling Setup -> Custom template -> Code**, paste the
   whole of `icebow\data\detect\label_studio_config.xml` (230 labels). Do **not** reuse project 1's config: it
   has 225 (a).
2. **Settings -> Cloud Storage -> Add Source Storage -> Local files**:
   - Absolute local path `C:\Users\benpe\ClashBot\icebow\data\detect\images\to_label_hero`
   - file filter `.*\.jpg`
   - "Treat every bucket object as a source file" ON
   - **Check Connection -> Add Storage**, and then **do NOT press Sync**

   The path must be *inside* the document root, not equal to it. LS 1.23 ships a test asserting that a storage
   path equal to `LOCAL_FILES_DOCUMENT_ROOT` fails validation (a, `io_storages/tests/test_localfiles_validation.py`).
   That is why this is `...\images\to_label_hero`, not `...\images` as `pre-annotate`'s printed hint says.
3. **Import** -> upload `icebow\data\detect\preannot_hero.json`. Every task arrives with board-24-5's boxes as
   predictions. When you open a task, the prediction becomes the editable starting annotation (b, LS
   behaviour). Submit each task.

### Step (e) -- what to correct on every frame
- **Add `ice_wizard` on the hero**: our hero, and any enemy hero (rare today, since zero hero matches exist in
  our data; HANDOFF AL/H2). There is **no** `ice_wizard_hero` class (a, taxonomy grep). Per the owner ruling do
  not invent one; LS would let you type nothing else anyway, because the label list comes from the XML.
  - Other heroes do have their own `*_hero` classes (`knight_hero`, `wizard_hero`, ...; detect_classes.yaml
    ~192-207). So this is a deliberate exception to the taxonomy's convention.
  - It costs nothing downstream. `card_threat.base_key` folds `_hero` to the base name (card_threat.py:34-47),
    and both the live whitelist (`observation.detector_cards`) and `detect-eval` work on base names (a).
  - Box the body plus weapon/staff, the same tightness as existing `ice_wizard` boxes.
  - Replace board-24-5's wrong boxes on the hero (`knight`, small misc boxes) rather than adding a second box.
- **Delete the false `rage` box on the snowy deploy circle**, and any `rage_aoe` there too (both classes exist).
  Leave the circle unboxed: that is what makes this frame a negative.
- **Delete the false `earthquake` on the ability button** (bottom-right, frame ~(0.909, 0.765), snowman icon,
  greyed or coloured). Also delete the older ally-king-tower `earthquake` phantom if it appears (HANDOFF AL,
  "T3"). The button is UI and gets no box.
- **The snowman spawned by the ability ("Frosty Fella") has no class** (a, no snowman / `ice_wizard_hero_ability`
  in the taxonomy). Delete whatever board-24-5 calls it and leave it unboxed.
  - **Owner decision needed:** the ability's freeze visual may resemble the Freeze spell, and `freeze_aoe` is a
    class. Boxing it as `freeze_aoe` would feed the threat logic a phantom enemy spell. Leaving it unboxed
    teaches "freeze-looking = background", which may cost a little real `freeze_aoe` recall (b).
  - Recommendation: leave it unboxed, for the same reason as the rage circle.
- **Fix every other box** (wrong class, loose box, missed unit) on both sides.
  - The detector is **team-agnostic**: a Musketeer is `musketeer` on either side (detect_classes.yaml:5-6), and
    team comes from colour at inference time.
  - So labelling cannot fix "own hero tagged ENEMY"; that is the colour team read, not the class (a for the
    mechanism).
  - Never encode team in the class.
- Draw axis-aligned rectangles. Rotated boxes are folded to their bounding box on import (detect.py:654-676),
  which loosens them.

### Step (f) -- export and import
1. In LS: **Export -> JSON** (not YOLO; the YOLO export crashes on Windows with `?d=` refs, detect.py:1063).
   Save it as `icebow\data\detect\batch8_hero.json`. The `batch*` name lets a later `detect-merge` fold it in
   (detect.py:858).
2. **Hold out one whole match as hero-val, before importing** (see trap T4). With `<HELD>` = the session
   stamp whose frames go to val:
```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; r=Path('data/detect'); sp=json.loads((r/'split.json').read_text(encoding='utf-8')); held='hero_<HELD>_'; st=[p.stem for p in (r/'images'/'to_label_hero').glob('hero_*.jpg')]; [sp.__setitem__(s, 'val' if s.startswith(held) else 'train') for s in st]; (r/'split.json').write_text(json.dumps(sp, indent=0, sort_keys=True), encoding='utf-8'); (r/'val_hero.txt').write_text('\n'.join(sorted(s for s in st if s.startswith(held)))+'\n', encoding='utf-8'); print(len(st), 'hero stems;', sum(s.startswith(held) for s in st), 'to val')"
```
   `detect-import` consults `split.json` first and hashes only stems that are absent (detect.py:1147-1150), so
   these assignments stick (a).
3. Import **the old source of truth AND the hero export together** (a: comma lists are supported, and
   `batch_all.json` covers all 15,167 current train/val stems):
```powershell
.\.venv\Scripts\python.exe run.py detect-import --export data\detect\batch_all.json,data\detect\batch8_hero.json
```
   Expect roughly `imported ~15,4xx images`, with `batch8_hero.json: N matched, 0 unmatched` and **no**
   "export class(es) not in the taxonomy" line. If the image count drops far below 15,167, stop and restore
   the Step 0 backup. Close the game, PPO and any engine first: the import decodes every image into RAM before
   writing (see trap T6).

### Step (g) -- fine-tune from board-24-5 and gate it
```powershell
.\.venv\Scripts\python.exe tools\detect\train.py --model runs\detect\board-24-5\weights\best.pt --epochs 15 --patience 15 --name board --workers 4
```
- `--model ...best.pt` is required. train.py defaults to `yolo11x.pt` (train.py:98), while board-24-5 is a
  **yolo11s** model (its `args.yaml`). Without the flag you would train a different, larger network from COCO (a).
- The checkpoint's 230 class names are identical, in the same order, to `data/detect/data.yaml`, so the head is
  reused unchanged (a, loaded on CPU and compared).
- `--name board` auto-increments to **`runs/detect/board-27`**. The installed ultralytics 8.4.107 uses
  `increment_path(sep="-")`, board-2..board-26 exist, and train.py never passes `exist_ok`
  (board-24-5 `args.yaml`: `exist_ok: false`). It **cannot overwrite board-24-5** (a).
  - Do **not** use `--resume board-24-5`: resuming continues training inside that run's own folder.
- 15 epochs: board-24-5 took ~304 s/epoch (cumulative 20,966.6 s at epoch 69 in `results.csv`), so about
  75-80 min (b, similar dataset size).
  - Ultralytics defaults stay in force: 3 warm-up epochs, `close_mosaic` 10 (so mosaic is on for the first 5 of
    15), `optimizer: auto` (SGD lr0 0.01 at this iteration count) (b, library defaults read from board-24-5's
    `args.yaml`).
  - Fewer than ~11 epochs would mean mosaic never runs (b).
  - The ~250 hero frames are ~1.4% of the ~17.8k training images (12.8k real + 5k synth), seen once per epoch.
    If hero recall is still low after this run, oversampling them is the next *separate* experiment
    (one change per experiment).

Gate: the pin only moves if the challenger is >= the incumbent on presence recall AND whitelist identity AND
deck-units-passing, on the same frozen subset (HANDOFF §3, board-26 verdict). `detect-eval` defaults to the
*pinned* weights (detect_eval.py:110-113), so pass `--weights` for both models:
```powershell
.\.venv\Scripts\python.exe run.py detect-eval --weights runs\detect\board-24-5\weights\best.pt --sweep --subset data\detect\val_board15.txt
.\.venv\Scripts\python.exe run.py detect-eval --weights runs\detect\board-27\weights\best.pt   --sweep --subset data\detect\val_board15.txt
.\.venv\Scripts\python.exe run.py detect-eval --weights runs\detect\board-24-5\weights\best.pt --subset data\detect\val_hero.txt
.\.venv\Scripts\python.exe run.py detect-eval --weights runs\detect\board-27\weights\best.pt   --subset data\detect\val_hero.txt
```
- `val_board15.txt` (241 stems) contains **no hero frames**, so it is the do-no-harm gate.
- `val_hero.txt` (the held-out match) is where `ice_wizard` recall should rise. It is printed in the deck block
  as `ice_wizard R x.xx (n=..)` (detect_eval.py:200-211).
- `detect-eval` does **not** print per-class false positives (it prints R per base plus a whitelist P;
  detect_eval.py:183-220). So the `rage` / `earthquake` negatives need their own count (b, not run):
```powershell
.\.venv\Scripts\python.exe -c "from ultralytics import YOLO; import collections; from pathlib import Path; s=[l.strip() for l in open('data/detect/val_hero.txt') if l.strip()]; [print(w, collections.Counter(m.names[int(c)] for r in m.predict([f'data/detect/images/val/{x}.jpg' for x in s], conf=0.40, imgsz=960, verbose=False, stream=True) for c in r.boxes.cls if m.names[int(c)] in ('rage','rage_aoe','earthquake','earthquake_aoe'))) for w in ('runs/detect/board-24-5/weights/best.pt','runs/detect/board-27/weights/best.pt') for m in [YOLO(w)]]"
```
- `pre-annotate` cannot be reused for this count: it skips every stem already in train/val (preannotate.py:84,114),
  even with `--reoffer` (a).
- Only after the gates pass, change `detect.weights` in `config/config.yaml:1445` to board-27, then
  re-measure `observation.sim_detector_recall*` as that comment demands.

---

## 4. Traps found

- **T1 -- import wipes the split (a).** `detect-import` treats the export(s) you pass as the whole dataset:
  it clears train/val and rewrites from them (detect.py:1138-1143). Always pass `batch_all.json` together with
  the hero export, and back up first (Step 0).
- **T2 -- the ledger / queue (a).** A bare `pre-annotate` would emit tasks for 2,599 unrelated never-offered
  `to_label` frames. Use `--subdir to_label_hero`. The ledger (`preannot_offered.txt`) is append-only: after a
  run the hero frames count as "offered", so a fresh LS project needs `--reoffer`.
  - `pre-annotate` always skips stems already imported to train/val, `--reoffer` or not (preannotate.py:84,114).
- **T3 -- Sync duplicates tasks (a).** Pressing Sync on the hero storage creates a second, prediction-less task
  per frame (preannotate.py:214-215). If it happens anyway, import dedupes by basename and keeps the task with
  the most boxes (detect.py:1119-1135). So an *unlabelled* duplicate cannot beat the labelled one, but it
  clutters the queue.
- **T4 -- val leakage between frames of one deploy (a).** New stems are split by an md5 hash of the filename
  (detect.py:792-803). Frames 1 s apart from the same deploy would land on both sides, and hero-val recall
  would be inflated by near-duplicates. Hold out whole matches by pre-seeding `split.json` (Step f.2), which
  the importer honours (detect.py:1147).
  - `detect-eval` scores all of `images/val` unless given `--subset` (detect_eval.py:121-135), so always pass
    `val_board15.txt` / `val_hero.txt`.
- **T5 -- filename collisions (a).** The importer maps each export ref to disk by BASENAME, taking the first
  hit of an `rglob` over `images/**` (detect.py:707-713). 14,535 basenames already appear in more than one
  folder there (train/val hold copies of `to_label` / `rf_*` originals).
  - The `hero_<session>_f<frame>.jpg` stems are unique by construction.
  - Never name frames generically (`frame_0005.png` restarts per batch, the reason `detect-adopt` exists,
    cli.py:975-978).
- **T6 -- RAM (a for both numbers, b for the consequence).** `_ls_json_pairs` decodes every matched image with
  `cv2.imread` and holds them all in a list before writing (detect.py:725-738, 1146-1155). Decoded,
  train+val is **30.8 GB** (15,167 images, measured from headers), on a machine with **31.4 GB** RAM.
  - Expect heavy paging, or a MemoryError, if anything else is running. The last import did complete at nearly
    this size.
  - A failure *while reading* happens before the wipe and loses nothing (a, order of operations). A crash
    *while writing* is what the Step 0 backup is for.
  - (b) Each re-import also re-encodes JPEGs that may themselves be earlier re-encoded copies (the source can
    be the `images/train` copy), so quality degrades slightly per generation.
  - The durable fix is to keep paths, not arrays, until write time. That is a code change and is NOT made.
- **T7 -- class names (a).** Import remaps by NAME. Any label not in `config/detect_classes.yaml` is silently
  dropped, with one summary line (detect.py:1167-1169). Use the current 230-label XML; project 1's stored
  config has 225. `ice_wizard_hero` is not a class.
- **T8 -- wrong base model / overwriting (a).**
  - A bare `tools\detect\train.py` trains yolo11x from COCO.
  - `--resume board-24-5` continues in board-24-5's own folder.
  - `detect-eval` without `--weights` scores the pinned model, not the new one.
- **T9 -- synth confound (a).** Do not run `run.py sprites --synth` between import and training.
  Synth is 5,000 of the train images and a regeneration changes them (cli.py:1079-1083), so the hero effect
  could no longer be attributed.
- **T10 -- the Local Storage path (a from LS's own test; b whether the UI enforces it on every path form).** The
  storage path must sit strictly inside `LOCAL_FILES_DOCUMENT_ROOT`. `pre-annotate`'s printed hint ("point at
  data/detect/images") equals the root and should fail validation; point at `images\to_label_hero`.
  - With the document root unset, LS 1.23 defaults it to `C:\`. That is how 242 old tasks got `?d=Users\...`
    refs. Those still import (basename match), but they will not display unless the root is `C:\` again.
- **T11 -- `PLAY` lines are stdout-only (a).** `data/play_*.log` does not contain them. Save stdout with
  `Tee-Object`. In Windows PowerShell 5.1 it writes UTF-16, which the extraction script handles.
- **T12 -- labelling cannot fix team tags (a for mechanism).** The "hero tagged ENEMY" / own-Tornado-on-own-hero
  bug (HANDOFF AL) is a colour-based team read, not a class. Proposed code fix D1 (drop detections inside the
  ability-button disc) is also separate from this fine-tune.

STATUS: complete
