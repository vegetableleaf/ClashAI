**GAUNTLET loop L67f** — the live defect is named, and half of it is fixed

**Did:** ran the next actions end to end — placement distribution, stability, an ablation of every live-only feature, then a labelled fill-vs-blank test, then wired the fix and verified it on real frames.

**Found (measured):**
- **Placement collapses live; the gate does not.** At matched unit counts, top-1 cell share is 0.25 live vs 0.07 engine (units 2-3: 0.33 vs 0.10). No jitter — live is *more* repetitive (same-cell 61.4% vs 38.7%), so it's one defect seen twice, not two.
- **The cause is MISSING values, not noisy ones.** Supplying unit HP takes concentration 0.400 → 0.303; supplying the scalars (exact elixir, opp elixir, king HP) → 0.287; both → 0.243. Removing spell tokens (0.417), resolving unknown team tags (0.390) and forcing confidence to 1.0 (0.403) do **nothing**.
- **CONTRADICTED:** the spell-token hypothesis I flagged twice. It was the cheapest thing to test and I should have tested it before writing it down twice.
- **Against pro labels** (v3 VAL, so this is quality, not just spread): blank_both 18.78 exact cell / 52.11 card → fill_both **20.15 / 63.25**. Supplying a plausible value beats flagging it unknown on every metric.
- Also: blank_both sits **2.19 pp** under clean — not the 4.2 pp `degrade()` predicted. Third independent sign that corruption model overstates the live penalty.

**Fixed and verified:** `play.py` now hands the student the opponent-elixir estimate it was already computing and discarding, plus the king alive-proxy and unit HP. On the same 292 real frames: top-1 share **0.411 → 0.322**, distinct cells 43 → 51, play rate 0.150 → 0.170. 20/20 contract tests pass. A rescale bug (0.8 elixir → 8) was caught in review before it shipped.

**Option B graded:** clean 21.56 ± 0.07 (vs 21.04), degraded 19.45 ± 0.05 (vs 16.35). Both caveats stand: the degraded gain is circular, and seed 0 is a 13-epoch crashed run. Its live gate is *shifted*, not broken (equal-rate tau 0.16) — retracting my earlier "it fails live".

**Next:** the unit-matched version of the full ablation (how much of the residual 0.243 is sparsity?), then a live A/B judged on the label-free instruments plus pro agreement.
**Cost:** commits 1c29e4b, f9b9d2c, a0e1b85, ac43945. Box idle.
