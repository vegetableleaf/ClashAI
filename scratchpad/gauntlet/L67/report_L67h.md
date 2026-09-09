**GAUNTLET L67h** — search over the student WORKS, and every control fails to explain it away

**Did:** built the missing bridge (sim state → the student's obs contract, verified faithful against engine state), ran the student through the sim's own match loop, then rolled out its own shortlist and played the best-scoring candidate. Re-measured from scratch rather than inheriting the old CNN's +19.9σ, which is not evidence about this model.

**Found (a), 12 matches, paired per seed, degraded view = what the live student sees:**
```
search      +1.714 ± 0.420  t=4.08   11/12 wins   37.3 plays/match
force_play  -0.322 ± 0.425           3/12         53.9
random      -0.571 ± 0.453           2/12         55.6
never play  -1.528 ± 0.426           0/12          0
baseline         --                  3/12         50.3
```
Absolute: student alone **25.0% wins / tower −0.871**; searched **91.7% / +0.843**.

Controls: NOT "it just plays more" (force_play plays 54/match with no rollouts, null-to-negative). NOT the shortlist alone (a random pick from the SAME candidates is worse than baseline). NOT the degenerate WAIT the scorer's elixir penalty could reward by construction — never-play is the worst arm on the board. Search plays **less** than the student while winning far more: restraint, the same signature the CNN's N=1 arm showed.

**Means:** distillation is licensed on this model, not by inheritance. Combined with today's other two numbers — the pro-agreement ceiling is 27.5% and the student is at 21.0 (76% of it), while the pro's own tile sits in its top-3 44% of the time — the picture is consistent: imitation is nearly exhausted, and the value that remains is in *choosing* within the shortlist, which is what a search evaluates and a policy can be taught.

**Does NOT establish:** it is the SIM (sim-optimal ≠ real-game-optimal; scripted ladder opponent); the teacher is PRIVILEGED (rollouts fork the true engine, the student sees the degraded view) — the spec's own gate is to check student↔teacher agreement on held-out states BEFORE a full labelling run; n=12.

**Next:** disjoint-seed confirmation (running) + cells=1 ablation (the CELL search was worth ~nothing for the CNN — does it matter for this model?), then the privileged-teacher gap check, then corpus labelling.

**Also shipped today, no retrain:** goblin-barrel Log aim now targets the predicted LANDING (owner's report confirmed: mid-air sightings sit a median 7.33 tiles from the landing, more than twice the Log's width); opponent-elixir input defaulted off (the freeze); estimator repaired and graded against sim truth (|err| 1.53 vs 1.84, bias +0.01 vs −1.68); deck-veto regression tests. Two of my own claims retracted along the way — the "gate ignores elixir" reading (conditioned sample) and the "estimator ratchets to a pinned 10" mechanism (contradicted in sim).
