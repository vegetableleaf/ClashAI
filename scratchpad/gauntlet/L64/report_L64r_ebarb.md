**GAUNTLET L64r (cont.)** — the ~19% drive failures are not random loss, they are a perfect filter on one archetype
**Did:** while the drive ran, tested the failed vs ok tags against battles.csv (no engine time) to see whether losing them costs us a random 19% or a biased 19%.
**Found:**
- (a) **0 of 563 ok replays have an evo-Elite-Barbarians opponent; 129 of 134 failures do (96.3%).** Across the whole icebow crawl, **381 of 2,073 battles (18.4%)** face one.
- (a) **Not skill-biased:** failed vs ok median rating 2072 vs 2057.5, our win rate 0.343 vs 0.367. It is matchup-biased — the failed opponents are golem / battle-ram / mortar beatdown decks that happen to run E-barbs.
- (a) **Consequence:** every corpus since v3 has been blind to ~18% of ladder matchups. **The model has never seen a pro defend an E-barb push**, and the S1 agreement numbers (18.17 / 19.84 / the v5 point tonight) are all measured on a distribution with that archetype cut out.
- (a) My own bug, caught on the second pass: `opponent_deck` is comma-separated, not pipe-separated — the first pass compared whole deck strings as if they were cards.
**Means:** the scaling curve is still valid (all three points share the same exclusion), but the corpus has a doctrine-shaped hole that more data will not fill. This is the strongest argument so far for spending sandbox time on evolution support for card 26000043 — it buys ~18% more corpus AND the archetype we are weakest against.
**Next:** unchanged — v5 chain fires when the drive exits (icebow 699/845 now), then hogeq's 423.
**Cost:** CSV read only, no engine time.
