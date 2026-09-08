**GAUNTLET loop L67d** — the student is wired to the live path, and the first live measurement contradicts an S4 premise

**Did:** wrote the live adapter (`clashrl/student_live.py` + 41 lines in `play.py`), then ran the student on REAL recorded frames through the REAL detector — no game, no clicks, no trophies spent.

**Found (measured):**
- **`degrade()` is wrong about the gate.** Elixir-matched, 3 seeds × 3 sessions, fraction of states where the student wants to play: engine VAL **.294–.298**, real live frames **.248–.325**, `degrade()` twin **.446–.524**. Real live behaves like the ENGINE; my model of the live shift makes the student 15–23 pp more trigger-happy than the real detector does. So the degraded VAL is **not** a proxy for live gating — and a B gain on it is not evidence of a live gain. (My first, uncontrolled read of this — .247/.172/.373 — was confounded by elixir mix; superseded.)
- **Latency is a non-issue:** student 28.7–37.6 ms per decision, detector 45–80 ms, against an act_period of 1.5 s.
- The student picks 4–9 distinct cards and 8–19 distinct cells across a session (not stuck), fails to read the tray on 5–9% of frames, and sees 29–78 spell tokens per run — a token type the training rows contain **zero** of.

**Means:** S4's premise ("live will be much worse than the bench") is weaker than L67a stated. On the one axis measurable live so far, real input costs nothing. Placement and card choice live are still unmeasured — the next cheap test is your own recorded clicks as live-labelled placements (the L63 own-click harness, re-pointed at the student).

**Live path — exactly what changed and how to revert:** `play.py` gains 41 lines behind a config key `play.student_ckpt`. **Unset = your live behaviour is unchanged** (verified: the key resolves to None today and the block is skipped). When set, the student decides card+cell only; deploy clamp, aim assists and the affordability mask all still run, and an unaffordable or unreadable answer is a WAIT, never a silent fall-back to the old CNN. Revert = unset the key, or `git revert 597ddb7`.

**I did NOT run ladder matches** — that's yours to start when you're up, and it's ~5 minutes with me watching the log.

**Next:** option B is training (seeds 0+1 in parallel, seed 2 after; 2-seed read is a screen, 3 seeds is the result). Numbers on both VALs by morning for two seeds.
**Cost:** two of my own bugs found and fixed (an NpzFile indexed inside a loop → MemoryError; three parallel trainers → 160 MB free RAM, killed at epoch 0, nothing lost). Commits 597ddb7, 89fd806.
