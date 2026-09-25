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
