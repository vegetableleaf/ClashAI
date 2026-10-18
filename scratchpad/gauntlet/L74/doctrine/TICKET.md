# API worker ticket (owner 10-18): measure the "keep both princess towers" doctrine
Owner claim (a hypothesis to TEST, not a fact): for X-Bow / icebow, a 1-1 crown state is far harder to win than keeping both
princess towers; a defence-first style (positive trades, most-effective not cheapest plays, early restraint, chip via
X-Bow locks + Rocket cycling) wins. Read the memory icebow-keep-both-towers-doctrine.md and HEAD's HANDOFF top entries first.

Measure, with 95% CIs and n per cell:
1. PRO replays of X-Bow / icebow players (the pro crawl / IL_Replay data the imitation build uses; find them via HANDOFF):
   P(win | crown state reached) for 0-0, 1-0, 0-1, 1-1 (state at any point, and at the 2nd minute / overtime start);
   P(win | lost a princess first) vs P(win | took one first). Same tables for our live matches (CLIII, CXXXVIII, cue_ab2)
   and for SIM self-play of CLIII if rows exist.
2. Style gaps, pros vs our live models: elixir trade per defence, share of defences with only cheap cards, early-match
   (first 60 s) offensive spend, own-tower damage taken per minute, X-Bow lock time on tower, Rocket-cycle tower damage.
3. Verdict per claim (measured / plausible untested / contradicted) and concrete design proposals for REB's successors
   (reward terms, eval slices, curriculum). Do NOT change training configs or live; proposals only.
Write scratchpad/gauntlet/L74/doctrine/DOCTRINE_MEASURED.md; prepend a short HANDOFF section via git show HEAD:HANDOFF.md
+ hash-object + update-index; commit explicit paths, push; post a <= 900-char Discord summary (L69/discord/post.py).
Rules: no `git add -A`; never print keys / webhook / reader internals; no `python -` stdin; kill only by exact PID; laptop is
shared (heavy compute on pods; free pods per HANDOFF; stop none). Use Codex (codex exec -m gpt-6-astra) for bulk data crunching
where useful; you keep the analysis and verdicts.
