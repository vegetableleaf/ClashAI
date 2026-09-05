
## L61 (2026-09-05 14:2x-15:0x UTC) -- BC dataset v2 from the REAL engine; checkpoint equally bad on real boards; sim-trained bias-map heads transfer; engine throughput measured
- 211/211 replays re-driven with full observe before every play: hashes identical to 5ay, 17,901 play frames, 2.34 s/match
  median with recording. Adapter (FakeEngine into SimMatchEnv._update_vectors) -> icebow/data/bc_pro_v2/: 9,444 samples,
  101/101 names mapped, 0 dropped; train 8,111 / val 1,333 (v1 split restricted). Sim vs engine at the same play:
  enemy bodies -0.74 (sim keeps more alive), towers-alive agree 70.7%, elixir +0.16.
- v2 val: c2r_best 2.78/11.10 (paired same-play: 3.12/10.75 engine vs 3.35/11.33 sim -> NOT a sim-board artefact);
  prior 12.08/37.66; kNN k15 14.03/37.28, k50 15.38/44.49. Sim-trained bias-map heads on engine boards 15.00/43.51,
  14.63/44.11, 14.93/43.44 (+2.6-2.9 top-1 ~3 SE, +5.8-6.5 top-5 ~4.5 SE over the v2 prior); trained map alone 10.58 ->
  the convs add +4.4 on real boards. x_bow 31-34% top-1 (c2r_best 0).
- Throughput: plays-only 2,800/h/slot; every-10-tick observe 920/h; every-2 260/h; 2 slots one VM 1,516/h (4.26 GB);
  direct RPC observe ~2 ms (5ay's "~20 ms" was adb -- retracted). Sim trainer ~2,880 matches/h on 16 cores (5cs.35).
  Opponent for an engine environment is unsolved (ghost / self-play / script) -> owner question.
- VM stopped. Next (after owner): model.py bias map + BC init + PPO with control; wave-4 crawl roster meanwhile.
