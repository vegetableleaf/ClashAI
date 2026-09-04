- L53 (2026-09-04 17:25-17:4x): SIM-ONLY SWARM PROBE (`L53/skarmy_probe.py`). Unanswered evo Skeleton Army vs the L11
  princess tower: tower dead at 10 s, 3947 total damage (non-evo 2279, tower survives at 773). Knight in front of the
  tower: evo 3947 -> 3947 (changes nothing), non-evo 2279 -> 407. Ice Wizard: evo -> 0 (splash kills Gerry at 3.1 s,
  ghosts vanish). Gerry trails 2-4 tiles behind, first shot by the tower at 12.2 s after the last live skeleton dies.
  `shadow_skeleton_speed_tiles: 1.0` in cards.yaml is read by nothing -- ghosts run at 1.5 t/s (wiki Medium = 1.0);
  driver patch `--patch shadow_speed`: 3947 -> 3785, population 55/211 -> 55/211 NULL. Clip 08QPVCPC9QQU: the pro's
  Ice Wizard lands inside 10 live + 5 ghost skeletons and dies in 0.7 s in the sim; the real one stopped the push --
  the real pack's position at 25.3 s is the first thing oracle step 2 must read. Crowns-match by opponent deck: any
  skeleton-army 3/32 = 9.4% vs 29.1% rest; other swarm 20.5%; none 31.4% -- side-0 bias in every subset (112/140
  sim side-0 wins vs real 55/140 even with no swarm card). c2r 35,000 eps, 17 procs, 4 GB free. HANDOFF 5cs.23.
