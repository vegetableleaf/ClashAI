- L55 (2026-09-04 18:18-18:4x, OWNER: stop c2r + "why oscillating" + "tesla in one tile"): c2r killed at 36,375 eps
  (17 -> 1 python procs, Nucleo untouched, 6.8 GB free; _best.pt = 36k ladder avg-5 31%, backed up to
  data/bench/c2r_best_36k_backup.pt). Live play_logs (36 matches, 1 W): tesla cell 235 x39/101, x_bow 235 x63/85.
  `policy_rl.pt` == c2r_best (max |diff| 0.0). Sim placement probe (`L55/place_probe.py`, greedy card+cell as
  play.py), c2r_best seeds 0-2: tesla -> cell 234 (row 13, col 0, left riverside corner) 52/82 = 63%, x_bow 21/34,
  tesla_evo 19/27, skeletons -> 423 (front of king) 153/154. LEARNED IN THE SIM, deployed unchanged; the 30% ladder
  was earned with it (scripted bots do not punish it). Oscillation: >=6 share 3.9/5.5/1.2/3.3/1.3 at m5k..m35k, all
  else flat 8k-36k, entropy 0.06, cell_struct 3350-5235x, gate PLAY drift negative in every batch on 5-20 play
  samples -- cause (b): no exploration left + gate updated from a handful of plays. Next: sim Tesla-outcome probe
  (corner vs centre), then an exploration arm from c2r_best. HANDOFF 5cs.25.
