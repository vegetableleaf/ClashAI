# Held-out screen for any checkpoint (generalist vs v6aug_s1)

`run_screen.py` plays rl_royale's held-out RoyaleSim screen (58 loadable held-out ghosts x k 0..2 = 174 matches,
eval obs seed `crc32("{tag}:eval:{k}")`, greedy live rule with tau 0.27 / afford mask / anti-stall 9 elixir + 12 s /
live_view obs / decide every 10 ticks, all read from `pipeline/rl_royale.yaml`) for one checkpoint, S1 or generalist
(`"gen": True` in the checkpoint -> `e1_eval.GenPolicy`). It writes one JSON line per (tag, k) match. `--pair A B`
scores B against A with `rl_royale.screen_score`, the RL screen's own scorer (entry-clustered delta + bootstrap CI).

Run from the repo root in the **Royale venv** (royalegym is not installed in the icebow venv). Before you start,
check that no live match is running: `(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*live_play.py*' | Measure-Object).Count` must print 0.

```
# generalist
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --ckpt icebow/data/pipeline/gen_v1_s0/gen_s0.pt --out scratchpad/gauntlet/L68/generalist/screen_gen/gen_v1_s0.jsonl ^
    --device cuda --batch 16

# icebow specialist (the RL init)
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --ckpt icebow/data/pipeline/s1_icebow_v6aug_s1.pt --out scratchpad/gauntlet/L68/generalist/screen_gen/v6aug_s1.jsonl ^
    --device cuda --batch 16

# pair: generalist (B) vs v6aug_s1 (A)
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --pair scratchpad/gauntlet/L68/generalist/screen_gen/v6aug_s1.jsonl scratchpad/gauntlet/L68/generalist/screen_gen/gen_v1_s0.jsonl
```

Options: `--device cpu` (default) with `--threads N`; `--resume` continues an interrupted `--out`; `--max-matches N`
for a smoke. Sidecars next to `--out`: `.run.json` (checkpoint sha, cfg), `.skipped.json` (entries RoyaleSim cannot
load; 2 x 3 jobs among the first entries in the smoke).

Known differences from the RL screen: `entry_index` in a line is the index in the whole held-out split, not in the
loadable list (not used by the scorer); the actors split the jobs over 3 processes, this runs one process. A match's
record depends only on its own state apart from float noise in the shared batched forward.

The old in-trainer init screen of v6aug_s1 (winrate 0.747, 174 matches) was made the same way; running v6aug_s1 here
again gives both sides of the pair from the same code.

## Opponent-elixir source arms (`--opp-elixir`, L68 T8b)

`--opp-elixir {truth,hidden,counter,counter_all}` sets ONLY where the model's `opp_elixir` comes from; every other
noise component is still what `--noise-off` says (use `--noise-off all` for the clean arms). Unset = today's behaviour
(measured: an unset 2-match smoke reproduces `oppHidden_gen_v1_s0.jsonl`'s lines exactly apart from `wall_s`).
- `truth` = exact engine value; `hidden` = None (`--noise-off all --opp-elixir hidden` is the same noise as the
  `oppHidden_*` runs).
- `counter` = `pipeline.opp_elixir_count.OppElixirCounter` fed ONLY the ghost's DELIVERED plays at their delivery tick
  <= now (e1_eval taps the env's `_fire_ghosts_at`), dropping bodiless spells (spells except Graveyard / Goblin Barrel /
  Barbarian Barrel / Royal Delivery / Clone -- eval_accounting.py's `reader` rule, pinned by
  `pipeline/tests/test_e1_opp_counter.py`): what the memory reader can count. Assumes PERFECT body detection.
- `counter_all` = every delivered play (perfect-detection upper bound).
Each line then carries `opp_counter`: fed / dropped / rebases, `mae` and `bias` of estimate minus the TRUE elixir over
the match's decisions (a diagnostic only -- the truth never reaches the estimate), and a (tick, est, truth) sample
every 20 decisions.

```
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --ckpt icebow/data/pipeline/gen_v1_s0/gen_s0.pt --noise-off all --opp-elixir counter ^
    --out scratchpad/gauntlet/L68/generalist/screen_gen/oppCounter_gen_v1_s0.jsonl --device cuda --batch 16
# likewise --opp-elixir counter_all -> oppCounterAll_gen_v1_s0.jsonl, and both with
#   --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt -> oppCounter_v6lat_s0.jsonl / oppCounterAll_v6lat_s0.jsonl
# pair each against its hidden arm (B vs A):
... run_screen.py --pair screen_gen/oppHidden_gen_v1_s0.jsonl screen_gen/oppCounter_gen_v1_s0.jsonl
```

## Action-delay arm (`--action-delay TICKS`, L68 T9)

Live, a play goes in ~24-27 ticks (1.2-1.35 s) after the frame the model decided on (first live match: decision tick
198 -> registered 222, 352 -> 379, 381 -> 408, 568 -> 592, 927 -> 953). The model was trained on the board at the tick
the pro's card went in, so this arm measures what that lag costs. `--action-delay D` (cfg `action_delay_ticks`,
`pipeline/e1_eval.py` `Match.apply`) reproduces `live_play.py`'s pending lock:
- a play decided on the board at tick T enters the engine at T + D, at the cell chosen at T (not revised);
- while it is pending there are no decisions, the card stays in hand and no elixir is spent; the next decision is the
  first decide-every grid tick after T + D (D = 26 -> T + 30);
- the model's own past plays and the anti-stall clock use the LANDING tick and position;
- a refusal at landing is counted (`refuse_reasons`, `plays_refused_at_landing`), never retried; a match that ends
  before a play lands counts it in `plays_unlanded` (reason `match_over_before_landing`).
Each line then carries `action_delay_ticks`, and each play carries `land_tick` (`tick` stays the decision tick).
0 (default) = today: a 2-match smoke at `--action-delay 0` reproduces `oppCounter_gen_v1_s0.jsonl`'s lines exactly
apart from `wall_s`. The flag works with `--noise-off` and `--opp-elixir` (the counter reads the ghost's delivered
plays, which the delay does not change).

The live condition (clean obs + opponent-elixir counter) at D = 26, paired against the existing delay-0 runs:
```
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --ckpt icebow/data/pipeline/gen_v1_s0/gen_s0.pt --noise-off all --opp-elixir counter --action-delay 26 ^
    --out scratchpad/gauntlet/L68/generalist/screen_gen/oppCounterDelay26_gen_v1_s0.jsonl --device cuda --batch 16
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py ^
    --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt --noise-off all --opp-elixir counter --action-delay 26 ^
    --out scratchpad/gauntlet/L68/generalist/screen_gen/oppCounterDelay26_v6lat_s0.jsonl --device cuda --batch 16
# pair each against its delay-0 run (B vs A):
... run_screen.py --pair screen_gen/oppCounter_gen_v1_s0.jsonl screen_gen/oppCounterDelay26_gen_v1_s0.jsonl
... run_screen.py --pair screen_gen/oppCounter_v6lat_s0.jsonl screen_gen/oppCounterDelay26_v6lat_s0.jsonl
```
