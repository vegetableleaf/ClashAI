
### §5cs.40 -- L62 (2026-09-05 17:0x UTC): OWNER ORDER "kill bcA now and start the engine training" -- SIM PPO IS OVER FOR NOW. bcA killed at 2,550 episodes (4% wr, checkpoint intact); bcB (KL-to-pro on the sim) NOT built -- the KL term belongs in the engine env instead; engine environment v0 under construction (2 agents: EngineMatchEnv + ghost pool)

**Owner exchange (16:5x-17:0x UTC).** Owner: "I thought we decided that the engine was better for training though
compared to the sim?" Correction given: Q2's answer (mining/ghosts/self-play) IS the engine route; bcA was queued
from the pre-answer plan and ran on the sim because the sim is the only thing with an opponent, a reward, drills,
gates and a PPO loop. Stated gaps for engine-as-environment: (1) opponent -- ghost v0 ~half a day, the crawl is
banking the timelines; (2) reward -- crowns/tower HP are in the frames, but every SHAPED term (drills, gates,
geometry, elixir doctrine) is written against the sim's internals and would have to be re-derived; (3) speed
920-1,516 matches/h/VM vs the sim's ~2,880/h -> a 40k-match run is ~1.5 days on one VM, under a day on two slots.
Recommendation given: stop sim PPO, do not build bcB for the sim, put the box on engine env v0. Owner: "Kill bcA
now and start the engine training."

**bcA stopped 17:0x UTC at 2,550 episodes** (4% winrate, avg_rew -15.3, 131W-1894L-1D, 0.6 ep/s, drills 524 / 50%
pass; state in `L61/bcA_stop_state.txt`). Tree 55244 killed with taskkill /T /F from PowerShell; python 17 -> 3
(Nucleo + 2 crawler), **11.06 GB free**. Final weights `data/policy_bcA_20260905.pt` (matches 2550, untouched);
the m2k snapshot `data/bench/bcA_m2k.pt` is the read in §5cs.39. bcA's control role lapses with bcB.

**What survives from the sim work.** The sim stays as the fast smoke/CI environment and as the obs RENDERER (the
engine adapter drives `SimMatchEnv._update_vectors`, §5cs.37) -- it is the sim's REWARD and opponent that are
retired from the training path, not its code. The BC init, the bias map, `read_ckpt.py` and both pro-agreement
val sets carry over unchanged; pro agreement remains the grading instrument, not winrate.

**Engine env v0 (in flight, `scratchpad/gauntlet/L62/`).** Two agents:
- `engine_env.md` / `engine_env.py`: `EngineMatchEnv` with the SimMatchEnv interface (reset/step/act + hand/next/
  elixir/threat vectors), ghost opponent issuing the recorded opponent commands, our side acting every 10 ticks
  (0.5 s), obs via the §5cs.37 adapter, reward from engine state only (tower HP deltas + crowns + outcome,
  UNSHAPED and documented as such), cell -> engine (x, y) inverse-mirror verified by round-tripping a pro play.
  Measures: s/match with a real policy in the loop (1 slot and 2), ghost REJECTION rate as the match diverges
  (the key v0 diagnostic), determinism over 3 repeats, and a 20-match sanity read.
- `ghost_pool.md` / `pool.jsonl`: every convertible mined battle as {decks, ghost commands, icebow commands,
  rating, result, crowns}; measures deck diversity (how far from the owner's 10,000-deck ambition), rating
  coverage vs the 10k-trophy-to-top target, and ghost command density.
