# crforge Stage 1 pilot (ticket A2b), status 2026-10-27: only the cost check has run

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted. Pod 33920, `/workspace/seeds/cost/`.

| D1 check | go | status |
|---|---|---|
| crown sequence, crforge minus fin16 | ≥ +0.15, CI above 0 | not run: the extractor and harness port come first (split below) |
| SME pilot | ≥ 45/50 | not run |
| faults on HF replays | ≤ 0.5% | not run. Related: 0 faults on 892 + 669 + 300 random-play battles (a, CRFORGE_S0.md and below) |
| cost | ≤ 1.5 core-s per match, ≤ 16 GB per pod for 24 actors | **pass on the engine alone (a): 0.87 core-s per match, about 9.9 GB for 24 JVMs** |
| parsed stats = device table pull | 100% | not run |

## Cost (a)
Setup:
- 24 JVMs at once, each `-Xmx1g -XX:ActiveProcessorCount=1`, one battle at a time (`Census decks`).
- Deck pairs: the 223 real Ranked pairs, 4 repetitions, so 892 battles.
- Random plays (3 decisions in 10), L16. Every battle ran to its end: 3,359,812 ticks in all, about 3,767 per match.

Results:
- Wall time 25 s.
- CPU: 754 s user + 25 s sys = **779 core-s over 892 matches, 0.87 core-s per match**. This includes JVM start-up, table loading and the JIT, so a long-lived actor will cost less (b).
- Memory: about 9.9 GB total RSS for the 24 JVMs, sampled 8 s into a second identical run. The `pgrep` count also caught 2 shell processes, which hold little memory.
- **Not included:** the policy forward pass (about 16 s CPU per match, EVAL.md) and the Python/JPype bridge.

## Proposed split of the rest of A2b (one context cannot hold it)
The plan sized this harness port at 3-5 engineer-days (REPORT_engine.md).
1. **A2b-1, extractor.** Live log to a crforge `ScenarioPlan`-equivalent input:
   - decks, forms and levels for both sides, from the battle log API (exact per-card levels) rather than max_hp read-offs;
   - tower levels;
   - our deal (exact, CRFORGE_S0 §3);
   - plays with 2 candidate ticks and a tile, reusing `fights.deployments` / `seen_casts`;
   - game version per match. Before 10-27 ~04:25 every log carries `phase2.build`; check whether the client changed after the maintenance.

   Test: the replay recording of 10-26 gives exact plays for both sides, so it is the ground-truth check of the extractor.
2. **A2b-2, J7 on crforge.** A crforge driver behind the `replay_metrics.j7()` interface, run on ≥ 300 post-10-19 RNG-free matches (census list: `live_attr.py` deck rule), crforge vs fin15 on the same inputs. fin15 runs where the parity harness already runs it.
3. **A2b-3, SME.** Full-match exactness with a first-divergence census. Start with the 10-26 replay-recorded match: it has exact inputs, but Princess makes it an RNG match, so its 2 seed candidates go in too.
4. **A2b-4, cost with the policy in the loop.** JPype or a batched VectorEnv per pod.
