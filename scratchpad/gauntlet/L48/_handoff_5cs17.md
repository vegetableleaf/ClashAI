
### 17. CROWN COUNT FIXED IN THE ENGINE -- owner ruling (A): `crowns()` returns 3 the moment the enemy king is dead; REPORTING AND REWARD change (2026-09-04 ~12:20-12:40, L48c). Landed while c2r runs, which is safe because c2r's processes imported the old engine at start; c2r trained ENTIRELY on the per-tower count

**Owner order (verbatim):** "do (A), change both the report and reward." -- the reward semantics question in 5cs.16 is
closed. **Edit:** `engine.py` `crowns(team)`: `if not enemy[2].alive: return 3`, else the dead-tower count as before
(docstring carries the bug history). No other code changed.

**Why landing now does not touch the running c2r (a, code read):** `RemotePool.__init__` (`remote_pool.py:289-307`)
spawns the workers ONCE with the `spawn` context, built once at `train_sim_ppo.py:156`; the eval envs are built once
at 1117 and live in the trainer process; `tools/ppo_watchdog.py` only uses subprocess to count processes. A file
edit on disk reaches none of those already-imported modules. TRAP for the record: if c2r is ever restarted with
`--resume` after this commit, its tail trains on the new count -- the run log must then be read as two reward
regimes. As of this section it has not been restarted (17 python processes before and after, unchanged).

**Checks (a):** live-engine state test: 0/1/2 dead princesses -> 0/1/2; king dead with one princess up -> 3; king
dead with both up -> 3; own side 0; `_check_end` after the enemy king dies -> done/win (the two in-engine callers,
`_check_end:5931` and `_score_outcome:5959`, run only after the king check has returned, so no OUTCOME can change).
`crown_undercount.py doctrine none 12`: engine crown_delta -0.917 == real-CR -0.917 (was -1.000 vs -1.104 over 48
pre-fix). `python -m unittest tests.test_sim_fidelity tests.test_r2_engine_schema tests.test_champion_ability_engine
tests.test_trade_events_sim`: 165 tests OK. No test asserts a crown count (grep `crowns` in tests: none).

**What changes downstream (a, by construction):** (1) `env.py:3207` `take_enemy_tower` / `lose_own_tower` now pay
`w_take x 2` / `w_lose x 2` in the step a king falls with a princess still standing (before: x1 + the terminal);
(2) `rollout_search.py:172` search scorer `crown_w x d_crowns` sees the same jump inside the horizon -- a king kill
inside 12 s is now worth 3 crowns to the searcher, which (b) may make the search push a king more aggressively; not
measured; (3) `sim_view` shows CR crowns; (4) every `crown_delta` in ledgers up to and including 5cs.16 is the OLD
count -- **never compare a post-fix crown_delta against a pre-fix one** (two instruments). `tower_delta` (the
paired discriminator) is unaffected: it counts towers and still does.

**First TRAINING run on the new count = the next run after c2r.** It goes on that run's change list as its own line
(one change per experiment: the crown fix is a reward change and must be attributable). The c2r-vs-next comparison
therefore carries this confound in addition to whatever else is landed; the greedy >=6 probe and the ladder EVAL are
outcome-based and unaffected, the per-crown shaping is the only term that moves.

**Compound drills (owner question, answered in the L48c report; recorded here):** `sim.drill_compound_frac` is 0.0
in `c2r_run.yaml:1697` (never enabled in any run; landed b028af9 2026-08-21; never measured as an instrument).
Config reads: pass_frac 0.5 / hp_frac 0.25 (code defaults 0.6 / 0.45 are NOT what runs). c2r already runs single
drills at 21% of episodes / 30% of steps, 46% pass. Recommendation: (i) NOT as a training change now (c2r running;
config change = new arm; queue behind the m30k read); (ii) YES as a cheap instrument read next loop -- in-process
override `drill_compound_frac=1.0` in a DrillEnv, reference/doctrine/policy(c2r m24k) pass rates on compound boards,
does `compound_verdict` fire at all -- minutes, no training; (iii) the mechanism argument for it is real but (b):
compound boards are the place where "wait everywhere" fails by construction, so if the m30k read collapses,
compound drills are the first candidate repair under the collapse ruling; if m30k holds, they queue as an arm
behind D1 and the crown fix.

**Does NOT establish:** any effect of the fix on training (b; next run); that the searcher's behaviour changes (b;
re-run the L43 search leg on slice 1 post-fix and compare tower_delta, not crown_delta). Files: engine.py (the
edit), `scratchpad/gauntlet/L48/{crown_undercount.py, _handoff_5cs17.md}`.
