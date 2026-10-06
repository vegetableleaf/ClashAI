**October 6: Public hand estimates and learned card retention**

**Work completed**

Built a public opponent-hand representation from memory-board play history, with unknown states, cycle bounds and conditional Mirror identification. Prepared and independently checked all 213,995 training and 54,723 development rows, keeping future response windows separate from model inputs.

Trained two models from the same eligible ordinary v5 weights, each for exactly 1,000 updates of 128 draws. Both have identical added capacity and training settings; only the hand model receives the hand estimates. Original expert actions and losses are unchanged. No counter table, card reservation rule or holding reward was added.

Qualified strict loading, original initial predictions, finite gradients, public-input privacy, future-event exclusion, resets and deterministic token ordering. Three earlier qualification failures remain documented; the corrected implementation passed. A separate opt-in live companion adds hand estimates to the public audit.

The final checkpoint also passed offline command-line loading. An initial companion-script import failure was fixed in a separate version; its failed receipt is preserved. No live hand-model match was started.

**What we found**

These are recorded-action agreement results on the same corrected observations. R1e here is not its original live-input evaluation. All four models use identical labels and scoring; the parent was already exposed to this broader data.

Rocket aim within one tile: R1e 290, ordinary v5 292, blind control 294, hand model 293 (out of 955).

Complete Rocket actions: R1e 54, ordinary v5 77, blind control 82, hand model 85 (out of 955).

Late Rocket actions: R1e 14, ordinary v5 22, blind control 26, hand model 25 (out of 320).

Hand-model gains against ordinary v5: Rocket aim +0.105 percentage points; full Rocket +0.838; late Rocket +0.938. The unchanged required gains are +5, +2 and +2 respectively.

Hand-model gains against blind control: Rocket aim -0.105 percentage points; full Rocket +0.314; late Rocket -0.312. The unchanged required gains are +5, +2 and +2 respectively.

Barrel responses (63 labels):

R1e: 36 correct-lane Logs, 20 wrong-lane Logs, 7 not fired; 18 complete expert actions.

ordinary v5: 40 correct-lane Logs, 22 wrong-lane Logs, 1 not fired; 20 complete expert actions.

blind control: 39 correct-lane Logs, 22 wrong-lane Logs, 2 not fired; 19 complete expert actions.

hand model: 40 correct-lane Logs, 22 wrong-lane Logs, 1 not fired; 19 complete expert actions.

Witch: R1e 332, ordinary v5 339, blind control 357, hand model 361 (out of 726).

Night Witch: R1e 156, ordinary v5 161, blind control 176, hand model 168 (out of 373).

Furnace: R1e 538, ordinary v5 549, blind control 578, hand model 570 (out of 1174).

Defense: R1e 3952, ordinary v5 4011, blind control 4174, hand model 4122 (out of 8183).

Late-game actions: R1e 1949, ordinary v5 1984, blind control 2104, hand model 2066 (out of 6422).

General card agreement (17,192 PLAY labels): R1e 11348, ordinary v5 11403, blind control 11357, hand model 11211.

Overall action agreement: R1e 30968, ordinary v5 31962, blind control 33236, hand model 32815 (out of 54723).

R1e: 2611 correct PLAY actions and 28357 correct WAIT actions; defense splits into 366 PLAY and 3586 WAIT.

ordinary v5: 2602 correct PLAY actions and 29360 correct WAIT actions; defense splits into 369 PLAY and 3642 WAIT.

blind control: 2401 correct PLAY actions and 30835 correct WAIT actions; defense splits into 357 PLAY and 3817 WAIT.

hand model: 2410 correct PLAY actions and 30405 correct WAIT actions; defense splits into 348 PLAY and 3774 WAIT.

The descriptive available-and-retained response slice: R1e 18373, ordinary v5 18944, blind control 19761, hand model 19504 (out of 29437).

Predicted spending of that later response card in this slice: R1e 3019, ordinary v5 2740, blind control 2363, hand model 2501. This is not an optimal-holding score.

**What it means**

The hand reader is useful but imperfect: on exposed past native re-drives, the Mirror-aware successor made 4,367 complete development estimates out of 10,424 queries; 4,253 were exact (97.39%). The earlier version had 4,245 correct of 4,354 (97.50%). Mirror inference added coverage but did not improve precision. Missed or delayed public play sightings remain possible; no hidden opponent state is used.

Expert windows include Log before Barrel, Tesla before several win conditions and Rocket before Collector. However, selecting a card because it is actually used later strongly favors retention or cycling back. Windows overlap and are not independent successes. These descriptive sequences do not establish intention, physical counter value, profitable retention or improved win rate. No new simulator matches or assistant-started live games were run for the hand models.

**Decision**

Against ordinary v5, the hand model missed all three required Rocket improvements. General card agreement fell by 192 of 17,192 PLAY decisions, exceeding the allowed decline.

Against the blind control, it missed all three Rocket improvements and the general card protection. It also regressed on Night Witch, Furnace, defensive and late-game action agreement.

The hand model is REJECTED for continuation by this fixed trial. The blind arm is an experimental control, not a replacement. Other improvements cannot override failed requirements. Neither model is accepted or deployed. All gameplay, physical, statistical, public-input and remaining final acceptance requirements stay in force.

**Next**

Diagnose where the added hand information changes decisions before choosing another learning recipe. Preserve the fixed budget and original failures; do not continue rejected weights or retune thresholds.

Separately improve qualification of public play timing and Mirror event identity. Continue to evaluate holding by downstream defense/resources/wins, not by how often a card is saved.

Training loss for blind control, first versus last 256 updates: 5.1226 to 5.1314. This is training loss, not fixed evaluation accuracy.

Training loss for hand model, first versus last 256 updates: 5.1239 to 5.0958. This is training loss, not fixed evaluation accuracy.
