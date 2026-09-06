### §5cs.55 -- L63c (2026-09-06 01:2x-01:5x UTC): **PROPOSAL APPROVED; four rulings recorded (§6); S3 compute estimate for the cloud decision; S0 begins with the engine guest-service reboot.** Concurrent-session trap: while L63b was being written, an OLDER gauntlet session (L62m) woke on the crawl's completion and wrote §5cs.52 -> collided -> renumbered itself §5cs.54 (commits 8544985/aaf36f9). Two sessions were editing HANDOFF at once; the owner should close the L62 session or it will fire again on the next background completion.

**A. S3 compute estimate (for ruling 4). Inputs (a) from §5cs.45-47: engine 2.3-3.5 s per full match, ~1,850 matches/h on the box's two slots, deterministic re-drive 211/211. Everything derived below is (b) until S3's first 100 decisions are timed.**

| item | derivation | slot-hours |
| --- | --- | --- |
| one teacher candidate | re-drive prefix (~half a match, ~1.5 s) + 15 s game-time rollout at ~60x realtime (~0.3 s) + overhead | ~2 s |
| one teacher decision | 12 candidates (top 8-16 + wait) | ~25-30 s |
| DAgger data | 5 iterations x 300 student matches x ~40 decisions x 25% of states searched = 15,000 + 500 pro-state calibration + 4,500 re-runs | 20,000 x 30 s = **167** |
| engine eval | n=500 x 2 opponents x 3 seeds x 6 checkpoints = 18,000 matches / 925 per slot-hour | **~20** |
| margin (failed runs, a second design pass) | x2 | -> **~400 slot-hours total** |

Where that runs: box alone = 2 slots -> ~200 h ~ 8-9 days of continuous engine time (feasible; S3 is a
multi-week stage anyway). GCP n2-standard-16 spot ~$0.30/h: slot density per 16 vCPU is (b) -- at 4 slots
$30, at 8 slots $15, even at 1 slot $120; **fits the $300 trial at any plausible density**, first hour is a
density test. Hetzner AX162 hourly $1.16/h: ~24 slots -> ~17 h ~ $20 + a setup day. Either is cheap; GCP is
free. **Recommendation: GCP $300 trial, signed up when S3 starts (~week 3; credits expire 90 days after
signup), not now.** The AVD image + libg must be copied to any cloud box; size and nested-virt emulator
speed on GCP are the two unmeasured numbers.

**B. hogeq inheritance (ruling 1).** Every S0-S4 component is written deck-parameterised (deck config, card set,
crawl dir, val split). S0 corpus rebuild runs both decks; hogeq's engine acceptance rate for its pro plays is
(b) -- icebow's was 99.2% (§5cs.45) -- and is the first hogeq number S0 produces. Live grading (ruling 2) is
per deck at 10,000 trophies.

**C. S0 step 1 DONE: engine guest services back, verified through the caller's own path (a).** `worker status`
read `services [false,false]`, vm_ready true (the L62l tree-kill casualty). `L63/s0/_boot.ps1` (copy of L62's)
FAILED 6/6 when launched from the Bash tool: `/usr/bin/tar: Cannot connect to C: resolve failed` -- the start
script's `tar` resolved to Git's GNU tar, which reads `C:\...` as a remote host. **TRAP: boot the engine services
from a native PowerShell environment (System32 first on PATH); from Git Bash the packaging step always fails.**
Native PowerShell: attempt 1, exit 0, ~30 s, `services [true,true]`. Liveness (`L63/s0/liveness.py`): replay
`000YLY0JCPGL` driven through `replay_drive.drive` on BOTH slots reproduces the L61 batch result exactly --
terminal_tick 6085, side0_win 1-0, state_hash d0874ff2026fa69e, opening hash 0bfbcb2adbea282e, 121/121 plays
accepted, 0 invalid placements; 4.38 s / 4.47 s per slot. (First version of the probe compared non-existent keys
and reported a vacuous "same" -- caught before use; a liveness check must print the values it compared.)

**D. Next (S0 step 2):** the observation contract. Read the engine's full observation schema (`record_full`) and
the live detector's output schema, write ONE `obs_builder` that consumes either and emits the same entity-list +
raster tensors, and measure detector->obs vs engine->obs agreement on recorded live frames that have a matched
engine timeline. Then S0 step 3: corpus rebuild for BOTH decks (625 icebow x/y replays; hogeq: 24,672 positioned
plays, engine acceptance unmeasured).

**Not established.** Nothing about S1-S4; the S3 compute figures in A are derivations from measured per-match
times, not timings of the teacher itself.
