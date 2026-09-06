**GAUNTLET loop 63d** — square one, S0 step 2: the shared observation contract is built and tested.
**Did:** two read-only audits (engine schema; live/detector path + every recording on disk), a written spec, then a new deck-agnostic package `pipeline/` (obs_contract.py, vocab.py, decks/icebow.yaml + hogeq.yaml, 19 tests). Stale sessions messaged per your ruling; clashbot-c9 confirmed idle.
**Found (measured):**
- No live recording on disk carries ground truth, and nothing logs player tag / battle time — a live match cannot be re-driven in the engine from existing data. The fidelity number has to be built: own-click test next, tag+timestamp logging before S4.
- The deployed `policy_rl.pt` has no `algo` key, so play.py used the legacy Q(wait)>=Q(play) gate — the "sample the gate" ruling never reached the live path for that checkpoint.
- Contract: vocab = detector's 230 classes + 2 engine-only; 122/122 cards map; sub-spawn rules measured at level 11 (mother-witch hog untested). 19/19 tests pass (their run and mine). Independent sweep: 211 recordings x 80,668 frames x both sides = 161,336 conversions, 0 unmapped, 0 out-of-range.
- Contradicted: the old builder's "kind 12 = deploying" for buildings — 22% of those rows are damaged buildings.
**Means:** one obs builder now feeds both engine and detector into the same BoardState/tokens; hogeq inherits by construction (one package, per-deck yaml — the two clashrl copies had already diverged by 20 files). `degrade()` lets S1 train under the measured detector corruption (recall 0.855 / precision 0.886).
**Next:** S0 step 3 — corpus rebuild for BOTH decks through the engine (background, ~1–2 h on 2 slots; first hogeq acceptance number), with the own-click contract test on the GPU in parallel.
**Cost:** ~60 min wall, 3 agents; nothing training; engine up, free RAM 4.8 GB.
