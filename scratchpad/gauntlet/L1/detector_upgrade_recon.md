# GAUNTLET L1 — detector upgrade recon (2026-09-02)

Owner rulings this loop (AskUserQuestion, all four = my recommendation):
1. Decision time = **LATENCY now** (<100 ms wall clock), act_period stays 0.6 s; lowering the
   period is a separate, retrained experiment queued behind this gauntlet.
2. PPO = **stop at ~18k episodes** (~6 h from 7.7k at 0.5 ep/s), then board training takes the GPU.
3. Installs = **isolated venv** for anything new; do not disturb `icebow/.venv` (torch 2.11.0+cu128).
4. Budget = **cheap screen, then ONE full run** (~24 h) of the winner with kitka folded in.

## 1. The isolated venv may not be needed at all (measured)

`icebow/.venv` has **ultralytics 8.4.107**, torch 2.11.0+cu128, CUDA True (RTX 5050 Laptop).
Its bundled model configs already include:

    11/  12/  26/  rt-detr/  v10/  v9/  v8/ ...
    26 -> yolo26, yolo26-p2, yolo26-p6, yolo26-seg, yolo26-obb, yolo26-pose, yoloe-26

So **YOLO26, YOLO12 and RT-DETR are all already supported by the installed package** — no install,
no venv, no risk to the deck venv's torch. `tools/detect/train.py` already accepts `--model`
(and already ships `rtdetr-l.pt`, `yolo26n.pt`, `yolo11s.pt` in `tools/detect/`).
An isolated venv is therefore only needed if a NON-ultralytics candidate (RF-DETR, D-FINE, DEIM)
survives the paper screen. That decision is deferred to the screen.

`yolo26-p2` is worth noting: a P2 (stride-4) head is the standard answer for SMALL objects, which
is exactly what CR units are at imgsz 960. Untested here; it is a screen candidate in its own right,
independent of the v11->v26 architecture change.

## 2. What board-26 actually is (the bar to beat)

`runs/detect/board-26/args.yaml` + `results.csv`, epoch 120:

| | |
|---|---|
| model | yolo11s, imgsz 960, batch 4, workers 4, patience 30 |
| wall  | **86,183 s = 23.9 h** for 120 epochs |
| mAP50 | **0.860** |
| mAP50-95 | **0.704** |
| precision / recall | 0.845 / 0.826 |

Dataset (`data/detect/data.yaml`): nc=**230**, train = 12,821 real + 5,000 synth images
(55,642 + 33,921 instances), val = 2,346 images / 10,179 instances.

## 3. kitka's data — smaller than it looks, but real, and pointed at a specific hole

`icebow/data/kitka/detector_data`, 194 MB, 10,957 PNGs, **no bounding boxes**: it is a SPRITE /
SEGMENT library for the synthetic-composition pipeline `katacr_segments.py` already implements.

* `segment/` — 183 class folders (our katacr import has 154; **29 not in katacr**).
* `dataset_updates/` — 3,165 crops / 29 classes (5 air, 21 ground, 3 spells), mostly evolutions.

**First read was wrong and is retracted here.** A naive name-normalizer said "88 classes new to us";
handling `evolution`->`evo` and plurals drops that to 14, and checking those against the detector's
own 230-class list drops it again. The honest breakdown:

* Our sprite bank already holds **42,313 crops / 184 classes**. kitka adds **6,200 crops across 128
  classes we already have** — about +15% variety. Useful, not transformative.
* Of the **45 detector classes with NO sprites at all**, kitka fills exactly **one**: `pekka_evo`
  (324 crops). The other 44 stay empty (hero abilities, `*_aoe` decals, `mirror`, `void`, ...).
* **The actual win is the THIN classes** — where our bank has 1-7 sprites, so every synthetic
  instance of that class is literally the same pixels and the class cannot be learned from synth:

| class | ours | + kitka |
|---|---|---|
| pekka_evo | 0 | 324 |
| hunter_evo | 6 | 540 |
| cannon_evo | 6 | 236 |
| lumberjack_evo | 3 | 186 |
| electro_dragon_evo | 7 | 160 |
| dart_goblin_evo | 1 | 142 |
| vines | 1 | 122 |
| executioner_evo | 7 | 88 |

That is **9 evolution-era classes moving from unlearnable-by-synth to properly represented.**
Defensible, targeted, and cheap to fold in — but it is not a wholesale dataset upgrade, and I should
not sell it as one.

## 4. ⚠ TRAP — mAP on the current val set CANNOT measure the kitka change (measured)

**69 of the 230 classes have ZERO instances in the val set.** Ultralytics averages AP only over
classes that have val instances, so those 69 contribute nothing and can never move. Worse, the
classes kitka fixes have **1-2 val instances each** (`hunter_evo` 2, `cannon_evo` 1,
`lumberjack_evo` 1, `dart_goblin_evo` 1, `electro_dragon_evo` 1, `vines` 1, `executioner_evo` **0**,
`pekka_evo` **0**), so their AP is a coin flip, not a measurement.

Consequence for the promotion verdict: **a kitka-driven improvement is invisible to mAP50 on this
val set.** If I compare a kitka run against board-26's 0.860 and call it a null, that null would be
an artifact of the instrument, not a fact about the detector. This is the same class of error as
HANDOFF §8's "never compare numbers from two different instruments".

Mitigation (to settle before the full run):
* `run.py detect-eval` already exists and is the RIGHT instrument — presence recall
  (class-agnostic), whitelist identity recall folded to base cards, and per-ROLE gates
  (UNIT >= 0.80). It is still limited to what is IN the val set, so it does not fully solve this.
* Needed: a val slice that actually contains the 9 thin classes. Cheapest honest option is a
  HELD-OUT SYNTHETIC val built from kitka sprites the training synth never saw, reported
  SEPARATELY from the real-frame val (never averaged into it).

## 5. Box state at loop close

* PPO cuda run alive: 7,700 -> target 40k at 0.5 ep/s. Background watcher armed (task b7720tqpr):
  fires at >= 18,000 episodes or if the process exits.
* GPU is PPO's until then. Guardrail: no training/throughput benchmark on a contended box, so the
  candidate screen and any detector latency benchmark WAIT for the GPU.
* Latency work that does NOT need the GPU (capture, warp, tracker, threat/observation build) can
  start next loop while PPO runs.

STATUS: complete
