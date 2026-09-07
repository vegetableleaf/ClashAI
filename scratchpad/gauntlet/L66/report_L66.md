**GAUNTLET L66 — runtime is on the VM; channel is 441.6 h; my pilot was wrong and is discarded**

**Q2 done.** The 1.1 GB runtime is on `clashbot-s3`. `libg.so` hashes identical on both ends (`fa6704b8…246ba`), which is the exact hash the sandbox's manifest pins — the version freeze survived the move. Nothing from any `data/` folder went with it.

**Q1 — the channel:** 1,382 videos, **441.6 hours**, median 17 min (metadata only, nothing downloaded for this count). That's comfortably more than the 78–139 hours that buys one corpus doubling — *if* enough of it is icebow.

**Built the deck identifier.** It reads the card **hand**, not the board — fixed slot positions, matched against our 2,174-crop card template library, evo folded to base. Four passes, three of them wrong: (1) it compared a whole card against templates that are tight crops of just the art, so it ranked wrong cards above right ones; (2) evo vs base naming; (3) it kept only each slot's top-2 guess, so a card that wasn't any slot's best guess scored zero — which made a **known icebow video** score zero. All three fixed.

**Then I threw out my own pilot.** Twelve random channel videos, 20-second clips, all scored 0.48–0.55 against known icebow at 0.62–0.63. Looked like a clean 0 out of 12. It means nothing — controlled test on footage I *know* is icebow, cut the same way:

• 20 s slice → **0.558** (i.e. reads as "not icebow")
• 180 s slice → **0.625**
• 180 s slice, 20 frames instead of 6 → **0.625**

**Slice length decides it; frame count is irrelevant.** Twenty seconds is two or three hands — an 8-card deck hasn't cycled, so cards never enter the hand and the score collapses. Every pilot clip was measured in the regime where real icebow reads ~0.56. The eyeball check agreed before the numbers did: the highest "negative" clip visibly shows tornado, rocket and a greyed x-bow.

**So I have no icebow-fraction estimate yet**, in either direction. Re-running the same twelve at 180 s now (paired), which gives a real hit rate.

**Shape of the full job:** stage 1 = one match (~180 s, ~30 MB) per video → ~40 GB to classify all 1,382; stage 2 = full download of the hits only.

**One caveat I keep flagging:** a doubling is worth +1.50 pp, and mined video is *not* engine-quality data — our slope was measured on replays driven through the sandbox with exact unit state. Nothing yet says what a mined replay is worth against a driven one, and I shouldn't assume they're equal.

**Also, plainly:** bulk-downloading the catalogue breaches YouTube's ToS and the videos are HunterCR's work. Your call, but I'd rather you make it deliberately than have it happen as a side effect.

**Cost:** ~1 h. §5cs.82.
