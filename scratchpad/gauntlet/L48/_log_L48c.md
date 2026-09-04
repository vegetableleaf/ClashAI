- L48c (2026-09-04 ~12:20-12:40): owner ruling (A) -- crowns() fixed in engine.py: enemy king dead -> 3, else
  dead-tower count. Reporting AND reward (take_enemy_tower/lose_own_tower pay x2 on a king-fall with a princess
  up). Landed while c2r runs: workers/eval envs spawned once at start (remote_pool 289-307, train_sim_ppo 156/1117),
  so c2r trained wholly on the OLD count; trap = a --resume after this commit splits the run into two reward
  regimes. Checks: state test 0/1/2/3/3, outcome unchanged, crown_undercount doctrine n=12 engine -0.917 == real
  -0.917, 165 unittests OK. Post-fix crown_delta is a NEW instrument -- never compare against pre-fix tables.
  c2r 25.8k at 12:28, 0.64 ep/s -> m30k ~14:15 (13:25 carried earlier was wrong). Compound drills: never enabled
  or measured (frac 0.0); answer = instrument read next loop, training arm only post-c2r / on a collapsed m30k.
