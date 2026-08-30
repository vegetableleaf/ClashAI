# Gauntlet log

Terse cross-loop ledger for `/gauntlet`. One block per iteration, newest at the bottom.
Full findings go in `HANDOFF.md`; this file exists so the next loop can orient in ~20 lines
instead of re-reading a 6,500-line handoff.

Format:

```
## L<n> — <YYYY-MM-DD HH:MM> — <goal, abbreviated>
DID      one line
FOUND    the number(s), labelled measured / untested / contradicted
MEANS    what changed about the plan
NEXT     the single action the following loop should take
STATE    what is running, what is queued, what is blocked
```

---

<!-- no loops yet; /gauntlet appends here -->
## L1 — 2026-08-30 11:05 — evaluate brainstorm; improve decision-making (spells, defense, x-bow)
DID      reviewed all 698 lines of LIVE_POLICY_PERFORMANCE_BRAINSTORM.md -> research/BRAINSTORM_REVIEW.md;
         built tools/response_regret.py v0 (paired per-state regret at enemy-play events, wraps
         Searcher.candidates/_rollout); prepared the 5y band retune as a gated patch
         (scratchpad/gauntlet/L1/band_retune.py); verified canvas_stack:1 claim true.
FOUND    measured: benchmark smoke (1 match, contended box, NOT a result): 7 events, policy waited
         all 7, a play scored better at 4/7. Doc's numbers check out against the ledger; its 14.1
         premise is refuted by 5ab. Discovery: TWO defense bands exist -- sim.* (tiles) and env.*
         (SCREEN-SPACE, foreshortened) -- the live one cannot take tile numbers without calibration.
MEANS    spine of the doc adopted (benchmark -> joint scorer -> temporal -> world model); two-speed
         router rejected pending bucket evidence; benchmark doubles as the 5ab power fix.
NEXT     when ab3 wave 3 lands: final 3-seed read, apply band_retune.py, then a real regret run
         (8 matches, idle box) on m18000 + ab3 checkpoints as the benchmark's first reference.
STATE    running: ab3 wave 3 (s43 ~m1175/1500). queued: retune apply, 3-seed read, regret reference.
         blocked: none. live env.* band flagged, needs screen mapping.
