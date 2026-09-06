**GAUNTLET loop 63c** — square one: APPROVED. Rulings applied; S0 started.
**Rulings recorded (HANDOFF §6):** approved as written, hogeq inherits every change; live grading = ladder at 10,000 trophies, 20-match blocks, EMA checkpoint, no learning in a block; crawler login when I re-open a session; cloud pending your call.

**Your Q4 answer — S3 compute (untested derivation from measured per-match times):** ~400 engine slot-hours including a 2× margin (20,000 teacher decisions at ~30 s each = 167 h; 18,000 eval matches = 20 h; ×2). The box alone does it in ~9 days of continuous engine time, so cloud only accelerates. GCP $300 trial covers all of S3 at any slot density (worst case 1 slot/box ≈ $120; likely $15–30). Hetzner hourly would be ~$20 + a setup day. **Recommendation: GCP trial, sign up when S3 starts (~2–3 weeks; credits expire 90 days after signup), not now.** Correction: my $283/mo Hetzner figure came from a stale mirror; your $1.16/h / $700+/mo is the live price.

**Two things I did not expect:**
- The crawler was NOT stalled: wave 4 finished on its own at 00:44 UTC (565 new replays, exit 0). No login needed until S2 launches the next wave — I'll re-open a session and ask then. "Stalled" in my last two reports was wrong.
- An OLDER gauntlet session (your L62 loop) woke on the crawl's completion and wrote a HANDOFF section (§5cs.54) at the same time I was writing §5cs.53; it renumbered itself after the collision. Two sessions editing HANDOFF at once is a trap — please close that session, or tell me to message it.

**Did (S0 step 1):** engine in-guest services were [false,false]. Booting from the Bash tool failed 6/6 (`/usr/bin/tar` reads `C:\...` as a remote host — trap recorded); native PowerShell brought both up on attempt 1 in ~30 s.
**Found (measured):** liveness through the real driver on BOTH slots reproduces the L61 batch result exactly: replay 000YLY0JCPGL, terminal tick 6085, 1-0, state hash d0874ff2026fa69e, 121/121 plays accepted, 4.4 s per slot.
**Means:** the engine is a trustworthy instrument again; S0 can proceed.
**Next:** S0 step 2 — the shared observation contract: one obs_builder fed by engine state or detector output, measured on recorded live frames. Then corpus rebuild for BOTH decks.
**Cost:** ~35 min; nothing training; qemu + 2 services up, free RAM 5.3 GB.
