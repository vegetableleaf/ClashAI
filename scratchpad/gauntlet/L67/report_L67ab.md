**GAUNTLET loop L67a+b** — S4 (student on the live path) + your FirstLight_CR pointer

**QUESTION (blocked, pick one):**
(A) Re-open the data axis: pull the exact-icebow games out of FirstLight's public 252k-replay dataset (~2,000 sides est., one more corpus doubling → v6), train 3 seeds, grade on the same v3 VAL. S2 slope predicts +1.5 pp exact cell. Risk: their skill tier is unknown (trophies stripped) — a weaker corpus could lower pro agreement; that is what the A/B measures.
(B) Stay on S4: retrain v5 with the live degradation as augmentation, 3 seeds, graded clean + degraded. Directly attacks the −4.2 pp measured below.
(C) Both, A first (my recommendation — A is cheap and its answer decides whether the universal-card model is worth building).
Answer A / B / C, or something else.

**Did:** (a) built a live-degraded twin of the v3 VAL (same 3,796 plays, every state through `obs_contract.degrade`) and scored v5lat s0/s1/s2 on clean vs degraded; (b) cloned and read FirstLight_CR end to end (docs, model, IL loss, engine API) and counted one shard of its dataset.

**Found:**
- (a, measured) Live shift cost: exact cell 21.4/21.0/20.5 → **16.7/16.6/17.1** (−4.2 pp); card 63.2/63.2/62.7 → **52.4/48.3/51.1** (−12.4 pp); placement error 3.54-3.61 → 4.53-4.64 tiles; gate acc .82 → .74-.76. That single shift costs more than a whole corpus doubling buys (+1.5 pp).
- (a) FirstLight = OFFLINE stack: modified Null's Royale client + C++ engine probe, Python reset/step, 252,238 RoyaleAPI replays (same source as ours, public on HF), 12.7 M-param universal-card LSTM (ours 1.26 M), PPO at 1,528 concurrent matches on 8 GPUs. Its env docstring: "without screenshot interpretation or ADB touch injection" — **no live path at all**.
- (b → unsupported) "has not plateaued": the repo has **no learning curve**. The only numbers are argmax win rates vs frozen opponents (General 73.3% vs IL; Hog specialist 2 89.9/87.0/88.0%), which the author says not to read as one curve. Their IL-only model is "modest"; all gains are PPO-vs-frozen-pool, and they hit our exact L62 trap: an 80.1% run where 296 of 306 wins came against an IL that played ≤3 cards. "Hall of Fame" is author-reported, no code path. In our metric (pro agreement) they measured nothing.
- (a) What they have that we don't: ~150× the replays and ~400× the engine throughput, and a card encoder that lets EVERY replay train one model (ours uses only exact-icebow games).
- (b, one shard) Their dataset: 41 exact-icebow sides per 5,000 replays → ~2,070 over the whole set; 176 x-bow+tesla per 5,000 → ~8,900.

**Means:** The lesson from FirstLight is scale + a deck-general model, not a trick that removes a plateau. The cheap, honest way to test "their gain is available to us" is to feed their icebow games through our own instrument (A). The S4 finding stands regardless: the live path needs a degradation-aware student before wiring (B).

**Next:** your call above. Nothing running; box idle; VM off.
**Cost:** ~2.5 h wall. Committed 1c54a07 (HANDOFF §5cs.95, review at scratchpad/gauntlet/L67/firstlight_review.md). Clone, parquet shard and .npz are local only.
