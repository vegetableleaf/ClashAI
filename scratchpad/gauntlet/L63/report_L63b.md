**GAUNTLET loop 63b** — square one: proposal posted, STOPPED for your approval
**Read it here:** https://claude.ai/code/artifact/0e57cffe-d199-46c2-b39c-5922032b6821 (HANDOFF §5cs.53 has the same content in house style)

**QUESTIONS (answer any way you like; I do nothing until then):**
1. **Approve the five-stage plan?** S0 obs contract + corpus rebuild -> S1 imitation v3 (new net) -> S2 corpus x3->x10 -> S3 engine search-teacher + supervised distillation (no policy gradient) -> S4 live layer. "Yes" = S0 starts immediately. Or name a stage to cut/reorder.
2. **Live grading protocol.** Proposed: 20-match blocks, one fixed mode, EMA checkpoint, no learning during a graded block. Which mode: trainer / ladder at a fixed trophy band / friendly vs you?
3. **Crawler.** It has looped on an expired Cloudflare clearance since 17:16 UTC (294 AuthErrors, no new output). Restart it myself, or you refresh the browser session?
4. **Cloud for S3 only.** GCP $300 trial (card needed, ~$0.30/h spot after), Hetzner ~$283/mo, or box-only (~150 teacher decisions/h vs ~1,000 on 16 emulators). S0-S2 need nothing.

**Did:** synthesised 6 research files (37 measured lessons, ~70 sourced lit claims, every public CR agent, 75 entries from 2025-26, asset + cloud audits) into one proposal; wrote HANDOFF §5cs.53 + log.
**Found (carried forward, all measured earlier this week):** the model UNDERFITS (17.6 train / 15.4 val, +1.8 over board-blind, embedding cos 0.991) -> representation is cause #1; PG gave 0 gain in 4 arms / 1,500 matches -> signal is cause #2; sim 26% vs engine 78% crowns-match -> environment is cause #3; live 12 W / 957 on an untested obs path -> cause #4.
**Means:** the new pipeline replaces all four: token transformer with full-res placement head; supervised learning from pro cells + an engine search teacher (Supercell's own route, 71% vs their BC); engine-only with fidelity numbers; one obs builder shared by engine and detector, sampled gate, EMA, reranked top-k live. Every stage has a pre-registered gate on 3 seeds; engine winrate at n=500 (SE 2.2 pp) becomes usable for the first time. Everything in the plan is (b) until run.
**Next:** on approval -> S0: reboot engine guest services, obs contract test on recorded frames, rebuild corpus from 613 replays, validate mask.
**Cost:** this loop ~40 min; nothing running; box idle (python 3, qemu up, guest services dead).
