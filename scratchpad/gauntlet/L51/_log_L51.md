- L51 (2026-09-04 15:2x-15:5x): SIM-PARITY ORACLE STEP 1 (owner-queued). `scratchpad/gauntlet/L51/sim_replay_drive.py`
  drives the crawl's real 20 Hz timelines through OUR sim with the engine's conversion (both sides L11 incl. towers
  3052/4824 = engine, abilities skipped, 40-tick slack). Same 211 tags, same 19,488 plays. Crowns match RoyaleAPI
  sim 55/211 = 26.1% (winner 44.1%) vs the real engine 77.7% / 80.1%; sim==engine crowns 28.9%; engine-clean 135:
  28.1%. ONE-DIRECTIONAL: real winners s1 129 / s0 82, engine 111/100, sim 23/188; side 1 = the X-Bow player in
  211/211. Mirror run (sides swapped) 28.4% with the bias following the deck -> sim symmetric, deck mechanics.
  Not the cause: heroes (no-ability subset 23%), elixir (1.2% of plays needed slack), tower HP, play counts. Sim
  games end earlier (median 180 s vs engine 276 s), 3-crown 58 vs real 20. Caveat: open-loop replay penalises the
  reactive deck first -- but the engine held the real board on the same inputs. Step 2 (engine per-tick diff,
  emulator, after c2r) now warranted. 31 s wall for the set. c2r 31,325 eps, 17 procs. HANDOFF 5cs.21.
