
## L62 (2026-09-05 17:0x UTC) -- owner: "kill bcA now and start the engine training". Sim PPO retired from the training path
- bcA killed at 2,550 eps (4% wr, state in L61/bcA_stop_state.txt), python 17 -> 3, 11.06 GB free. bcB (KL on the sim)
  NOT built -- the KL term moves to the engine env.
- Engine env v0 under construction in scratchpad/gauntlet/L62/: EngineMatchEnv (SimMatchEnv interface, ghost opponent,
  0.5 s decision cadence, engine-only unshaped reward) + ghost pool from the mined battles. Key v0 diagnostics:
  s/match with a policy in the loop, ghost rejection rate as the match diverges, deck/rating coverage.
- The sim survives as the obs RENDERER (the adapter drives _update_vectors) and as the fast smoke env; its reward and
  opponent are what is retired.
