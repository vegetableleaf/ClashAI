### §5cs.82 -- L66 (2026-09-07 02:4x-04:0x UTC): **the runtime is on the VM (libg.so hash matches byte-for-byte) and the channel holds 441.6 hours across 1,382 videos. A deck identifier was built in four passes, three of which were wrong; the pilot that used it is DISCARDED because 20-second clips cannot show an 8-card deck -- measured on known-icebow footage, not argued**

**A. Owner rulings.** Q2 granted (runtime may be copied to the VM). Q1 answered with a task: identify which of HunterCR's videos are icebow by inspecting frames, verify card-by-card that all eight are present, and see how much footage that yields.

**B. Runtime is on clashbot-s3 (a).** 1.1 GB transferred over ssh (`tar | ssh tar -x`), 5 APKs + 14 `.so` + 383 DataTables. **`libg.so` sha256 `fa6704b8...246ba` on both ends** -- identical to the hash `bindings/runtime-manifest.json` pins, so the version freeze survived the move. Nothing under any `*/data/` path was included.

**C. Channel inventory (a), metadata only, no video fetched.** `yt-dlp --flat-playlist`: **1,382 videos, 441.6 hours, median 17.0 min**, 1,379 of them over 10 minutes. So the raw supply comfortably exceeds the 78-139 video-hours that §5cs.80 measured as one corpus doubling -- *if* enough of it is icebow, which is the open question.

**D. The deck identifier (a), `scratchpad/gauntlet/L66/deckid.py` + `profile.py`.** Read the HAND, not the board: the four hand slots and the "Next" slot sit at fixed fractions of a full-screen portrait capture, the art is large and unoccluded, and a cycling deck shows all eight cards over enough frames. Matching is NCC against `icebow/templates/cards/` (2,174 crops, 110 cards, 64x80, captured from our own screen), evo folded to base keys. Slot boxes were read off a labelled coordinate grid on a real frame, not guessed. **It took four passes and the first three were wrong:**

1. **Whole-crop dot product.** Compared a slot box (card + border + elixir badge) against templates that are *tighter* crops of just the art. Calibration on known-icebow footage: non-icebow p90 0.635-0.691 sat **above** the icebow median 0.51-0.567 -- i.e. it ranked wrong cards higher than right ones. Fixed by sliding the template inside the slot at multiple scales (x_bow 0.80, rocket 0.82, tornado 0.75, tesla 0.73 after the fix).
2. **Evo names.** The deck is `tesla_evo`/`knight_evo`, the matcher reads `tesla`/`knight` off the same art. Folded to base keys -- deck identity does not depend on which two slots are evolved.
3. **Kept only each slot's top-2.** A card that was never any slot's argmax got no score and defaulted to 0.000, which made a **known-icebow video read `worst_icebow = 0.000`**, indistinguishable from any other deck. The per-card scores were being computed and thrown away. Fixed by returning the full vector (`slot_card_scores`).

The surviving readout is per-video, not per-slot: for each of the eight icebow cards take its max score over all slots and frames; the verdict is the **worst** of those eight. A real icebow deck's weakest member still beats every card it does not play; another deck can share two or three commodity cards (log, rocket, skeletons) but not eight.

**E. THE PILOT IS DISCARDED (c) -- and this is the load-bearing finding.** Twelve videos sampled at random from the channel, 20-second clips, all twelve scored `worst_icebow` 0.483-0.545 against known-icebow footage at 0.623-0.634 -- an apparently clean 0/12. **It is uninformative.** A controlled test on footage known to be icebow, cut the same way the pilot was:

| footage | slice | frames sampled | worst_icebow |
|---|---|---|---|
| known icebow (HunterCR_1) | 20 s | 6 | **0.558** |
| known icebow (HunterCR_1) | 180 s | 6 | **0.625** |
| known icebow (HunterCR_1) | 180 s | 20 | **0.625** |

**Slice LENGTH decides it, frame count does not** (0.625 either way). Twenty seconds is two or three hands; an eight-card deck has not cycled, so several cards never enter the hand and the minimum-over-eight collapses. Every pilot clip was measured in the regime where genuine icebow reads ~0.56. The eyeball check agreed before the numbers did: the hand strip of `NYAWcJcGU3E` (the highest "negative" at 0.545) shows tornado, rocket and a greyed x-bow. **No conclusion about the channel's icebow fraction survives, in either direction.** Re-running the same twelve at 180 s, paired.

**F. What the re-run costs, and the shape of the real job (b).** One match (~180 s) at <=720p is ~30 MB, so classifying all 1,382 videos costs ~40 GB and one pass of downloads; only the videos that pass would then be fetched in full. That is a two-stage design and the stage-1 slice must be at least one match long -- which is exactly what E establishes and what a 20-second stage 1 would have got wrong at scale.

**G. Standing caveat, unchanged by any of this (b).** Even a large icebow haul buys corpus doublings at +1.50 pp each (§5cs.78), and video-mined data is not engine-quality: the scaling slope was measured on replays driven through the sandbox with exact unit state, while mined data would carry detector noise in both observation and label. **The slope does not transfer to noisier data by assumption**, and nothing measured so far says what a mined replay is worth relative to a driven one.
